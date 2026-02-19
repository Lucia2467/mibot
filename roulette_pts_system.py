"""
roulette_pts_system.py - Sistema de Ruleta PTS
===============================================
Ruleta gratuita que otorga PTS cada 20 minutos
Premios: 5, 7, 10, 13, 15 PTS
Opción de duplicar viendo anuncio de Monetag
Notificación por Telegram cuando el giro está disponible
"""

import logging
import random
import os
import requests
import threading
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN DE LA RULETA
# ============================================
ROULETTE_CONFIG = {
    'prizes': [5, 7, 10, 13, 15],           # Premios posibles en PTS
    'cooldown_minutes': 20,                  # 20 minutos entre giros
    'cooldown_seconds': 20 * 60,            # 1200 segundos
    'double_multiplier': 2                   # x2 al ver anuncio
}

# Pesos de probabilidad (mayor = más probable)
# Ajustar para que premios menores sean más probables
PRIZE_WEIGHTS = {
    5: 35,    # 35% - más común
    7: 28,    # 28%
    10: 20,   # 20%
    13: 12,   # 12%
    15: 5     # 5% - más raro
}

# Telegram Bot Config
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
WEBAPP_URL = os.environ.get('WEBAPP_URL', 'https://isaax23.pythonanywhere.com')

roulette_pts_bp = Blueprint('roulette_pts', __name__)

# Traducciones para notificaciones del bot
BOT_TRANSLATIONS = {
    'en': {
        'roulette_ready_title': '🎰 Your PTS Roulette spin is ready!',
        'roulette_ready_desc': 'You have a free spin available.\nWin between 5-15 PTS and double by watching an ad!',
        'spin_button': '🎰 Spin Roulette'
    },
    'es': {
        'roulette_ready_title': '🎰 ¡Tu giro de la Ruleta PTS está listo!',
        'roulette_ready_desc': 'Tienes un giro gratuito disponible.\nGana entre 5-15 PTS y ¡duplica viendo un anuncio!',
        'spin_button': '🎰 Girar Ruleta'
    },
    'pt': {
        'roulette_ready_title': '🎰 Seu giro da Roleta PTS está pronto!',
        'roulette_ready_desc': 'Você tem um giro gratuito disponível.\nGanhe entre 5-15 PTS e duplique assistindo um anúncio!',
        'spin_button': '🎰 Girar Roleta'
    },
    'ru': {
        'roulette_ready_title': '🎰 Ваш спин Рулетки PTS готов!',
        'roulette_ready_desc': 'У вас есть бесплатный спин.\nВыиграйте 5-15 PTS и удвойте просмотром рекламы!',
        'spin_button': '🎰 Крутить рулетку'
    },
    'ar': {
        'roulette_ready_title': '🎰 دورة روليت PTS جاهزة!',
        'roulette_ready_desc': 'لديك دورة مجانية متاحة.\nاربح من 5-15 نقطة وضاعفها بمشاهدة إعلان!',
        'spin_button': '🎰 أدر الروليت'
    }
}

