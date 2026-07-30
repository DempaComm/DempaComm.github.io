"""Local-only browser interface for reviewing manuscript changes safely.

The editor remains VS Code.  This module only orchestrates the existing
review, approval, LaTeXML, and validation commands from a loopback server.
It deliberately has no Git commit or push action.
"""

from __future__ import annotations

import html
import json
import mimetypes
import secrets
import subprocess
import sys
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, quote, unquote, urlparse

from dempa_site.catalog.metadata import rendered_keywords
from dempa_site.conversion.latexml import run_latexml_trial
from dempa_site.conversion.latexml_publication import publish_latexml_trial
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.loader import load_manifest_directory, load_schema
from dempa_site.manifests.model import Paper
from dempa_site.manifests.validation import validate_manifest_data
from dempa_site.paths import safe_relative_path
from dempa_site.protection.approval import approve_changes
from dempa_site.protection.change_workflow import changed_protected_files, review_changes
from dempa_site.site.snapshot import (
    check_baseline,
    snapshot_differences,
    write_baseline,
)
from tools.check_all import complete_check_steps


LOCAL_ADMIN_TITLE = "数識電収 ローカル管理"


@dataclass(frozen=True)
class LocalFile:
    root: Path
    label: str


@dataclass(frozen=True)
class ReviewResult:
    path: str
    token: str
    findings: str
    rendered_pages: tuple[str, ...]


