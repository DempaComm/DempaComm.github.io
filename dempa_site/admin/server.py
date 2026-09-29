"""Loopback HTTP routing, request validation and mutation serialization."""
from __future__ import annotations

import mimetypes
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from dempa_site.errors import PaperToolError
from .service import LocalAdmin
from .views import (
    _page, _message, _dashboard, _paper_page, _result_page,
    _review_page, _baseline_preview_page, _help_page,
)

ADMIN_ASSETS = {
    "/admin.css": ("text/css; charset=utf-8", Path(__file__).with_name("local_admin.css")),
    "/admin.js": ("text/javascript; charset=utf-8", Path(__file__).with_name("local_admin.js")),
}


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
                    values = parse_qs(parsed.query)
                    self.send_html(_dashboard(app, _one(values, "q"), _one(values, "view")))
                    return
                if parsed.path == "/help":
                    self.send_html(_help_page())
                    return
                if parsed.path in ADMIN_ASSETS:
                    content_type, asset_path = ADMIN_ASSETS[parsed.path]
                    content = asset_path.read_bytes()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(content)
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
                        self.send_html(_message(
                            "サイト全体の検査",
                            "すべての検査を通過しました。" if code == 0 else "検査で確認が必要な点が見つかりました。下の詳細を確認してください。",
                            output=output, good=code == 0,
                            next_url="/#publish", next_label="公開前の確認に戻る",
                        ))
                        return
                    if parsed.path == "/actions/prepare-baseline":
                        try:
                            token, differences, checks = app.prepare_baseline()
                        except PaperToolError as error:
                            if str(error) != "承認する公開差分はありません":
                                raise
                            self.send_html(_message(
                                "公開ページの確認が終わりました",
                                "事前検査を通過しました。公開ページは前回確認した内容と同じなので、追加の変更記録は不要です。",
                                good=True, next_url="/help#publish", next_label="公開までの手順を見る",
                            ))
                            return
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
                                "公開前の確認が終わりました",
                                "確認した変更を記録しました。最後にGitで記録（commit）して送信（push）すると、サイトへの公開が始まります。",
                                output=output,
                                good=True,
                                next_url="/help#publish", next_label="公開までの手順を見る",
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
                            if not files:
                                raise PaperToolError("検査するファイルがありません。記事に戻り、保存した修正が表示されるか確認してください。")
                            results = app.review(slug, files)
                            self.send_html(_review_page(app, slug, results))
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
                                    "修正を登録しました",
                                    "修正の登録と事前検査が終わりました。HTML版も更新する場合は、続けて確認用のHTML版を作ってください。",
                                    output=output,
                                    good=True,
                                    next_url=f"/papers/{quote(slug)}#html", next_label="この記事の続きを開く",
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
                            self.send_html(_message(
                                "HTML版を公開用に登録しました",
                                "次に、公開前の検査と変更点の確認を行ってください。",
                                output=f"登録したファイル: {published}", good=True,
                                next_url="/#publish", next_label="公開前の確認へ進む",
                            ))
                            return
                    raise PaperToolError("この操作は存在しません")
            except PaperToolError as error:
                back = "/#publish"
                label = "公開前の確認に戻る"
                if parsed.path.startswith("/papers/"):
                    back = "/papers/" + quote(unquote(parsed.path.removeprefix("/papers/").split("/")[0]))
                    label = "この記事に戻る"
                self.send_html(_message(
                    "確認が必要なため、処理を止めました",
                    str(error).splitlines()[0], output=str(error),
                    next_url=back, next_label=label,
                ), HTTPStatus.BAD_REQUEST)

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
