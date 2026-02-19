"""
GIGAPUB - Módulo de Anuncios Reward-Based
=========================================
Proveedor de anuncios on-demand (rewarded)

Placement: "principal"
SDK: window.showGiga("principal")
Tipo: Reward-based (on-demand, solo se muestra al hacer clic)

REGLAS (IDÉNTICAS A LAS DEMÁS PLATAFORMAS):
- Máximo 12 anuncios por día
- Cooldown de 40 segundos entre anuncios
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
# CONFIGURACIÓN EXCLUSIVA DE GIGAPUB
# ============================================
GIGAPUB_CONFIG = {
    'placement': 'principal',
    'max_daily_ads': 12,              # Máximo 12 anuncios por día
    'cooldown_seconds': 40,           # 40 segundos de cooldown
    'min_watch_seconds': 15,          # 15 segundos mínimos
    'reward_per_ad': 0.002,           # DOGE por anuncio
    'token_expiry_seconds': 120       # Token válido por 2 minutos
}

# Blueprint para rutas de GigaPub
gigapub_bp = Blueprint('gigapub', __name__, url_prefix='/gigapub')


# ============================================
# FUNCIONES DE BASE DE DATOS - GIGAPUB
# ============================================

def init_gigapub_tables():
    """
    Inicializa las tablas de GigaPub si no existen.
    Se ejecuta al arrancar la aplicación.
    """
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            # Tabla de progreso de GigaPub
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gigapub_progress (
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

            # Tabla de historial de GigaPub
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gigapub_history (
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

        logger.info("[GigaPub] Tables initialized successfully")
        return True

    except Exception as e:
        logger.error(f"[GigaPub] Error initializing tables: {e}")
        return False


def get_gigapub_progress(user_id):
    """
    Obtiene el progreso de GigaPub del usuario para hoy.
    Resetea automáticamente cuando cambia la fecha.
    """
    from db import get_cursor
    today = datetime.now().date()

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT ads_watched, total_earned, completed, last_ad_at, progress_date
                   FROM gigapub_progress WHERE user_id = %s""",
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
                        """UPDATE gigapub_progress
                           SET ads_watched = 0, total_earned = 0, completed = 0,
                               progress_date = %s, session_token = NULL, updated_at = NOW()
                           WHERE user_id = %s""",
                        (today, str(user_id))
                    )
                    logger.info(f"[GigaPub] Daily reset for user {user_id}")
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
        logger.warning(f"[GigaPub] Error getting progress: {e}")
        return {
            'ads_watched': 0,
            'total_earned': 0.0,
            'completed': False,
            'last_ad_at': None
        }


def check_gigapub_cooldown(user_id):
    """
    Verifica el cooldown de GigaPub.
    Returns: (can_watch, seconds_remaining)
    """
    try:
        progress = get_gigapub_progress(user_id)
        last_ad_at = progress.get('last_ad_at')

        if not last_ad_at:
            return True, 0

        if isinstance(last_ad_at, str):
            last_ad_at = datetime.strptime(last_ad_at, '%Y-%m-%d %H:%M:%S')

        elapsed = (datetime.now() - last_ad_at).total_seconds()
        cooldown = GIGAPUB_CONFIG['cooldown_seconds']

        if elapsed >= cooldown:
            return True, 0

        return False, int(cooldown - elapsed)

    except Exception as e:
        logger.warning(f"[GigaPub] Error checking cooldown: {e}")
        return True, 0


def generate_gigapub_token(user_id):
    """Genera un token único para la sesión de visualización de GigaPub"""
    random_bytes = secrets.token_bytes(32)
    timestamp = str(datetime.now().timestamp())
    data = f"gigapub:{user_id}:{timestamp}:{random_bytes.hex()}"
    return hashlib.sha256(data.encode()).hexdigest()


def validate_gigapub_token(user_id, token):
    """Valida que el token de sesión de GigaPub sea válido y no haya expirado"""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT session_token, token_created_at
                   FROM gigapub_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            result = cursor.fetchone()

            if not result:
                return False, "No session found"

            stored_token = result.get('session_token')
            token_created = result.get('token_created_at')

            if not stored_token or stored_token != token:
                return False, "Invalid token"

            if token_created:
                if isinstance(token_created, str):
                    token_created = datetime.strptime(token_created, '%Y-%m-%d %H:%M:%S')
                elapsed = (datetime.now() - token_created).total_seconds()
                if elapsed > GIGAPUB_CONFIG['token_expiry_seconds']:
                    return False, "Token expired"

            return True, "Valid"

    except Exception as e:
        logger.warning(f"[GigaPub] Error validating token: {e}")
        return False, str(e)


# ============================================
# RUTAS DE GIGAPUB
# ============================================

