/**
 * adsgram_boost.js - Sistema de Boost de Minería con AdsGram
 * ===========================================================
 * - Modal de consentimiento obligatorio
 * - Integración con AdsGram Rewarded Video
 * - NO paga dinero directo, solo activa boost x2
 * - Block ID: 20479
 */

// ============================================
// CONFIGURACIÓN
// ============================================
const ADSGRAM_BOOST_CONFIG = {
    blockId: 20479,
    boostMultiplier: 2,
    boostDurationMinutes: 60
};

// Estado global
let adsgramController = null;
let isAdsgramReady = false;
let boostStatusInterval = null;

// ============================================
// INICIALIZACIÓN DE ADSGRAM
// ============================================

/**
 * Inicializar AdsGram SDK
 * IMPORTANTE: Solo cargar cuando el usuario acepte ver el anuncio
 */
function initAdsgram() {
    return new Promise((resolve, reject) => {
        // Verificar si ya está cargado
        if (window.Adsgram && isAdsgramReady) {
            resolve(adsgramController);
            return;
        }

        // Cargar script de AdsGram si no está presente
        if (!window.Adsgram) {
            const script = document.createElement('script');
            script.src = 'https://sad.adsgram.ai/js/sad.min.js';
            script.async = true;
            
            script.onload = () => {
                try {
                    adsgramController = window.Adsgram.init({ 
                        blockId: String(ADSGRAM_BOOST_CONFIG.blockId) 
                    });
                    isAdsgramReady = true;
                    console.log('[AdsGram Boost] SDK inicializado correctamente');
                    resolve(adsgramController);
                } catch (error) {
                    console.error('[AdsGram Boost] Error inicializando SDK:', error);
                    reject(error);
                }
            };
            
            script.onerror = () => {
                console.error('[AdsGram Boost] Error cargando SDK');
                reject(new Error('Failed to load AdsGram SDK'));
            };
            
            document.head.appendChild(script);
        } else {
            try {
                adsgramController = window.Adsgram.init({ 
                    blockId: String(ADSGRAM_BOOST_CONFIG.blockId) 
                });
                isAdsgramReady = true;
                resolve(adsgramController);
            } catch (error) {
                reject(error);
            }
        }
    });
}

// ============================================
// MODAL DE CONSENTIMIENTO
// ============================================

/**
 * Crear e insertar el modal de consentimiento en el DOM
 */
