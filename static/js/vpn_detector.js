/**
 * SALLY-E VPN/Proxy Detection System
 * Verificación silenciosa en segundo plano — sin overlay de espera
 */

(function() {
    'use strict';

    const VPN_CHECK_CONFIG = {
        enabled: true,
        apiEndpoint: '/api/vpn-check',
        blockOnError: false,
        cacheTimeout: 60000,
        maxRetries: 2,
        debug: false
    };

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

            if (!response.ok) throw new Error('VPN check failed');

            const data = await response.json();
            return data;
        } catch (error) {
            return { vpn_detected: VPN_CHECK_CONFIG.blockOnError, error: true };
        }
    }

    function redirectToBlockedPage() {
        const urlParams = new URLSearchParams(window.location.search);
        const userId = urlParams.get('user_id') || '';
        window.location.href = '/vpn-blocked' + (userId ? '?user_id=' + userId : '');
    }

    // Verificación completamente silenciosa — sin overlay, sin animación
    async function initVPNCheck() {
        if (!VPN_CHECK_CONFIG.enabled) return;
        if (window.location.pathname === '/vpn-blocked') return;
        if (window.location.pathname.startsWith('/admin')) return;

        // Resultado cacheado — verificar sin bloquear
        const cachedResult = sessionStorage.getItem('vpn_check_result');
        const cachedTime   = sessionStorage.getItem('vpn_check_time');

        if (cachedResult && cachedTime) {
            const elapsed = Date.now() - parseInt(cachedTime);
            if (elapsed < VPN_CHECK_CONFIG.cacheTimeout) {
                const result = JSON.parse(cachedResult);
                if (result.vpn_detected) redirectToBlockedPage();
                return; // No VPN: el usuario ya ve la app, no se interrumpe
            }
        }

        // Sin caché: verificar en segundo plano sin mostrar nada
        let retries = 0;
        let result = null;

        while (retries < VPN_CHECK_CONFIG.maxRetries) {
            result = await checkVPNStatus();
            if (!result.error) break;
            retries++;
            await new Promise(resolve => setTimeout(resolve, 500));
        }

        if (result && !result.error) {
            sessionStorage.setItem('vpn_check_result', JSON.stringify(result));
            sessionStorage.setItem('vpn_check_time', Date.now().toString());
        }

        if (result && result.vpn_detected) {
            redirectToBlockedPage();
        }
        // Sin VPN: no se hace nada, el usuario sigue navegando normal
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVPNCheck);
    } else {
        initVPNCheck();
    }

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
