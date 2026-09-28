"""Local manuscript operations and their review/rollback rules."""
from __future__ import annotations

import secrets
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from dempa_site.catalog.writing import write_catalog
from dempa_site.conversion.latexml import run_latexml_trial
from dempa_site.conversion.latexml_publication import publish_latexml_trial
from dempa_site.errors import PaperToolError
from dempa_site.files import read_json, sha256_file, write_json
from dempa_site.manifests.loader import load_manifest_directory, load_schema
from dempa_site.manifests.model import Paper
from dempa_site.manifests.validation import validate_manifest_data
from dempa_site.paths import RepositoryPaths, safe_relative_path
from dempa_site.protection.approval import approve_changes
from dempa_site.protection.change_workflow import changed_protected_files, review_changes
from dempa_site.site.snapshot import check_baseline, snapshot_differences, write_baseline
from tools.check_all import preflight_check_steps


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
        for step in preflight_check_steps(self.root, self.root / "_site"):
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
        write_catalog(RepositoryPaths(self.root), self.papers())

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
