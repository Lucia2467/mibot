"""
adsgram_boost.py - Sistema de Boost de Minería x2 con AdsGram
======================================================
- NO paga dinero directo
- Solo activa boost x2 por 30 minutos
- Validación SOLO en backend
- AdsGram Block ID: 20479
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN DEL BOOST
# ============================================
ADSGRAM_BOOST_CONFIG = {
    'block_id': 20479,
    'boost_multiplier': 2.0,       # x2
    'boost_duration_minutes': 60,   # 30 minutos
    'cooldown_minutes': 5,          # 5 min entre anuncios
    'max_daily_boosts': 3,          # Máximo 6 boosts por día
    'min_user_id': 100000           # Ignorar IDs pequeños (tests de AdsGram)
}

# Blueprint
adsgram_boost_bp = Blueprint('adsgram_boost', __name__)

# ============================================
# FUNCIONES DE BASE DE DATOS
# ============================================

def init_adsgram_boost_tables():
    """Crear tabla de boosts si no existe"""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mining_boosts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    multiplier FLOAT DEFAULT 2.0,
                    activated_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    source VARCHAR(50) DEFAULT 'adsgram',
                    INDEX idx_user_expires (user_id, expires_at),
                    INDEX idx_expires (expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS adsgram_boost_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    activated_at DATETIME NOT NULL,
                    boost_date DATE NOT NULL,
                    INDEX idx_user_date (user_id, boost_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            logger.info("✅ Tablas de AdsGram Boost inicializadas")
    except Exception as e:
        logger.error(f"❌ Error creando tablas de boost: {e}")


def get_active_boost(user_id):
    """Obtener boost activo del usuario (si existe)"""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT multiplier, expires_at
                FROM mining_boosts
                WHERE user_id = %s AND expires_at > NOW()
                ORDER BY expires_at DESC
                LIMIT 1
            """, (str(user_id),))

            result = cursor.fetchone()
            if result:
                return {
                    'active': True,
                    'multiplier': float(result['multiplier']),
                    'expires_at': result['expires_at']
                }
    except Exception as e:
        logger.error(f"Error obteniendo boost activo: {e}")

    return {'active': False, 'multiplier': 1.0, 'expires_at': None}


def get_boost_multiplier(user_id):
    """Obtener el multiplicador actual del usuario (1.0 si no tiene boost)"""
    boost = get_active_boost(user_id)
    return boost['multiplier'] if boost['active'] else 1.0


def count_daily_boosts(user_id):
    """Contar cuántos boosts ha usado el usuario hoy"""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM adsgram_boost_history
                WHERE user_id = %s AND boost_date = %s
            """, (str(user_id), today))

            result = cursor.fetchone()
            return int(result['count']) if result else 0
    except Exception as e:
        logger.error(f"Error contando boosts diarios: {e}")
        return 0


def get_last_boost_time(user_id):
    """Obtener la hora del último boost activado"""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT activated_at
                FROM adsgram_boost_history
                WHERE user_id = %s
                ORDER BY activated_at DESC
                LIMIT 1
            """, (str(user_id),))

            result = cursor.fetchone()
            if result:
                return result['activated_at']
    except Exception as e:
        logger.error(f"Error obteniendo último boost: {e}")

    return None


def can_activate_boost(user_id):
    """Verificar si el usuario puede activar un boost"""
    config = ADSGRAM_BOOST_CONFIG

    # Verificar límite diario
    daily_count = count_daily_boosts(user_id)
    if daily_count >= config['max_daily_boosts']:
        return False, f"Límite diario alcanzado ({config['max_daily_boosts']} boosts)"

    # Verificar cooldown
    last_boost = get_last_boost_time(user_id)
    if last_boost:
        cooldown_end = last_boost + timedelta(minutes=config['cooldown_minutes'])
        if datetime.now() < cooldown_end:
            remaining = (cooldown_end - datetime.now()).seconds
            return False, f"Cooldown activo. Espera {remaining // 60}m {remaining % 60}s"

    # Verificar si ya tiene boost activo
    active_boost = get_active_boost(user_id)
    if active_boost['active']:
        return False, "Ya tienes un boost activo"

    return True, "OK"


