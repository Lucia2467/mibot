/**
 * TON Wallet Integration for Telegram Mini App
 * Handles TON Connect, wallet linking, and withdrawals
 */

// TON Connect configuration
const TON_CONNECT_MANIFEST_URL = window.location.origin + '/tonconnect-manifest.json';

// Wallet state
let tonWalletConnected = false;
let tonWalletAddress = null;
let tonConnectUI = null;

// Initialize TON Connect
async function initTonConnect() {
    try {
        // Check if TON Connect is available
        if (typeof TonConnectUI === 'undefined') {
            console.log('TON Connect SDK not loaded');
            return false;
        }

        tonConnectUI = new TonConnectUI({
            manifestUrl: TON_CONNECT_MANIFEST_URL,
            buttonRootId: 'ton-connect-button'
        });

        // Subscribe to wallet changes
        tonConnectUI.onStatusChange(async (walletInfo) => {
            if (walletInfo) {
                tonWalletConnected = true;
                tonWalletAddress = walletInfo.account.address;
                console.log('TON Wallet connected:', tonWalletAddress);
                
                // Update UI
                updateTonWalletUI(true, tonWalletAddress);
                
                // Link wallet to user account
                await linkTonWallet(tonWalletAddress);
            } else {
                tonWalletConnected = false;
                tonWalletAddress = null;
                updateTonWalletUI(false, null);
            }
        });

        // Check if already connected
        const isConnected = await tonConnectUI.isConnected();
        if (isConnected) {
            const walletInfo = tonConnectUI.wallet;
            if (walletInfo) {
                tonWalletConnected = true;
                tonWalletAddress = walletInfo.account.address;
                updateTonWalletUI(true, tonWalletAddress);
            }
        }

        return true;
    } catch (error) {
        console.error('Error initializing TON Connect:', error);
        return false;
    }
}

// Update UI based on wallet connection status
function updateTonWalletUI(connected, address) {
    const connectButton = document.getElementById('ton-connect-button');
    const addressDisplay = document.getElementById('ton-wallet-display');
    const withdrawTonBtn = document.getElementById('withdraw-ton-btn');

    if (connected && address) {
        if (connectButton) {
            connectButton.innerHTML = `
                <span style="color: #28a745;">✓</span>
                ${formatAddress(address)}
            `;
            connectButton.classList.add('connected');
        }
        if (addressDisplay) {
            addressDisplay.textContent = formatAddress(address);
            addressDisplay.style.display = 'block';
        }
        if (withdrawTonBtn) {
            withdrawTonBtn.disabled = false;
        }
    } else {
        if (connectButton) {
            connectButton.innerHTML = '💎 Connect TON Wallet';
            connectButton.classList.remove('connected');
        }
        if (addressDisplay) {
            addressDisplay.style.display = 'none';
        }
    }
}

// Format address for display
function formatAddress(address) {
    if (!address || address.length < 12) return address;
    return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
}

// Connect TON wallet
async function connectTonWallet() {
    if (tonConnectUI) {
        try {
            await tonConnectUI.openModal();
        } catch (error) {
            console.error('Error opening TON Connect modal:', error);
            showNotification('Error connecting wallet', 'error');
        }
    } else {
        // Fallback: Manual address input
        openManualTonWalletModal();
    }
}

// Disconnect TON wallet
async function disconnectTonWallet() {
    if (tonConnectUI && tonWalletConnected) {
        await tonConnectUI.disconnect();
        tonWalletConnected = false;
        tonWalletAddress = null;
        updateTonWalletUI(false, null);
    }
}

