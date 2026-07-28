import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]


class FrontendNavigationTests(unittest.TestCase):
    def test_shell_exposes_landmarks_and_skip_navigation(self):
        index = (_REPO_ROOT / "frontend" / "templates" / "index.html").read_text()
        sidebar = (_REPO_ROOT / "frontend" / "templates" / "components" / "sidebar.html").read_text()

        self.assertIn('class="skip-link" href="#mainContent"', index)
        self.assertIn('<main class="main-content" id="mainContent" tabindex="-1">', index)
        self.assertIn('<aside class="sidebar" id="sidebar">', sidebar)
        self.assertIn('aria-label="Primary navigation"', sidebar)

    def test_primary_navigation_uses_in_page_hash_routes(self):
        sidebar = (_REPO_ROOT / "frontend" / "templates" / "components" / "sidebar.html").read_text()

        for section in ("home", "apps", "settings", "scheduling", "logs", "history"):
            with self.subTest(section=section):
                self.assertIn(f'href="#{section}"', sidebar)

        self.assertNotIn('href="/#', sidebar)
        self.assertNotIn("function setActiveNavItem()", sidebar)

    def test_main_navigation_owns_accessible_active_state(self):
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()

        self.assertIn("const link = e.target.closest('.nav-item');", source)
        self.assertIn("item.removeAttribute('aria-current');", source)
        self.assertIn("activeNavItem.setAttribute('aria-current', 'page');", source)
        self.assertIn("document.title = `${newTitle} · NeutArr`;", source)

    def test_shell_honors_reduced_motion_preferences(self):
        source = (_REPO_ROOT / "frontend" / "static" / "css" / "shell-foundation.css").read_text()

        self.assertIn("@media (prefers-reduced-motion: reduce)", source)


if __name__ == "__main__":
    unittest.main()