function createBoostConsentModal() {
    // Verificar si ya existe
    if (document.getElementById('boost-consent-modal')) {
        return;
    }
    
    // Obtener traducciones
    const boostTitle = window.t ? window.t('boost_modal_title') : '🚀 Activar Boost x2 por 30 minutos';
    const boostSubtitle = window.t ? window.t('boost_modal_subtitle') : 'Para activar el boost necesitás ver un anuncio en video.';
    const boostMultiplier = window.t ? window.t('boost_multiplier') : 'Multiplicador:';
    const boostDuration = window.t ? window.t('boost_duration') : 'Duración:';
    const boostMinutes = window.t ? window.t('boost_30_minutes') : '30 minutos';
    const boostPtsReward = window.t ? window.t('boost_pts_reward') : 'Bonus PTS:';
    const boostDisclaimer = window.t ? window.t('boost_disclaimer') : 'Ver el anuncio es opcional. Si no lo hacés, tu minería continuará normalmente.';
    const boostActivateBtn = window.t ? window.t('boost_activate_btn') : 'Activar Boost';
    const boostCancelBtn = window.t ? window.t('boost_cancel_btn') : 'Ahora no';
    const boostLoading = window.t ? window.t('boost_loading') : 'Cargando anuncio...';
    
    const modalHTML = `
        <div id="boost-consent-modal" class="boost-modal-overlay" style="display:none;">
            <div class="boost-modal-container">
                <!-- Header -->
                <div class="boost-modal-header">
                    <div class="boost-modal-icon">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                        </svg>
                    </div>
                    <h2 class="boost-modal-title">${boostTitle}</h2>
                    <p class="boost-modal-subtitle">${boostSubtitle}</p>
                </div>
                
                <!-- Body -->
                <div class="boost-modal-body">
                    <div class="boost-info-card">
                        <div class="boost-info-row">
                            <span class="boost-info-label">${boostMultiplier}</span>
                            <span class="boost-info-value">x2</span>
                        </div>
                        <div class="boost-info-row">
                            <span class="boost-info-label">${boostDuration}</span>
                            <span class="boost-info-value">${boostMinutes}</span>
                        </div>
                        <div class="boost-info-row" style="background: linear-gradient(135deg, rgba(0, 245, 255, 0.15) 0%, rgba(0, 82, 204, 0.15) 100%); border-radius: 8px; padding: 8px 12px; margin-top: 8px;">
                            <span class="boost-info-label">${boostPtsReward}</span>
                            <span class="boost-info-value" style="color: #00d4ff; font-weight: 700;">+15 PTS</span>
                        </div>
                    </div>
                    
                    <div class="boost-disclaimer">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M12 16v-4"/>
                            <path d="M12 8h.01"/>
                        </svg>
                        <span>${boostDisclaimer}</span>
                    </div>
                </div>
                
                <!-- Footer / Buttons -->
                <div class="boost-modal-footer">
                    <button id="boost-accept-btn" class="boost-btn boost-btn-primary" onclick="acceptAndShowAd()">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                        </svg>
                        <span>${boostActivateBtn}</span>
                    </button>
                    <button id="boost-cancel-btn" class="boost-btn boost-btn-secondary" onclick="closeBoostModal()">
                        <span>${boostCancelBtn}</span>
                    </button>
                </div>
                
                <!-- Loading state -->
                <div id="boost-loading" class="boost-loading" style="display:none;">
                    <div class="boost-spinner"></div>
                    <span>${boostLoading}</span>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

/**
 * Crear estilos del modal
 */
function createBoostModalStyles() {
    if (document.getElementById('boost-modal-styles')) {
        return;
    }
    
    const styles = `
        <style id="boost-modal-styles">
            /* Overlay */
            .boost-modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.85);
                backdrop-filter: blur(10px);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                animation: boostFadeIn 0.3s ease;
            }
            
            @keyframes boostFadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            /* Container */
            .boost-modal-container {
                background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
                border: 1px solid rgba(0, 245, 255, 0.3);
                border-radius: 20px;
                max-width: 380px;
                width: 100%;
                overflow: hidden;
                box-shadow: 0 25px 80px rgba(0, 0, 0, 0.6),
                            0 0 40px rgba(0, 245, 255, 0.1);
                animation: boostSlideUp 0.4s ease;
                position: relative;
            }
            
            @keyframes boostSlideUp {
                from { 
                    transform: translateY(30px); 
                    opacity: 0; 
                }
                to { 
                    transform: translateY(0); 
                    opacity: 1; 
                }
            }
            
            /* Header */
            .boost-modal-header {
                background: linear-gradient(135deg, rgba(0, 245, 255, 0.1) 0%, rgba(232, 82, 170, 0.1) 100%);
                padding: 30px 25px 25px;
                text-align: center;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .boost-modal-icon {
                width: 70px;
                height: 70px;
                margin: 0 auto 15px;
                background: linear-gradient(135deg, #00d4ff 0%, #3b82f6 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 10px 30px rgba(0, 245, 255, 0.4);
            }
            
            .boost-modal-icon svg {
                color: white;
            }
            
            .boost-modal-title {
                font-size: 1.4rem;
                font-weight: 700;
                color: #ffffff;
                margin: 0 0 8px;
            }
            
            .boost-modal-subtitle {
                font-size: 0.95rem;
                color: rgba(255, 255, 255, 0.7);
                margin: 0;
                line-height: 1.5;
            }
            
            /* Body */
            .boost-modal-body {
                padding: 25px;
            }
            
            .boost-info-card {
                background: rgba(0, 245, 255, 0.08);
                border: 1px solid rgba(0, 245, 255, 0.2);
                border-radius: 12px;
                padding: 15px 20px;
                margin-bottom: 20px;
            }
            
            .boost-info-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 0;
            }
            
            .boost-info-row:not(:last-child) {
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .boost-info-label {
                color: rgba(255, 255, 255, 0.7);
                font-size: 0.9rem;
            }
            
            .boost-info-value {
                color: #00d4ff;
                font-weight: 600;
                font-size: 1rem;
            }
            
            .boost-disclaimer {
                display: flex;
                align-items: flex-start;
                gap: 10px;
                padding: 12px 15px;
                background: rgba(255, 193, 7, 0.1);
                border: 1px solid rgba(255, 193, 7, 0.3);
                border-radius: 10px;
                font-size: 0.8rem;
                color: rgba(255, 255, 255, 0.8);
                line-height: 1.5;
            }
            
            .boost-disclaimer svg {
                flex-shrink: 0;
                color: #ffc107;
                margin-top: 2px;
            }
            
            /* Footer / Buttons */
            .boost-modal-footer {
                padding: 0 25px 25px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            
            .boost-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                padding: 16px 24px;
                border: none;
                border-radius: 12px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                width: 100%;
            }
            
            .boost-btn-primary {
                background: linear-gradient(135deg, #00d4ff 0%, #00c8ff 50%, #3b82f6 100%);
                color: #000;
                box-shadow: 0 8px 25px rgba(0, 245, 255, 0.4);
            }
            
            .boost-btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 35px rgba(0, 245, 255, 0.5);
            }
            
            .boost-btn-primary:active {
                transform: translateY(0);
            }
            
            .boost-btn-primary:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            
            .boost-btn-secondary {
                background: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            
            .boost-btn-secondary:hover {
                background: rgba(255, 255, 255, 0.15);
                color: #ffffff;
            }
            
            /* Loading */
            .boost-loading {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(26, 26, 46, 0.95);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 15px;
                color: #ffffff;
                font-size: 0.95rem;
            }
            
            .boost-spinner {
                width: 40px;
                height: 40px;
                border: 3px solid rgba(0, 245, 255, 0.2);
                border-top-color: #00d4ff;
                border-radius: 50%;
                animation: boostSpin 0.8s linear infinite;
            }
            
            @keyframes boostSpin {
                to { transform: rotate(360deg); }
            }
            
            /* Boost Active Indicator */
            .boost-active-badge {
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
                animation: boostPulse 2s ease infinite;
            }
            
            @keyframes boostPulse {
                0%, 100% { box-shadow: 0 0 10px rgba(0, 245, 255, 0.3); }
                50% { box-shadow: 0 0 20px rgba(0, 245, 255, 0.6); }
            }
            
            /* Boost Button (para agregar al dashboard) */
            .boost-trigger-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                padding: 12px 20px;
                background: linear-gradient(135deg, rgba(0, 245, 255, 0.15) 0%, rgba(232, 82, 170, 0.15) 100%);
                border: 1px solid rgba(0, 245, 255, 0.3);
                border-radius: 12px;
                color: #00d4ff;
                font-weight: 600;
                font-size: 0.9rem;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            .boost-trigger-btn:hover {
                background: linear-gradient(135deg, rgba(0, 245, 255, 0.25) 0%, rgba(232, 82, 170, 0.25) 100%);
                box-shadow: 0 5px 20px rgba(0, 245, 255, 0.3);
            }
            
            .boost-trigger-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            
            .boost-trigger-btn svg {
                width: 18px;
                height: 18px;
            }
        </style>
    `;
    
    document.head.insertAdjacentHTML('beforeend', styles);
}

// ============================================
// FUNCIONES PRINCIPALES
// ============================================

/**
 * Abrir modal de consentimiento para boost
 */
async function openBoostModal() {
    // Crear modal y estilos si no existen
    createBoostModalStyles();
    createBoostConsentModal();
    
    // Verificar si puede activar boost antes de mostrar modal
    const userId = getUserId();
    if (!userId) {
        showBoostToast('Error: Usuario no identificado', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/boost/can-activate?user_id=${userId}`);
        const data = await response.json();
        
        if (!data.can_activate) {
            showBoostToast(data.reason || 'No puedes activar boost ahora', 'warning');
            return;
        }
        
        // Mostrar modal
        const modal = document.getElementById('boost-consent-modal');
        modal.style.display = 'flex';
        
        // Haptic feedback
        if (window.Telegram?.WebApp?.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        }
        
    } catch (error) {
        console.error('[AdsGram Boost] Error verificando estado:', error);
        showBoostToast('Error de conexión', 'error');
    }
}

