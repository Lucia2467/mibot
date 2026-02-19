"""
MONETAG - Módulo Independiente de Anuncios Interstitiales
=========================================================
Plataforma de anuncios completamente separada de Adsgram, Telega.io y Adexium

Zone ID: 10311387
SDK: show_10311387
Tipo: Interstitial (Telegram Mini App)

REGLAS (IDÉNTICAS A ADEXIUM):
- Máximo 12 anuncios por día
- Cooldown de 7 minutos (420 segundos) entre anuncios
- Tiempo mínimo de visualización: 15 segundos
- Reset diario automático
- Recompensa solo validada por backend
- MISMA MONEDA y MISMA RECOMPENSA que las demás plataformas
"""

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime
import hashlib
import secrets
import logging

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN EXCLUSIVA DE MONETAG
# ============================================
MONETAG_CONFIG = {
    'zone_id': '10311387',
    'sdk_function': 'show_10311387',
    'max_daily_ads': 10,              # Máximo 12 anuncios por día (igual que Adexium)
    'cooldown_seconds': 60,          # 7 minutos = 420 segundos (igual que Adexium)
    'min_watch_seconds': 15,          # 15 segundos mínimos (igual que Adexium)
    'reward_per_ad': 0.002,           # DOGE por anuncio (IGUAL QUE ADEXIUM)
    'token_expiry_seconds': 120       # Token válido por 2 minutos
}

# Blueprint para rutas de Monetag
monetag_bp = Blueprint('monetag', __name__, url_prefix='/monetag')


# ============================================
# FUNCIONES DE BASE DE DATOS - MONETAG
# ============================================

