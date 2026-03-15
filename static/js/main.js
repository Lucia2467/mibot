/* ==================== SALLY-E ULTRA PRO - EFECTOS ESPECIALES ==================== */

// ==================== SISTEMA DE PARTÍCULAS FLOTANTES ====================
class ParticleSystem {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.particles = [];
        this.particleCount = 50;
        this.init();
    }

    init() {
        // Crear canvas para partículas
        this.canvas = document.createElement('canvas');
        this.canvas.style.position = 'fixed';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.zIndex = '-1';
        this.canvas.style.pointerEvents = 'none';
        
        document.body.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        
        this.resize();
        this.createParticles();
        this.animate();
        
        window.addEventListener('resize', () => this.resize());
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    createParticles() {
        this.particles = [];
        for (let i = 0; i < this.particleCount; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                size: Math.random() * 3 + 1,
                speedX: (Math.random() - 0.5) * 0.5,
                speedY: (Math.random() - 0.5) * 0.5,
                opacity: Math.random() * 0.5 + 0.2,
                color: this.getRandomColor()
            });
        }
    }

    getRandomColor() {
        const colors = [
            'rgba(0, 102, 255, ',
            'rgba(0, 82, 204, ',
            'rgba(0, 245, 255, ',
            'rgba(0, 64, 255, '
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.particles.forEach(particle => {
            // Actualizar posición
            particle.x += particle.speedX;
            particle.y += particle.speedY;
            
            // Rebotar en los bordes
            if (particle.x < 0 || particle.x > this.canvas.width) {
                particle.speedX *= -1;
            }
            if (particle.y < 0 || particle.y > this.canvas.height) {
                particle.speedY *= -1;
            }
            
            // Dibujar partícula con glow
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            
            // Crear efecto de glow
            const gradient = this.ctx.createRadialGradient(
                particle.x, particle.y, 0,
                particle.x, particle.y, particle.size * 4
            );
            gradient.addColorStop(0, particle.color + particle.opacity + ')');
            gradient.addColorStop(1, particle.color + '0)');
            
            this.ctx.fillStyle = gradient;
            this.ctx.fill();
        });
        
        requestAnimationFrame(() => this.animate());
    }
}

// ==================== EFECTO DE MOUSE TRAIL ====================
class MouseTrail {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.points = [];
        this.maxPoints = 20;
        this.init();
    }

    init() {
        this.canvas = document.createElement('canvas');
        this.canvas.style.position = 'fixed';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.zIndex = '9998';
        this.canvas.style.pointerEvents = 'none';
        
        document.body.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        
        this.resize();
        this.animate();
        
        window.addEventListener('resize', () => this.resize());
        window.addEventListener('mousemove', (e) => this.addPoint(e.clientX, e.clientY));
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    addPoint(x, y) {
        this.points.push({ x, y, age: 0 });
        if (this.points.length > this.maxPoints) {
            this.points.shift();
        }
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        for (let i = 0; i < this.points.length - 1; i++) {
            const point = this.points[i];
            const nextPoint = this.points[i + 1];
            
            point.age++;
            
            const opacity = 1 - (point.age / this.maxPoints);
            const size = 10 * opacity;
            
            // Crear gradiente
            const gradient = this.ctx.createLinearGradient(
                point.x, point.y,
                nextPoint.x, nextPoint.y
            );
            gradient.addColorStop(0, `rgba(0, 102, 255, ${opacity * 0.3})`);
            gradient.addColorStop(0.5, `rgba(0, 82, 204, ${opacity * 0.3})`);
            gradient.addColorStop(1, `rgba(0, 245, 255, ${opacity * 0.3})`);
            
            this.ctx.strokeStyle = gradient;
            this.ctx.lineWidth = size;
            this.ctx.lineCap = 'round';
            
            this.ctx.beginPath();
            this.ctx.moveTo(point.x, point.y);
            this.ctx.lineTo(nextPoint.x, nextPoint.y);
            this.ctx.stroke();
        }
        
        // Eliminar puntos viejos
        this.points = this.points.filter(point => point.age < this.maxPoints);
        
        requestAnimationFrame(() => this.animate());
    }
}

