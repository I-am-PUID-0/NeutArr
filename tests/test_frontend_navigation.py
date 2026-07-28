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

        self.assertIn("const link = e.target.closest('.nav-item, .brand-home-link');", source)
        self.assertIn("item.removeAttribute('aria-current');", source)
        self.assertIn("activeNavItem.setAttribute('aria-current', 'page');", source)
        self.assertIn("document.title = `${newTitle} · NeutArr`;", source)
        self.assertIn("this.elements.mainContent.scrollTop = 0;", source)

    def test_brand_and_version_badge_are_useful_navigation_links(self):
        sidebar = (_REPO_ROOT / "frontend" / "templates" / "components" / "sidebar.html").read_text()
        topbar = (_REPO_ROOT / "frontend" / "templates" / "components" / "topbar.html").read_text()
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()

        self.assertIn('href="#home" class="logo-container brand-home-link"', sidebar)
        self.assertIn('aria-label="Go to NeutArr home"', sidebar)
        self.assertIn("e.target.closest('.nav-item, .brand-home-link')", source)
        self.assertIn('id="versionReleaseLink"', topbar)
        self.assertIn('target="_blank" rel="noopener noreferrer"', topbar)
        self.assertIn("this.updateVersionReleaseLink(currentVersion);", source)
        self.assertIn("`${repositoryReleases}/tag/${encodeURIComponent(normalizedVersion)}`", source)
        self.assertIn("View NeutArr releases on GitHub", source)

    def test_mobile_navigation_is_a_dismissible_inert_drawer(self):
        index = (_REPO_ROOT / "frontend" / "templates" / "index.html").read_text()
        topbar = (_REPO_ROOT / "frontend" / "templates" / "components" / "topbar.html").read_text()
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()

        self.assertIn('id="sidebarBackdrop"', index)
        self.assertIn('id="navToggle"', topbar)
        self.assertIn('aria-controls="sidebar"', topbar)
        self.assertIn("window.matchMedia('(max-width: 900px)')", source)
        self.assertIn("this.elements.sidebar.inert =", source)
        self.assertIn("event.key === 'Escape'", source)
        self.assertIn("this.trapSidebarFocus(event);", source)
        self.assertIn("this.elements.navToggle.setAttribute('aria-expanded'", source)

    def test_primary_sections_share_redesign_headings(self):
        components = _REPO_ROOT / "frontend" / "templates" / "components"
        expected_text = {
            "home_section.html": "Automation activity",
            "apps_section.html": "App integrations",
            "settings_section.html": "Manage application behavior",
            "scheduling_section.html": "Run recurring pause",
            "logs_section.html": "Live logs",
            "history_section.html": "Audit trail",
        }

        for filename, marker in expected_text.items():
            with self.subTest(component=filename):
                self.assertIn(marker, (components / filename).read_text())

    def test_redesign_covers_every_primary_surface_and_breakpoint(self):
        source = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        for selector in (
            "#homeSection .dashboard-grid",
            "#appsSection .single-scroll-container",
            ".settings-group",
            ".scheduler-container",
            ".logs",
            ".modern-table-wrapper",
            "@media (max-width: 900px)",
            "@media (max-width: 720px)",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, source)

    def test_home_dashboard_only_reveals_configured_apps(self):
        template = (_REPO_ROOT / "frontend" / "templates" / "components" / "home_section.html").read_text()
        script = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        for app in ("sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"):
            with self.subTest(app=app):
                self.assertIn(f'data-app="{app}" hidden', template)

        self.assertIn('id="homeAppsState" role="status"', template)
        self.assertIn('href="#apps" class="dashboard-empty-action"', template)
        self.assertIn("Open app integrations", template)
        self.assertIn("appBox.hidden = !isConfigured;", script)
        self.assertIn("this.updateHomeAppsState(false)", script)
        self.assertIn("statsContainer.insertAdjacentHTML(", script)
        self.assertIn(".app-stats-card[hidden]", styles)
        self.assertIn("display: none !important;", styles)

    def test_home_dashboard_shows_live_per_app_cycle_countdowns(self):
        template = (_REPO_ROOT / "frontend" / "templates" / "components" / "home_section.html").read_text()
        script = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        for app in ("sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"):
            with self.subTest(app=app):
                self.assertIn(f'data-cycle-countdown="{app}"', template)

        self.assertEqual(template.count('role="timer" aria-live="off"'), 6)
        self.assertIn("this.setupCycleCountdowns();", script)
        self.assertIn("NeutArrUtils.fetchWithTimeout('/api/cycles')", script)
        self.assertIn("this.cycleServerOffsetMs = (data.server_time * 1000) - Date.now();", script)
        self.assertIn("formatCycleCountdown: function(totalSeconds)", script)
        self.assertIn('"countdown countdown"', styles)
        self.assertIn(".cycle-countdown", styles)
        self.assertIn("font-variant-numeric: tabular-nums;", styles)

    def test_section_headers_and_instance_forms_remain_in_normal_flow(self):
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn("#settingsSection .section-header", styles)
        self.assertIn("position: relative !important;", styles)
        self.assertIn("#appsSection .instances-container", styles)
        self.assertIn("grid-template-columns: repeat(auto-fit", styles)

    def test_scheduling_controls_remain_inside_their_panel(self):
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn("grid-template-columns: repeat(auto-fit, minmax(min(132px, 100%), 1fr))", styles)
        self.assertIn("#schedulingSection .day-checkbox label", styles)
        self.assertIn("overflow-wrap: anywhere;", styles)
        self.assertIn("#schedulingSection .time-selection", styles)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", styles)
        self.assertIn("grid-template-columns: 1fr !important;", styles)
        self.assertIn("min-width: 0 !important;", styles)

    def test_mobile_logs_keep_a_compact_complete_toolbar(self):
        template = (_REPO_ROOT / "frontend" / "templates" / "components" / "logs_section.html").read_text()
        script = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn('id="logSearchResults" hidden', template)
        self.assertIn('id="clearSearchButton" class="clear-search-button" hidden', template)
        self.assertIn("this.elements.clearSearchButton.hidden = false;", script)
        self.assertIn("this.elements.logSearchResults.hidden = true;", script)
        self.assertIn("#logsSection .log-controls", styles)
        self.assertIn('"stream status options"', styles)
        self.assertIn('"search search search"', styles)
        self.assertIn("#logsSection #clearLogsButton", styles)
        self.assertIn("height: clamp(320px, calc(100dvh - 270px), 720px)", styles)

    def test_app_integration_layout_is_scrollable_and_compact(self):
        template = (_REPO_ROOT / "frontend" / "templates" / "components" / "apps_section.html").read_text()
        script = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertNotIn("overflow: hidden !important", template)
        self.assertIn("body .app-container .main-content", styles)
        self.assertIn("overflow-y: auto !important;", styles)
        self.assertIn(".remove-instance-btn", styles)
        self.assertIn("width: auto !important;", styles)
        self.assertIn('class="swaparr-intro"', script)
        self.assertIn(".swaparr-intro p", styles)
        self.assertIn("max-width: none !important;", styles)
        self.assertIn('<fieldset class="swaparr-app-instance-group">', script)
        self.assertIn("#swaparr_app_instances .checkbox-group label", styles)

    def test_app_instance_controls_keep_consistent_layout_when_added(self):
        script = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn("generateInstanceIdentity: function(index, name)", script)
        self.assertIn("bindInstanceNameHeading: function(instanceItem)", script)
        self.assertIn('class="instance-number"', script)
        self.assertIn("data-instance-name", script)
        self.assertNotIn("<h4>Instance ${index + 1}:", script)
        self.assertIn("#appsSection .instance-identity", styles)
        self.assertIn("#appsSection .instance-number", styles)
        self.assertIn(".setting-item label.toggle-switch", styles)
        self.assertIn("width: 40px !important;", styles)
        self.assertIn("#appsSection .instance-header", styles)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto;", styles)
        self.assertIn("flex-wrap: nowrap !important;", styles)
        self.assertIn(
            'class="info-icon" title="Toggle this instance on or off without removing it"',
            script,
        )

    def test_new_and_missing_app_instances_default_to_disabled(self):
        settings = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()
        main = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()

        self.assertEqual(settings.count("instance.enabled === true ? 'checked' : ''"), 6)
        self.assertNotIn("instance.enabled !== false", settings)
        self.assertIn("const enabled = enabledInput ? enabledInput.checked : false;", settings)
        self.assertIn(
            'id="${appType}-enabled-${currentCount}" name="enabled">',
            settings,
        )
        self.assertIn("enabled: false", main)
        self.assertNotIn("enabledInput ? enabledInput.checked : true", main)

    def test_default_instance_name_is_reserved_for_the_disabled_placeholder(self):
        settings = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()
        main = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()
        apps = (_REPO_ROOT / "frontend" / "static" / "js" / "apps.js").read_text()

        self.assertIn("validateInstanceNames: function(container)", settings)
        self.assertIn("normalizedName !== 'default'", settings)
        self.assertIn("isEmptyDisabledPlaceholder", settings)
        self.assertIn("nameInput.setCustomValidity(", settings)
        self.assertIn("SettingsForms.validateInstanceNames(settingsForm)", main)
        self.assertIn("SettingsForms.validateInstanceNames(appPanel)", apps)
        self.assertIn("“Default” is reserved for the disabled placeholder.", settings)

    def test_swaparr_only_offers_enabled_source_instances(self):
        settings = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn("const getEnabledInstances = (app) =>", settings)
        self.assertIn("instance.querySelector('input[name=\"enabled\"]')?.checked === true", settings)
        self.assertIn("formInstances.filter(instance => instance.enabled === true)", settings)
        self.assertIn(
            "sourceSettings[app].instances.filter(instance => instance?.enabled === true)",
            settings,
        )
        self.assertIn("if (instances.length === 0) return '';", settings)
        self.assertIn("No app instances are enabled.", settings)
        self.assertNotIn("return [{ name: 'Default' }];", settings)
        self.assertIn(".swaparr-instances-empty", styles)

    def test_account_actions_and_history_empty_state_do_not_create_overflow(self):
        settings = (_REPO_ROOT / "frontend" / "templates" / "components" / "settings_section.html").read_text()
        account_script = (_REPO_ROOT / "frontend" / "static" / "js" / "new-user.js").read_text()
        history = (_REPO_ROOT / "frontend" / "templates" / "components" / "history_section.html").read_text()
        history_script = (_REPO_ROOT / "frontend" / "static" / "js" / "history.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn('class="settings-account-action-buttons"', settings)
        self.assertIn('class="action-button secondary-button api-key-visibility-button"', settings)
        self.assertIn('aria-controls="apiKeyDisplay"', settings)
        self.assertIn('aria-pressed="false"', settings)
        self.assertIn("this.setAttribute('aria-pressed', String(willShow));", account_script)
        self.assertIn("#accountSettingsPanel #toggleApiKey", styles)
        self.assertIn("position: absolute;", styles)
        self.assertIn("padding-right: 92px !important;", styles)
        self.assertIn("width: auto !important;", styles)
        self.assertIn("flex: 0 0 auto;", settings)
        self.assertIn('class="modern-table-wrapper" hidden', history)
        self.assertIn('class="pagination-controls" hidden', history)
        self.assertNotIn("<style>", history)
        self.assertNotIn("<script>", history)
        self.assertNotIn("position: absolute", history)
        self.assertNotIn("history-scrollbar-fix", history)
        self.assertIn("showViewState: function(state)", history_script)
        self.assertIn("this.elements.historyTableWrapper.hidden = state !== 'data';", history_script)
        self.assertIn("#historySection .history-container", styles)
        self.assertIn("height: auto !important;", styles)
        self.assertIn("#historySection .modern-table-wrapper[hidden]", styles)
        self.assertIn("#historySection .empty-state-message:not([hidden])", styles)
        self.assertIn("position: static !important;", styles)

    def test_mobile_shell_removes_legacy_collapsed_sidebar_offset(self):
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn("position: relative !important;", styles)
        self.assertIn("inset: auto !important;", styles)
        self.assertIn("margin-left: 0 !important;", styles)
        self.assertIn("min-width: min(300px, calc(100vw - 48px)) !important;", styles)
        self.assertIn("max-width: min(300px, calc(100vw - 48px)) !important;", styles)
        self.assertIn("body .sidebar .nav-item span", styles)

    def test_information_icons_are_clickable_and_keyboard_accessible(self):
        source = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn("this.setupInfoTooltips();", source)
        self.assertIn("new MutationObserver", source)
        self.assertIn("icon.setAttribute('role', 'button');", source)
        self.assertIn("event.key === 'Enter' || event.key === ' '", source)
        self.assertIn("tooltip.setAttribute('role', 'tooltip');", source)
        self.assertIn(".info-icon:focus-visible", styles)
        self.assertIn(".info-tooltip[hidden]", styles)

    def test_appearance_preferences_apply_immediately_and_stay_browser_local(self):
        preload = (_REPO_ROOT / "frontend" / "static" / "js" / "theme-preload.js").read_text()
        settings = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()
        main = (_REPO_ROOT / "frontend" / "static" / "js" / "new-main.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertIn("window.NeutArrAppearance", preload)
        self.assertIn("neutarr-appearance-theme", preload)
        self.assertIn("neutarr-appearance-density", preload)
        self.assertIn("document.documentElement.dataset.neutarrTheme", preload)
        self.assertIn('id="interface_theme" data-local-preference="true"', settings)
        self.assertIn('id="interface_density" data-local-preference="true"', settings)
        self.assertIn("Object.entries(appearanceThemes)", settings)
        self.assertIn("window.NeutArrAppearance.apply(", settings)
        self.assertIn("event.target.dataset.localPreference !== 'true'", main)
        self.assertIn("input.dataset.localPreference === 'true'", main)

        for theme in (
            "graphite",
            "ocean",
            "nordic",
            "forest",
            "amethyst",
            "rosewood",
            "ember",
            "golden",
            "neon",
        ):
            with self.subTest(theme=theme):
                self.assertIn(f"{theme}:", preload)
                self.assertIn(f':root[data-neutarr-theme="{theme}"]', styles)

        self.assertIn(':root[data-neutarr-density="compact"]', styles)

    def test_mobile_general_settings_stay_within_the_viewport(self):
        settings = (_REPO_ROOT / "frontend" / "static" / "js" / "settings_forms.js").read_text()
        reset = (_REPO_ROOT / "frontend" / "static" / "js" / "direct-reset.js").read_text()
        styles = (_REPO_ROOT / "frontend" / "static" / "css" / "redesign.css").read_text()

        self.assertNotIn("margin-left: -3ch", settings)
        self.assertIn('class="setting-item toggle-setting-item"', settings)
        self.assertIn('class="settings-group stateful-settings"', settings)
        self.assertIn("resetButton.className = 'danger-button emergency-reset-button';", reset)
        self.assertNotIn("resetButton.style.marginLeft", reset)
        self.assertIn("#generalSettings .toggle-setting-item", styles)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto !important;", styles)
        self.assertIn("#generalSettings .info-container", styles)
        self.assertIn("grid-template-columns: minmax(0, 1fr) !important;", styles)
        self.assertIn("#generalSettings .date-info-block", styles)
        self.assertIn("flex-direction: column;", styles)
        self.assertIn("#generalSettings #emergency_reset_btn", styles)

    def test_shell_honors_reduced_motion_preferences(self):
        source = (_REPO_ROOT / "frontend" / "static" / "css" / "shell-foundation.css").read_text()

        self.assertIn("@media (prefers-reduced-motion: reduce)", source)


if __name__ == "__main__":
    unittest.main()
