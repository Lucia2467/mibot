/**
 * 🔄 DB_LOADER.JS - Database Connection Status Loader
 * Version 1.0 - Visual feedback while waiting for database connections
 * 
 * Usage:
 *   1. Include this script in your HTML
 *   2. Call DbLoader.init() on page load
 *   3. Use DbLoader.wrap() for API calls
 * 
 * Example:
 *   const data = await DbLoader.wrap(
 *     fetch('/api/users'),
 *     'Loading users...'
 *   );
 */

const DbLoader = {
    // Configuration
    config: {
        pollInterval: 500,      // How often to poll status (ms)
        pollTimeout: 10000,     // Maximum polling time (ms)
        statusEndpoint: '/api/db-status',
        fadeOutDelay: 300       // Animation delay (ms)
    },

    // State
    state: {
        isPolling: false,
        pollTimer: null,
        loaderElement: null,
        activeRequests: 0
    },

    /**
     * Initialize the loader system
     * Call this once when your app loads
     */
    init() {
        this.createLoaderElement();
        this.injectStyles();
        console.log('🔄 DbLoader initialized');
    },

    /**
     * Create the loader overlay element
     */
    createLoaderElement() {
        // Check if already exists
        if (document.getElementById('db-loader-overlay')) {
            this.state.loaderElement = document.getElementById('db-loader-overlay');
            return;
        }

        const overlay = document.createElement('div');
        overlay.id = 'db-loader-overlay';
        overlay.className = 'db-loader-hidden';
        overlay.innerHTML = `
            <div class="db-loader-content">
                <div class="db-loader-spinner">
                    <div class="db-loader-ring"></div>
                    <div class="db-loader-ring"></div>
                    <div class="db-loader-ring"></div>
                </div>
                <div class="db-loader-message" id="db-loader-message">
                    ⏳ Connecting to database...
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        this.state.loaderElement = overlay;
    },

    /**
     * Inject CSS styles for the loader
     */
    injectStyles() {
        if (document.getElementById('db-loader-styles')) return;

        const style = document.createElement('style');
        style.id = 'db-loader-styles';
        style.textContent = `
            /* Loader Overlay */
            #db-loader-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(4px);
                -webkit-backdrop-filter: blur(4px);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                opacity: 1;
                transition: opacity 0.3s ease;
            }

            #db-loader-overlay.db-loader-hidden {
                opacity: 0;
                pointer-events: none;
            }

            /* Loader Content Box */
            .db-loader-content {
                background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
                border-radius: 16px;
                padding: 32px 48px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4),
                           inset 0 1px 0 rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }

            /* Spinner Container */
            .db-loader-spinner {
                position: relative;
                width: 60px;
                height: 60px;
                margin: 0 auto 20px;
            }

            /* Animated Rings */
            .db-loader-ring {
                position: absolute;
                width: 100%;
                height: 100%;
                border-radius: 50%;
                border: 3px solid transparent;
            }

            .db-loader-ring:nth-child(1) {
                border-top-color: #00d4ff;
                animation: db-spin 1s linear infinite;
            }

            .db-loader-ring:nth-child(2) {
                border-right-color: #7c3aed;
                animation: db-spin 1.5s linear infinite reverse;
                width: 80%;
                height: 80%;
                top: 10%;
                left: 10%;
            }

            .db-loader-ring:nth-child(3) {
                border-bottom-color: #10b981;
                animation: db-spin 2s linear infinite;
                width: 60%;
                height: 60%;
                top: 20%;
                left: 20%;
            }

            @keyframes db-spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* Message Text */
            .db-loader-message {
                color: #e2e8f0;
                font-size: 14px;
                font-weight: 500;
                letter-spacing: 0.5px;
                max-width: 250px;
                line-height: 1.5;
            }

            /* Success State */
            #db-loader-overlay.db-loader-success .db-loader-message {
                color: #10b981;
            }

            /* Error State */
            #db-loader-overlay.db-loader-error .db-loader-message {
                color: #ef4444;
            }

            /* Mobile Responsive */
            @media (max-width: 480px) {
                .db-loader-content {
                    padding: 24px 32px;
                    margin: 0 16px;
                }

                .db-loader-spinner {
                    width: 50px;
                    height: 50px;
                }

                .db-loader-message {
                    font-size: 13px;
                }
            }
        `;

        document.head.appendChild(style);
    },

    /**
     * Show the loader overlay
     * @param {string} message - Optional custom message
     */
    show(message = '⏳ Connecting to database...') {
        this.state.activeRequests++;
        
        if (!this.state.loaderElement) {
            this.createLoaderElement();
        }

        const messageEl = document.getElementById('db-loader-message');
        if (messageEl) {
            messageEl.textContent = message;
        }

        this.state.loaderElement.classList.remove('db-loader-hidden', 'db-loader-success', 'db-loader-error');
        this.startPolling();
    },

    /**
     * Hide the loader overlay
     * @param {string} status - 'success' or 'error' for visual feedback
     */
    hide(status = '') {
        this.state.activeRequests = Math.max(0, this.state.activeRequests - 1);
        
        // Only hide if no more active requests
        if (this.state.activeRequests > 0) return;

        this.stopPolling();

        if (this.state.loaderElement) {
            if (status === 'success') {
                this.state.loaderElement.classList.add('db-loader-success');
                this.updateMessage('✅ Connected');
            } else if (status === 'error') {
                this.state.loaderElement.classList.add('db-loader-error');
            }

            setTimeout(() => {
                this.state.loaderElement.classList.add('db-loader-hidden');
            }, this.config.fadeOutDelay);
        }
    },

    /**
     * Update the loader message
     * @param {string} message - New message to display
     */
    updateMessage(message) {
        const messageEl = document.getElementById('db-loader-message');
        if (messageEl) {
            messageEl.textContent = message;
        }
    },

    /**
     * Start polling the status endpoint
     */
    startPolling() {
        if (this.state.isPolling) return;
        this.state.isPolling = true;

        const startTime = Date.now();

        const poll = async () => {
            // Check timeout
            if (Date.now() - startTime > this.config.pollTimeout) {
                this.stopPolling();
                return;
            }

            try {
                const response = await fetch(this.config.statusEndpoint);
                const data = await response.json();

                if (data.message && data.is_connecting) {
                    this.updateMessage(data.message);
                }
            } catch (e) {
                // Silently fail - status polling is optional
                console.debug('Status poll failed:', e);
            }

            if (this.state.isPolling) {
                this.state.pollTimer = setTimeout(poll, this.config.pollInterval);
            }
        };

        poll();
    },

    /**
     * Stop polling the status endpoint
     */
    stopPolling() {
        this.state.isPolling = false;
        if (this.state.pollTimer) {
            clearTimeout(this.state.pollTimer);
            this.state.pollTimer = null;
        }
    },

    /**
     * Wrap a fetch/promise with loader display
     * @param {Promise} promise - The promise to wrap
     * @param {string} message - Optional loading message
     * @returns {Promise} - Resolves with the original promise result
     */
    async wrap(promise, message = '⏳ Loading...') {
        this.show(message);
        
        try {
            const result = await promise;
            this.hide('success');
            return result;
        } catch (error) {
            this.hide('error');
            throw error;
        }
    },

    /**
     * Wrapper for API calls with automatic loader
     * @param {string} url - API endpoint
     * @param {object} options - Fetch options
     * @param {string} message - Loading message
     * @returns {Promise} - JSON response
     */
    async fetchWithLoader(url, options = {}, message = '⏳ Loading...') {
        return this.wrap(
            fetch(url, options).then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            }),
            message
        );
    }
};

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => DbLoader.init());
} else {
    DbLoader.init();
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DbLoader;
}