def activate_boost(user_id):
    """Activar boost x2 por 30 minutos"""
    from db import get_cursor

    config = ADSGRAM_BOOST_CONFIG

    # Verificar si puede activar
    can_activate, reason = can_activate_boost(user_id)
    if not can_activate:
        return False, reason

    try:
        now = datetime.now()
        expires = now + timedelta(minutes=config['boost_duration_minutes'])
        today = now.strftime('%Y-%m-%d')

        with get_cursor() as cursor:
            # Insertar boost activo
            cursor.execute("""
                INSERT INTO mining_boosts (user_id, multiplier, activated_at, expires_at, source)
                VALUES (%s, %s, %s, %s, 'adsgram')
            """, (str(user_id), config['boost_multiplier'], now, expires))

            # Registrar en historial
            cursor.execute("""
                INSERT INTO adsgram_boost_history (user_id, activated_at, boost_date)
                VALUES (%s, %s, %s)
            """, (str(user_id), now, today))

        # Agregar PTS por activar boost (15 PTS)
        pts_reward = 15  # PTS por activar boost x2
        pts_added = False
        try:
            from onclicka_pts_system import add_pts
            success_pts, msg_pts = add_pts(user_id, pts_reward, 'boost_activated', 'Boost x2 activado')
            if success_pts:
                pts_added = True
                logger.info(f"✅ [AdsGram Boost] +{pts_reward} PTS agregados a {user_id}")
            else:
                logger.warning(f"⚠️ [AdsGram Boost] No se pudieron agregar PTS: {msg_pts}")
        except Exception as pts_error:
            logger.warning(f"⚠️ [AdsGram Boost] Error agregando PTS: {pts_error}")
            import traceback
            traceback.print_exc()

        logger.info(f"✅ [AdsGram Boost] User {user_id} activó boost x{config['boost_multiplier']} hasta {expires}")

        # Mensaje con PTS si se agregaron
        if pts_added:
            return True, f"Boost x{int(config['boost_multiplier'])} activado por {config['boost_duration_minutes']} minutos +{pts_reward} PTS"
        return True, f"Boost x{int(config['boost_multiplier'])} activado por {config['boost_duration_minutes']} minutos"

    except Exception as e:
        logger.error(f"❌ Error activando boost: {e}")
        return False, "Error al activar boost"


def get_boost_status(user_id):
    """Obtener estado completo del boost para el frontend"""
    config = ADSGRAM_BOOST_CONFIG
    active_boost = get_active_boost(user_id)
    daily_count = count_daily_boosts(user_id)
    can_activate, reason = can_activate_boost(user_id)

    # Calcular tiempo restante de cooldown
    cooldown_remaining = 0
    last_boost = get_last_boost_time(user_id)
    if last_boost:
        cooldown_end = last_boost + timedelta(minutes=config['cooldown_minutes'])
        if datetime.now() < cooldown_end:
            cooldown_remaining = int((cooldown_end - datetime.now()).total_seconds())

    # Calcular tiempo restante de boost activo
    boost_remaining = 0
    if active_boost['active'] and active_boost['expires_at']:
        boost_remaining = max(0, int((active_boost['expires_at'] - datetime.now()).total_seconds()))

    return {
        'has_active_boost': active_boost['active'],
        'multiplier': active_boost['multiplier'],
        'boost_remaining_seconds': boost_remaining,
        'daily_boosts_used': daily_count,
        'daily_boosts_limit': config['max_daily_boosts'],
        'can_activate': can_activate,
        'cooldown_remaining_seconds': cooldown_remaining,
        'reason': reason if not can_activate else None
    }


# ============================================
# ENDPOINT DE REWARD (llamado por AdsGram)
# ============================================

