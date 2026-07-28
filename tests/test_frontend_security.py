import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]


class FrontendSecurityTests(unittest.TestCase):
    def test_swaparr_renderer_never_uses_html_injection_sinks(self):
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "apps" / "swaparr.js").read_text()

        for unsafe_sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            with self.subTest(sink=unsafe_sink):
                self.assertNotIn(unsafe_sink, source)

        self.assertIn("element.textContent = String(value ?? '');", source)
        self.assertIn("configPanel.replaceChildren(config);", source)
        self.assertIn("tableView.replaceChildren(table);", source)


if __name__ == "__main__":
    unittest.main()