def get_user_language(user_id):
    """Obtener idioma del usuario desde la base de datos"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT language FROM users WHERE user_id = %s", (str(user_id),))
            result = cursor.fetchone()
            if result and result.get('language'):
                return result['language']
    except Exception as e:
        logger.warning(f"Error getting user language: {e}")
    return 'es'  # Idioma por defecto

def get_bot_translation(user_id, key):
    """Obtener traducción del bot para el usuario"""
    lang = get_user_language(user_id)
    if lang not in BOT_TRANSLATIONS:
        lang = 'en'
    return BOT_TRANSLATIONS.get(lang, BOT_TRANSLATIONS['en']).get(key, '')


# ============================================
# FUNCIONES DE BASE DE DATOS
# ============================================

def init_roulette_tables():
    """Crear tablas para la ruleta PTS"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            # Tabla de progreso de ruleta
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roulette_pts_progress (
                    user_id VARCHAR(50) PRIMARY KEY,
                    total_spins INT DEFAULT 0,
                    total_pts_won INT DEFAULT 0,
                    last_spin_at DATETIME NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Historial de giros
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roulette_pts_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    prize INT NOT NULL,
                    doubled TINYINT(1) DEFAULT 0,
                    final_prize INT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_date (user_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
        logger.info("✅ [Roulette PTS] Tablas inicializadas")
        return True
    except Exception as e:
        logger.error(f"❌ [Roulette PTS] Error creando tablas: {e}")
        return False


def get_roulette_status(user_id):
    """Obtener estado de la ruleta para un usuario"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT total_spins, total_pts_won, last_spin_at
                FROM roulette_pts_progress
                WHERE user_id = %s
            """, (str(user_id),))
            
            result = cursor.fetchone()
            
            if result:
                last_spin = result['last_spin_at']
                now = datetime.now()
                
                if last_spin:
                    next_spin_time = last_spin + timedelta(seconds=ROULETTE_CONFIG['cooldown_seconds'])
                    can_spin = now >= next_spin_time
                    remaining_seconds = max(0, int((next_spin_time - now).total_seconds()))
                else:
                    can_spin = True
                    remaining_seconds = 0
                    next_spin_time = now
                
                return {
                    'total_spins': result['total_spins'],
                    'total_pts_won': result['total_pts_won'],
                    'last_spin_at': last_spin,
                    'can_spin': can_spin,
                    'remaining_seconds': remaining_seconds,
                    'next_spin_timestamp': int(next_spin_time.timestamp()) if not can_spin else 0
                }
            else:
                # Nuevo usuario - crear registro
                cursor.execute("""
                    INSERT INTO roulette_pts_progress (user_id, total_spins, total_pts_won)
                    VALUES (%s, 0, 0)
                """, (str(user_id),))
                
                return {
                    'total_spins': 0,
                    'total_pts_won': 0,
                    'last_spin_at': None,
                    'can_spin': True,
                    'remaining_seconds': 0,
                    'next_spin_timestamp': 0
                }
                
    except Exception as e:
        logger.error(f"❌ [Roulette PTS] Error obteniendo estado: {e}")
        return None


# ============================================
# NOTIFICACIÓN POR TELEGRAM
# ============================================

def send_spin_ready_notification(user_id):
    """Enviar notificación al usuario cuando su giro esté disponible"""
    try:
        if not BOT_TOKEN:
            logger.warning("[Roulette] No BOT_TOKEN configured")
            return False
        
        # Obtener traducciones según idioma del usuario
        title = get_bot_translation(user_id, 'roulette_ready_title')
        desc = get_bot_translation(user_id, 'roulette_ready_desc')
        button_text = get_bot_translation(user_id, 'spin_button')
        
        message = (
            f"<b>{title}</b>\n\n"
            f"{desc}\n\n"
            "👉 Abre la app para girar ahora"
        )
        
        # Crear inline keyboard con botón para abrir la webapp
        keyboard = {
            "inline_keyboard": [[
                {
                    "text": button_text,
                    "web_app": {"url": f"{WEBAPP_URL}/roulette-pts?user_id={user_id}"}
                }
            ]]
        }
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ [Roulette] Notificación enviada a {user_id}")
            return True
        else:
            logger.warning(f"⚠️ [Roulette] Error enviando notificación: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ [Roulette] Error en notificación: {e}")
        return False


def schedule_spin_notification(user_id, delay_seconds):
    """Programar notificación para cuando el giro esté disponible"""
    def delayed_notification():
        import time
        time.sleep(delay_seconds)
        send_spin_ready_notification(user_id)
    
    # Ejecutar en thread separado para no bloquear
    thread = threading.Thread(target=delayed_notification, daemon=True)
    thread.start()
    logger.info(f"📅 [Roulette] Notificación programada para {user_id} en {delay_seconds}s")


def spin_roulette(user_id):
    """Girar la ruleta y obtener premio"""
    from db import get_cursor
    
    try:
        # Verificar si puede girar
        status = get_roulette_status(user_id)
        if not status or not status['can_spin']:
            return None, "Debes esperar antes de girar de nuevo"
        
        # Seleccionar premio basado en pesos
        prizes = list(PRIZE_WEIGHTS.keys())
        weights = list(PRIZE_WEIGHTS.values())
        prize = random.choices(prizes, weights=weights, k=1)[0]
        
        now = datetime.now()
        next_spin_time = now + timedelta(seconds=ROULETTE_CONFIG['cooldown_seconds'])
        
        with get_cursor() as cursor:
            # Actualizar progreso
            cursor.execute("""
                UPDATE roulette_pts_progress
                SET total_spins = total_spins + 1,
                    total_pts_won = total_pts_won + %s,
                    last_spin_at = %s
                WHERE user_id = %s
            """, (prize, now, str(user_id)))
            
            # Registrar en historial
            cursor.execute("""
                INSERT INTO roulette_pts_history (user_id, prize, doubled, final_prize)
                VALUES (%s, %s, 0, %s)
            """, (str(user_id), prize, prize))
            
            spin_id = cursor.lastrowid
            
            # Agregar PTS al usuario
            from onclicka_pts_system import add_pts
            success, msg = add_pts(user_id, prize, 'roulette_spin', f'Ruleta: {prize} PTS')
            
            if not success:
                logger.warning(f"⚠️ [Roulette PTS] Error agregando PTS: {msg}")
        
        # Programar notificación para cuando el próximo giro esté disponible
        schedule_spin_notification(user_id, ROULETTE_CONFIG['cooldown_seconds'])
        
        return {
            'prize': prize,
            'spin_id': spin_id,
            'next_spin_timestamp': int(next_spin_time.timestamp())
        }, None
        
    except Exception as e:
        logger.error(f"❌ [Roulette PTS] Error en spin: {e}")
        return None, str(e)


def double_prize(user_id, original_prize):
    """Duplicar el premio después de ver anuncio"""
    from db import get_cursor
    
    try:
        bonus = original_prize  # El bonus es igual al premio original
        
        with get_cursor() as cursor:
            # Actualizar el último giro como duplicado
            cursor.execute("""
                UPDATE roulette_pts_history
                SET doubled = 1, final_prize = %s
                WHERE user_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (original_prize * 2, str(user_id)))
            
            # Actualizar total ganado
            cursor.execute("""
                UPDATE roulette_pts_progress
                SET total_pts_won = total_pts_won + %s
                WHERE user_id = %s
            """, (bonus, str(user_id)))
            
            # Agregar PTS bonus al usuario
            from onclicka_pts_system import add_pts
            success, msg = add_pts(user_id, bonus, 'roulette_double', f'Ruleta x2: +{bonus} PTS')
            
            if not success:
                logger.warning(f"⚠️ [Roulette PTS] Error agregando bonus: {msg}")
                return False, msg
        
        return True, None
        
    except Exception as e:
        logger.error(f"❌ [Roulette PTS] Error duplicando: {e}")
        return False, str(e)


def get_pts_balance(user_id):
    """Obtener balance PTS del usuario"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT pts_balance FROM user_pts WHERE user_id = %s
            """, (str(user_id),))
            result = cursor.fetchone()
            return result['pts_balance'] if result else 0
    except Exception as e:
        logger.error(f"Error obteniendo balance PTS: {e}")
        return 0


# ============================================
# RUTAS
# ============================================

@roulette_pts_bp.route('/roulette-pts')
def roulette_page():
    """Página de la ruleta PTS"""
    user_id = request.args.get('user_id')
    if not user_id:
        return "User ID required", 400
    
    status = get_roulette_status(user_id)
    pts_balance = get_pts_balance(user_id)
    
    # Formatear tiempo restante
    remaining_time = "00:00"
    if status and not status['can_spin']:
        mins = status['remaining_seconds'] // 60
        secs = status['remaining_seconds'] % 60
        remaining_time = f"{mins:02d}:{secs:02d}"
    
    return render_template('roulette_pts.html',
        user_id=user_id,
        pts_balance=pts_balance,
        can_spin=status['can_spin'] if status else True,
        remaining_time=remaining_time,
        next_spin_timestamp=status['next_spin_timestamp'] if status else 0,
        total_spins=status['total_spins'] if status else 0,
        total_pts_won=status['total_pts_won'] if status else 0
    )


@roulette_pts_bp.route('/api/roulette-pts/spin', methods=['POST'])
def api_spin():
    """API para girar la ruleta"""
    data = request.json or {}
    user_id = data.get('user_id') or request.args.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    result, error = spin_roulette(user_id)
    
    if error:
        return jsonify({'success': False, 'error': error})
    
    # Obtener nuevo balance
    new_balance = get_pts_balance(user_id)
    
    return jsonify({
        'success': True,
        'prize': result['prize'],
        'new_balance': new_balance,
        'next_spin_time': result['next_spin_timestamp']
    })


@roulette_pts_bp.route('/api/roulette-pts/double', methods=['POST'])
def api_double():
    """API para duplicar premio"""
    data = request.json or {}
    user_id = data.get('user_id') or request.args.get('user_id')
    original_prize = data.get('original_prize', 0)
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    if not original_prize or original_prize not in ROULETTE_CONFIG['prizes']:
        return jsonify({'success': False, 'error': 'Invalid prize'}), 400
    
    success, error = double_prize(user_id, original_prize)
    
    if not success:
        return jsonify({'success': False, 'error': error or 'Error duplicando'})
    
    new_balance = get_pts_balance(user_id)
    
    return jsonify({
        'success': True,
        'doubled_prize': original_prize * 2,
        'new_balance': new_balance
    })


@roulette_pts_bp.route('/api/roulette-pts/status', methods=['GET'])
def api_status():
    """API para obtener estado de la ruleta"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    status = get_roulette_status(user_id)
    pts_balance = get_pts_balance(user_id)
    
    if not status:
        return jsonify({'success': False, 'error': 'Error getting status'})
    
    return jsonify({
        'success': True,
        'can_spin': status['can_spin'],
        'remaining_seconds': status['remaining_seconds'],
        'next_spin_timestamp': status['next_spin_timestamp'],
        'total_spins': status['total_spins'],
        'total_pts_won': status['total_pts_won'],
        'pts_balance': pts_balance
    })