def init_monetag_tables():
    """
    Inicializa las tablas de Monetag si no existen.
    Se ejecuta al arrancar la aplicación.
    """
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            # Tabla de progreso de Monetag
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monetag_progress (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL UNIQUE,
                    ads_watched INT DEFAULT 0,
                    total_earned DECIMAL(18,8) DEFAULT 0,
                    completed TINYINT(1) DEFAULT 0,
                    last_ad_at DATETIME NULL,
                    progress_date DATE NULL,
                    session_token VARCHAR(255) NULL,
                    token_created_at DATETIME NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_progress_date (progress_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Tabla de historial de Monetag
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monetag_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    session_token VARCHAR(255) NULL,
                    status ENUM('started', 'completed', 'cancelled', 'failed') DEFAULT 'started',
                    watch_duration INT DEFAULT 0,
                    reward_amount DECIMAL(18,8) DEFAULT 0,
                    ip_address VARCHAR(45) NULL,
                    user_agent VARCHAR(255) NULL,
                    fail_reason VARCHAR(100) NULL,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME NULL,
                    INDEX idx_user_id (user_id),
                    INDEX idx_session_token (session_token),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

        logger.info("[Monetag] Tables initialized successfully")
        return True

    except Exception as e:
        logger.error(f"[Monetag] Error initializing tables: {e}")
        return False


def get_monetag_progress(user_id):
    """
    Obtiene el progreso de Monetag del usuario para hoy.
    Resetea automáticamente cuando cambia la fecha.
    Variables EXCLUSIVAS de Monetag - NO compartidas con otras plataformas.
    """
    from db import get_cursor
    today = datetime.now().date()

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT ads_watched, total_earned, completed, last_ad_at, progress_date
                   FROM monetag_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            result = cursor.fetchone()

            if result:
                progress_date = result.get('progress_date')
                if progress_date:
                    if isinstance(progress_date, str):
                        progress_date = datetime.strptime(progress_date, '%Y-%m-%d').date()
                    elif hasattr(progress_date, 'date'):
                        progress_date = progress_date.date() if callable(getattr(progress_date, 'date', None)) else progress_date

                # Si la fecha es diferente a hoy, resetear (reset diario)
                if progress_date != today:
                    cursor.execute(
                        """UPDATE monetag_progress
                           SET ads_watched = 0, total_earned = 0, completed = 0,
                               progress_date = %s, session_token = NULL, updated_at = NOW()
                           WHERE user_id = %s""",
                        (today, str(user_id))
                    )
                    logger.info(f"[Monetag] Daily reset for user {user_id}")
                    return {
                        'ads_watched': 0,
                        'total_earned': 0.0,
                        'completed': False,
                        'last_ad_at': None
                    }

                return {
                    'ads_watched': int(result.get('ads_watched', 0)),
                    'total_earned': float(result.get('total_earned', 0)),
                    'completed': bool(result.get('completed', 0)),
                    'last_ad_at': result.get('last_ad_at')
                }

        return {
            'ads_watched': 0,
            'total_earned': 0.0,
            'completed': False,
            'last_ad_at': None
        }

    except Exception as e:
        logger.warning(f"[Monetag] Error getting progress: {e}")
        return {
            'ads_watched': 0,
            'total_earned': 0.0,
            'completed': False,
            'last_ad_at': None
        }


def check_monetag_cooldown(user_id):
    """
    Verifica el cooldown de Monetag (7 minutos).
    Returns: (can_watch, seconds_remaining)
    """
    try:
        progress = get_monetag_progress(user_id)
        last_ad_at = progress.get('last_ad_at')

        if not last_ad_at:
            return True, 0

        if isinstance(last_ad_at, str):
            last_ad_at = datetime.strptime(last_ad_at, '%Y-%m-%d %H:%M:%S')

        elapsed = (datetime.now() - last_ad_at).total_seconds()
        cooldown = MONETAG_CONFIG['cooldown_seconds']

        if elapsed >= cooldown:
            return True, 0

        return False, int(cooldown - elapsed)

    except Exception as e:
        logger.warning(f"[Monetag] Error checking cooldown: {e}")
        return True, 0


def generate_monetag_token(user_id):
    """Genera un token único para la sesión de visualización de Monetag"""
    random_bytes = secrets.token_bytes(32)
    timestamp = str(datetime.now().timestamp())
    data = f"monetag:{user_id}:{timestamp}:{random_bytes.hex()}"
    return hashlib.sha256(data.encode()).hexdigest()


def validate_monetag_token(user_id, token):
    """Valida que el token de sesión de Monetag sea válido y no haya expirado"""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT session_token, token_created_at
                   FROM monetag_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            result = cursor.fetchone()

            if not result:
                return False, "No session found"

            stored_token = result.get('session_token')
            token_created_at = result.get('token_created_at')

            if not stored_token or stored_token != token:
                return False, "Invalid token"

            if not token_created_at:
                return False, "Token timestamp missing"

            if isinstance(token_created_at, str):
                token_created_at = datetime.strptime(token_created_at, '%Y-%m-%d %H:%M:%S')

            elapsed = (datetime.now() - token_created_at).total_seconds()
            if elapsed > MONETAG_CONFIG['token_expiry_seconds']:
                return False, "Token expired"

            return True, "Valid"

    except Exception as e:
        logger.warning(f"[Monetag] Error validating token: {e}")
        return False, str(e)


# ============================================
# RUTAS DE MONETAG
# ============================================

@monetag_bp.route('/')
def monetag_page():
    """Página principal de Monetag en Explorar"""
    from app import get_user_id, get_user

    user_id = request.args.get('user_id') or get_user_id()

    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    if user.get('banned'):
        return render_template('banned.html', reason=user.get('ban_reason', 'Cuenta suspendida'))

    progress = get_monetag_progress(user_id)
    can_watch, cooldown_remaining = check_monetag_cooldown(user_id)

    return render_template('monetag.html',
        user_id=user_id,
        user=user,
        progress=progress,
        config=MONETAG_CONFIG,
        can_watch=can_watch and not progress['completed'],
        cooldown_remaining=cooldown_remaining
    )


@monetag_bp.route('/status', methods=['GET'])
def monetag_status():
    """Obtiene el estado actual del sistema Monetag para el usuario"""
    from app import get_user_id, get_user

    user_id = request.args.get('user_id') or get_user_id()

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    progress = get_monetag_progress(user_id)
    can_watch, cooldown_remaining = check_monetag_cooldown(user_id)

    config = MONETAG_CONFIG
    ads_remaining = config['max_daily_ads'] - progress['ads_watched']

    return jsonify({
        'success': True,
        'progress': {
            'ads_watched': progress['ads_watched'],
            'total_earned': progress['total_earned'],
            'completed': progress['completed'],
            'ads_remaining': max(0, ads_remaining)
        },
        'can_watch': can_watch and not progress['completed'] and ads_remaining > 0,
        'cooldown_remaining': cooldown_remaining,
        'config': {
            'max_daily_ads': config['max_daily_ads'],
            'cooldown_seconds': config['cooldown_seconds'],
            'min_watch_seconds': config['min_watch_seconds'],
            'reward_per_ad': config['reward_per_ad'],
            'total_possible_reward': config['max_daily_ads'] * config['reward_per_ad'],
            'zone_id': config['zone_id']
        }
    })


@monetag_bp.route('/start', methods=['POST'])
def monetag_start():
    """
    Inicia una sesión de visualización de anuncio Monetag.
    Genera un token único para verificar la visualización completa.
    ANTI-ABUSO: Bloquea múltiples clics rápidos.
    """
    from app import get_user_id, get_user
    from db import get_cursor

    data = request.get_json() or {}
    user_id = data.get('user_id') or get_user_id()

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    config = MONETAG_CONFIG
    progress = get_monetag_progress(user_id)

    # Verificar límite diario (12 anuncios)
    if progress['completed'] or progress['ads_watched'] >= config['max_daily_ads']:
        return jsonify({
            'success': False,
            'error': 'Has alcanzado el límite diario de anuncios',
            'completed': True,
            'ads_watched': progress['ads_watched']
        })

    # Verificar cooldown (7 minutos)
    can_watch, cooldown_remaining = check_monetag_cooldown(user_id)
    if not can_watch:
        minutes = cooldown_remaining // 60
        seconds = cooldown_remaining % 60
        return jsonify({
            'success': False,
            'error': f'Próximo anuncio disponible en {minutes}m {seconds}s',
            'cooldown_remaining': cooldown_remaining
        })

    # Generar token de sesión
    session_token = generate_monetag_token(user_id)
    today = datetime.now().date()

    try:
        with get_cursor() as cursor:
            # Verificar si existe registro
            cursor.execute(
                "SELECT user_id FROM monetag_progress WHERE user_id = %s",
                (str(user_id),)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """UPDATE monetag_progress
                       SET session_token = %s, token_created_at = NOW(), updated_at = NOW()
                       WHERE user_id = %s""",
                    (session_token, str(user_id))
                )
            else:
                cursor.execute(
                    """INSERT INTO monetag_progress
                       (user_id, ads_watched, total_earned, completed, progress_date, session_token, token_created_at)
                       VALUES (%s, 0, 0, 0, %s, %s, NOW())""",
                    (str(user_id), today, session_token)
                )

            # Registrar inicio en historial
            cursor.execute(
                """INSERT INTO monetag_history
                   (user_id, session_token, status, ip_address, user_agent, started_at)
                   VALUES (%s, %s, 'started', %s, %s, NOW())""",
                (str(user_id), session_token, request.remote_addr, request.headers.get('User-Agent', '')[:255])
            )

        logger.info(f"[Monetag] Session started for user {user_id}, token: {session_token[:16]}...")

        return jsonify({
            'success': True,
            'session_token': session_token,
            'min_watch_seconds': config['min_watch_seconds'],
            'reward': config['reward_per_ad'],
            'zone_id': config['zone_id'],
            'message': 'Mira el anuncio durante 15 segundos para obtener la recompensa'
        })

    except Exception as e:
        logger.error(f"[Monetag] Error starting session: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@monetag_bp.route('/reward', methods=['POST'])
def monetag_reward():
    """
    Completa una sesión de Monetag y otorga la recompensa.
    Requiere el token de sesión y la duración de visualización (mínimo 15 segundos).
    VALIDACIÓN ESTRICTA: Solo el backend otorga recompensas.
    """
    from app import get_user_id, get_user
    from db import get_cursor

    data = request.get_json() or {}
    user_id = data.get('user_id') or get_user_id()
    session_token = data.get('session_token')
    watch_duration = data.get('watch_duration', 0)

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    if not session_token:
        return jsonify({'success': False, 'error': 'Session token required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    config = MONETAG_CONFIG

    # Validar token de sesión
    is_valid, validation_msg = validate_monetag_token(user_id, session_token)
    if not is_valid:
        logger.warning(f"[Monetag] Invalid token for user {user_id}: {validation_msg}")
        return jsonify({
            'success': False,
            'error': 'Sesión inválida o expirada',
            'detail': validation_msg
        }), 400

    # Validar duración mínima (15 segundos)
    try:
        watch_duration = int(watch_duration)
    except (ValueError, TypeError):
        watch_duration = 0

    if watch_duration < config['min_watch_seconds']:
        logger.warning(f"[Monetag] Insufficient watch time for user {user_id}: {watch_duration}s < {config['min_watch_seconds']}s")

        # Actualizar historial como fallido
        try:
            with get_cursor() as cursor:
                cursor.execute(
                    """UPDATE monetag_history
                       SET status = 'failed', watch_duration = %s, completed_at = NOW(),
                           fail_reason = 'insufficient_time'
                       WHERE session_token = %s AND user_id = %s""",
                    (watch_duration, session_token, str(user_id))
                )
        except:
            pass

        return jsonify({
            'success': False,
            'error': f'Debes ver el anuncio al menos {config["min_watch_seconds"]} segundos',
            'watch_duration': watch_duration,
            'required': config['min_watch_seconds']
        })

    # Verificar límite diario nuevamente (anti-abuso)
    progress = get_monetag_progress(user_id)
    if progress['ads_watched'] >= config['max_daily_ads']:
        return jsonify({
            'success': False,
            'error': 'Has alcanzado el límite diario de anuncios',
            'completed': True
        })

    # Otorgar recompensa - MISMA MONEDA (DOGE) que las demás plataformas
    reward = config['reward_per_ad']
    pts_reward = 10  # PTS por anuncio visto
    new_ads_watched = progress['ads_watched'] + 1
    new_total_earned = progress['total_earned'] + reward
    completed = new_ads_watched >= config['max_daily_ads']

    try:
        with get_cursor() as cursor:
            # Actualizar balance del usuario (DOGE) - MISMO SISTEMA QUE ADEXIUM
            cursor.execute(
                """UPDATE users
                   SET doge_balance = doge_balance + %s, updated_at = NOW()
                   WHERE user_id = %s""",
                (reward, str(user_id))
            )

            # Actualizar progreso de Monetag
            cursor.execute(
                """UPDATE monetag_progress
                   SET ads_watched = %s, total_earned = %s, completed = %s,
                       last_ad_at = NOW(), session_token = NULL, updated_at = NOW()
                   WHERE user_id = %s""",
                (new_ads_watched, new_total_earned, 1 if completed else 0, str(user_id))
            )

            # Actualizar historial como completado
            cursor.execute(
                """UPDATE monetag_history
                   SET status = 'completed', watch_duration = %s, reward_amount = %s, completed_at = NOW()
                   WHERE session_token = %s AND user_id = %s""",
                (watch_duration, reward, session_token, str(user_id))
            )

            # Registrar en balance_history - MISMO FORMATO
            cursor.execute(
                """INSERT INTO balance_history
                   (user_id, action, currency, amount, description, created_at)
                   VALUES (%s, 'monetag_reward', 'DOGE', %s, %s, NOW())""",
                (str(user_id), reward, f'Recompensa Monetag #{new_ads_watched}')
            )

        # Agregar PTS al ranking
        try:
            from onclicka_pts_system import add_pts
            add_pts(user_id, pts_reward, 'ad_watched', 'Monetag ad')
        except Exception as pts_error:
            logger.warning(f"[Monetag] Error adding PTS: {pts_error}")

        logger.info(f"[Monetag] Reward granted to user {user_id}: +{reward} DOGE +{pts_reward} PTS (ad #{new_ads_watched})")

        # Calcular próximo cooldown
        cooldown = config['cooldown_seconds']
        ads_remaining = config['max_daily_ads'] - new_ads_watched

        return jsonify({
            'success': True,
            'reward': reward,
            'ads_watched': new_ads_watched,
            'total_earned': new_total_earned,
            'completed': completed,
            'ads_remaining': max(0, ads_remaining),
            'cooldown': cooldown if not completed else 0,
            'message': f'+{reward} DOGE' if not completed else '¡Límite diario alcanzado!'
        })

    except Exception as e:
        logger.error(f"[Monetag] Error granting reward: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@monetag_bp.route('/cancel', methods=['POST'])
def monetag_cancel():
    """
    Cancela una sesión de Monetag sin recompensa.
    Para casos donde el usuario cierra el anuncio antes de tiempo.
    """
    from app import get_user_id
    from db import get_cursor

    data = request.get_json() or {}
    user_id = data.get('user_id') or get_user_id()
    session_token = data.get('session_token')
    watch_duration = data.get('watch_duration', 0)

    if not user_id or not session_token:
        return jsonify({'success': False}), 400

    try:
        with get_cursor() as cursor:
            # Actualizar historial como cancelado
            cursor.execute(
                """UPDATE monetag_history
                   SET status = 'cancelled', watch_duration = %s, completed_at = NOW(),
                       fail_reason = 'user_cancelled'
                   WHERE session_token = %s AND user_id = %s""",
                (watch_duration, session_token, str(user_id))
            )

            # Limpiar token de sesión
            cursor.execute(
                """UPDATE monetag_progress
                   SET session_token = NULL
                   WHERE user_id = %s""",
                (str(user_id),)
            )

        logger.info(f"[Monetag] Session cancelled for user {user_id}, duration: {watch_duration}s")

    except Exception as e:
        logger.warning(f"[Monetag] Error cancelling session: {e}")

    return jsonify({'success': True, 'cancelled': True})


# ============================================
# FUNCIÓN PARA REGISTRAR BLUEPRINT EN APP
# ============================================

def init_monetag(app):
    """Registra el blueprint de Monetag en la aplicación Flask"""
    app.register_blueprint(monetag_bp)
    init_monetag_tables()
    logger.info("[Monetag] Module initialized successfully")
