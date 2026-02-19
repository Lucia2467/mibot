/**
 * SALLY-E Device Fingerprint
 * Client-side device identification for fraud detection
 */

(function() {
    'use strict';

    const DeviceFingerprint = {
        // Generate canvas fingerprint
        getCanvasFingerprint: function() {
            try {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.width = 200;
                canvas.height = 50;
                
                ctx.textBaseline = 'top';
                ctx.font = '14px Arial';
                ctx.fillStyle = '#f60';
                ctx.fillRect(0, 0, 125, 62);
                ctx.fillStyle = '#069';
                ctx.fillText('SE-Device-FP', 2, 15);
                ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
                ctx.fillText('SE-Device-FP', 4, 17);
                
                // Add some unique shapes
                ctx.beginPath();
                ctx.arc(50, 25, 20, 0, Math.PI * 2);
                ctx.stroke();
                
                return this.hashCode(canvas.toDataURL());
            } catch (e) {
                return 'canvas_not_available';
            }
        },

        // Get WebGL fingerprint
        getWebGLFingerprint: function() {
            try {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                
                if (!gl) return 'webgl_not_available';
                
                const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                if (debugInfo) {
                    const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                    const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                    return this.hashCode(vendor + '~' + renderer);
                }
                
                return 'no_debug_info';
            } catch (e) {
                return 'webgl_error';
            }
        },

        // Get audio fingerprint
        getAudioFingerprint: function() {
            try {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return 'audio_not_available';
                
                const context = new AudioContext();
                const oscillator = context.createOscillator();
                const analyser = context.createAnalyser();
                const gainNode = context.createGain();
                const scriptProcessor = context.createScriptProcessor(4096, 1, 1);
                
                gainNode.gain.value = 0;
                oscillator.type = 'triangle';
                oscillator.connect(analyser);
                analyser.connect(scriptProcessor);
                scriptProcessor.connect(gainNode);
                gainNode.connect(context.destination);
                
                oscillator.start(0);
                
                const bins = new Float32Array(analyser.frequencyBinCount);
                analyser.getFloatFrequencyData(bins);
                
                oscillator.stop();
                context.close();
                
                let sum = 0;
                for (let i = 0; i < bins.length; i++) {
                    sum += Math.abs(bins[i]);
                }
                
                return 'audio_' + Math.abs(sum).toString(36).substring(0, 8);
            } catch (e) {
                return 'audio_error';
            }
        },

        // Get screen info
        getScreenInfo: function() {
            return {
                width: screen.width,
                height: screen.height,
                colorDepth: screen.colorDepth,
                pixelRatio: window.devicePixelRatio || 1,
                availWidth: screen.availWidth,
                availHeight: screen.availHeight
            };
        },

        // Get browser info
        getBrowserInfo: function() {
            return {
                userAgent: navigator.userAgent,
                language: navigator.language,
                platform: navigator.platform,
                hardwareConcurrency: navigator.hardwareConcurrency || 'unknown',
                deviceMemory: navigator.deviceMemory || 'unknown',
                maxTouchPoints: navigator.maxTouchPoints || 0,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                plugins: this.getPluginsHash()
            };
        },

        // Get plugins hash
        getPluginsHash: function() {
            try {
                const plugins = [];
                for (let i = 0; i < navigator.plugins.length; i++) {
                    plugins.push(navigator.plugins[i].name);
                }
                return this.hashCode(plugins.sort().join(','));
            } catch (e) {
                return 'no_plugins';
            }
        },

        // Get storage fingerprint
        getStorageFingerprint: function() {
            const hasLocalStorage = !!window.localStorage;
            const hasSessionStorage = !!window.sessionStorage;
            const hasIndexedDB = !!window.indexedDB;
            return `ls:${hasLocalStorage}|ss:${hasSessionStorage}|idb:${hasIndexedDB}`;
        },

        // Simple hash function
        hashCode: function(str) {
            let hash = 0;
            if (!str || str.length === 0) return hash.toString(36);
            
            for (let i = 0; i < str.length; i++) {
                const char = str.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash;
            }
            
            return Math.abs(hash).toString(36);
        },

        // Generate full fingerprint
        generate: function() {
            const canvas = this.getCanvasFingerprint();
            const webgl = this.getWebGLFingerprint();
            const audio = this.getAudioFingerprint();
            const screen = this.getScreenInfo();
            const browser = this.getBrowserInfo();
            const storage = this.getStorageFingerprint();
            
            const components = [
                canvas,
                webgl,
                audio,
                screen.width + 'x' + screen.height,
                screen.colorDepth,
                screen.pixelRatio,
                browser.platform,
                browser.timezone,
                browser.hardwareConcurrency,
                browser.maxTouchPoints,
                browser.plugins,
                storage
            ];
            
            const fullHash = this.hashCode(components.join('|'));
            const shortHash = this.hashCode(canvas + webgl + screen.width + browser.platform);
            
            return {
                hash: 'df_' + shortHash + '_' + fullHash,
                device_info: {
                    canvas: canvas,
                    webgl: webgl,
                    audio: audio,
                    screen: screen,
                    browser: browser,
                    storage: storage
                }
            };
        },

        // Send fingerprint to server
        sendToServer: function(userId) {
            if (!userId) return;
            
            const fingerprint = this.generate();
            
            // Store in cookie for server-side access
            document.cookie = '_se_dfp_hash=' + fingerprint.hash + ';path=/;max-age=31536000';
            
            // Send to server
            fetch('/system/auto-ban-check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Device-Hash': fingerprint.hash
                },
                body: JSON.stringify({
                    user_id: userId,
                    device_hash: fingerprint.hash,
                    device_info: fingerprint.device_info
                })
            }).then(response => {
                if (!response.ok) {
                    console.log('[SE-FP] Server check completed');
                }
            }).catch(error => {
                // Silent fail - don't expose fingerprinting to user
            });
        },

        // Get stored fingerprint
        getStoredFingerprint: function() {
            const stored = localStorage.getItem('_se_device_fp');
            if (stored) {
                try {
                    const data = JSON.parse(stored);
                    // Check if fingerprint is less than 24 hours old
                    if (data.timestamp && (Date.now() - data.timestamp) < 86400000) {
                        return data.hash;
                    }
                } catch (e) {}
            }
            
            const fingerprint = this.generate();
            localStorage.setItem('_se_device_fp', JSON.stringify({
                hash: fingerprint.hash,
                timestamp: Date.now()
            }));
            
            return fingerprint.hash;
        },

        // Initialize
        init: function(userId) {
            if (userId) {
                setTimeout(() => this.sendToServer(userId), 1000);
            }
        }
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            window.DeviceFingerprint = DeviceFingerprint;
        });
    } else {
        window.DeviceFingerprint = DeviceFingerprint;
    }
})();
