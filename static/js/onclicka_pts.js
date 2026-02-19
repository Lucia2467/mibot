/**
 * onclicka_pts.js - Sistema de PTS con OnClickA
 * ==============================================
 * - Tareas de anuncios
 * - Check-in diario
 * - Boost de minería
 * - Ranking PTS
 */

// ============================================
// CONFIGURACIÓN
// ============================================
const ONCLICKA_CONFIG = {
    adCodeId: 408797,
    scriptUrl: 'https://js.onclckvd.com/in-stream-ad-admanager/tma.js'
};

// Estado global
let onclickaReady = false;
let pendingAdCallback = null;

// ============================================
// INICIALIZACIÓN DE ONCLICKA
// ============================================

/**
 * Cargar SDK de OnClickA
 */
function loadOnClickaSDK() {
    return new Promise((resolve, reject) => {
        if (onclickaReady) {
            resolve(true);
            return;
        }
        
        // Verificar si ya está cargado
        if (document.querySelector(`script[src="${ONCLICKA_CONFIG.scriptUrl}"]`)) {
            onclickaReady = true;
            resolve(true);
            return;
        }
        
        const script = document.createElement('script');
        script.src = ONCLICKA_CONFIG.scriptUrl;
        script.async = true;
        script.dataset.adCode = ONCLICKA_CONFIG.adCodeId;
        
        script.onload = () => {
            onclickaReady = true;
            console.log('[OnClickA] SDK cargado');
            resolve(true);
        };
        
        script.onerror = () => {
            console.error('[OnClickA] Error cargando SDK');
            reject(new Error('Failed to load OnClickA SDK'));
        };
        
        document.head.appendChild(script);
    });
}

/**
 * Mostrar anuncio de OnClickA
 */