@gigapub_bp.route('/')
def gigapub_page():
    """Página principal de GigaPub"""
    from app import get_user_id, get_user

    user_id = request.args.get('user_id') or get_user_id()

    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    if user.get('banned'):
        return render_template('banned.html', user=user)

    progress = get_gigapub_progress(user_id)
    config = GIGAPUB_CONFIG

    can_watch, cooldown_remaining = check_gigapub_cooldown(user_id)

    return render_template(
        'gigapub.html',
        user_id=user_id,
        user=user,
        progress=progress,
        config=config,
        can_watch=can_watch,
        cooldown_remaining=cooldown_remaining
    )


@gigapub_bp.route('/start', methods=['POST'])
def gigapub_start():
    """
    Inicia una sesión de GigaPub.
    Genera un token de sesión y verifica elegibilidad.
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

    config = GIGAPUB_CONFIG
    progress = get_gigapub_progress(user_id)

    # Verificar límite diario
    if progress['ads_watched'] >= config['max_daily_ads']:
        return jsonify({
            'success': False,
            'error': 'Daily limit reached',
            'completed': True,
            'ads_watched': progress['ads_watched']
        })

    # Verificar cooldown
    can_watch, cooldown_remaining = check_gigapub_cooldown(user_id)
    if not can_watch:
        return jsonify({
            'success': False,
            'error': 'Cooldown active',
            'cooldown': cooldown_remaining
        })

    # Generar token de sesión
    session_token = generate_gigapub_token(user_id)

    try:
        with get_cursor() as cursor:
            # Actualizar o crear registro de progreso con el token
            cursor.execute(
                """INSERT INTO gigapub_progress (user_id, progress_date, session_token, token_created_at)
                   VALUES (%s, CURDATE(), %s, NOW())
                   ON DUPLICATE KEY UPDATE session_token = %s, token_created_at = NOW()""",
                (str(user_id), session_token, session_token)
            )

            # Registrar en historial
            cursor.execute(
                """INSERT INTO gigapub_history
                   (user_id, session_token, status, ip_address, user_agent)
                   VALUES (%s, %s, 'started', %s, %s)""",
                (str(user_id), session_token,
                 request.remote_addr,
                 request.headers.get('User-Agent', '')[:255])
            )

        logger.info(f"[GigaPub] Session started for user {user_id}")

        return jsonify({
            'success': True,
            'session_token': session_token,
            'min_watch_seconds': config['min_watch_seconds'],
            'reward': config['reward_per_ad'],
            'placement': config['placement'],
            'message': 'Mira el anuncio durante 15 segundos para obtener la recompensa'
        })

    except Exception as e:
        logger.error(f"[GigaPub] Error starting session: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@gigapub_bp.route('/reward', methods=['POST'])
def gigapub_reward():
    """
    Completa una sesión de GigaPub y otorga la recompensa.
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

    config = GIGAPUB_CONFIG

    # Validar token de sesión
    is_valid, validation_msg = validate_gigapub_token(user_id, session_token)
    if not is_valid:
        logger.warning(f"[GigaPub] Invalid token for user {user_id}: {validation_msg}")
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
        logger.warning(f"[GigaPub] Insufficient watch time for user {user_id}: {watch_duration}s < {config['min_watch_seconds']}s")

        # Actualizar historial como fallido
        try:
            with get_cursor() as cursor:
                cursor.execute(
                    """UPDATE gigapub_history
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
    progress = get_gigapub_progress(user_id)
    if progress['ads_watched'] >= config['max_daily_ads']:
        return jsonify({
            'success': False,
            'error': 'Has alcanzado el límite diario de anuncios',
            'completed': True
        })

    # Otorgar recompensa - MISMA MONEDA (DOGE) que las demás plataformas
    reward = config['reward_per_ad']
    pts_reward = 5  # PTS por anuncio visto
    new_ads_watched = progress['ads_watched'] + 1
    new_total_earned = progress['total_earned'] + reward
    completed = new_ads_watched >= config['max_daily_ads']

    try:
        with get_cursor() as cursor:
            # Actualizar balance del usuario (DOGE)
            cursor.execute(
                """UPDATE users
                   SET doge_balance = doge_balance + %s, updated_at = NOW()
                   WHERE user_id = %s""",
                (reward, str(user_id))
            )

            # Actualizar progreso de GigaPub
            cursor.execute(
                """UPDATE gigapub_progress
                   SET ads_watched = %s, total_earned = %s, completed = %s,
                       last_ad_at = NOW(), session_token = NULL, updated_at = NOW()
                   WHERE user_id = %s""",
                (new_ads_watched, new_total_earned, 1 if completed else 0, str(user_id))
            )

            # Actualizar historial como completado
            cursor.execute(
                """UPDATE gigapub_history
                   SET status = 'completed', watch_duration = %s, reward_amount = %s, completed_at = NOW()
                   WHERE session_token = %s AND user_id = %s""",
                (watch_duration, reward, session_token, str(user_id))
            )

            # Registrar en balance_history
            cursor.execute(
                """INSERT INTO balance_history
                   (user_id, action, currency, amount, description, created_at)
                   VALUES (%s, 'gigapub_reward', 'DOGE', %s, %s, NOW())""",
                (str(user_id), reward, f'Recompensa GigaPub #{new_ads_watched}')
            )

        # Agregar PTS al ranking
        try:
            from onclicka_pts_system import add_pts
            add_pts(user_id, pts_reward, 'ad_watched', 'GigaPub ad')
        except Exception as pts_error:
            logger.warning(f"[GigaPub] Error adding PTS: {pts_error}")

        logger.info(f"[GigaPub] Reward granted to user {user_id}: +{reward} DOGE +{pts_reward} PTS (ad #{new_ads_watched})")

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
        logger.error(f"[GigaPub] Error granting reward: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@gigapub_bp.route('/cancel', methods=['POST'])
def gigapub_cancel():
    """
    Cancela una sesión de GigaPub sin recompensa.
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
                """UPDATE gigapub_history
                   SET status = 'cancelled', watch_duration = %s, completed_at = NOW(),
                       fail_reason = 'user_cancelled'
                   WHERE session_token = %s AND user_id = %s""",
                (watch_duration, session_token, str(user_id))
            )

            # Limpiar token de sesión
            cursor.execute(
                """UPDATE gigapub_progress
                   SET session_token = NULL
                   WHERE user_id = %s""",
                (str(user_id),)
            )

        logger.info(f"[GigaPub] Session cancelled for user {user_id}, duration: {watch_duration}s")

    except Exception as e:
        logger.warning(f"[GigaPub] Error cancelling session: {e}")

    return jsonify({'success': True, 'cancelled': True})


