/**
 * shrinkearn.js - Frontend para Sistema ShrinkEarn
 * =================================================
 * Maneja la UI de misiones ShrinkEarn en SALLY-E
 */

// Estado global de ShrinkEarn
window.ShrinkEarnState = {
    loaded: false,
    enabled: false,
    missions: [],
    dailyStats: null,
    activeMission: null,
    userId: null
};

/**
 * Inicializar sistema ShrinkEarn
 */
async function initShrinkEarn(userId) {
    if (!userId) {
        console.error('ShrinkEarn: userId required');
        return false;
    }
    
    ShrinkEarnState.userId = userId;
    
    try {
        const response = await fetch(`/shrinkearn/status?user_id=${userId}`);
        const data = await response.json();
        
        if (data.success) {
            ShrinkEarnState.loaded = true;
            ShrinkEarnState.enabled = data.enabled;
            ShrinkEarnState.missions = data.missions;
            ShrinkEarnState.dailyStats = data.daily_stats;
            
            console.log('✅ ShrinkEarn initialized:', data);
            return true;
        }
    } catch (error) {
        console.error('❌ ShrinkEarn init error:', error);
    }
    
    return false;
}

/**
 * Renderizar sección de misiones ShrinkEarn
 */
function renderShrinkEarnMissions(containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error('ShrinkEarn: container not found:', containerId);
        return;
    }
    
    if (!ShrinkEarnState.loaded) {
        container.innerHTML = `
            <div class="shrinkearn-loading">
                <div class="loading-spinner"></div>
                <p>Cargando misiones...</p>
            </div>
        `;
        return;
    }
    
    if (!ShrinkEarnState.enabled) {
        container.innerHTML = `
            <div class="shrinkearn-disabled">
                <span class="icon">🚧</span>
                <p>Las misiones de enlaces están temporalmente deshabilitadas.</p>
            </div>
        `;
        return;
    }
    
    const { missions, dailyStats } = ShrinkEarnState;
    const lang = window.currentLanguage || 'es';
    
    let html = `
        <!-- Header con estadísticas -->
        <div class="shrinkearn-header">
            <div class="shrinkearn-title">
                <span class="icon">🔗</span>
                <span>${lang === 'es' ? 'Tareas de Enlaces' : 'Link Tasks'}</span>
            </div>
            <div class="shrinkearn-stats">
                <div class="stat-item">
                    <span class="stat-value">${dailyStats.completed}</span>
                    <span class="stat-label">${lang === 'es' ? 'Completadas' : 'Completed'}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value">${dailyStats.remaining}</span>
                    <span class="stat-label">${lang === 'es' ? 'Restantes' : 'Remaining'}</span>
                </div>
                <div class="stat-item highlight">
                    <span class="stat-value">${dailyStats.earned_doge.toFixed(4)}</span>
                    <span class="stat-label">DOGE</span>
                </div>
            </div>
        </div>
        
        <!-- Lista de misiones -->
        <div class="shrinkearn-missions">
    `;
    
    missions.forEach(mission => {
        const name = lang === 'es' ? mission.name_es : mission.name;
        const desc = lang === 'es' ? mission.description_es : mission.description;
        const isAvailable = mission.available;
        const cooldown = mission.cooldown_remaining;
        
        html += `
            <div class="shrinkearn-mission ${!isAvailable ? 'disabled' : ''}" 
                 data-mission-id="${mission.id}"
                 onclick="${isAvailable ? `startShrinkEarnMission('${mission.id}')` : ''}">
                
                <div class="mission-icon">${mission.icon}</div>
                
                <div class="mission-info">
                    <div class="mission-name">${name}</div>
                    <div class="mission-desc">${desc}</div>
                </div>
                
                <div class="mission-reward">
                    <div class="reward-amount">+${mission.reward} DOGE</div>
                    ${mission.reward_pts > 0 ? `<div class="reward-pts">+${mission.reward_pts} PTS</div>` : ''}
                </div>
                
                <div class="mission-action">
                    ${isAvailable ? `
                        <button class="start-btn">
                            <span class="btn-icon">▶</span>
                        </button>
                    ` : cooldown > 0 ? `
                        <div class="cooldown-timer" data-seconds="${cooldown}">
                            <span class="cooldown-icon">⏱</span>
                            <span class="cooldown-time">${formatCooldown(cooldown)}</span>
                        </div>
                    ` : `
                        <div class="limit-reached">
                            <span>${lang === 'es' ? 'Límite' : 'Limit'}</span>
                        </div>
                    `}
                </div>
            </div>
        `;
    });
    
    html += `
        </div>
        
        <!-- Info adicional -->
        <div class="shrinkearn-info">
            <p>
                <span class="info-icon">ℹ️</span>
                ${lang === 'es' 
                    ? 'Completa los anuncios para recibir tu recompensa automáticamente.' 
                    : 'Complete the ads to receive your reward automatically.'}
            </p>
        </div>
    `;
    
    container.innerHTML = html;
    
    // Iniciar timers de cooldown
    startCooldownTimers();
}

