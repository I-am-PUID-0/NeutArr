(function() {
    // Store logo URL consistently across the app - use local path instead of GitHub
    const LOGO_URL = '/static/logo/256.png';
    const THEME_STORAGE_KEY = 'neutarr-appearance-theme';
    const DENSITY_STORAGE_KEY = 'neutarr-appearance-density';
    const DEFAULT_THEME = 'midnight';
    const DEFAULT_DENSITY = 'comfortable';
    const themes = {
        midnight: {
            label: 'Midnight Indigo',
            canvas: '#080d18',
            sidebar: '#0b1120',
            surface: '#111827'
        },
        graphite: {
            label: 'Graphite',
            canvas: '#0d0f12',
            sidebar: '#101216',
            surface: '#171a20'
        },
        ocean: {
            label: 'Deep Ocean',
            canvas: '#06121a',
            sidebar: '#071722',
            surface: '#0d202c'
        },
        nordic: {
            label: 'Nordic Frost',
            canvas: '#0b1118',
            sidebar: '#0d151e',
            surface: '#16212d'
        },
        forest: {
            label: 'Evergreen',
            canvas: '#07130f',
            sidebar: '#081710',
            surface: '#0e2118'
        },
        amethyst: {
            label: 'Amethyst',
            canvas: '#120a1c',
            sidebar: '#140b20',
            surface: '#21112f'
        },
        rosewood: {
            label: 'Rosewood',
            canvas: '#170b11',
            sidebar: '#190c13',
            surface: '#28131d'
        },
        ember: {
            label: 'Ember',
            canvas: '#160c0b',
            sidebar: '#190e0d',
            surface: '#261513'
        },
        golden: {
            label: 'Golden Hour',
            canvas: '#151006',
            sidebar: '#171208',
            surface: '#251d0d'
        },
        neon: {
            label: 'Neon Noir',
            canvas: '#090819',
            sidebar: '#0c0a1e',
            surface: '#17132e'
        }
    };
    const densities = new Set(['comfortable', 'compact']);

    const normalizeTheme = (value) => Object.prototype.hasOwnProperty.call(themes, value) ? value : DEFAULT_THEME;
    const normalizeDensity = (value) => densities.has(value) ? value : DEFAULT_DENSITY;

    const applyAppearance = (theme, density, persist = true) => {
        const selectedTheme = normalizeTheme(theme);
        const selectedDensity = normalizeDensity(density);

        document.documentElement.dataset.neutarrTheme = selectedTheme;
        document.documentElement.dataset.neutarrDensity = selectedDensity;
        document.documentElement.classList.add('dark-theme');

        if (document.body) {
            document.body.classList.add('dark-theme');
        }

        if (persist) {
            localStorage.setItem(THEME_STORAGE_KEY, selectedTheme);
            localStorage.setItem(DENSITY_STORAGE_KEY, selectedDensity);
        }

        return { theme: selectedTheme, density: selectedDensity };
    };

    const getAppearance = () => ({
        theme: normalizeTheme(localStorage.getItem(THEME_STORAGE_KEY)),
        density: normalizeDensity(localStorage.getItem(DENSITY_STORAGE_KEY))
    });

    window.NeutArrAppearance = {
        themes,
        densities: Array.from(densities),
        apply: applyAppearance,
        get: getAppearance
    };

    const appearance = getAppearance();
    const activePalette = themes[appearance.theme];
    applyAppearance(appearance.theme, appearance.density, false);
    
    // Create and preload image with local path
    const preloadImg = new Image();
    preloadImg.src = LOGO_URL;
    
    // Retain the legacy dark-mode preference for older pages.
    localStorage.setItem('neutarr-dark-mode', 'true');
    
    // Add inline style to immediately set background color
    // This prevents flash before the CSS files load
    const style = document.createElement('style');
    style.textContent = `
        body, html { 
            background-color: ${activePalette.canvas} !important;
            color: #f8f9fa !important;
        }
        .sidebar {
            background-color: ${activePalette.sidebar} !important;
        }
        .top-bar {
            background-color: ${activePalette.surface} !important;
        }
        .login-container {
            background-color: ${activePalette.surface} !important;
        }
        .login-header {
            background-color: ${activePalette.sidebar} !important;
        }
    `;
    document.head.appendChild(style);
    
    // Store the logo URL in localStorage for persistence across page loads
    localStorage.setItem('neutarr-logo-url', LOGO_URL);
    
    // Create a global function to apply the logo to all logo elements
    window.applyLogoToAllElements = function() {
        const logoUrl = localStorage.getItem('neutarr-logo-url') || LOGO_URL;
        const logoElements = document.querySelectorAll('.logo, .login-logo');
        
        logoElements.forEach(img => {
            if (!img.src || img.src !== logoUrl) {
                img.src = logoUrl;
            }
            
            // Handle image load event properly
            if (img.complete) {
                img.classList.add('loaded');
            } else {
                img.onload = function() {
                    this.classList.add('loaded');
                };
                img.onerror = function() {
                    // Fallback if local path fails
                    console.warn('Logo failed to load, trying alternate source');
                    if (this.src !== '/logo/256.png') {
                        this.src = '/logo/256.png';
                    }
                };
            }
        });

        // Check if the logo source needs updating
        document.querySelectorAll('img[alt*="Logo"]').forEach(img => {
            // Check if the src is not the correct static path
            const currentSrc = new URL(img.src, window.location.origin).pathname;
            if (currentSrc !== LOGO_URL) {
                // Check against the old incorrect path as well, just in case
                if (currentSrc === '/logo/64.png') {
                    img.src = LOGO_URL;
                }
                // You might want to add more specific checks or broader updates here
                // For now, we only correct the specific incorrect path found
            }
        });
    };
    
    // Apply logo as soon as DOM is interactive
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.applyLogoToAllElements);
    } else {
        // DOMContentLoaded already fired
        window.applyLogoToAllElements();
    }
    
    // Set up MutationObserver to catch any dynamically added logo elements
    document.addEventListener('DOMContentLoaded', function() {
        const observer = new MutationObserver(function(mutations) {
            let shouldApplyLogos = false;
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length) {
                    shouldApplyLogos = true;
                }
            });
            if (shouldApplyLogos) {
                window.applyLogoToAllElements();
            }
        });
        
        observer.observe(document.body, { childList: true, subtree: true });
    });
    
    // Ensure logo is loaded when navigating with AJAX
    window.addEventListener('load', window.applyLogoToAllElements);
})();
