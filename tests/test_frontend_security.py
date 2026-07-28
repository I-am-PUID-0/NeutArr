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

    def test_proxy_auth_requirements_only_show_for_proxy_mode(self):
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()

        self.assertIn('id="proxy_auth_requirements"', source)
        self.assertIn(
            "proxyAuthRequirements.style.display = authModeSelect.value === 'no_login' ? '' : 'none';",
            source,
        )

    def test_scheduler_rows_do_not_interpolate_persisted_values_as_html(self):
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "scheduling.js").read_text()

        self.assertNotIn("scheduleItem.innerHTML", source)
        self.assertNotIn('data-id="${schedule.id}"', source)
        self.assertNotIn('data-app-type="${schedule.appType}"', source)
        self.assertIn("timeElement.textContent = formattedTime;", source)
        self.assertIn("daysElement.textContent = daysText;", source)
        self.assertIn("actionElement.textContent = actionText;", source)
        self.assertIn("appElement.textContent = appText;", source)
        self.assertIn("deleteButton.dataset.id = String(schedule.id ?? '');", source)
        self.assertIn("deleteButton.dataset.appType = String(schedule.appType ?? 'global');", source)

    def test_browser_auth_does_not_persist_or_inject_jwts(self):
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "auth.js").read_text()

        self.assertNotIn("localStorage.setItem(ACCESS_KEY", source)
        self.assertNotIn("localStorage.setItem(REFRESH_KEY", source)
        self.assertNotIn("headers.set('Authorization'", source)
        self.assertIn("clearLegacyBrowserTokens();", source)
        self.assertIn("_legacyTokenMigrationPending = true;", source)
        self.assertIn("await AuthManager.refresh()", source)
        self.assertIn("response.headers.get('X-NeutArr-Auth-Required') !== '1'", source)


if __name__ == "__main__":
    unittest.main()
