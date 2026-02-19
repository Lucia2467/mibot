/**
 * 💰 WALLET_FRONTEND.JS - Integración Frontend para MiniApp
 * 
 * Este archivo muestra cómo integrar las APIs de wallet
 * con tu HTML/CSS existente SIN modificar el diseño.
 * 
 * IMPORTANTE: Este código usa tus colores y diseño actual.
 * Solo conecta la lógica del wallet.
 */

// ============================================
// 🌐 CONFIGURACIÓN
// ============================================

const WALLET_CONFIG = {
    apiBase: window.location.origin, // URL de tu app
    userId: null, // Se obtiene de Telegram WebApp
    colors: {
        // Tus colores actuales de Sally-E
        primary: '#0066FF',
        secondary: '#003D99',
        accent: '#3B82F6'
    }
};

// Obtener user_id de Telegram WebApp
if (window.Telegram && window.Telegram.WebApp) {
    const tg = window.Telegram.WebApp;
    tg.ready();
    WALLET_CONFIG.userId = tg.initDataUnsafe?.user?.id || null;
}

// ============================================
// 🔧 FUNCIONES DE API
// ============================================

/**
 * Función helper para hacer requests a la API
 */
async function apiRequest(endpoint, method = 'GET', body = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (body && method !== 'GET') {
            options.body = JSON.stringify(body);
        }
        
        const response = await fetch(`${WALLET_CONFIG.apiBase}${endpoint}`, options);
        const data = await response.json();
        
        return data;
        
    } catch (error) {
        console.error('API Error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

/**
 * Obtener balance del usuario
 */
async function getBalance() {
    const userId = WALLET_CONFIG.userId;
    if (!userId) {
        showNotification('Error: Usuario no identificado', 'error');
        return null;
    }
    
    const response = await apiRequest(`/api/wallet/balance/${userId}`);
    
    if (response.success) {
        return response.data;
    } else {
        showNotification(response.error, 'error');
        return null;
    }
}

/**
 * Vincular wallet del usuario
 */
async function linkWallet(walletAddress) {
    const userId = WALLET_CONFIG.userId;
    
    const response = await apiRequest('/api/wallet/link_wallet', 'POST', {
        user_id: userId,
        wallet_address: walletAddress
    });
    
    if (response.success) {
        showNotification('✅ Wallet vinculada exitosamente', 'success');
        return true;
    } else {
        showNotification(`❌ ${response.error}`, 'error');
        return false;
    }
}

/**
 * Solicitar retiro
 */
async function requestWithdrawal(currency, amount, walletAddress) {
    const userId = WALLET_CONFIG.userId;
    
    // Mostrar loading
    showLoading('Procesando retiro...');
    
    const response = await apiRequest('/api/wallet/request_withdraw', 'POST', {
        user_id: userId,
        currency: currency,
        amount: parseFloat(amount),
        wallet_address: walletAddress
    });
    
    hideLoading();
    
    if (response.success) {
        const data = response.data;
        showNotification(
            `✅ Retiro solicitado: ${data.amount} ${data.currency}\n` +
            `Fee: ${data.fee} ${data.currency}\n` +
            `ID: ${data.withdrawal_id}`,
            'success'
        );
        
        // Actualizar balance en la UI
        await updateBalanceDisplay();
        
        return data;
    } else {
        showNotification(`❌ ${response.error}`, 'error');
        return null;
    }
}

/**
 * Obtener historial de retiros
 */
async function getWithdrawalHistory(limit = 20) {
    const userId = WALLET_CONFIG.userId;
    
    const response = await apiRequest(`/api/wallet/history/${userId}?limit=${limit}`);
    
    if (response.success) {
        return response.data.withdrawals;
    } else {
        showNotification(response.error, 'error');
        return [];
    }
}

/**
 * Obtener estadísticas
 */
async function getStats() {
    const userId = WALLET_CONFIG.userId;
    
    const response = await apiRequest(`/api/wallet/stats/${userId}`);
    
    if (response.success) {
        return response.data;
    } else {
        return null;
    }
}

/**
 * Obtener info del sistema
 */
async function getSystemInfo() {
    const response = await apiRequest('/api/wallet/info');
    
    if (response.success) {
        return response.data;
    } else {
        return null;
    }
}

// ============================================
// 🎨 FUNCIONES DE UI
// ============================================

/**
 * Actualizar display de balance
 */
async function updateBalanceDisplay() {
    const balance = await getBalance();
    
    if (!balance) return;
    
    // Actualizar en tu HTML existente
    // Ajusta los IDs según tu HTML actual
    
    const seBalanceEl = document.getElementById('se-balance');
    if (seBalanceEl) {
        seBalanceEl.textContent = balance.se_balance.toFixed(2);
    }
    
    const usdtBalanceEl = document.getElementById('usdt-balance');
    if (usdtBalanceEl) {
        usdtBalanceEl.textContent = balance.usdt_balance.toFixed(2);
    }
    
    const dogeBalanceEl = document.getElementById('doge-balance');
    if (dogeBalanceEl) {
        dogeBalanceEl.textContent = balance.doge_balance.toFixed(2);
    }
    
    // Mostrar/ocultar sección de wallet según si está vinculada
    const walletSection = document.getElementById('wallet-section');
    if (walletSection) {
        walletSection.style.display = balance.wallet_linked ? 'block' : 'none';
    }
    
    const linkWalletSection = document.getElementById('link-wallet-section');
    if (linkWalletSection) {
        linkWalletSection.style.display = balance.wallet_linked ? 'none' : 'block';
    }
}

/**
 * Renderizar historial de retiros
 */
function renderWithdrawalHistory(withdrawals) {
    const container = document.getElementById('withdrawal-history');
    if (!container) return;
    
    if (withdrawals.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #666;">
                <p>No tienes retiros aún</p>
            </div>
        `;
        return;
    }
    
    const html = withdrawals.map(w => `
        <div class="withdrawal-item" style="
            background: white;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 10px;
            border-left: 4px solid ${getStatusColor(w.status)};
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-weight: 600; font-size: 18px;">
                        ${w.amount} ${w.currency}
                    </div>
                    <div style="font-size: 12px; color: #666; margin-top: 4px;">
                        ${new Date(w.created_at).toLocaleString('es-ES')}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div class="status-badge" style="
                        background: ${getStatusColor(w.status)};
                        color: white;
                        padding: 4px 12px;
                        border-radius: 12px;
                        font-size: 11px;
                        font-weight: 600;
                    ">
                        ${w.status.toUpperCase()}
                    </div>
                    ${w.tx_hash ? `
                        <a href="${w.bscscan_url}" 
                           target="_blank" 
                           style="
                               display: inline-block;
                               margin-top: 6px;
                               font-size: 11px;
                               color: ${WALLET_CONFIG.colors.primary};
                           ">
                            Ver en BSCScan
                        </a>
                    ` : ''}
                </div>
            </div>
            ${w.wallet ? `
                <div style="
                    font-size: 11px;
                    color: #999;
                    margin-top: 8px;
                    font-family: monospace;
                ">
                    ${w.wallet.substring(0, 10)}...${w.wallet.substring(w.wallet.length - 8)}
                </div>
            ` : ''}
            <button onclick="viewReceipt('${w.id}')" style="
                background: none;
                border: 1px solid ${WALLET_CONFIG.colors.primary};
                color: ${WALLET_CONFIG.colors.primary};
                padding: 6px 12px;
                border-radius: 6px;
                margin-top: 10px;
                font-size: 12px;
                cursor: pointer;
            ">
                Ver Comprobante
            </button>
        </div>
    `).join('');
    
    container.innerHTML = html;
}

/**
 * Renderizar estadísticas
 */
async function renderStats() {
    const stats = await getStats();
    if (!stats) return;
    
    const container = document.getElementById('stats-container');
    if (!container) return;
    
    container.innerHTML = `
        <div style="
            background: linear-gradient(135deg, ${WALLET_CONFIG.colors.secondary} 0%, ${WALLET_CONFIG.colors.primary} 100%);
            padding: 20px;
            border-radius: 16px;
            color: white;
        ">
            <h3 style="margin: 0 0 15px 0;">📊 Tus Estadísticas</h3>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <div>
                    <div style="opacity: 0.8; font-size: 12px;">Total Retiros</div>
                    <div style="font-size: 24px; font-weight: 700;">
                        ${stats.total_withdrawals}
                    </div>
                </div>
                
                <div>
                    <div style="opacity: 0.8; font-size: 12px;">Completados</div>
                    <div style="font-size: 24px; font-weight: 700;">
                        ${stats.completed_count}
                    </div>
                </div>
                
                <div>
                    <div style="opacity: 0.8; font-size: 12px;">Retirado USDT</div>
                    <div style="font-size: 18px; font-weight: 700;">
                        ${stats.total_withdrawn.USDT.toFixed(2)}
                    </div>
                </div>
                
                <div>
                    <div style="opacity: 0.8; font-size: 12px;">Retirado DOGE</div>
                    <div style="font-size: 18px; font-weight: 700;">
                        ${stats.total_withdrawn.DOGE.toFixed(2)}
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Mostrar modal de retiro
 */
function showWithdrawModal() {
    const modal = document.getElementById('withdraw-modal');
    if (!modal) return;
    
    // Tu código existente para mostrar el modal
    modal.style.display = 'flex';
}

/**
 * Procesar formulario de retiro
 */
async function handleWithdrawSubmit(event) {
    event.preventDefault();
    
    // Obtener valores del formulario
    // Ajusta los IDs según tu HTML
    const currency = document.getElementById('withdraw-currency').value;
    const amount = document.getElementById('withdraw-amount').value;
    const walletAddress = document.getElementById('withdraw-wallet').value;
    
    // Validaciones básicas
    if (!currency || !amount || !walletAddress) {
        showNotification('❌ Completa todos los campos', 'error');
        return;
    }
    
    if (parseFloat(amount) <= 0) {
        showNotification('❌ El monto debe ser mayor a 0', 'error');
        return;
    }
    
    // Solicitar retiro
    const result = await requestWithdrawal(currency, amount, walletAddress);
    
    if (result) {
        // Cerrar modal
        const modal = document.getElementById('withdraw-modal');
        if (modal) modal.style.display = 'none';
        
        // Limpiar formulario
        document.getElementById('withdraw-form').reset();
        
        // Actualizar historial
        await loadWithdrawalHistory();
    }
}

/**
 * Ver comprobante de retiro
 */
function viewReceipt(withdrawalId) {
    // Abrir comprobante en nueva ventana
    window.open(
        `${WALLET_CONFIG.apiBase}/api/wallet/receipt/${withdrawalId}?format=html`,
        '_blank',
        'width=600,height=800'
    );
}

/**
 * Cargar historial de retiros
 */
async function loadWithdrawalHistory() {
    const withdrawals = await getWithdrawalHistory(20);
    renderWithdrawalHistory(withdrawals);
}

// ============================================
// 🔔 FUNCIONES DE NOTIFICACIONES
// ============================================

/**
 * Mostrar notificación
 */
function showNotification(message, type = 'info') {
    // Si usas Telegram WebApp
    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.showAlert(message);
        return;
    }
    
    // O tu sistema de notificaciones actual
    // Ajusta según tu implementación
    alert(message);
}

/**
 * Mostrar loading
 */
function showLoading(message = 'Cargando...') {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = 'flex';
        const loaderText = loader.querySelector('.loader-text');
        if (loaderText) loaderText.textContent = message;
    }
}

/**
 * Ocultar loading
 */
function hideLoading() {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = 'none';
    }
}

// ============================================
// 🎨 HELPERS DE UI
// ============================================

/**
 * Obtener color según estado
 */
function getStatusColor(status) {
    const colors = {
        'pendiente': '#FFC107',
        'procesando': '#2196F3',
        'exitoso': '#4CAF50',
        'fallido': '#F44336',
        'cancelado': '#9E9E9E'
    };
    return colors[status] || '#999';
}

/**
 * Formatear número con separadores de miles
 */
function formatNumber(num) {
    return num.toLocaleString('es-ES', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// ============================================
// 🚀 INICIALIZACIÓN
// ============================================

/**
 * Inicializar wallet cuando se carga la página
 */
async function initWallet() {
    console.log('🔧 Inicializando Wallet System...');
    
    // Verificar user_id
    if (!WALLET_CONFIG.userId) {
        console.warn('⚠️ User ID no disponible');
        return;
    }
    
    try {
        // Cargar balance
        await updateBalanceDisplay();
        
        // Cargar historial si estamos en la página de wallet
        if (document.getElementById('withdrawal-history')) {
            await loadWithdrawalHistory();
        }
        
        // Cargar stats si estamos en la página de wallet
        if (document.getElementById('stats-container')) {
            await renderStats();
        }
        
        // Cargar info del sistema
        const systemInfo = await getSystemInfo();
        if (systemInfo) {
            console.log('📊 System Info:', systemInfo);
            
            // Mostrar montos mínimos en la UI si existe el elemento
            const minWithdrawalsEl = document.getElementById('min-withdrawals');
            if (minWithdrawalsEl) {
                minWithdrawalsEl.innerHTML = `
                    <div>USDT: ${systemInfo.min_withdrawals.USDT}</div>
                    <div>DOGE: ${systemInfo.min_withdrawals.DOGE}</div>
                    <div>S-E: ${systemInfo.min_withdrawals.SE}</div>
                `;
            }
        }
        
        console.log('✅ Wallet System inicializado');
        
    } catch (error) {
        console.error('❌ Error inicializando wallet:', error);
    }
}

// Event listeners para formularios
document.addEventListener('DOMContentLoaded', () => {
    // Inicializar wallet
    initWallet();
    
    // Form de retiro
    const withdrawForm = document.getElementById('withdraw-form');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', handleWithdrawSubmit);
    }
    
    // Form de vincular wallet
    const linkWalletForm = document.getElementById('link-wallet-form');
    if (linkWalletForm) {
        linkWalletForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const walletAddress = document.getElementById('wallet-address-input').value;
            const success = await linkWallet(walletAddress);
            if (success) {
                await updateBalanceDisplay();
                linkWalletForm.reset();
            }
        });
    }
    
    // Auto-actualizar balance cada 30 segundos
    setInterval(updateBalanceDisplay, 30000);
    
    // Auto-actualizar historial cada minuto
    if (document.getElementById('withdrawal-history')) {
        setInterval(loadWithdrawalHistory, 60000);
    }
});

// ============================================
// 📤 EXPORTAR FUNCIONES GLOBALES
// ============================================

// Hacer funciones disponibles globalmente para onclick en HTML
window.walletAPI = {
    getBalance,
    linkWallet,
    requestWithdrawal,
    getWithdrawalHistory,
    getStats,
    viewReceipt,
    showWithdrawModal,
    updateBalanceDisplay,
    loadWithdrawalHistory
};

console.log('💰 Wallet Frontend cargado - window.walletAPI disponible');