/**
 * Cerrar modal de consentimiento
 */
function closeBoostModal() {
    const modal = document.getElementById('boost-consent-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    
    // Ocultar loading
    const loading = document.getElementById('boost-loading');
    if (loading) {
        loading.style.display = 'none';
    }
    
    // Habilitar botones
    const acceptBtn = document.getElementById('boost-accept-btn');
    const cancelBtn = document.getElementById('boost-cancel-btn');
    if (acceptBtn) acceptBtn.disabled = false;
    if (cancelBtn) cancelBtn.disabled = false;
    
    // Haptic feedback
    if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
    }
}

/**
 * Usuario aceptó: mostrar anuncio de AdsGram
 */
async function acceptAndShowAd() {
    const acceptBtn = document.getElementById('boost-accept-btn');
    const cancelBtn = document.getElementById('boost-cancel-btn');
    const loading = document.getElementById('boost-loading');
    
    // Deshabilitar botones y mostrar loading
    if (acceptBtn) acceptBtn.disabled = true;
    if (cancelBtn) cancelBtn.disabled = true;
    if (loading) loading.style.display = 'flex';
    
    try {
        // Inicializar AdsGram
        const controller = await initAdsgram();
        
        // Mostrar anuncio
        const result = await controller.show();
        
        console.log('[AdsGram Boost] Resultado del anuncio:', result);
        
        // El anuncio se completó correctamente
        // AdsGram llamará automáticamente al backend (/adsgram/reward)
        // Pero también actualizamos la UI
        
        if (result.done) {
            // Éxito - el anuncio fue visto
            // AdsGram puede haber llamado automáticamente a /adsgram/reward
            // Pero por seguridad, también intentamos activar desde aquí
            try {
                const userId = getUserId();
                const activateResponse = await fetch(`/api/boost/activate?user_id=${userId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                const activateData = await activateResponse.json();
                
                // Cerrar modal primero
                closeBoostModal();
                
                if (activateData.success) {
                    // Boost activado exitosamente
                    const ptsMsg = activateData.boost?.pts_earned ? ` +${activateData.boost.pts_earned} PTS` : ' +15 PTS';
                    showBoostToast(`🚀 ¡Boost x2 activado por 30 minutos!${ptsMsg}`, 'success');
                } else if (activateData.error && activateData.error.includes('activo')) {
                    // Ya hay boost activo (AdsGram lo activó primero) - mostrar éxito igual
                    showBoostToast('🚀 ¡Boost x2 activado por 30 minutos! +15 PTS', 'success');
                } else {
                    // Otro error
                    showBoostToast(activateData.error || 'Boost activado', 'info');
                }
            } catch (activateError) {
                console.error('[AdsGram Boost] Error activando boost:', activateError);
                closeBoostModal();
                // Asumir que AdsGram ya lo activó
                showBoostToast('🚀 ¡Boost x2 activado por 30 minutos! +15 PTS', 'success');
            }
            
            // Actualizar UI del boost
            setTimeout(() => {
                updateBoostUI();
            }, 1000);
            
            // Haptic feedback de éxito
            if (window.Telegram?.WebApp?.HapticFeedback) {
                window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
            }
        }
        
    } catch (error) {
        console.error('[AdsGram Boost] Error mostrando anuncio:', error);
        
        // Verificar si fue cancelado por el usuario
        if (error.message?.includes('user') || error.description?.includes('user')) {
            showBoostToast('Anuncio cancelado', 'info');
        } else {
            showBoostToast('Error al cargar anuncio. Intenta de nuevo.', 'error');
        }
        
        // Haptic feedback de error
        if (window.Telegram?.WebApp?.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('error');
        }
    } finally {
        // Restaurar estado
        if (loading) loading.style.display = 'none';
        if (acceptBtn) acceptBtn.disabled = false;
        if (cancelBtn) cancelBtn.disabled = false;
        closeBoostModal();
    }
}

/**
 * Obtener estado actual del boost
 */
async function getBoostStatus() {
    const userId = getUserId();
    if (!userId) return null;
    
    try {
        const response = await fetch(`/api/boost/status?user_id=${userId}`);
        return await response.json();
    } catch (error) {
        console.error('[AdsGram Boost] Error obteniendo estado:', error);
        return null;
    }
}

/**
 * Actualizar UI según estado del boost
 */
async function updateBoostUI() {
    const status = await getBoostStatus();
    if (!status?.success) return;
    
    // Actualizar indicador de boost activo
    const boostIndicator = document.getElementById('boost-active-indicator');
    const boostButton = document.getElementById('boost-trigger-button');
    
    if (status.has_active_boost) {
        // Mostrar indicador de boost activo
        if (boostIndicator) {
            const minutes = Math.floor(status.boost_remaining_seconds / 60);
            const seconds = status.boost_remaining_seconds % 60;
            boostIndicator.innerHTML = `
                <span class="boost-active-badge">
                    ⚡ x${status.multiplier} Boost activo - ${minutes}:${seconds.toString().padStart(2, '0')}
                </span>
            `;
            boostIndicator.style.display = 'block';
        }
        
        // Deshabilitar botón de boost
        if (boostButton) {
            boostButton.disabled = true;
            boostButton.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                </svg>
                <span>Boost Activo</span>
            `;
        }
    } else {
        // Ocultar indicador
        if (boostIndicator) {
            boostIndicator.style.display = 'none';
        }
        
        // Habilitar/deshabilitar botón según cooldown y límites
        if (boostButton) {
            boostButton.disabled = !status.can_activate;
            
            if (status.cooldown_remaining_seconds > 0) {
                const mins = Math.floor(status.cooldown_remaining_seconds / 60);
                const secs = status.cooldown_remaining_seconds % 60;
                boostButton.innerHTML = `
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 6v6l4 2"/>
                    </svg>
                    <span>Espera ${mins}:${secs.toString().padStart(2, '0')}</span>
                `;
            } else if (status.daily_boosts_used >= status.daily_boosts_limit) {
                boostButton.innerHTML = `
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                    </svg>
                    <span>Límite diario (${status.daily_boosts_used}/${status.daily_boosts_limit})</span>
                `;
            } else {
                boostButton.innerHTML = `
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                    </svg>
                    <span>Activar Boost x2</span>
                `;
            }
        }
    }
}

/**
 * Iniciar actualización periódica del estado del boost
 */
function startBoostStatusUpdates() {
    // Actualizar inmediatamente
    updateBoostUI();
    
    // Actualizar cada 10 segundos
    if (boostStatusInterval) {
        clearInterval(boostStatusInterval);
    }
    boostStatusInterval = setInterval(updateBoostUI, 10000);
}

/**
 * Detener actualizaciones
 */
function stopBoostStatusUpdates() {
    if (boostStatusInterval) {
        clearInterval(boostStatusInterval);
        boostStatusInterval = null;
    }
}

// ============================================
// UTILIDADES
// ============================================

/**
 * Obtener user_id del contexto actual
 */
function getUserId() {
    // Intentar desde URL
    const urlParams = new URLSearchParams(window.location.search);
    let userId = urlParams.get('user_id');
    
    // Intentar desde Telegram WebApp
    if (!userId && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        userId = window.Telegram.WebApp.initDataUnsafe.user.id;
    }
    
    return userId;
}

/**
 * Mostrar notificación toast
 */
function showBoostToast(message, type = 'info') {
    // Usar función global si existe
    if (window.showToast) {
        window.showToast(message, type);
        return;
    }
    
    // Fallback: crear toast simple
    const existingToast = document.querySelector('.boost-toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const colors = {
        success: '#00d4ff',
        error: '#ff4757',
        warning: '#ffc107',
        info: '#00d4ff'
    };
    
    const toast = document.createElement('div');
    toast.className = 'boost-toast';
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
        animation: boostToastIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Auto-remove después de 3 segundos
    setTimeout(() => {
        toast.style.animation = 'boostToastOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Agregar animaciones para toast
const toastStyles = document.createElement('style');
toastStyles.textContent = `
    @keyframes boostToastIn {
        from { opacity: 0; transform: translate(-50%, 20px); }
        to { opacity: 1; transform: translate(-50%, 0); }
    }
    @keyframes boostToastOut {
        from { opacity: 1; transform: translate(-50%, 0); }
        to { opacity: 0; transform: translate(-50%, -20px); }
    }
`;
document.head.appendChild(toastStyles);

// ============================================
// INICIALIZACIÓN AUTOMÁTICA
// ============================================

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Crear estilos y modal
    createBoostModalStyles();
    createBoostConsentModal();
    
    // Iniciar actualizaciones de estado
    startBoostStatusUpdates();
    
    console.log('[AdsGram Boost] Sistema inicializado');
});

// Exportar funciones globales
window.openBoostModal = openBoostModal;
window.closeBoostModal = closeBoostModal;
window.acceptAndShowAd = acceptAndShowAd;
window.getBoostStatus = getBoostStatus;
window.updateBoostUI = updateBoostUI;