// ==================== SISTEMA DE TOAST ULTRA PROFESIONAL ====================
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

    // SVG de checkmark verde 3D con gradiente ultra pro
    getCheckmarkSVG() {
        return `<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="checkGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#00ff88;stop-opacity:1" />
                    <stop offset="50%" style="stop-color:#00dd77;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#00cc66;stop-opacity:1" />
                </linearGradient>
                <filter id="glow">
                    <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
                    <feMerge>
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
                <filter id="shadow">
                    <feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#00ff88" flood-opacity="0.7"/>
                </filter>
            </defs>
            <circle cx="14" cy="14" r="12" fill="url(#checkGradient)" filter="url(#shadow)" opacity="0.25"/>
            <circle cx="14" cy="14" r="10" fill="url(#checkGradient)" filter="url(#glow)"/>
            <path d="M9 14L12 17L19 10" stroke="#000000" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
        </svg>`;
    }

    // SVG de spinner ultra pro
    getSpinnerSVG() {
        return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="rotating">
            <defs>
                <linearGradient id="spinnerGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" style="stop-color:#00ff88;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#00ff88;stop-opacity:0" />
                </linearGradient>
            </defs>
            <circle cx="12" cy="12" r="10" stroke="url(#spinnerGradient)" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        </svg>`;
    }

    show(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: this.getCheckmarkSVG(),
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        
        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="font-size: 1.1rem; flex-shrink: 0;">${icons[type] || 'ℹ'}</div>
                <div style="flex: 1; font-weight: 600; font-size: 0.8125rem; color: #ffffff; line-height: 1.3;">${message}</div>
            </div>
        `;
        
        this.container.appendChild(toast);
        
        // Auto-remove
        setTimeout(() => {
            toast.style.animation = 'slideInRight 0.3s reverse';
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, duration);
    }
    
    /**
     * Show ultra professional processing notification
     * @param {string} initialMessage - Initial processing message
     * @param {string} successMessage - Success message after processing
     * @param {string} customIconUrl - URL to custom icon image (optional, uses SVG if null)
     * @param {number} processingDuration - How long to show processing state (ms)
     */
    showProcessing(initialMessage = 'Procesando...', successMessage = '¡Hecho!', customIconUrl = null, processingDuration = 2000) {
        const toast = document.createElement('div');
        toast.className = 'toast toast-processing toast-success';
        
        // Icon HTML - use custom image or SVG spinner
        const iconHtml = customIconUrl 
            ? `<img src="${customIconUrl}" style="width: 28px; height: 28px; border-radius: 50%; object-fit: cover;" alt="icon" />`
            : this.getSpinnerSVG();
        
        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <div id="toast-icon" style="display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    ${iconHtml}
                </div>
                <div style="flex: 1;">
                    <div id="toast-message" style="font-weight: 600; font-size: 0.8125rem; color: #FFFFFF; line-height: 1.3;">${initialMessage}</div>
                </div>
            </div>
        `;
        
        this.container.appendChild(toast);
        
        // After processing duration, update to success state
        setTimeout(() => {
            const messageEl = toast.querySelector('#toast-message');
            const iconEl = toast.querySelector('#toast-icon');
            
            // Update icon to 3D checkmark or custom success icon
            const successIconHtml = customIconUrl
                ? `<img src="${customIconUrl}" style="width: 28px; height: 28px; border-radius: 50%; object-fit: cover; filter: brightness(1.2);" alt="success" />`
                : this.getCheckmarkSVG();
            
            iconEl.innerHTML = successIconHtml;
            
            // Update message
            messageEl.textContent = successMessage;
            
            // Vibrate if available
            if (window.vibrateDevice) {
                window.vibrateDevice([50, 100, 50]);
            }
            
            // Telegram haptic feedback
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
            }
            
            // Remove after showing success
            setTimeout(() => {
                toast.style.animation = 'slideInRight 0.3s reverse';
                setTimeout(() => {
                    toast.remove();
                }, 300);
            }, 2500);
        }, processingDuration);
    }
}

// Add CSS for rotating animation if not exists
if (!document.getElementById('toast-rotating-style')) {
    const style = document.createElement('style');
    style.id = 'toast-rotating-style';
    style.textContent = `
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        .rotating {
            animation: rotate 1s linear infinite;
        }
    `;
    document.head.appendChild(style);
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

// ==================== EFECTOS DE CARD PARALLAX ====================
function initCardParallax() {
    // DESHABILITADO - Animaciones 3D removidas para mejorar rendimiento
    return;
}

// ==================== RIPPLE EFFECT EN BOTONES ====================
function initRippleEffect() {
    const buttons = document.querySelectorAll('.btn, .nav-item');
    
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
                background: radial-gradient(circle, rgba(255, 255, 255, 0.3) 0%, transparent 70%);
                left: ${x}px;
                top: ${y}px;
                pointer-events: none;
                transform: scale(0);
                animation: rippleEffect 0.6s ease-out;
            `;
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => ripple.remove(), 600);
        });
    });
    
    // Agregar animación CSS
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