/**
 * Formatear tiempo de cooldown
 */
function formatCooldown(seconds) {
    if (seconds < 60) {
        return `${seconds}s`;
    }
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Iniciar timers de cooldown
 */
function startCooldownTimers() {
    const timers = document.querySelectorAll('.cooldown-timer');
    
    timers.forEach(timer => {
        let seconds = parseInt(timer.dataset.seconds);
        
        const interval = setInterval(() => {
            seconds--;
            
            if (seconds <= 0) {
                clearInterval(interval);
                // Recargar misiones
                refreshShrinkEarnMissions();
                return;
            }
            
            const timeSpan = timer.querySelector('.cooldown-time');
            if (timeSpan) {
                timeSpan.textContent = formatCooldown(seconds);
            }
        }, 1000);
    });
}

/**
 * Refrescar lista de misiones
 */
async function refreshShrinkEarnMissions() {
    if (!ShrinkEarnState.userId) return;
    
    await initShrinkEarn(ShrinkEarnState.userId);
    
    // Re-renderizar si hay contenedor
    const container = document.getElementById('shrinkearn-container');
    if (container) {
        renderShrinkEarnMissions('shrinkearn-container');
    }
}

/**
 * Iniciar una misión ShrinkEarn
 */
async function startShrinkEarnMission(missionId) {
    if (!ShrinkEarnState.userId) {
        showToast('Error: Usuario no identificado', 'error');
        return;
    }
    
    // Prevenir doble click
    if (ShrinkEarnState.activeMission) {
        return;
    }
    
    ShrinkEarnState.activeMission = missionId;
    
    // Mostrar loading en el botón
    const missionEl = document.querySelector(`[data-mission-id="${missionId}"]`);
    if (missionEl) {
        const btn = missionEl.querySelector('.start-btn');
        if (btn) {
            btn.innerHTML = '<div class="btn-spinner"></div>';
            btn.disabled = true;
        }
    }
    
    try {
        const response = await fetch('/shrinkearn/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: ShrinkEarnState.userId,
                mission_type: missionId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Haptic feedback
            if (window.Telegram?.WebApp?.HapticFeedback) {
                window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
            }
            
            // Mostrar modal de confirmación
            showMissionStartModal(data);
            
            // Redirigir al enlace de ShrinkEarn
            setTimeout(() => {
                window.open(data.shortened_url, '_blank');
            }, 500);
            
        } else {
            // Error
            const errorMsg = data.error_es || data.error || 'Error al iniciar misión';
            showToast(errorMsg, 'error');
            
            // Si es cooldown, mostrar tiempo restante
            if (data.cooldown_remaining) {
                showToast(`Espera ${formatCooldown(data.cooldown_remaining)}`, 'warning');
            }
        }
        
    } catch (error) {
        console.error('Error starting mission:', error);
        showToast('Error de conexión', 'error');
    } finally {
        ShrinkEarnState.activeMission = null;
        
        // Restaurar botón
        if (missionEl) {
            const btn = missionEl.querySelector('.start-btn');
            if (btn) {
                btn.innerHTML = '<span class="btn-icon">▶</span>';
                btn.disabled = false;
            }
        }
        
        // Refrescar después de un delay
        setTimeout(refreshShrinkEarnMissions, 2000);
    }
}

/**
 * Mostrar modal de misión iniciada
 */
function showMissionStartModal(data) {
    const lang = window.currentLanguage || 'es';
    const mission = data.mission;
    
    const modalHtml = `
        <div class="shrinkearn-modal-overlay" id="missionModal" onclick="closeMissionModal(event)">
            <div class="shrinkearn-modal">
                <div class="modal-header">
                    <span class="modal-icon">${mission.icon}</span>
                    <h3>${lang === 'es' ? 'Misión Iniciada' : 'Mission Started'}</h3>
                </div>
                
                <div class="modal-body">
                    <p class="modal-mission-name">${lang === 'es' ? mission.name_es : mission.name}</p>
                    
                    <div class="modal-reward">
                        <span class="reward-label">${lang === 'es' ? 'Recompensa:' : 'Reward:'}</span>
                        <span class="reward-value">+${mission.reward} DOGE</span>
                        ${mission.reward_pts > 0 ? `<span class="reward-pts">+${mission.reward_pts} PTS</span>` : ''}
                    </div>
                    
                    <div class="modal-instructions">
                        <div class="instruction-step">
                            <span class="step-num">1</span>
                            <span>${lang === 'es' ? 'Se abrirá una nueva ventana' : 'A new window will open'}</span>
                        </div>
                        <div class="instruction-step">
                            <span class="step-num">2</span>
                            <span>${lang === 'es' ? 'Completa todos los anuncios' : 'Complete all the ads'}</span>
                        </div>
                        <div class="instruction-step">
                            <span class="step-num">3</span>
                            <span>${lang === 'es' ? 'Recibirás tu recompensa automáticamente' : 'You will receive your reward automatically'}</span>
                        </div>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button class="modal-btn" onclick="closeMissionModal()">
                        ${lang === 'es' ? 'Entendido' : 'Got it'}
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Agregar al DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Animar entrada
    setTimeout(() => {
        const modal = document.getElementById('missionModal');
        if (modal) {
            modal.classList.add('visible');
        }
    }, 10);
}

/**
 * Cerrar modal de misión
 */
function closeMissionModal(event) {
    if (event && event.target !== event.currentTarget) return;
    
    const modal = document.getElementById('missionModal');
    if (modal) {
        modal.classList.remove('visible');
        setTimeout(() => modal.remove(), 300);
    }
}

/**
 * Mostrar toast notification
 */
function showToast(message, type = 'info') {
    // Usar función existente si está disponible
    if (typeof window.showNotification === 'function') {
        window.showNotification(message, type);
        return;
    }
    
    // Fallback simple
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'error' ? '#ff3366' : type === 'success' ? '#00ff88' : '#00d4ff'};
        color: ${type === 'error' || type === 'warning' ? '#fff' : '#000'};
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        z-index: 9999;
        animation: toastIn 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// CSS para el sistema ShrinkEarn (inyectar si no existe)
const shrinkEarnStyles = `
<style id="shrinkearn-styles">
/* ShrinkEarn Container */
.shrinkearn-loading,
.shrinkearn-disabled {
    text-align: center;
    padding: 40px 20px;
    color: var(--text-secondary, rgba(255,255,255,0.6));
}

.shrinkearn-loading .loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(255,255,255,0.1);
    border-top-color: var(--neon-cyan, #00d4ff);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 16px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.shrinkearn-disabled .icon {
    font-size: 48px;
    display: block;
    margin-bottom: 12px;
}

/* Header */
.shrinkearn-header {
    padding: 16px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}

.shrinkearn-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
}

.shrinkearn-title .icon {
    font-size: 24px;
}

.shrinkearn-stats {
    display: flex;
    gap: 12px;
}

.shrinkearn-stats .stat-item {
    flex: 1;
    text-align: center;
    padding: 12px;
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
}

.shrinkearn-stats .stat-item.highlight {
    background: linear-gradient(135deg, rgba(255,204,0,0.15), rgba(255,204,0,0.05));
    border: 1px solid rgba(255,204,0,0.2);
}

.shrinkearn-stats .stat-value {
    display: block;
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary, #fff);
}

.shrinkearn-stats .stat-item.highlight .stat-value {
    color: var(--neon-yellow, #ffcc00);
}

.shrinkearn-stats .stat-label {
    display: block;
    font-size: 11px;
    color: var(--text-muted, rgba(255,255,255,0.5));
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
}

/* Missions List */
.shrinkearn-missions {
    padding: 12px;
}

.shrinkearn-mission {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    margin-bottom: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.shrinkearn-mission:hover:not(.disabled) {
    background: rgba(255,255,255,0.06);
    border-color: var(--neon-cyan, #00d4ff);
    transform: translateY(-2px);
}

.shrinkearn-mission.disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.shrinkearn-mission .mission-icon {
    font-size: 32px;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, rgba(0,245,255,0.1), rgba(168,85,247,0.1));
    border-radius: 12px;
}

.shrinkearn-mission .mission-info {
    flex: 1;
    min-width: 0;
}

.shrinkearn-mission .mission-name {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary, #fff);
    margin-bottom: 4px;
}

.shrinkearn-mission .mission-desc {
    font-size: 12px;
    color: var(--text-secondary, rgba(255,255,255,0.6));
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.shrinkearn-mission .mission-reward {
    text-align: right;
}

.shrinkearn-mission .reward-amount {
    font-size: 14px;
    font-weight: 700;
    color: var(--neon-yellow, #ffcc00);
}

.shrinkearn-mission .reward-pts {
    font-size: 11px;
    color: var(--neon-cyan, #00d4ff);
    margin-top: 2px;
}

.shrinkearn-mission .mission-action {
    min-width: 50px;
    text-align: center;
}

.shrinkearn-mission .start-btn {
    width: 44px;
    height: 44px;
    border: none;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--neon-cyan, #00d4ff), var(--neon-purple, #a855f7));
    color: white;
    font-size: 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
}

.shrinkearn-mission .start-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 4px 20px rgba(0,245,255,0.4);
}

.shrinkearn-mission .start-btn .btn-spinner {
    width: 20px;
    height: 20px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

.shrinkearn-mission .cooldown-timer {
    display: flex;
    flex-direction: column;
    align-items: center;
    font-size: 12px;
    color: var(--text-muted, rgba(255,255,255,0.5));
}

.shrinkearn-mission .cooldown-icon {
    font-size: 16px;
    margin-bottom: 2px;
}

.shrinkearn-mission .limit-reached {
    font-size: 11px;
    color: var(--neon-red, #ff3366);
    text-transform: uppercase;
}

/* Info Section */
.shrinkearn-info {
    padding: 12px 16px;
    margin: 8px 12px 12px;
    background: rgba(0,245,255,0.05);
    border: 1px solid rgba(0,245,255,0.1);
    border-radius: 12px;
}

.shrinkearn-info p {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary, rgba(255,255,255,0.6));
    line-height: 1.5;
    margin: 0;
}

.shrinkearn-info .info-icon {
    flex-shrink: 0;
}

/* Modal */
.shrinkearn-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.8);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
    padding: 20px;
}

.shrinkearn-modal-overlay.visible {
    opacity: 1;
    visibility: visible;
}

.shrinkearn-modal {
    background: var(--bg-card, #12121a);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 24px;
    width: 100%;
    max-width: 360px;
    transform: scale(0.9) translateY(20px);
    transition: transform 0.3s ease;
    overflow: hidden;
}

.shrinkearn-modal-overlay.visible .shrinkearn-modal {
    transform: scale(1) translateY(0);
}

.shrinkearn-modal .modal-header {
    text-align: center;
    padding: 24px 20px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}

.shrinkearn-modal .modal-icon {
    font-size: 48px;
    display: block;
    margin-bottom: 12px;
}

.shrinkearn-modal .modal-header h3 {
    font-size: 20px;
    font-weight: 700;
    color: var(--neon-cyan, #00d4ff);
    margin: 0;
}

.shrinkearn-modal .modal-body {
    padding: 20px;
}

.shrinkearn-modal .modal-mission-name {
    text-align: center;
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
}

.shrinkearn-modal .modal-reward {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px;
    background: rgba(255,204,0,0.1);
    border-radius: 12px;
    margin-bottom: 20px;
}

.shrinkearn-modal .reward-label {
    color: var(--text-secondary, rgba(255,255,255,0.6));
}

.shrinkearn-modal .reward-value {
    font-weight: 700;
    color: var(--neon-yellow, #ffcc00);
}

.shrinkearn-modal .reward-pts {
    color: var(--neon-cyan, #00d4ff);
}

.shrinkearn-modal .modal-instructions {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.shrinkearn-modal .instruction-step {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    color: var(--text-secondary, rgba(255,255,255,0.7));
}

.shrinkearn-modal .step-num {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--neon-cyan, #00d4ff), var(--neon-purple, #a855f7));
    border-radius: 50%;
    font-size: 13px;
    font-weight: 700;
    color: white;
    flex-shrink: 0;
}

.shrinkearn-modal .modal-footer {
    padding: 16px 20px 20px;
}

.shrinkearn-modal .modal-btn {
    width: 100%;
    padding: 14px;
    background: linear-gradient(135deg, var(--neon-cyan, #00d4ff), var(--neon-purple, #a855f7));
    border: none;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 600;
    color: white;
    cursor: pointer;
    transition: all 0.2s ease;
}

.shrinkearn-modal .modal-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,245,255,0.3);
}

/* Toast Animations */
@keyframes toastIn {
    from { transform: translateX(-50%) translateY(20px); opacity: 0; }
    to { transform: translateX(-50%) translateY(0); opacity: 1; }
}

@keyframes toastOut {
    from { transform: translateX(-50%) translateY(0); opacity: 1; }
    to { transform: translateX(-50%) translateY(20px); opacity: 0; }
}
</style>
`;

// Inyectar estilos si no existen
if (!document.getElementById('shrinkearn-styles')) {
    document.head.insertAdjacentHTML('beforeend', shrinkEarnStyles);
}

// Exportar funciones para uso global
window.initShrinkEarn = initShrinkEarn;
window.renderShrinkEarnMissions = renderShrinkEarnMissions;
window.refreshShrinkEarnMissions = refreshShrinkEarnMissions;
window.startShrinkEarnMission = startShrinkEarnMission;
window.closeMissionModal = closeMissionModal;

console.log('✅ ShrinkEarn frontend module loaded');