// Open manual TON wallet input modal
function openManualTonWalletModal() {
    const modal = document.getElementById('ton-wallet-modal');
    if (modal) {
        modal.classList.add('active');
    } else {
        // Create modal dynamically
        const modalHtml = `
            <div id="ton-wallet-modal" class="modal active">
                <div class="modal-content">
                    <h3 style="color: #0098EA; margin-bottom: 20px;">
                        💎 Link TON Wallet
                    </h3>
                    <p style="color: #888; font-size: 14px; margin-bottom: 15px;">
                        Enter your TON wallet address to receive withdrawals
                    </p>
                    <input type="text" id="ton-address-input" 
                           placeholder="EQ... or UQ..."
                           style="width: 100%; padding: 12px; background: rgba(0,0,0,0.3); 
                                  border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; 
                                  color: #fff; font-family: monospace; margin-bottom: 15px;">
                    <div style="display: flex; gap: 10px;">
                        <button onclick="submitTonWallet()" 
                                style="flex: 1; padding: 12px; background: linear-gradient(135deg, #0098EA, #0077B6); 
                                       border: none; border-radius: 8px; color: white; font-weight: 600; cursor: pointer;">
                            ✓ Link Wallet
                        </button>
                        <button onclick="closeTonWalletModal()" 
                                style="padding: 12px 20px; background: #333; border: none; 
                                       border-radius: 8px; color: white; cursor: pointer;">
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }
}

// Close TON wallet modal
function closeTonWalletModal() {
    const modal = document.getElementById('ton-wallet-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Submit manual TON wallet address
async function submitTonWallet() {
    const input = document.getElementById('ton-address-input');
    if (!input) return;

    const address = input.value.trim();
    if (!address) {
        showNotification('Please enter a wallet address', 'error');
        return;
    }

    // Validate address format
    const isValid = await validateTonAddress(address);
    if (!isValid) {
        showNotification('Invalid TON address format', 'error');
        return;
    }

    // Link wallet
    const success = await linkTonWallet(address);
    if (success) {
        tonWalletAddress = address;
        updateTonWalletUI(true, address);
        closeTonWalletModal();
        showNotification('TON wallet linked successfully!', 'success');
    }
}

// Validate TON address
async function validateTonAddress(address) {
    try {
        const response = await fetch('/api/ton/validate-address', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address })
        });
        const data = await response.json();
        return data.valid;
    } catch (error) {
        console.error('Error validating address:', error);
        // Basic client-side validation
        const prefixes = ['EQ', 'UQ', 'Ef', 'Uf', 'kQ', 'kf', '0Q', '0f'];
        return prefixes.some(p => address.startsWith(p)) && address.length === 48;
    }
}

// Link TON wallet to user account
async function linkTonWallet(address) {
    try {
        const userId = getUserId();
        if (!userId) {
            showNotification('User not found', 'error');
            return false;
        }

        const response = await fetch('/api/ton/link-wallet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_id: userId,
                address: address 
            })
        });

        const data = await response.json();
        
        if (data.success) {
            return true;
        } else {
            showNotification(data.error || 'Failed to link wallet', 'error');
            return false;
        }
    } catch (error) {
        console.error('Error linking wallet:', error);
        showNotification('Connection error', 'error');
        return false;
    }
}

// Request TON withdrawal
async function requestTonWithdrawal(amount) {
    try {
        const userId = getUserId();
        if (!userId) {
            showNotification('User not found', 'error');
            return { success: false };
        }

        // Get wallet address
        let address = tonWalletAddress;
        if (!address) {
            // Try to get from user data
            const userResponse = await fetch(`/api/user?user_id=${userId}`);
            const userData = await userResponse.json();
            address = userData.user?.ton_wallet_address;
        }

        if (!address) {
            showNotification('Please link your TON wallet first', 'error');
            return { success: false };
        }

        const response = await fetch('/api/ton/withdraw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                amount: parseFloat(amount),
                address: address
            })
        });

        const data = await response.json();
        
        if (data.success) {
            showNotification(data.message || 'Withdrawal request submitted!', 'success');
            return { success: true, payment_id: data.payment_id };
        } else {
            showNotification(data.error || 'Withdrawal failed', 'error');
            return { success: false, error: data.error };
        }
    } catch (error) {
        console.error('Error requesting withdrawal:', error);
        showNotification('Connection error', 'error');
        return { success: false, error: error.message };
    }
}

// Get payment status
async function getTonPaymentStatus(paymentId) {
    try {
        const response = await fetch(`/api/ton/status/${paymentId}`);
        return await response.json();
    } catch (error) {
        console.error('Error getting payment status:', error);
        return { success: false, error: error.message };
    }
}

// Get TON payment history
async function getTonPaymentHistory() {
    try {
        const userId = getUserId();
        if (!userId) return [];

        const response = await fetch(`/api/ton/history/${userId}`);
        const data = await response.json();
        
        if (data.success) {
            return data.payments;
        }
        return [];
    } catch (error) {
        console.error('Error getting payment history:', error);
        return [];
    }
}

// Get user ID from various sources
function getUserId() {
    // Try from URL
    const urlParams = new URLSearchParams(window.location.search);
    let userId = urlParams.get('user_id');
    
    // Try from Telegram WebApp
    if (!userId && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        userId = window.Telegram.WebApp.initDataUnsafe.user.id;
    }
    
    // Try from global variable
    if (!userId && window.currentUserId) {
        userId = window.currentUserId;
    }
    
    return userId;
}

// Show notification
function showNotification(message, type = 'info') {
    // Check if there's a global notification function
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
        return;
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        padding: 15px 25px;
        border-radius: 10px;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#0098EA'};
        color: white;
        font-weight: 600;
        z-index: 10000;
        animation: slideDown 0.3s ease;
        box-shadow: 0 5px 20px rgba(0,0,0,0.3);
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideUp 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideDown {
        from { transform: translate(-50%, -100%); opacity: 0; }
        to { transform: translate(-50%, 0); opacity: 1; }
    }
    @keyframes slideUp {
        from { transform: translate(-50%, 0); opacity: 1; }
        to { transform: translate(-50%, -100%); opacity: 0; }
    }
    
    .modal {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.8);
        z-index: 9999;
        align-items: center;
        justify-content: center;
    }
    
    .modal.active {
        display: flex;
    }
    
    .modal-content {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(0, 152, 234, 0.3);
        border-radius: 16px;
        padding: 25px;
        max-width: 400px;
        width: 90%;
    }
    
    #ton-connect-button {
        padding: 12px 20px;
        background: linear-gradient(135deg, #0098EA 0%, #0077B6 100%);
        border: none;
        border-radius: 10px;
        color: white;
        font-weight: 600;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        transition: all 0.3s;
    }
    
    #ton-connect-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 152, 234, 0.4);
    }
    
    #ton-connect-button.connected {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
    }
`;
document.head.appendChild(style);

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Try to initialize TON Connect if SDK is loaded
    if (typeof TonConnectUI !== 'undefined') {
        initTonConnect();
    }
});

// Export functions for global access
window.tonWallet = {
    connect: connectTonWallet,
    disconnect: disconnectTonWallet,
    linkManual: openManualTonWalletModal,
    validate: validateTonAddress,
    withdraw: requestTonWithdrawal,
    getStatus: getTonPaymentStatus,
    getHistory: getTonPaymentHistory,
    isConnected: () => tonWalletConnected,
    getAddress: () => tonWalletAddress
};