// ==================== SCROLL REVEAL ====================
function initScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, {
        threshold: 0.1
    });
    
    document.querySelectorAll('.card, .stat-card').forEach(element => {
        element.style.opacity = '0';
        element.style.transform = 'translateY(20px)';
        element.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(element);
    });
}

// ==================== VIBRATION API ====================
function vibrateDevice(pattern = [50]) {
    if ('vibrate' in navigator) {
        navigator.vibrate(pattern);
    }
}

// ==================== HAPTIC FEEDBACK PARA BOTONES ====================
function initHapticFeedback() {
    const buttons = document.querySelectorAll('.btn, .nav-item');
    
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            vibrateDevice([10]);
        });
    });
}

// ==================== INICIALIZACIÓN ====================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Sally-E Ultra Pro Edition iniciando...');
    
    // Verificar preferencias de movimiento reducido
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    
    if (!prefersReducedMotion) {
        // Sistema de partículas DESHABILITADO para mejorar rendimiento
        // new ParticleSystem();
        
        // Mouse trail DESHABILITADO para mejorar rendimiento
        // new MouseTrail();
        
        // Parallax en cards DESHABILITADO para mejorar rendimiento
        // initCardParallax();
        
        // Inicializar scroll reveal
        setTimeout(() => initScrollReveal(), 100);
    }
    
    // Inicializar efectos táctiles
    initRippleEffect();
    initHapticFeedback();
    
    // Inicializar iconos Lucide si está disponible
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    console.log('✨ Sally-E Ultra Pro Edition listo');
});

// ==================== EXPORTAR FUNCIONES GLOBALES ====================

