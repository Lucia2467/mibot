/**
 * SALLY-E VPN/Proxy Detection System
 * This script detects VPN/Proxy usage and blocks access to the app
 * Version: 1.0.0
 */

(function() {
    'use strict';

    // Configuration
    const VPN_CHECK_CONFIG = {
        enabled: true,
        apiEndpoint: '/api/vpn-check',
        blockOnError: false,  // Whether to block if API fails
        cacheTimeout: 60000,  // 1 minute cache
        maxRetries: 2,
        debug: false
    };

    // Styles for the blocking overlay
    const OVERLAY_STYLES = `
        .vpn-block-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: #000000;
            z-index: 999999;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease, visibility 0.3s ease;
        }
        .vpn-block-overlay.active {
            opacity: 1;
            visibility: visible;
        }
        .vpn-block-overlay.checking {
            opacity: 1;
            visibility: visible;
        }
        .vpn-checking-content {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        .vpn-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #0066FF;
            animation: vpnDotBounce 1.4s ease-in-out infinite both;
        }
        .vpn-dot:nth-child(1) { animation-delay: 0s; }
        .vpn-dot:nth-child(2) { animation-delay: 0.2s; }
        .vpn-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes vpnDotBounce {
            0%, 80%, 100% { transform: scale(0.7); opacity: 0.35; }
            40%            { transform: scale(1.2); opacity: 1; }
        }
    `;

    // Create and inject overlay immediately
    function createOverlay() {
        // Add styles
        const styleEl = document.createElement('style');
        styleEl.textContent = OVERLAY_STYLES;
        document.head.appendChild(styleEl);

        // Create overlay element
        const overlay = document.createElement('div');
        overlay.id = 'vpn-block-overlay';
        overlay.className = 'vpn-block-overlay checking';
        overlay.innerHTML = `
            <div class="vpn-checking-content">
                <div class="vpn-dot"></div>
                <div class="vpn-dot"></div>
                <div class="vpn-dot"></div>
            </div>
        `;
        
        // Insert at the beginning of body or wait for it
        if (document.body) {
            document.body.insertBefore(overlay, document.body.firstChild);
        } else {
            document.addEventListener('DOMContentLoaded', () => {
                document.body.insertBefore(overlay, document.body.firstChild);
            });
        }

        return overlay;
    }

    // Check VPN status via server
    async function checkVPNStatus() {
        try {
            const response = await fetch(VPN_CHECK_CONFIG.apiEndpoint, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error('VPN check failed');
            }

            const data = await response.json();
            
            if (VPN_CHECK_CONFIG.debug) {
                console.log('[VPN Check] Response:', data);
            }

            return data;
        } catch (error) {
            console.error('[VPN Check] Error:', error);
            return { 
                vpn_detected: VPN_CHECK_CONFIG.blockOnError, 
                error: true 
            };
        }
    }

    // Redirect to VPN blocked page
    function redirectToBlockedPage() {
        // Get user_id from URL if present
        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user_id') || '';
        
        // Redirect to blocked page
        window.location.href = '/vpn-blocked' + (userId ? '?user_id=' + userId : '');
    }

    // Hide the checking overlay
    function hideOverlay() {
        const overlay = document.getElementById('vpn-block-overlay');
        if (overlay) {
            overlay.classList.remove('checking', 'active');
            setTimeout(() => {
                overlay.remove();
            }, 300);
        }
    }

    // Main initialization
    async function initVPNCheck() {
        if (!VPN_CHECK_CONFIG.enabled) {
            return;
        }

        // Skip check on VPN blocked page itself
        if (window.location.pathname === '/vpn-blocked') {
            return;
        }

        // Skip check on admin pages
        if (window.location.pathname.startsWith('/admin')) {
            return;
        }

        // Create overlay immediately to hide content
        const overlay = createOverlay();

        // Check cached result
        const cachedResult = sessionStorage.getItem('vpn_check_result');
        const cachedTime = sessionStorage.getItem('vpn_check_time');
        
        if (cachedResult && cachedTime) {
            const elapsed = Date.now() - parseInt(cachedTime);
            if (elapsed < VPN_CHECK_CONFIG.cacheTimeout) {
                const result = JSON.parse(cachedResult);
                if (result.vpn_detected) {
                    redirectToBlockedPage();
                    return;
                } else {
                    hideOverlay();
                    return;
                }
            }
        }

        // Perform VPN check
        let retries = 0;
        let result = null;

        while (retries < VPN_CHECK_CONFIG.maxRetries) {
            result = await checkVPNStatus();
            
            if (!result.error) {
                break;
            }
            
            retries++;
            await new Promise(resolve => setTimeout(resolve, 500));
        }

        // Cache the result
        if (result && !result.error) {
            sessionStorage.setItem('vpn_check_result', JSON.stringify(result));
            sessionStorage.setItem('vpn_check_time', Date.now().toString());
        }

        // Handle result
        if (result && result.vpn_detected) {
            if (VPN_CHECK_CONFIG.debug) {
                console.log('[VPN Check] VPN detected, blocking access');
            }
            redirectToBlockedPage();
        } else {
            if (VPN_CHECK_CONFIG.debug) {
                console.log('[VPN Check] No VPN detected, allowing access');
            }
            hideOverlay();
        }
    }

    // Run check immediately
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVPNCheck);
    } else {
        initVPNCheck();
    }

    // Expose for manual re-check if needed
    window.VPNCheck = {
        recheck: async function() {
            sessionStorage.removeItem('vpn_check_result');
            sessionStorage.removeItem('vpn_check_time');
            await initVPNCheck();
        },
        clearCache: function() {
            sessionStorage.removeItem('vpn_check_result');
            sessionStorage.removeItem('vpn_check_time');
        }
    };

})();
