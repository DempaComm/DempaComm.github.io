"""Loopback HTTP routing, request validation and mutation serialization."""
from __future__ import annotations

import mimetypes
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from dempa_site.errors import PaperToolError
from .service import LocalAdmin
from .views import _page, _message, _dashboard, _paper_page, _result_page, _review_result_card, _baseline_preview_page


def _require_csrf(app: LocalAdmin, values: dict[str, list[str]]) -> None:
    supplied = _one(values, "csrf")
    if not secrets.compare_digest(supplied, app.csrf_token):
        raise PaperToolError("操作確認トークンが不正です。管理画面を開き直してください")


def _form_values(handler: BaseHTTPRequestHandler) -> dict[str, list[str]]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8", errors="replace")
    return parse_qs(raw, keep_blank_values=True)


def _one(values: dict[str, list[str]], key: str) -> str:
    return values.get(key, [""])[0].strip()


def _require_checked(values: dict[str, list[str]], key: str, message: str) -> None:
    if _one(values, key) != "yes":
        raise PaperToolError(message)


def _slug_from_path(path: str) -> str:
    return unquote(path).removeprefix("/papers/").strip("/")


def make_handler(app: LocalAdmin):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def send_html(self, payload: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; form-action 'self'; "
                "frame-ancestors 'none'",
            )
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self.send_html(_dashboard(app))
                    return
                if parsed.path.startswith("/papers/"):
                    self.send_html(_paper_page(app, _slug_from_path(parsed.path)))
                    return
                if parsed.path.startswith("/files/"):
                    _, _, token, relative = parsed.path.split("/", 3)
                    target = app.readable_file(token, unquote(relative))
                    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                    content = target.read_bytes()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(content)
                    return
                self.send_html(_message("見つかりません", "この画面は存在しません"), HTTPStatus.NOT_FOUND)
            except PaperToolError as error:
                self.send_html(_message("操作できません", str(error)), HTTPStatus.BAD_REQUEST)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            values = _form_values(self)
            try:
                _require_csrf(app, values)
                with app._lock:
                    if parsed.path == "/actions/check-all":
                        code, output = app.command(["check-all"])
                        self.send_html(_message("全体検査", "成功" if code == 0 else "失敗", output=output, good=code == 0))
                        return
                    if parsed.path == "/actions/prepare-baseline":
                        token, differences, checks = app.prepare_baseline()
                        self.send_html(
                            _baseline_preview_page(app, token, differences, checks)
                        )
                        return
                    if parsed.path == "/actions/write-baseline":
                        _require_checked(
                            values,
                            "accept",
                            "表示された公開差分を確認したことをチェックしてください",
                        )
                        reason = _one(values, "reason")
                        if not reason:
                            raise PaperToolError("公開基準を更新する理由を入力してください")
                        output = app.accept_baseline(_one(values, "preview"), reason)
                        self.send_html(
                            _message(
                                "公開基準の更新",
                                "成功",
                                output=output,
                                good=True,
                            )
                        )
                        return
                    if parsed.path.startswith("/papers/"):
                        rest = parsed.path.removeprefix("/papers/").strip("/").split("/")
                        if len(rest) != 2:
                            raise PaperToolError("操作先の記事を特定できません")
                        slug, action = unquote(rest[0]), rest[1]
                        if action == "review":
                            files = values.get("file", [])
                            results = app.review(slug, files)
                            cards = [_review_result_card(result) for result in results]
                            self.send_html(_page("変更検査", "<h1>変更検査を作成しました</h1>" + "".join(cards) + "<p>PDF全ページと報告を確認してから、記事画面の承認操作へ進んでください。</p>"))
                            return
                        if action == "finish":
                            _require_checked(values, "privacy_reviewed", "PDF全ページと検査報告を確認してから進めてください")
                            _require_checked(values, "accept_public_change", "公開差分の承認確認をチェックしてください")
                            reason = _one(values, "reason")
                            files = values.get("file", [])
                            if not reason or not files:
                                raise PaperToolError("修正理由と承認対象ファイルを指定してください")
                            output = app.approve_reviewed_change(slug, files, reason)
                            self.send_html(
                                _message(
                                    "承認と事前検査",
                                    "成功。HTML版を生成し、最後に公開差分を確認してください。",
                                    output=output,
                                    good=True,
                                )
                            )
                            return
                        if action == "trial":
                            token, report = app.create_trial(slug)
                            self.send_html(_result_page(app, slug, token, report))
                            return
                        if action == "publish":
                            _require_checked(values, "reviewed", "PDFとHTMLを比較してから公開登録してください")
                            published = app.publish_trial(slug, _one(values, "trial"))
                            self.send_html(_message("HTML版を公開登録", f"{published} を登録しました。次に全体検査を実行し、公開差分を表示して確認してください。", good=True))
                            return
                    raise PaperToolError("この操作は存在しません")
            except PaperToolError as error:
                self.send_html(_message("操作できません", str(error)), HTTPStatus.BAD_REQUEST)

    return Handler


def serve_local_admin(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the local administration interface until interrupted."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise PaperToolError("管理画面はlocalhostだけで起動できます")
    app = LocalAdmin(root)
    try:
        server = ThreadingHTTPServer((host, port), make_handler(app))
    except OSError as error:
        raise PaperToolError(
            f"管理画面を http://{host}:{port}/ で起動できません: {error}"
        ) from error
    print(f"LOCAL ADMIN: http://{host}:{port}/")
    print("VS Codeで原稿を編集し、この画面で検査・HTML生成・公開準備を行います。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLOCAL ADMIN stopped")
    finally:
        server.server_close()