// ════════════════════════════════════════
//  showRewardModal — MODAL UNIVERSAL (4 colores)
// ════════════════════════════════════════
window.showRewardModal = function(message, type) {
    type = type || 'info';
    const palette = {
        success: { c:'#22c55e', cd:'#16a34a', cl:'#4ade80', icon:'check', badge:'✅' },
        error:   { c:'#c0392b', cd:'#96281b', cl:'#e74c3c', icon:'x',     badge:'❌' },
        warning: { c:'#F59E0B', cd:'#D97706', cl:'#FCD34D', icon:'alert', badge:'⚠️' },
        info:    { c:'#3B82F6', cd:'#2563EB', cl:'#93C5FD', icon:'info',  badge:'ℹ️' },
    };
    const p = palette[type] || palette.info;
    const c = p.c, cd = p.cd, cl = p.cl;
    const icons = {
        check: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="'+c+'" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        x:     '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="'+c+'" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
        alert: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="'+c+'" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        info:  '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="'+c+'" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
    };
    const svgIcon = icons[p.icon] || icons.info;
    const tt = typeof window.t === 'function' ? window.t : function(k){ return null; };
    const labels = { success: tt('reward_label')||'Recompensa', error: (tt('error_label')||'Error').toUpperCase(), warning: (tt('warning_label')||'Aviso').toUpperCase(), info: (tt('info_label')||'Info').toUpperCase() };
    const subs   = { success: tt('reward_added_balance')||'¡Añadido a tu balance!', error: '', warning: tt('warning_sub')||'', info: tt('info_sub')||'' };
    const label = labels[type] || labels.info;
    const sub   = subs[type]   || '';
    // Strip leading emoji/symbols from message
    const cleanMsg = message.replace(/^[\s✓✕✗⚠❌✅ℹ️⚠️❌✓✔×✘]+/, '').trim() || message;
    const fontSize = cleanMsg.length > 25 ? '1.3rem' : '2rem';

    // Inject CSS once
    if (!document.getElementById('_rm_css')) {
        const s = document.createElement('style'); s.id = '_rm_css';
        s.textContent = '@keyframes _rmFadeIn{from{opacity:0}to{opacity:1}}@keyframes _rmFadeOut{from{opacity:1}to{opacity:0}}@keyframes _rmScaleIn{from{opacity:0;transform:scale(0.7)}to{opacity:1;transform:scale(1)}}@keyframes _rmScaleOut{from{opacity:1;transform:scale(1)}to{opacity:0;transform:scale(0.7)}}@keyframes _rmGlow{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}@keyframes _rmSpin{from{transform:translate(-50%,-50%) rotate(0deg)}to{transform:translate(-50%,-50%) rotate(360deg)}}@keyframes _rmPulse{0%,100%{transform:translate(-50%,-50%) scale(1)}50%{transform:translate(-50%,-50%) scale(1.08)}}@keyframes _rmP1{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}@keyframes _rmP2{0%,100%{transform:translateY(0)}50%{transform:translateY(6px)}}@keyframes _rmP3{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}';
        document.head.appendChild(s);
    }

    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.75);backdrop-filter:blur(12px);display:flex;align-items:center;justify-content:center;animation:_rmFadeIn 0.35s ease;';

    const notif = document.createElement('div');
    notif.style.cssText = 'position:relative;background:linear-gradient(135deg,rgba(18,18,18,0.98),rgba(30,30,30,0.98));border-radius:32px;overflow:hidden;box-shadow:0 0 0 1px '+c+'44,0 30px 90px rgba(0,0,0,0.8),inset 0 1px 0 rgba(255,255,255,0.05);animation:_rmScaleIn 0.45s cubic-bezier(0.34,1.56,0.64,1);min-width:300px;max-width:88vw;text-align:center;';

    const glow = document.createElement('div');
    glow.style.cssText = 'position:absolute;top:-2px;left:-2px;right:-2px;bottom:-2px;background:linear-gradient(135deg,'+c+','+cd+','+c+');border-radius:32px;opacity:0.5;filter:blur(18px);animation:_rmGlow 3s linear infinite;z-index:-1;';

    const header = document.createElement('div');
    header.style.cssText = 'background:linear-gradient(135deg,'+c+'26,'+c+'0d);padding:36px 28px 24px;border-bottom:1px solid '+c+'33;position:relative;overflow:hidden;';
    header.innerHTML = '<div style="position:absolute;top:10%;left:10%;width:4px;height:4px;background:'+c+';border-radius:50%;animation:_rmP1 2s ease-in-out infinite;"></div><div style="position:absolute;top:30%;right:15%;width:3px;height:3px;background:'+cl+';border-radius:50%;animation:_rmP2 2.5s ease-in-out infinite;"></div><div style="position:absolute;bottom:20%;left:20%;width:5px;height:5px;background:'+cd+';border-radius:50%;animation:_rmP3 3s ease-in-out infinite;"></div><div style="position:relative;width:90px;height:90px;margin:0 auto 18px;"><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:90px;height:90px;border:2px solid transparent;border-top-color:'+c+';border-right-color:'+c+';border-radius:50%;animation:_rmSpin 2s linear infinite;opacity:0.6;"></div><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:62px;height:62px;background:'+c+'3d;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 0 28px '+c+'66;animation:_rmPulse 1.5s ease-in-out infinite;">'+svgIcon+'</div></div><div style="font-size:0.7rem;font-weight:700;color:'+cl+';text-transform:uppercase;letter-spacing:2px;position:relative;z-index:1;">'+p.badge+' '+label+'</div>';

    const body = document.createElement('div');
    body.style.cssText = 'padding:26px 28px 30px;';
    body.innerHTML = '<div style="font-size:'+fontSize+';font-weight:900;background:linear-gradient(135deg,'+c+','+cl+',#fff8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:10px;letter-spacing:1px;">'+message+'</div>'+(sub?'<div style="font-size:0.88rem;color:rgba(255,255,255,0.45);margin-bottom:18px;">'+sub+'</div>':'')+'<div style="width:50px;height:3px;background:linear-gradient(90deg,transparent,'+c+',transparent);margin:0 auto;border-radius:2px;"></div>';

    notif.appendChild(glow); notif.appendChild(header); notif.appendChild(body);
    overlay.appendChild(notif); document.body.appendChild(overlay);

    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback)
        window.Telegram.WebApp.HapticFeedback.notificationOccurred(type==='success'?'success':type==='error'?'error':'warning');

    const close = function() {
        overlay.style.animation = '_rmFadeOut 0.35s ease forwards';
        notif.style.animation   = '_rmScaleOut 0.35s cubic-bezier(0.16,1,0.3,1) forwards';
        setTimeout(function(){ overlay.remove(); }, 380);
    };
    setTimeout(close, 3200);
    overlay.addEventListener('click', function(e){ if(e.target===overlay) close(); });
};