class LocalAdmin:
    """State and safe command wrappers for one local administration session."""

    def __init__(self, root: Path, privacy_root: Path | None = None) -> None:
        self.root = root.resolve()
        self.papers_dir = self.root / "papers"
        self.privacy_root = (privacy_root or self.root / ".privacy-review").resolve()
        self.experiments_root = self.root / "_experiments" / "local-admin"
        self._files: dict[str, LocalFile] = {}
        self._trials: dict[str, tuple[str, Path]] = {}
        self._baseline_previews: dict[str, tuple[str, ...]] = {}
        self.csrf_token = secrets.token_urlsafe(32)
        self._lock = threading.Lock()

    def papers(self) -> list[tuple[Path, Paper]]:
        return load_manifest_directory(self.papers_dir, error_type=PaperToolError)

    def paper(self, slug: str) -> tuple[Path, Paper]:
        selected = load_manifest_directory(
            self.papers_dir, [slug], error_type=PaperToolError
        )
        return selected[0]

    def git_status(self) -> list[tuple[str, str]]:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            return [("??", "Gitの状態を取得できません")]
        rows: list[tuple[str, str]] = []
        for line in completed.stdout.splitlines():
            if len(line) >= 4:
                rows.append((line[:2], line[3:]))
        return rows

    def status_for_slug(self, slug: str) -> list[tuple[str, str]]:
        prefix = f"papers/{slug}/"
        return [item for item in self.git_status() if item[1].startswith(prefix)]

    def changed_files(self, manifest_path: Path, paper: Paper) -> set[str]:
        return changed_protected_files(manifest_path, paper)

    def token_for(self, root: Path, label: str) -> str:
        token = secrets.token_urlsafe(18)
        self._files[token] = LocalFile(root.resolve(), label)
        return token

    def readable_file(self, token: str, relative: str) -> Path:
        entry = self._files.get(token)
        if entry is None:
            raise PaperToolError("ローカル表示用の参照が期限切れです")
        path = entry.root / safe_relative_path(relative, PaperToolError)
        if not path.is_file() or entry.root not in path.resolve().parents:
            raise PaperToolError("表示できないローカルファイルです")
        return path

    def review(self, slug: str, files: Iterable[str]) -> list[ReviewResult]:
        manifest_path, paper = self.paper(slug)
        reviewed = review_changes(
            manifest_path, paper, self.privacy_root, list(files)
        )
        results = []
        for item in reviewed:
            if item.report_directory is None:
                results.append(
                    ReviewResult(item.path, "", "自動個人情報検査は不要です", ())
                )
                continue
            token = self.token_for(item.report_directory, f"{slug} の検査報告")
            findings = "\n".join(item.findings) or "自動検査の確認事項はありません"
            report = read_json(item.report_directory / "report.json")
            rendered_pages = tuple(
                str(value) for value in report.get("rendered_pages", [])
            )
            results.append(ReviewResult(item.path, token, findings, rendered_pages))
        return results

    def retire_stale_html(
        self, manifest_path: Path, paper: Paper
    ) -> tuple[tuple[str, ...], Path | None]:
        """Move HTML derived from changed sources aside and unregister it safely."""
        stale_versions = []
        entries = {entry.path: entry for entry in paper.files}
        for version in paper.html_versions:
            source = entries.get(version.source_path)
            source_path = paper.source_path.parent / safe_relative_path(
                version.source_path, PaperToolError
            )
            if source is None or not source_path.is_file():
                stale_versions.append(version)
                continue
            if sha256_file(source_path) != version.source_sha256:
                stale_versions.append(version)
        if not stale_versions:
            return (), None
        stale_directories = {
            Path(version.path).parts[0] for version in stale_versions
        }
        return self.retire_html_directories(
            manifest_path, paper, stale_directories
        )

    def retire_html_directories(
        self,
        manifest_path: Path,
        paper: Paper,
        stale_directories: set[str],
    ) -> tuple[tuple[str, ...], Path | None]:
        """Recoverably unregister and move selected derived HTML directories."""
        if not stale_directories:
            return (), None
        non_derived = [
            entry.path
            for entry in paper.files
            if Path(entry.path).parts[0] in stale_directories
            and entry.role not in {"derived-html", "derived-asset"}
        ]
        if non_derived:
            raise PaperToolError(
                "HTMLフォルダに派生物ではない保護ファイルがあります: "
                + ", ".join(non_derived)
            )
        current_versions = [
            version
            for version in paper.html_versions
            if Path(version.path).parts[0] not in stale_directories
        ]
        used_directories = {
            Path(version.path).parts[0] for version in current_versions
        }
        conflict = stale_directories & used_directories
        if conflict:
            raise PaperToolError(
                "同じフォルダを使うHTML版があるため安全に退避できません: "
                + ", ".join(sorted(conflict))
            )

        backup = (
            self.experiments_root
            / "retired-html"
            / f"{paper.slug}-{secrets.token_urlsafe(10)}"
        )
        backup.mkdir(parents=True, exist_ok=False)
        moved: list[tuple[Path, Path]] = []
        original = manifest_path.read_bytes()
        try:
            for directory in sorted(stale_directories):
                source_dir = manifest_path.parent / directory
                if not source_dir.is_dir():
                    raise PaperToolError(f"退避するHTMLフォルダがありません: {source_dir}")
                target_dir = backup / directory
                source_dir.rename(target_dir)
                moved.append((source_dir, target_dir))

            manifest = paper.to_dict()
            manifest["files"] = [
                entry
                for entry in manifest["files"]
                if Path(entry["path"]).parts[0] not in stale_directories
            ]
            versions = [
                version
                for version in manifest.get("html_versions", [])
                if Path(version["path"]).parts[0] not in stale_directories
            ]
            if versions:
                manifest["html_versions"] = versions
            else:
                manifest.pop("html_versions", None)
            validate_manifest_data(
                manifest, manifest_path, load_schema(), PaperToolError
            )
            write_json(manifest_path, manifest)
        except Exception:
            manifest_path.write_bytes(original)
            for source_dir, target_dir in reversed(moved):
                if target_dir.exists() and not source_dir.exists():
                    target_dir.rename(source_dir)
            raise
        return tuple(sorted(stale_directories)), backup

    def preflight(self) -> str:
        """Run every check except the expected public snapshot comparison."""
        lines = []
        for step in complete_check_steps(self.root, self.root / "_site")[:-1]:
            completed = subprocess.run(
                step.command,
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            lines.append(f"{step.label}: {'成功' if completed.returncode == 0 else '失敗'}")
            if completed.returncode:
                detail = "\n".join(
                    value.rstrip()
                    for value in (completed.stdout, completed.stderr)
                    if value.strip()
                )
                raise PaperToolError("\n".join(lines + [detail]))
        return "\n".join(lines)

    def approve_reviewed_change(
        self, slug: str, files: list[str], reason: str
    ) -> str:
        """Approve reviewed files, retiring now-stale HTML before validation."""
        manifest_path, paper = self.paper(slug)
        original = manifest_path.read_bytes()
        retired, backup = self.retire_stale_html(manifest_path, paper)
        try:
            _, refreshed = self.paper(slug)
            count = approve_changes(
                manifest_path,
                refreshed,
                self.privacy_root,
                reason,
                files,
                True,
                None,
            )
        except Exception:
            manifest_path.write_bytes(original)
            if backup is not None:
                for directory in retired:
                    source_dir = backup / directory
                    target_dir = manifest_path.parent / directory
                    if source_dir.exists() and not target_dir.exists():
                        source_dir.rename(target_dir)
            raise
        checked = self.preflight()
        retirement = (
            "\n旧HTMLを回復可能な隔離領域へ退避: " + ", ".join(retired)
            if retired
            else ""
        )
        return f"承認したファイル: {count}件{retirement}\n{checked}"

    def create_trial(self, slug: str) -> tuple[str, dict]:
        manifest_path, paper = self.paper(slug)
        changed = self.changed_files(manifest_path, paper)
        if changed:
            raise PaperToolError(
                "未承認の変更があるためHTML試験を開始できません: "
                + ", ".join(sorted(changed))
            )
        self.experiments_root.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(10)
        output = self.experiments_root / f"{slug}-{token}"
        report = run_latexml_trial(
            root=self.root,
            papers=[(manifest_path, paper)],
            output=output,
            requested_slugs=[slug],
        )
        self._trials[token] = (slug, output)
        return token, report

    def publish_trial(self, slug: str, token: str) -> str:
        recorded = self._trials.get(token)
        if recorded is None or recorded[0] != slug:
            raise PaperToolError("この画面で作成したHTML試験出力を選んでください")
        manifest_path, paper = self.paper(slug)
        original = manifest_path.read_bytes()
        directories = {
            Path(version.path).parts[0]
            for version in paper.html_versions
            if Path(version.path).parts[0] == "html"
        }
        if (manifest_path.parent / "html").exists() and not directories:
            raise PaperToolError(
                "paper.jsonに登録されていないhtmlフォルダがあるため置換できません"
            )
        retired, backup = self.retire_html_directories(
            manifest_path, paper, directories
        )
        try:
            _, refreshed = self.paper(slug)
            publication = publish_latexml_trial(
                root=self.root,
                paper=refreshed,
                trial_output=recorded[1],
            )
        except Exception:
            manifest_path.write_bytes(original)
            if backup is not None:
                for directory in retired:
                    source_dir = backup / directory
                    target_dir = manifest_path.parent / directory
                    if source_dir.exists() and not target_dir.exists():
                        source_dir.rename(target_dir)
            raise
        self.write_catalog()
        return str(publication.html_path.relative_to(self.root))

    def write_catalog(self) -> None:
        from dempa_site.site.rendering import rendered_home_page

        papers = self.papers()
        (self.root / "index.html").write_text(
            rendered_home_page(papers), encoding="utf-8"
        )
        for manifest_path, paper in papers:
            (manifest_path.parent / "keywords.txt").write_text(
                rendered_keywords(paper), encoding="utf-8"
            )

    def command(self, arguments: list[str]) -> tuple[int, str]:
        completed = subprocess.run(
            [sys.executable, str(self.root / "scripts" / "paper_tool.py"), *arguments],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        output = "\n".join(
            value.rstrip() for value in (completed.stdout, completed.stderr) if value.strip()
        )
        return completed.returncode, output or "出力はありません"

    def prepare_baseline(self) -> tuple[str, tuple[str, ...], str]:
        checks = self.preflight()
        differences = snapshot_differences(
            self.root / "_site",
            self.papers_dir,
            self.root / "tests" / "fixtures" / "site-baseline.json",
        )
        if not differences:
            raise PaperToolError("承認する公開差分はありません")
        token = secrets.token_urlsafe(18)
        self._baseline_previews[token] = differences
        return token, differences, checks

    def accept_baseline(self, token: str, reason: str) -> str:
        expected = self._baseline_previews.get(token)
        if expected is None:
            raise PaperToolError("公開差分の確認が期限切れです。もう一度差分を表示してください")
        checks = self.preflight()
        baseline = self.root / "tests" / "fixtures" / "site-baseline.json"
        current = snapshot_differences(self.root / "_site", self.papers_dir, baseline)
        if current != expected:
            raise PaperToolError("確認後に公開差分が変わりました。もう一度差分を確認してください")
        original = baseline.read_bytes()
        try:
            write_baseline(self.root / "_site", self.papers_dir, baseline)
            check_baseline(self.root / "_site", self.papers_dir, baseline)
        except Exception:
            baseline.write_bytes(original)
            raise
        self._baseline_previews.pop(token, None)
        return f"理由: {reason}\n{checks}\n公開基準を更新しました（差分{len(current)}件）"


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _csrf_field(app: LocalAdmin) -> str:
    return f'<input type="hidden" name="csrf" value="{_escape(app.csrf_token)}">'


def _require_csrf(app: LocalAdmin, values: dict[str, list[str]]) -> None:
    supplied = _one(values, "csrf")
    if not secrets.compare_digest(supplied, app.csrf_token):
        raise PaperToolError("操作確認トークンが不正です。管理画面を開き直してください")


def _page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)} — {LOCAL_ADMIN_TITLE}</title>
<style>
body{{margin:0;background:#f6f7fb;color:#202431;font:16px/1.6 system-ui,-apple-system,sans-serif}}
main{{max-width:1060px;margin:0 auto;padding:28px 20px 64px}} h1{{margin:0 0 8px}} h2{{margin-top:34px}}
a{{color:#144ea0}} .muted{{color:#637083}} .card{{background:#fff;border:1px solid #d9deea;border-radius:12px;padding:18px;margin:14px 0}}
.ok{{color:#087443}} .warn{{color:#a35100}} .danger{{color:#a12222}} .status{{font-family:ui-monospace,SFMono-Regular,monospace}}
button{{background:#164e9b;color:#fff;border:0;border-radius:7px;padding:9px 14px;font:inherit;cursor:pointer}} button.warn{{background:#9a5000}} button.danger{{background:#9b2929}}
input[type=text]{{width:min(100%,620px);padding:8px;border:1px solid #aeb8c9;border-radius:6px;font:inherit}} pre{{white-space:pre-wrap;background:#161a22;color:#edf0f5;padding:14px;border-radius:8px;overflow:auto}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid #e1e5ec;padding:8px;text-align:left;vertical-align:top}} .actions{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.pages{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}} .pages img{{display:block;width:100%;height:auto;border:1px solid #cbd2df;border-radius:6px}}
</style></head><body><main><p><a href="/">← 記事一覧</a></p>{body}</main></body></html>""".encode("utf-8")


def _message(title: str, message: str, *, output: str = "", good: bool = False) -> bytes:
    category = "ok" if good else "danger"
    block = f"<pre>{_escape(output)}</pre>" if output else ""
    return _page(title, f"<h1>{_escape(title)}</h1><p class=\"{category}\">{_escape(message)}</p>{block}")


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


def _dashboard(app: LocalAdmin) -> bytes:
    status = app.git_status()
    dirty = {path.split("/")[1] for _, path in status if path.startswith("papers/")}
    rows = []
    for manifest_path, paper in app.papers():
        changed = app.changed_files(manifest_path, paper)
        state = []
        if paper.slug in dirty:
            state.append("VS Codeの変更あり")
        if changed:
            state.append("未承認: " + ", ".join(sorted(changed)))
        if not state:
            state.append("変更なし")
        html_state = "HTMLあり" if paper.html_versions else "HTMLなし"
        rows.append(
            "<tr><td><a href=\"/papers/" + quote(paper.slug) + "\">"
            + _escape(paper.title) + "</a><br><span class=\"muted\">"
            + _escape(paper.slug) + "</span></td><td>" + _escape(html_state)
            + "</td><td>" + _escape(" / ".join(state)) + "</td></tr>"
        )
    changes = "\n".join(f"{code} {path}" for code, path in status) or "変更はありません"
    body = f"""<h1>{LOCAL_ADMIN_TITLE}</h1>
<p>原稿はVS Codeで編集します。この画面は、検査・HTML生成・公開準備だけを行います。Gitへのコミットとpushは行いません。</p>
<div class="card"><strong>作業ツリー</strong><pre>{_escape(changes)}</pre></div>
<div class="card actions"><form method="post" action="/actions/check-all">{_csrf_field(app)}<button class="warn">全体検査を実行</button></form>
<form method="post" action="/actions/prepare-baseline">{_csrf_field(app)}<button class="danger">公開差分を表示</button></form></div>
<h2>記事</h2><table><thead><tr><th>記事</th><th>HTML</th><th>状態</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"""
    return _page(LOCAL_ADMIN_TITLE, body)


def _paper_page(app: LocalAdmin, slug: str) -> bytes:
    manifest_path, paper = app.paper(slug)
    changed = app.changed_files(manifest_path, paper)
    git_rows = app.status_for_slug(slug)
    changed_rows = []
    for entry in paper.files:
        state = "未承認の変更" if entry.path in changed else "承認済み"
        checked = " checked" if entry.path in changed else ""
        changed_rows.append(
            f"<tr><td><input type=\"checkbox\" name=\"file\" value=\"{_escape(entry.path)}\"{checked}></td>"
            f"<td>{_escape(entry.path)}</td><td>{_escape(entry.role)}</td><td>{_escape(state)}</td></tr>"
        )
    git_text = "\n".join(f"{code} {path}" for code, path in git_rows) or "VS Codeからの未保存・未追跡変更はありません"
    html_note = "あり" if paper.html_versions else "なし"
    body = f"""<h1>{_escape(paper.title)}</h1><p class="muted">{_escape(slug)} · HTML版: {html_note}</p>
<div class="card"><strong>VS Codeの変更</strong><pre>{_escape(git_text)}</pre>
<p class="muted">新規BibTeX・図版など、paper.json未登録の公開ファイルはこの初期版では登録しません。先に移行手順を使ってください。</p></div>
<form class="card" method="post" action="/papers/{quote(slug)}/review">{_csrf_field(app)}<h2>1. 修正を検査</h2><p>変更した保護ファイルを選び、個人情報検査レポートを作ります。</p>
<table><thead><tr><th></th><th>ファイル</th><th>種類</th><th>状態</th></tr></thead><tbody>{''.join(changed_rows)}</tbody></table><p><button>変更を検査</button></p></form>
<form class="card" method="post" action="/papers/{quote(slug)}/finish">{_csrf_field(app)}<h2>2. 承認して事前検査</h2><p>PDF全ページと検査報告を確認した後だけ実行してください。選択した既存ファイルを承認し、古くなったHTML版があれば回復可能な隔離領域へ退避します。</p>
<input name="reason" type="text" required placeholder="修正理由"><p><label><input type="checkbox" name="privacy_reviewed" value="yes"> PDF全ページと個人情報検査報告を確認した</label></p>
<p><label><input type="checkbox" name="accept_public_change" value="yes"> 意図した公開差分だけを承認する</label></p>
<p>承認するファイル:</p><table><tbody>{''.join(changed_rows)}</tbody></table><p><button class="danger">承認して事前検査</button></p></form>
<div class="card"><h2>3. HTML版を生成</h2><p>未承認の原稿変更がない場合だけ、隔離領域に試験HTMLを生成します。</p><form method="post" action="/papers/{quote(slug)}/trial">{_csrf_field(app)}<button>HTML試験版を生成</button></form></div>"""
    return _page(paper.title, body)


def _result_page(app: LocalAdmin, slug: str, token: str, report: dict) -> bytes:
    item = report["results"][0]
    file_token = app.token_for(app._trials[token][1], f"{slug} のLaTeXML試験")
    html_path = item.get("html", "")
    result_link = ""
    if html_path:
        result_link = f'<p><a href="/files/{file_token}/{quote(html_path)}" target="_blank">試験HTMLを開く</a></p>'
    passed = bool(item.get("automatic_checks_passed"))
    reasons = "\n".join(item.get("blocking_reasons", [])) or "なし"
    publish = ""
    if passed:
        publish = f"""<form class="card" method="post" action="/papers/{quote(slug)}/publish">{_csrf_field(app)}
<input type="hidden" name="trial" value="{_escape(token)}"><h2>HTML版を公開登録</h2>
<p>PDFとHTMLを比較した後にだけ進めます。公開登録後は「全体検査」と「公開差分を表示」を行ってください。</p>
<label><input type="checkbox" name="reviewed" value="yes"> PDFと比較して公開してよいことを確認した</label><p><button class="danger">HTML版を公開登録</button></p></form>"""
    body = f"""<h1>HTML試験版</h1><p class="{'ok' if passed else 'danger'}">自動検査: {'合格' if passed else '不合格'}</p>{result_link}
<div class="card"><strong>停止理由</strong><pre>{_escape(reasons)}</pre><strong>変換処理</strong><pre>{_escape(json.dumps(item.get('source_normalizations', []), ensure_ascii=False, indent=2))}</pre></div>{publish}"""
    return _page("HTML試験版", body)


def _review_result_card(result: ReviewResult) -> str:
    report_link = ""
    pages = ""
    if result.token:
        report_link = (
            f' <a href="/files/{result.token}/report.txt" target="_blank">'
            "検査報告を開く</a>"
        )
        page_links = []
        for number, page in enumerate(result.rendered_pages, start=1):
            href = f"/files/{result.token}/{quote(page)}"
            page_links.append(
                f'<a href="{href}" target="_blank"><img src="{href}" '
                f'alt="{_escape(result.path)} {number}ページ"></a>'
            )
        if page_links:
            pages = (
                '<p><strong>PDF全ページ画像</strong></p><div class="pages">'
                + "".join(page_links)
                + "</div>"
            )
    return (
        f'<div class="card"><strong>{_escape(result.path)}</strong>{report_link}'
        f'<pre>{_escape(result.findings)}</pre>{pages}</div>'
    )


def _baseline_preview_page(
    app: LocalAdmin, token: str, differences: tuple[str, ...], checks: str
) -> bytes:
    rows = "".join(f"<li>{_escape(value)}</li>" for value in differences)
    body = f"""<h1>公開差分の確認</h1><p class="ok">公開基準以外の事前検査は成功しました。</p>
<pre>{_escape(checks)}</pre><div class="card"><h2>承認対象の公開差分</h2><ul>{rows}</ul></div>
<form class="card" method="post" action="/actions/write-baseline">{_csrf_field(app)}
<input type="hidden" name="preview" value="{_escape(token)}"><input name="reason" type="text" required placeholder="基準更新の理由">
<p><label><input type="checkbox" name="accept" value="yes"> 上記の公開差分をすべて確認した</label></p>
<button class="danger">確認した差分を公開基準へ反映</button></form>"""
    return _page("公開差分の確認", body)


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