async function showOnClickaAd(options = {}) {
    const {
        onComplete = () => {},
        onError = () => {},
        onSkip = () => {}
    } = options;
    
    try {
        // Cargar SDK si no está listo
        await loadOnClickaSDK();
        
        // Verificar si puede ver anuncio
        const userId = getUserId();
        const checkResponse = await fetch(`/api/ad/can-watch?user_id=${userId}`);
        const checkData = await checkResponse.json();
        
        if (!checkData.can_watch) {
            onError(checkData.reason || 'No puedes ver anuncios ahora');
            return false;
        }
        
        // Mostrar el anuncio usando la API de OnClickA TMA
        return new Promise((resolve) => {
            // Configurar callback global para OnClickA
            window.onclickaAdComplete = async (result) => {
                if (result.completed) {
                    // Registrar en backend
                    const response = await fetch(`/api/ad/watch?user_id=${userId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ task_type: options.taskType || 'single_ad' })
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        onComplete(data);
                    } else {
                        onError(data.message || 'Error al registrar anuncio');
                    }
                } else {
                    onSkip();
                }
                resolve(result.completed);
            };
            
            // Disparar el anuncio
            if (window.show_ad) {
                window.show_ad({
                    adCode: ONCLICKA_CONFIG.adCodeId,
                    onComplete: window.onclickaAdComplete,
                    onError: (err) => {
                        onError(err.message || 'Error mostrando anuncio');
                        resolve(false);
                    }
                });
            } else {
                // Fallback: simular click en el trigger de OnClickA
                const adTrigger = document.querySelector('[data-ad-code]');
                if (adTrigger) {
                    adTrigger.click();
                    // Esperar a que termine
                    setTimeout(() => {
                        onComplete({ pts_earned: 0, message: 'Anuncio mostrado' });
                        resolve(true);
                    }, 30000);
                } else {
                    onError('No se pudo iniciar el anuncio');
                    resolve(false);
                }
            }
        });
        
    } catch (error) {
        console.error('[OnClickA] Error:', error);
        onError(error.message || 'Error al cargar anuncio');
        return false;
    }
}

// ============================================
// FUNCIONES DE UI
// ============================================

/**
 * Obtener estado completo de PTS
 */
async function getPtsStatus() {
    const userId = getUserId();
    if (!userId) return null;
    
    try {
        const response = await fetch(`/api/pts/status?user_id=${userId}`);
        return await response.json();
    } catch (error) {
        console.error('[PTS] Error obteniendo estado:', error);
        return null;
    }
}

/**
 * Obtener ranking
 */
async function getPtsRanking() {
    const userId = getUserId();
    try {
        const response = await fetch(`/api/pts/ranking?user_id=${userId || ''}`);
        return await response.json();
    } catch (error) {
        console.error('[PTS] Error obteniendo ranking:', error);
        return null;
    }
}

/**
 * Hacer check-in diario
 */
async function doCheckin() {
    const userId = getUserId();
    if (!userId) {
        showPtsToast('Error: Usuario no identificado', 'error');
        return;
    }
    
    const btn = document.getElementById('checkin-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="pts-spinner"></span> Procesando...';
    }
    
    try {
        const response = await fetch(`/api/checkin?user_id=${userId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        
        if (data.success) {
            showPtsToast(`✅ ${data.message} +${data.pts_earned} PTS`, 'success');
            hapticFeedback('success');
            updatePtsUI();
            
            // Mostrar opción de duplicar
            if (data.status && !data.status.doubled) {
                showDoubleOption();
            }
        } else {
            showPtsToast(data.message || 'Error', 'error');
            hapticFeedback('error');
        }
    } catch (error) {
        showPtsToast('Error de conexión', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            updateCheckinButton();
        }
    }
}

/**
 * Duplicar recompensa de check-in viendo anuncio
 */
async function doubleCheckinReward() {
    const userId = getUserId();
    if (!userId) return;
    
    // Mostrar modal de confirmación
    showAdConsentModal({
        title: '🎁 Duplicar Recompensa',
        subtitle: 'Mira un anuncio para duplicar tu recompensa de check-in',
        reward: '+10 PTS extra',
        onAccept: async () => {
            closeAdConsentModal();
            
            // Mostrar anuncio
            await showOnClickaAd({
                taskType: 'checkin_double',
                onComplete: async () => {
                    // Llamar al backend para duplicar
                    const response = await fetch(`/api/checkin/double?user_id=${userId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        showPtsToast(`🎉 ${data.message} +${data.pts_earned} PTS`, 'success');
                        hapticFeedback('success');
                        updatePtsUI();
                    } else {
                        showPtsToast(data.message || 'Error', 'error');
                    }
                },
                onError: (msg) => showPtsToast(msg, 'error'),
                onSkip: () => showPtsToast('Anuncio cancelado', 'info')
            });
        }
    });
}

/**
 * Ver anuncio para ganar PTS
 */
async function watchAdForPts() {
    const userId = getUserId();
    if (!userId) {
        showPtsToast('Error: Usuario no identificado', 'error');
        return;
    }
    
    // Verificar si puede ver
    const checkResponse = await fetch(`/api/ad/can-watch?user_id=${userId}`);
    const checkData = await checkResponse.json();
    
    if (!checkData.can_watch) {
        showPtsToast(checkData.reason || 'Espera antes de ver otro anuncio', 'warning');
        return;
    }
    
    // Mostrar modal de confirmación
    showAdConsentModal({
        title: '📺 Ver Anuncio',
        subtitle: 'Mira un video para ganar PTS',
        reward: '+5 PTS',
        onAccept: async () => {
            closeAdConsentModal();
            
            await showOnClickaAd({
                taskType: 'single_ad',
                onComplete: (data) => {
                    let msg = `✅ +${data.pts_earned} PTS`;
                    if (data.ad_progress && data.ad_progress.ads_watched >= 5 && !data.ad_progress.completed) {
                        msg += ' 🎁 ¡Bonus por 5 anuncios!';
                    }
                    showPtsToast(msg, 'success');
                    hapticFeedback('success');
                    updatePtsUI();
                },
                onError: (msg) => showPtsToast(msg, 'error'),
                onSkip: () => showPtsToast('Anuncio cancelado', 'info')
            });
        }
    });
}

/**
 * Activar boost de minería con anuncio
 */
async function activateMiningBoost() {
    const userId = getUserId();
    if (!userId) {
        showPtsToast('Error: Usuario no identificado', 'error');
        return;
    }
    
    // Verificar estado
    const response = await fetch(`/api/boost/onclicka/status?user_id=${userId}`);
    const status = await response.json();
    
    if (!status.can_activate) {
        showPtsToast(status.reason || 'No puedes activar boost ahora', 'warning');
        return;
    }
    
    // Mostrar modal de confirmación
    showAdConsentModal({
        title: '🚀 Activar Boost x2',
        subtitle: 'Mira un anuncio para activar el boost de minería',
        reward: 'x2 por 30 minutos + 15 PTS',
        info: 'Tu minería continuará normalmente si no aceptas',
        onAccept: async () => {
            closeAdConsentModal();
            
            await showOnClickaAd({
                taskType: 'boost_ad',
                onComplete: async () => {
                    // Activar boost en backend
                    const response = await fetch(`/api/boost/onclicka/activate?user_id=${userId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        showPtsToast(`🚀 ${data.message}`, 'success');
                        hapticFeedback('success');
                        updatePtsUI();
                        updateBoostIndicator();
                    } else {
                        showPtsToast(data.message || 'Error', 'error');
                    }
                },
                onError: (msg) => showPtsToast(msg, 'error'),
                onSkip: () => showPtsToast('Boost cancelado', 'info')
            });
        }
    });
}

// ============================================
// COMPONENTES UI
// ============================================

/**
 * Crear e insertar modal de consentimiento
 */
function createAdConsentModal() {
    if (document.getElementById('ad-consent-modal')) return;
    
    const modalHTML = `
        <div id="ad-consent-modal" class="pts-modal-overlay" style="display:none;">
            <div class="pts-modal-container">
                <div class="pts-modal-header">
                    <div class="pts-modal-icon" id="consent-modal-icon">📺</div>
                    <h2 class="pts-modal-title" id="consent-modal-title">Ver Anuncio</h2>
                    <p class="pts-modal-subtitle" id="consent-modal-subtitle">Mira un video para ganar recompensas</p>
                </div>
                <div class="pts-modal-body">
                    <div class="pts-reward-preview" id="consent-modal-reward">
                        <span class="pts-reward-label">Recompensa:</span>
                        <span class="pts-reward-value">+5 PTS</span>
                    </div>
                    <div class="pts-info-box" id="consent-modal-info">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M12 16v-4"/><path d="M12 8h.01"/>
                        </svg>
                        <span>Ver el anuncio es opcional. Si no lo hacés, no pasa nada.</span>
                    </div>
                </div>
                <div class="pts-modal-footer">
                    <button class="pts-btn pts-btn-primary" id="consent-accept-btn">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polygon points="5 3 19 12 5 21 5 3"/>
                        </svg>
                        <span>Ver Anuncio</span>
                    </button>
                    <button class="pts-btn pts-btn-secondary" onclick="closeAdConsentModal()">
                        <span>Ahora no</span>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

/**
 * Mostrar modal de consentimiento
 */
function showAdConsentModal(options = {}) {
    createAdConsentModal();
    
    const modal = document.getElementById('ad-consent-modal');
    const title = document.getElementById('consent-modal-title');
    const subtitle = document.getElementById('consent-modal-subtitle');
    const reward = document.getElementById('consent-modal-reward');
    const info = document.getElementById('consent-modal-info');
    const acceptBtn = document.getElementById('consent-accept-btn');
    
    if (options.title) title.textContent = options.title;
    if (options.subtitle) subtitle.textContent = options.subtitle;
    if (options.reward) {
        reward.querySelector('.pts-reward-value').textContent = options.reward;
    }
    if (options.info) {
        info.querySelector('span').textContent = options.info;
    }
    
    // Configurar callback de aceptar
    acceptBtn.onclick = options.onAccept || (() => closeAdConsentModal());
    
    modal.style.display = 'flex';
    hapticFeedback('light');
}

/**
 * Cerrar modal de consentimiento
 */
function closeAdConsentModal() {
    const modal = document.getElementById('ad-consent-modal');
    if (modal) modal.style.display = 'none';
}

/**
 * Actualizar UI de PTS
 */
async function updatePtsUI() {
    const status = await getPtsStatus();
    if (!status?.success) return;
    
    // Balance de PTS
    const ptsBalance = document.getElementById('pts-balance');
    if (ptsBalance) {
        ptsBalance.textContent = status.pts.balance;
    }
    
    // PTS de hoy
    const ptsToday = document.getElementById('pts-today');
    if (ptsToday) {
        ptsToday.textContent = `${status.pts.today}/${status.daily_ad_limit * 5}`;
    }
    
    // Progreso de tarea de 5 anuncios
    const adProgress = document.getElementById('ad-task-progress');
    if (adProgress && status.ad_task) {
        adProgress.textContent = `${status.ad_task.ads_watched}/${status.ad_task.ads_target}`;
        
        const progressBar = document.getElementById('ad-task-progress-bar');
        if (progressBar) {
            const percent = (status.ad_task.ads_watched / status.ad_task.ads_target) * 100;
            progressBar.style.width = `${Math.min(percent, 100)}%`;
        }
    }
    
    // Anuncios disponibles hoy
    const adsRemaining = document.getElementById('ads-remaining');
    if (adsRemaining) {
        const remaining = Math.max(0, status.daily_ad_limit - status.ads_watched_today);
        adsRemaining.textContent = remaining;
    }
    
    // Botón de check-in
    updateCheckinButton(status.checkin);
    
    // Ranking del usuario
    if (status.rank) {
        const rankDisplay = document.getElementById('user-rank');
        if (rankDisplay) {
            rankDisplay.textContent = status.rank.rank > 0 ? `#${status.rank.rank}` : '-';
        }
    }
}

/**
 * Actualizar botón de check-in
 */
function updateCheckinButton(checkinStatus = null) {
    const btn = document.getElementById('checkin-btn');
    const doubleBtn = document.getElementById('checkin-double-btn');
    
    if (!btn) return;
    
    if (checkinStatus) {
        if (checkinStatus.done_today) {
            btn.disabled = true;
            btn.innerHTML = `<span>✅ Check-in hecho</span>`;
            btn.classList.add('completed');
            
            // Mostrar opción de duplicar si aplica
            if (doubleBtn) {
                if (checkinStatus.can_double) {
                    doubleBtn.style.display = 'flex';
                } else {
                    doubleBtn.style.display = 'none';
                }
            }
        } else {
            btn.disabled = false;
            btn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                <span>Check-in (+${checkinStatus.base_reward} PTS)</span>
            `;
            btn.classList.remove('completed');
            
            if (doubleBtn) doubleBtn.style.display = 'none';
        }
    }
}

/**
 * Actualizar indicador de boost
 */
async function updateBoostIndicator() {
    const userId = getUserId();
    if (!userId) return;
    
    try {
        const response = await fetch(`/api/boost/onclicka/status?user_id=${userId}`);
        const status = await response.json();
        
        const indicator = document.getElementById('boost-indicator');
        const boostBtn = document.getElementById('boost-btn');
        
        if (status.has_active_boost) {
            if (indicator) {
                const mins = Math.floor(status.boost_remaining_seconds / 60);
                const secs = status.boost_remaining_seconds % 60;
                indicator.innerHTML = `⚡ x${status.multiplier} - ${mins}:${secs.toString().padStart(2, '0')}`;
                indicator.style.display = 'inline-flex';
            }
            if (boostBtn) {
                boostBtn.disabled = true;
                boostBtn.innerHTML = '<span>Boost Activo</span>';
            }
        } else {
            if (indicator) indicator.style.display = 'none';
            if (boostBtn) {
                boostBtn.disabled = !status.can_activate;
                if (status.can_activate) {
                    boostBtn.innerHTML = `
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                        </svg>
                        <span>Activar Boost x2</span>
                    `;
                } else {
                    boostBtn.innerHTML = `<span>${status.reason || 'No disponible'}</span>`;
                }
            }
        }
    } catch (error) {
        console.error('[Boost] Error:', error);
    }
}

/**
 * Actualizar ranking
 */
async function updateRankingUI() {
    const data = await getPtsRanking();
    if (!data?.success) return;
    
    const container = document.getElementById('pts-ranking-list');
    if (!container) return;
    
    if (!data.ranking || data.ranking.length === 0) {
        container.innerHTML = '<div class="pts-empty">Sin datos de ranking aún</div>';
        return;
    }
    
    let html = '';
    data.ranking.forEach(entry => {
        const medals = ['🥇', '🥈', '🥉'];
        const medal = medals[entry.rank - 1] || `#${entry.rank}`;
        const qualifyClass = entry.qualifies ? 'qualifies' : '';
        
        html += `
            <div class="pts-ranking-item ${qualifyClass}">
                <div class="pts-rank-medal">${medal}</div>
                <div class="pts-rank-info">
                    <span class="pts-rank-name">${entry.first_name || entry.username}</span>
                    <span class="pts-rank-pts">${entry.pts} PTS</span>
                </div>
                <div class="pts-rank-reward">
                    ${entry.qualifies ? `${entry.reward_doge} DOGE` : '-'}
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// ============================================
// UTILIDADES
// ============================================

function getUserId() {
    const urlParams = new URLSearchParams(window.location.search);
    let userId = urlParams.get('user_id');
    if (!userId && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        userId = window.Telegram.WebApp.initDataUnsafe.user.id;
    }
    return userId;
}

function hapticFeedback(type) {
    if (window.Telegram?.WebApp?.HapticFeedback) {
        if (type === 'success' || type === 'error' || type === 'warning') {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
        } else {
            window.Telegram.WebApp.HapticFeedback.impactOccurred(type);
        }
    }
}

function showPtsToast(message, type = 'info') {
    if (window.showToast) {
        window.showToast(message, type);
        return;
    }
    
    const colors = {
        success: '#00d4ff',
        error: '#ff4757',
        warning: '#ffc107',
        info: '#00d4ff'
    };
    
    const existingToast = document.querySelector('.pts-toast');
    if (existingToast) existingToast.remove();
    
    const toast = document.createElement('div');
    toast.className = 'pts-toast';
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        padding: 14px 24px;
        background: rgba(26, 26, 46, 0.95);
        border: 1px solid ${colors[type]};
        border-radius: 12px;
        color: white;
        font-size: 0.9rem;
        font-weight: 500;
        z-index: 10001;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        animation: ptsToastIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'ptsToastOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================
// ESTILOS
// ============================================

function injectPtsStyles() {
    if (document.getElementById('pts-system-styles')) return;
    
    const styles = document.createElement('style');
    styles.id = 'pts-system-styles';
    styles.textContent = `
        /* Animaciones */
        @keyframes ptsToastIn {
            from { opacity: 0; transform: translate(-50%, 20px); }
            to { opacity: 1; transform: translate(-50%, 0); }
        }
        @keyframes ptsToastOut {
            from { opacity: 1; transform: translate(-50%, 0); }
            to { opacity: 0; transform: translate(-50%, -20px); }
        }
        @keyframes ptsPulse {
            0%, 100% { box-shadow: 0 0 10px rgba(0, 245, 255, 0.3); }
            50% { box-shadow: 0 0 20px rgba(0, 245, 255, 0.6); }
        }
        @keyframes ptsSlideUp {
            from { transform: translateY(30px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        /* Modal */
        .pts-modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(10px);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .pts-modal-container {
            background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
            border: 1px solid rgba(0, 245, 255, 0.3);
            border-radius: 20px;
            max-width: 380px;
            width: 100%;
            overflow: hidden;
            animation: ptsSlideUp 0.4s ease;
        }
        
        .pts-modal-header {
            background: linear-gradient(135deg, rgba(0, 245, 255, 0.1) 0%, rgba(232, 82, 170, 0.1) 100%);
            padding: 25px 20px;
            text-align: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .pts-modal-icon {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        
        .pts-modal-title {
            font-size: 1.3rem;
            font-weight: 700;
            color: #ffffff;
            margin: 0 0 8px;
        }
        
        .pts-modal-subtitle {
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.7);
            margin: 0;
        }
        
        .pts-modal-body {
            padding: 20px;
        }
        
        .pts-reward-preview {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: rgba(0, 245, 255, 0.1);
            border: 1px solid rgba(0, 245, 255, 0.3);
            border-radius: 12px;
            margin-bottom: 15px;
        }
        
        .pts-reward-label {
            color: rgba(255, 255, 255, 0.7);
        }
        
        .pts-reward-value {
            color: #00d4ff;
            font-weight: 700;
            font-size: 1.1rem;
        }
        
        .pts-info-box {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 12px;
            background: rgba(255, 193, 7, 0.1);
            border: 1px solid rgba(255, 193, 7, 0.3);
            border-radius: 10px;
            font-size: 0.8rem;
            color: rgba(255, 255, 255, 0.8);
        }
        
        .pts-info-box svg {
            flex-shrink: 0;
            color: #ffc107;
        }
        
        .pts-modal-footer {
            padding: 0 20px 20px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        /* Botones */
        .pts-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 14px 20px;
            border: none;
            border-radius: 12px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
        }
        
        .pts-btn-primary {
            background: linear-gradient(135deg, #00d4ff 0%, #00c8ff 50%, #3b82f6 100%);
            color: #000;
            box-shadow: 0 6px 20px rgba(0, 245, 255, 0.4);
        }
        
        .pts-btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 245, 255, 0.5);
        }
        
        .pts-btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .pts-btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .pts-btn-secondary:hover {
            background: rgba(255, 255, 255, 0.15);
            color: #ffffff;
        }
        
        /* Spinner */
        .pts-spinner {
            width: 18px;
            height: 18px;
            border: 2px solid rgba(0, 0, 0, 0.2);
            border-top-color: #000;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
            display: inline-block;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Tarjetas de tareas */
        .pts-task-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 12px;
            transition: all 0.3s ease;
        }
        
        .pts-task-card:hover {
            border-color: rgba(0, 245, 255, 0.3);
        }
        
        .pts-task-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .pts-task-icon {
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, rgba(0, 245, 255, 0.2) 0%, rgba(232, 82, 170, 0.2) 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.3rem;
        }
        
        .pts-task-info {
            flex: 1;
        }
        
        .pts-task-title {
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 2px;
        }
        
        .pts-task-reward {
            font-size: 0.85rem;
            color: #00d4ff;
        }
        
        .pts-task-progress {
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        
        .pts-task-progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #00d4ff, #3b82f6);
            border-radius: 3px;
            transition: width 0.3s ease;
        }
        
        .pts-task-btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, rgba(0, 245, 255, 0.15) 0%, rgba(232, 82, 170, 0.15) 100%);
            border: 1px solid rgba(0, 245, 255, 0.3);
            border-radius: 10px;
            color: #00d4ff;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .pts-task-btn:hover:not(:disabled) {
            background: linear-gradient(135deg, rgba(0, 245, 255, 0.25) 0%, rgba(232, 82, 170, 0.25) 100%);
        }
        
        .pts-task-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .pts-task-btn.completed {
            background: rgba(0, 200, 150, 0.2);
            border-color: rgba(0, 200, 150, 0.4);
            color: #00c896;
        }
        
        /* Ranking */
        .pts-ranking-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            margin-bottom: 8px;
        }
        
        .pts-ranking-item.qualifies {
            border: 1px solid rgba(0, 245, 255, 0.3);
        }
        
        .pts-rank-medal {
            font-size: 1.5rem;
            width: 36px;
            text-align: center;
        }
        
        .pts-rank-info {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .pts-rank-name {
            font-weight: 600;
            color: #ffffff;
        }
        
        .pts-rank-pts {
            font-size: 0.85rem;
            color: #00d4ff;
        }
        
        .pts-rank-reward {
            font-weight: 600;
            color: #ffd700;
        }
        
        /* Badge de boost */
        .pts-boost-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: linear-gradient(135deg, rgba(0, 245, 255, 0.2) 0%, rgba(232, 82, 170, 0.2) 100%);
            border: 1px solid rgba(0, 245, 255, 0.4);
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            color: #00d4ff;
            animation: ptsPulse 2s ease infinite;
        }
        
        /* Balance de PTS */
        .pts-balance-card {
            background: linear-gradient(135deg, rgba(0, 245, 255, 0.1) 0%, rgba(232, 82, 170, 0.1) 100%);
            border: 1px solid rgba(0, 245, 255, 0.3);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
        }
        
        .pts-balance-label {
            font-size: 0.85rem;
            color: rgba(255, 255, 255, 0.7);
            margin-bottom: 5px;
        }
        
        .pts-balance-value {
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #00d4ff, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .pts-balance-suffix {
            font-size: 1rem;
            color: rgba(255, 255, 255, 0.7);
            margin-left: 5px;
        }
        
        .pts-empty {
            text-align: center;
            padding: 30px;
            color: rgba(255, 255, 255, 0.5);
        }
    `;
    
    document.head.appendChild(styles);
}

// ============================================
// INICIALIZACIÓN
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    injectPtsStyles();
    loadOnClickaSDK().catch(() => {});
    
    // Actualizar UI inicial
    updatePtsUI();
    updateBoostIndicator();
    updateRankingUI();
    
    // Actualizar periódicamente
    setInterval(updatePtsUI, 30000);
    setInterval(updateBoostIndicator, 10000);
    
    console.log('[PTS System] Inicializado');
});

// Exportar funciones globales
window.doCheckin = doCheckin;
window.doubleCheckinReward = doubleCheckinReward;
window.watchAdForPts = watchAdForPts;
window.activateMiningBoost = activateMiningBoost;
window.updatePtsUI = updatePtsUI;
window.showAdConsentModal = showAdConsentModal;
window.closeAdConsentModal = closeAdConsentModal;