# ============================================
# ENDPOINT PARA GIGAPUB.HTML (Solo DOGE, no afecta tareas PTS)
# ============================================

@gigapub_bp.route('/quick-reward', methods=['POST'])
def gigapub_quick_reward():
    """
    Endpoint para gigapub.html - Solo otorga DOGE, NO afecta tareas PTS.
    """
    from db import get_cursor
    
    data = request.get_json() or {}
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    config = GIGAPUB_CONFIG
    today = datetime.now().date()
    
    try:
        with get_cursor() as cursor:
            # Verificar progreso de GigaPub
            cursor.execute(
                """SELECT ads_watched, progress_date FROM gigapub_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            gp_result = cursor.fetchone()
            
            gp_ads_watched = 0
            if gp_result:
                progress_date = gp_result.get('progress_date')
                if progress_date:
                    if isinstance(progress_date, str):
                        progress_date = datetime.strptime(progress_date, '%Y-%m-%d').date()
                    elif hasattr(progress_date, 'date'):
                        progress_date = progress_date.date() if callable(getattr(progress_date, 'date', None)) else progress_date
                    if progress_date == today:
                        gp_ads_watched = int(gp_result.get('ads_watched', 0))
            
            # Verificar límite diario
            if gp_ads_watched >= config['max_daily_ads']:
                return jsonify({
                    'success': False,
                    'error': 'Límite diario alcanzado',
                    'completed': True
                })
            
            reward = config['reward_per_ad']
            new_gp_ads = gp_ads_watched + 1
            gp_completed = new_gp_ads >= config['max_daily_ads']
            
            # Actualizar balance DOGE
            cursor.execute(
                """UPDATE users SET doge_balance = doge_balance + %s, updated_at = NOW() WHERE user_id = %s""",
                (reward, str(user_id))
            )
            
            # Actualizar/insertar progreso GigaPub
            if gp_result and gp_result.get('progress_date'):
                cursor.execute(
                    """UPDATE gigapub_progress
                       SET ads_watched = %s, total_earned = total_earned + %s, 
                           completed = %s, last_ad_at = NOW(), progress_date = %s, updated_at = NOW()
                       WHERE user_id = %s""",
                    (new_gp_ads, reward, 1 if gp_completed else 0, today, str(user_id))
                )
            else:
                cursor.execute(
                    """INSERT INTO gigapub_progress 
                       (user_id, ads_watched, total_earned, completed, last_ad_at, progress_date)
                       VALUES (%s, %s, %s, %s, NOW(), %s)
                       ON DUPLICATE KEY UPDATE 
                       ads_watched = %s, total_earned = total_earned + %s,
                       completed = %s, last_ad_at = NOW(), progress_date = %s""",
                    (str(user_id), new_gp_ads, reward, 1 if gp_completed else 0, today,
                     new_gp_ads, reward, 1 if gp_completed else 0, today)
                )
        
        logger.info(f"[GigaPub] Quick reward (DOGE only): user {user_id} +{reward} DOGE")
        
        return jsonify({
            'success': True,
            'reward': reward,
            'ads_watched': new_gp_ads,
            'completed': gp_completed
        })
        
    except Exception as e:
        logger.error(f"[GigaPub] Quick reward error: {e}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# ============================================
# ENDPOINT PARA TASKS_PTS.HTML (Solo PTS, no afecta GigaPub)
# ============================================

@gigapub_bp.route('/pts-reward', methods=['POST'])
def gigapub_pts_reward():
    """
    Endpoint para tasks_pts.html - Solo otorga PTS y cuenta para tarea de 5 anuncios.
    NO afecta el contador de gigapub.html.
    LÍMITE: 10 anuncios diarios máximo.
    """
    from db import get_cursor
    
    # Límite diario de anuncios para PTS
    DAILY_AD_LIMIT = 10
    
    data = request.get_json() or {}
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now()
    
    try:
        with get_cursor() as cursor:
            # PRIMERO: Verificar cuántos anuncios ha visto hoy
            cursor.execute("""
                SELECT ads_watched FROM ad_tasks_progress 
                WHERE user_id = %s AND task_type = 'watch_5_ads' AND task_date = %s
            """, (str(user_id), today_str))
            current = cursor.fetchone()
            current_ads = int(current['ads_watched']) if current else 0
            
            # BLOQUEAR si ya alcanzó el límite
            if current_ads >= DAILY_AD_LIMIT:
                return jsonify({
                    'success': False, 
                    'error': f'Límite diario alcanzado ({DAILY_AD_LIMIT} anuncios)',
                    'limit_reached': True,
                    'ads_watched': current_ads,
                    'daily_limit': DAILY_AD_LIMIT
                }), 429
        
        pts_earned = 5  # PTS base por anuncio
        bonus_earned = 0
        
        with get_cursor() as cursor:
            # Registrar en ad_tasks_progress para la tarea de 5 anuncios
            cursor.execute("""
                INSERT INTO ad_tasks_progress (user_id, task_type, ads_watched, ads_target, task_date, last_ad_at)
                VALUES (%s, 'watch_5_ads', 1, 5, %s, %s) 
                ON DUPLICATE KEY UPDATE ads_watched = ads_watched + 1, last_ad_at = %s
            """, (str(user_id), today_str, now, now))
            
            # Verificar progreso
            cursor.execute("""
                SELECT ads_watched, completed FROM ad_tasks_progress 
                WHERE user_id = %s AND task_type = 'watch_5_ads' AND task_date = %s
            """, (str(user_id), today_str))
            progress = cursor.fetchone()
            
            ads_watched = int(progress['ads_watched']) if progress else 1
            task_completed = bool(progress['completed']) if progress else False
            
            # Otorgar bonus de 20 PTS al completar 5 anuncios
            if ads_watched >= 5 and not task_completed:
                cursor.execute("""
                    UPDATE ad_tasks_progress SET completed = 1 
                    WHERE user_id = %s AND task_type = 'watch_5_ads' AND task_date = %s
                """, (str(user_id), today_str))
                bonus_earned = 20
                task_completed = True
        
        # Agregar PTS
        total_pts = pts_earned + bonus_earned
        try:
            from onclicka_pts_system import add_pts
            add_pts(user_id, total_pts, 'ad_watched', f'Ad PTS{" + bonus" if bonus_earned > 0 else ""}')
        except Exception as pts_error:
            logger.warning(f"[GigaPub] Error adding PTS: {pts_error}")
        
        ads_remaining = max(0, DAILY_AD_LIMIT - ads_watched)
        logger.info(f"[GigaPub] PTS reward: user {user_id} +{total_pts} PTS (ads: {ads_watched}/{DAILY_AD_LIMIT})")
        
        return jsonify({
            'success': True,
            'pts': total_pts,
            'ads_watched': ads_watched,
            'ads_remaining': ads_remaining,
            'daily_limit': DAILY_AD_LIMIT,
            'bonus': bonus_earned > 0,
            'task_completed': task_completed
        })
        
    except Exception as e:
        logger.error(f"[GigaPub] PTS reward error: {e}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# ============================================
# FUNCIÓN PARA REGISTRAR BLUEPRINT EN APP
# ============================================

def init_gigapub(app):
    """Registra el blueprint de GigaPub en la aplicación Flask"""
    app.register_blueprint(gigapub_bp)
    init_gigapub_tables()
    logger.info("[GigaPub] Module initialized successfully")
