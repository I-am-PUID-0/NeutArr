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

    def test_settings_forms_escape_persisted_free_form_values(self):
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()

        self.assertIn("escapeHtml: function(value)", source)
        self.assertNotIn("${instance.name || 'Unnamed'}", source)
        self.assertNotIn("value=\"${instance.name || ''}\"", source)
        self.assertNotIn("value=\"${instance.api_url || ''}\"", source)
        self.assertNotIn("value=\"${instance.api_key || ''}\"", source)
        self.assertEqual(source.count("SettingsForms.escapeHtml(instance.name"), 6)
        self.assertEqual(source.count("SettingsForms.generateInstanceIdentity(index, instance.name)"), 6)
        self.assertIn("SettingsForms.escapeHtml(displayName)", source)
        self.assertEqual(source.count("SettingsForms.escapeHtml(instance.api_url"), 6)
        self.assertEqual(source.count("SettingsForms.escapeHtml(instance.api_key"), 6)
        self.assertIn(
            "SettingsForms.escapeHtml(settings.max_download_time || '2h')",
            source,
        )
        self.assertIn(
            "SettingsForms.escapeHtml(settings.ignore_above_size || '25GB')",
            source,
        )

    def test_log_search_highlights_text_without_reparsing_log_html(self):
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()

        self.assertNotIn("data-original-html", source)
        self.assertNotIn("logEntry.innerHTML = newHtml", source)
        self.assertIn(
            "document.createTreeWalker(logEntry, NodeFilter.SHOW_TEXT)",
            source,
        )
        self.assertIn("highlight.textContent = text.slice(", source)
        self.assertIn("textNode.replaceWith(fragment);", source)
        self.assertIn("this.clearLogHighlights(entry);", source)

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
