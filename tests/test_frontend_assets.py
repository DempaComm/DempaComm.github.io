"""Exercise the actual module graph after mapping source files to public URLs."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from dempa_site.features.relation_graph import GRAPH_ASSETS
from dempa_site.site.assets import PACKAGE_SCRIPTS, ROOT_SCRIPTS, STYLE_PARTS, stylesheet_bytes

ROOT = Path(__file__).resolve().parents[1]


class FrontendAssetsTest(unittest.TestCase):
    def test_styles_preserve_order_and_require_every_part(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            styles = root / "assets" / "styles"
            styles.mkdir(parents=True)
            parts = [f".same {{ color: var(--color-{index}); }}\n".encode()
                     for index in range(len(STYLE_PARTS))]
            for name, content in zip(STYLE_PARTS, parts):
                (styles / name).write_bytes(content)
            self.assertEqual(b"".join(parts), stylesheet_bytes(root))
            (styles / STYLE_PARTS[1]).unlink()
            with self.assertRaises(FileNotFoundError):
                stylesheet_bytes(root)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed for frontend contracts")
    def test_public_javascript_syntax_and_module_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "package.json").write_text('{"type":"module"}')
            sources = {name: ROOT / name for name in ROOT_SCRIPTS}
            sources.update({name: ROOT / "dempa_site/site" / source
                            for name, source in PACKAGE_SCRIPTS.items()})
            sources.update({f"graph/{name}": ROOT / "dempa_site/features" / source
                            for name, source in GRAPH_ASSETS.items() if name.endswith(".js")})
            for name, source in sources.items():
                output = target / name
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(source.read_bytes())
                checked = subprocess.run(["node", "--check", str(output)],
                                         capture_output=True, text=True)
                self.assertEqual(0, checked.returncode, checked.stderr)
            result = subprocess.run(["node", str(ROOT / "tests/frontend_modules.mjs"), str(target)],
                                    capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