window.toastSystem = new ToastSystem();
window.showToast = function(message, type, duration) {
    if (typeof window.showRewardModal === 'function') {
        // Strip emoji prefixes added by callers
        const cleanMessage = String(message).replace(/^\W+/, '').trim() || message;
        window.showRewardModal(cleanMessage, type || 'info');
        return;
    }
    window.toastSystem.show(message, type, duration);
};
window.showProcessingToast = (initialMsg, successMsg, customIcon, duration) => window.toastSystem.showProcessing(initialMsg, successMsg, customIcon, duration);
window.animateCounter = animateCounter;
window.showSkeleton = showSkeleton;
window.hideSkeleton = hideSkeleton;
window.vibrateDevice = vibrateDevice;

// ==================== FUNCIONES DE REFERIDOS ====================

/**
 * Copiar link de referido al portapapeles
 */
function copyReferralLink() {
    const input = document.getElementById('referral-link');
    if (!input) {
        console.error('Input de referral-link no encontrado');
        return;
    }
    
    const link = input.value;
    const successMsg = typeof t === 'function' ? t('copied_to_clipboard') : '✅ Link copiado al portapapeles';
    const errorMsg = typeof t === 'function' ? t('error_occurred') : '❌ Error al copiar';
    
    // Intentar copiar usando Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(link)
            .then(() => {
                showToast('✅ ' + successMsg, 'success', 2000);
                vibrateDevice(50);
            })
            .catch(err => {
                console.error('Error copiando link:', err);
                fallbackCopyLink(input);
            });
    } else {
        fallbackCopyLink(input);
    }
}

/**
 * Método fallback para copiar link
 */
function fallbackCopyLink(input) {
    input.select();
    input.setSelectionRange(0, 99999); // Para móviles
    
    const successMsg = typeof t === 'function' ? t('copied_to_clipboard') : '✅ Link copiado';
    const errorMsg = typeof t === 'function' ? t('error_occurred') : '❌ Error al copiar';
    
    try {
        document.execCommand('copy');
        showToast('✅ ' + successMsg, 'success', 2000);
        vibrateDevice(50);
    } catch (err) {
        console.error('Error en fallback copy:', err);
        showToast('❌ ' + errorMsg, 'error', 2000);
    }
}

/**
 * Compartir link de referido usando Web Share API
 */
