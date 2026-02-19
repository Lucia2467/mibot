/* ==================== SALLY-E - EFECTOS ULTRA LIGEROS ==================== */
/* Versión OPTIMIZADA - Sin animaciones 3D, rendimiento máximo */

// ==================== SISTEMA DE TOAST MEJORADO ====================
class ToastSystem {
    constructor() {
        this.container = this.createContainer();
    }

    createContainer() {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    show(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        
        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="font-size: 1.25rem;">${icons[type] || 'ℹ'}</div>
                <div style="flex: 1; font-weight: 600;">${message}</div>
            </div>
        `;
        
        this.container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

// ==================== CONTADOR ANIMADO ====================
function animateCounter(element, target, duration = 1000) {
    if (!element) return;
    
    const start = parseFloat(element.textContent) || 0;
    const increment = (target - start) / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        
        if ((increment > 0 && current >= target) || (increment < 0 && current <= target)) {
            current = target;
            clearInterval(timer);
        }
        
        const decimals = target.toString().includes('.') ? 
            (target.toString().split('.')[1] || '').length : 0;
        element.textContent = current.toFixed(decimals);
    }, 16);
}

// ==================== EFECTOS 3D COMPLETAMENTE DESHABILITADOS ====================
function initCardParallax() {
    // DESHABILITADO - Sin efecto 3D de inclinación de tarjetas
    return;
}

// ==================== RIPPLE EFFECT LIGERO ====================
function initRippleEffect() {
    // Solo en desktop, deshabilitado en móviles para mejor rendimiento
    if (window.innerWidth < 768 || 'ontouchstart' in window) {
        return;
    }
    
    const buttons = document.querySelectorAll('.btn');
    
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.cssText = `
                position: absolute;
                width: ${size}px;
                height: ${size}px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.2);
                left: ${x}px;
                top: ${y}px;
                pointer-events: none;
                transform: scale(0);
                animation: rippleEffect 0.4s ease-out;
            `;
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => ripple.remove(), 400);
        });
    });
    
    // Agregar animación CSS si no existe
    if (!document.getElementById('ripple-style')) {
        const style = document.createElement('style');
        style.id = 'ripple-style';
        style.textContent = `
            @keyframes rippleEffect {
                to {
                    transform: scale(2);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
}

// ==================== LOADING SKELETON ====================
function showSkeleton(element) {
    if (!element) return;
    
    element.style.background = 'linear-gradient(90deg, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.1) 50%, rgba(255, 255, 255, 0.05) 75%)';
    element.style.backgroundSize = '200% 100%';
    element.style.animation = 'skeleton-loading 1.5s infinite';
    element.style.color = 'transparent';
    
    if (!document.getElementById('skeleton-style')) {
        const style = document.createElement('style');
        style.id = 'skeleton-style';
        style.textContent = `
            @keyframes skeleton-loading {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
        `;
        document.head.appendChild(style);
    }
}

function hideSkeleton(element) {
    if (!element) return;
    element.style.background = '';
    element.style.animation = '';
    element.style.color = '';
}

// ==================== SCROLL REVEAL LIGERO ====================
function initScrollReveal() {
    // Deshabilitado en móviles para mejor rendimiento
    if (window.innerWidth < 768) {
        return;
    }
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target); // Solo animar una vez
            }
        });
    }, {
        threshold: 0.1
    });
    
    document.querySelectorAll('.card, .stat-card').forEach(element => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(15px)';
        element.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        observer.observe(element);
    });
}

// ==================== VIBRATION API ====================
function vibrateDevice(pattern = [50]) {
    if ('vibrate' in navigator) {
        navigator.vibrate(pattern);
    }
}

// ==================== HAPTIC FEEDBACK LIGERO ====================
function initHapticFeedback() {
    const buttons = document.querySelectorAll('.btn, .nav-item');
    
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            vibrateDevice([10]);
        });
    });
}

// ==================== INICIALIZACIÓN ULTRA LIGERA ====================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Sally-E Lite iniciando...');
    
    // Verificar preferencias de movimiento reducido
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    
    // Solo efectos mínimos en desktop
    if (!prefersReducedMotion && window.innerWidth >= 768) {
        // Ripple effect solo en desktop
        initRippleEffect();
        
        // Scroll reveal solo en desktop
        setTimeout(() => initScrollReveal(), 200);
    }
    
    // Haptic feedback en todos los dispositivos
    initHapticFeedback();
    
    // Inicializar iconos Lucide
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    console.log('✨ Sally-E Lite listo');
});

// ==================== EXPORTAR FUNCIONES GLOBALES ====================
window.toastSystem = new ToastSystem();
window.showToast = (message, type, duration) => window.toastSystem.show(message, type, duration);
window.animateCounter = animateCounter;
window.showSkeleton = showSkeleton;
window.hideSkeleton = hideSkeleton;
window.vibrateDevice = vibrateDevice;

// ==================== SIN PARTÍCULAS NI MOUSE TRAIL ====================
// Completamente removidos para máximo rendimiento en móviles