@adsgram_boost_bp.route('/adsgram/reward', methods=['GET', 'POST'])
def adsgram_reward():
    """
    Endpoint que AdsGram llama cuando el usuario completa el video.

    IMPORTANTE: AdsGram envía el userId como query string simple, no como key=value.
    Ejemplo: /adsgram/reward?123456789

    Se debe leer con: request.query_string.decode()
    """
    config = ADSGRAM_BOOST_CONFIG

    # Obtener user_id del query string (formato especial de AdsGram)
    query_string = request.query_string.decode('utf-8')

    # El query string puede ser: "123456789" o "[userId]" o vacío
    user_id = query_string.strip()

    # Limpiar posibles caracteres extra
    user_id = user_id.replace('[', '').replace(']', '').strip()

    logger.info(f"[AdsGram Reward] Query string raw: '{query_string}' -> user_id: '{user_id}'")

    # Validar user_id
    if not user_id:
        logger.warning("[AdsGram Reward] No user_id provided")
        return jsonify({'success': False, 'error': 'No user_id'}), 400

    # Verificar que sea un ID numérico válido
    try:
        user_id_int = int(user_id)
    except ValueError:
        logger.warning(f"[AdsGram Reward] Invalid user_id format: {user_id}")
        return jsonify({'success': False, 'error': 'Invalid user_id format'}), 400

    # Ignorar IDs pequeños (tests automáticos de AdsGram)
    if user_id_int < config['min_user_id']:
        logger.info(f"[AdsGram Reward] Ignoring test user_id: {user_id}")
        return jsonify({'success': True, 'message': 'Test ID ignored'}), 200

    # Verificar que el usuario existe
    from database import get_user
    user = get_user(user_id)

    if not user:
        logger.warning(f"[AdsGram Reward] User not found: {user_id}")
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Verificar que no esté baneado
    if user.get('banned'):
        logger.warning(f"[AdsGram Reward] Banned user attempted boost: {user_id}")
        return jsonify({'success': False, 'error': 'User banned'}), 403

    # Activar el boost
    success, message = activate_boost(user_id)

    if success:
        logger.info(f"[AdsGram Reward] Boost activated for user {user_id}")
        return jsonify({
            'success': True,
            'message': message,
            'boost': {
                'multiplier': config['boost_multiplier'],
                'duration_minutes': config['boost_duration_minutes']
            }
        }), 200
    else:
        logger.info(f"[AdsGram Reward] Boost denied for user {user_id}: {message}")
        return jsonify({
            'success': False,
            'error': message
        }), 400


# ============================================
# ENDPOINTS API PARA EL FRONTEND
# ============================================

@adsgram_boost_bp.route('/api/boost/status', methods=['GET'])
def api_boost_status():
    """Obtener estado del boost para mostrar en frontend"""
    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    status = get_boost_status(user_id)
    return jsonify({
        'success': True,
        **status
    })


@adsgram_boost_bp.route('/api/boost/can-activate', methods=['GET'])
def api_can_activate():
    """Verificar si el usuario puede activar boost (antes de mostrar anuncio)"""
    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    can_activate, reason = can_activate_boost(user_id)

    return jsonify({
        'success': True,
        'can_activate': can_activate,
        'reason': reason if not can_activate else None,
        'block_id': ADSGRAM_BOOST_CONFIG['block_id']
    })


@adsgram_boost_bp.route('/api/boost/activate', methods=['POST'])
def api_activate_boost():
    """
    Endpoint para activar el boost directamente desde el frontend.
    Se llama después de que el usuario vea el anuncio de AdsGram.
    """
    user_id = request.args.get('user_id') or (request.json.get('user_id') if request.json else None)

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    # Verificar que el usuario existe
    from database import get_user
    user = get_user(user_id)

    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Verificar que no esté baneado
    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    # Activar el boost
    success, message = activate_boost(user_id)

    if success:
        logger.info(f"[API Boost] Boost activated for user {user_id}")
        return jsonify({
            'success': True,
            'message': message,
            'boost': {
                'multiplier': ADSGRAM_BOOST_CONFIG['boost_multiplier'],
                'duration_minutes': ADSGRAM_BOOST_CONFIG['boost_duration_minutes'],
                'pts_earned': 15
            }
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 400


# ============================================
# FUNCIONES PARA INTEGRAR CON MINERÍA
# ============================================

def apply_boost_to_rate(user_id, base_rate):
    """
    Aplicar multiplicador de boost a la tasa de minería.

    IMPORTANTE: Esta función NO modifica la lógica de minería,
    solo multiplica el resultado final si hay boost activo.
    """
    multiplier = get_boost_multiplier(user_id)
    return base_rate * multiplier


def cleanup_expired_boosts():
    """Limpiar boosts expirados de la base de datos"""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM mining_boosts
                WHERE expires_at < NOW()
            """)
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"[AdsGram Boost] Limpiados {deleted} boosts expirados")
    except Exception as e:
        logger.error(f"Error limpiando boosts: {e}")