function shareReferralLink() {
    const input = document.getElementById('referral-link');
    if (!input) {
        console.error('Input de referral-link no encontrado');
        return;
    }
    
    const link = input.value;
    const text = '🚀 ¡Únete a SALLY-E y gana criptomonedas! 💰 Recibe 50 S-E de bono al unirte con mi enlace.';
    
    // Intentar usar Web Share API si está disponible
    if (navigator.share) {
        navigator.share({
            title: 'SALLY-E - Gana Criptomonedas',
            text: text,
            url: link
        })
        .then(() => {
            console.log('Link compartido exitosamente');
            vibrateDevice(50);
        })
        .catch(err => {
            console.log('Error compartiendo o usuario canceló:', err);
            // Si falla, copiar al portapapeles
            copyReferralLink();
        });
    } else {
        // Fallback: abrir Telegram directamente
        const telegramShareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
        window.open(telegramShareUrl, '_blank');
        vibrateDevice(50);
    }
}

/**
 * Cargar lista de referidos desde la API
 */
async function loadReferralsList(userId) {
    try {
        // Usar apiGet con loader si está disponible
        const data = typeof apiGet !== 'undefined' 
            ? await apiGet(`/api/referrals/list?user_id=${userId}`, '⏳ Cargando referidos...')
            : await fetch(`/api/referrals/list?user_id=${userId}`).then(r => r.json());
        
        if (data.success) {
            updateReferralsDisplay(data);
            return data;
        } else {
            console.error('Error cargando referidos:', data.message);
            return null;
        }
    } catch (error) {
        console.error('Error en loadReferralsList:', error);
        return null;
    }
}

/**
 * Actualizar display de referidos
 */
function updateReferralsDisplay(data) {
    // Actualizar contador de referidos
    const countDisplay = document.getElementById('referral-count-display');
    if (countDisplay) {
        animateCounter(countDisplay, data.total_referrals);
    }
    
    // Actualizar S-E ganados
    const seEarnedDisplay = document.getElementById('se-earned-display');
    if (seEarnedDisplay) {
        animateCounter(seEarnedDisplay, data.total_se_earned);
    }
    
    // Actualizar comisiones si existe el elemento
    const commissionDisplay = document.getElementById('total-commission-display');
    if (commissionDisplay) {
        animateCounter(commissionDisplay, data.total_commission);
    }
}

/**
 * Cargar estadísticas de ranking
 */
async function loadRankingStats(userId) {
    try {
        // Usar apiGet con loader si está disponible
        const data = typeof apiGet !== 'undefined'
            ? await apiGet(`/api/ranking/top`, '⏳ Cargando ranking...')
            : await fetch(`/api/ranking/top`).then(r => r.json());
        
        if (data.success) {
            return data;
        } else {
            console.error('Error cargando ranking:', data.message);
            return null;
        }
    } catch (error) {
        console.error('Error en loadRankingStats:', error);
        return null;
    }
}

// Exportar funciones de referidos
window.copyReferralLink = copyReferralLink;
window.shareReferralLink = shareReferralLink;
window.loadReferralsList = loadReferralsList;
window.loadRankingStats = loadRankingStats;

// ==================== API HELPER CON LOADER ====================
/**
 * API helper que muestra loader automáticamente durante llamadas DB
 * @param {string} url - URL del endpoint
 * @param {object} options - Opciones de fetch
 * @param {string} loadingMessage - Mensaje a mostrar en loader
 * @returns {Promise<object>} - Respuesta JSON
 */
async function apiCall(url, options = {}, loadingMessage = '⏳ Cargando...') {
    // Verificar si DbLoader está disponible
    if (typeof DbLoader !== 'undefined' && DbLoader.wrap) {
        return DbLoader.wrap(
            fetch(url, options).then(res => {
                if (!res.ok) throw new Error(`Error HTTP ${res.status}`);
                return res.json();
            }),
            loadingMessage
        );
    }
    
    // Fallback sin loader
    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`Error HTTP ${response.status}`);
    return response.json();
}

/**
 * POST API call con loader
 */
async function apiPost(url, data, loadingMessage = '⏳ Procesando...') {
    return apiCall(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }, loadingMessage);
}

/**
 * GET API call con loader  
 */
async function apiGet(url, loadingMessage = '⏳ Cargando...') {
    return apiCall(url, {}, loadingMessage);
}

// Exportar helpers de API
window.apiCall = apiCall;
window.apiPost = apiPost;
window.apiGet = apiGet;
