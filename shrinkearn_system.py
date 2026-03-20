"""
shrinkearn_system.py - Sistema de Monetización ShrinkEarn para ARCADE PXC
=====================================================================
Implementación REAL usando la API de ShrinkEarn para acortamiento de enlaces.

FLUJO:
1. Usuario inicia misión → se crea registro pending con token único
2. Se genera enlace acortado via API ShrinkEarn
3. Usuario completa anuncios en ShrinkEarn
4. ShrinkEarn redirige al usuario a /shrinkearn/verify?token=XXX
5. Backend valida token, marca como completed, acredita recompensa
6. Usuario ve página de éxito

IMPORTANTE: ShrinkEarn NO tiene webhook ni postback.
La redirección final ES la única confirmación de que el usuario completó el flujo.
"""

import os
import secrets
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
from flask import Blueprint, request, jsonify, render_template, redirect

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN
# ============================================

SHRINKEARN_CONFIG = {
    # API Key de ShrinkEarn (obtener en shrinkearn.com/member/tools/api)
    'api_key': os.environ.get('SHRINKEARN_API_KEY', 'db2565e558c626a33c8bd18c1587029a01b590f8'),

    # URL base de tu webapp (CAMBIAR a tu dominio real)
    'webapp_url': os.environ.get('WEBAPP_URL', 'https://arcadepxc.pythonanywhere.com'),

    # Endpoint de la API ShrinkEarn
    'api_endpoint': 'https://shrinkearn.com/api',

    # Tiempo mínimo que debe pasar entre inicio y verificación (segundos)
    # Esto previene abuso - ajustar según el tiempo real que toman los anuncios
    'min_completion_time': 30,

    # Tiempo máximo de validez de un token (segundos)
    # Después de este tiempo, el token expira
    'token_expiry_time': 3600,  # 1 hora

    # Cooldown entre misiones del mismo tipo (segundos)
    'mission_cooldown': 300,  # 5 minutos

    # Límite diario de misiones por usuario
    'daily_mission_limit': 1,

    # Nombre para mostrar
    'display_name': 'ShrinkEarn',

    # Color del tema
    'theme_color': '#00D4FF',

    # Icono
    'icon': 'link-2',
}

# Misiones disponibles con sus recompensas
SHRINKEARN_MISSIONS = {
    'short_ad': {
        'name': 'Quick Task',
        'name_es': 'Tarea Rápida',
        'description': 'Complete a short task',
        'description_es': 'Completa una tarea corta',
        'reward': 0.005,  # DOGE
        'reward_pts': 10,  # PTS alternativos
        'icon': '⚡',
        'cooldown': 180,  # 3 minutos
        'enabled': True,
    },

}

# Blueprint para las rutas
shrinkearn_bp = Blueprint('shrinkearn', __name__, url_prefix='/shrinkearn')


# ============================================
# RUTA DE PÁGINA PRINCIPAL
# ============================================

@shrinkearn_bp.route('/')
def shrinkearn_page():
    """Página principal de ShrinkEarn."""
    user_id = request.args.get('user_id', '')

    return render_template('shrinkearn.html',
        user_id=user_id,
        config=SHRINKEARN_CONFIG,
        missions=SHRINKEARN_MISSIONS
    )


# ============================================
# INICIALIZACIÓN DE BASE DE DATOS
# ============================================

def init_shrinkearn_tables():
    """
    Crear tablas necesarias para el sistema ShrinkEarn.
    Llamar esta función al iniciar la aplicación.
    """
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            # Tabla principal de tareas/misiones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shrinkearn_tasks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    token VARCHAR(64) UNIQUE NOT NULL,
                    mission_type VARCHAR(50) NOT NULL DEFAULT 'standard_ad',
                    reward DECIMAL(10,6) NOT NULL,
                    reward_pts INT DEFAULT 0,
                    status ENUM('pending', 'completed', 'expired', 'cancelled') DEFAULT 'pending',
                    shortened_url VARCHAR(255),
                    ip_address VARCHAR(45),
                    user_agent VARCHAR(255),
                    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME DEFAULT NULL,
                    INDEX idx_user_status (user_id, status),
                    INDEX idx_token (token),
                    INDEX idx_started (started_at),
                    INDEX idx_user_mission (user_id, mission_type, started_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Tabla de estadísticas diarias por usuario
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shrinkearn_daily_stats (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    stat_date DATE NOT NULL,
                    missions_started INT DEFAULT 0,
                    missions_completed INT DEFAULT 0,
                    total_reward DECIMAL(10,6) DEFAULT 0,
                    total_pts INT DEFAULT 0,
                    UNIQUE KEY unique_user_date (user_id, stat_date),
                    INDEX idx_date (stat_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Tabla de configuración (para admin)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shrinkearn_config (
                    config_key VARCHAR(50) PRIMARY KEY,
                    config_value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Insertar configuración por defecto si no existe
            default_configs = [
                ('enabled', 'true'),
                ('daily_limit', '1'),
                ('min_completion_time', '30'),
                ('api_key', SHRINKEARN_CONFIG['api_key']),
            ]

            for key, value in default_configs:
                cursor.execute("""
                    INSERT IGNORE INTO shrinkearn_config (config_key, config_value)
                    VALUES (%s, %s)
                """, (key, value))

            logger.info("✅ ShrinkEarn tables initialized successfully")
            return True

    except Exception as e:
        logger.error(f"❌ Error initializing ShrinkEarn tables: {e}")
        return False


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def generate_secure_token():
    """Generar un token único y seguro para identificar la misión."""
    # Combinar timestamp + random para mayor unicidad
    timestamp = str(datetime.utcnow().timestamp())
    random_part = secrets.token_hex(16)
    combined = f"{timestamp}-{random_part}"
    # Hash para token más corto pero seguro
    return hashlib.sha256(combined.encode()).hexdigest()[:48]


def get_shrinkearn_config(key, default=None):
    """Obtener configuración de la base de datos."""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT config_value FROM shrinkearn_config WHERE config_key = %s",
                (key,)
            )
            result = cursor.fetchone()
            return result['config_value'] if result else default
    except Exception as e:
        logger.error(f"Error getting shrinkearn config {key}: {e}")
        return default


def set_shrinkearn_config(key, value):
    """Guardar configuración en la base de datos."""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO shrinkearn_config (config_key, config_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
            """, (key, value))
            return True
    except Exception as e:
        logger.error(f"Error setting shrinkearn config {key}: {e}")
        return False


def is_shrinkearn_enabled():
    """Verificar si el sistema ShrinkEarn está habilitado."""
    enabled = get_shrinkearn_config('enabled', 'true')
    return enabled.lower() == 'true'


def get_user_daily_stats(user_id):
    """Obtener estadísticas del día actual para un usuario."""
    from db import get_cursor
    today = datetime.utcnow().date()

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT missions_started, missions_completed, total_reward, total_pts
                FROM shrinkearn_daily_stats
                WHERE user_id = %s AND stat_date = %s
            """, (user_id, today))
            result = cursor.fetchone()

            if result:
                return result
            return {
                'missions_started': 0,
                'missions_completed': 0,
                'total_reward': 0,
                'total_pts': 0
            }
    except Exception as e:
        logger.error(f"Error getting daily stats for user {user_id}: {e}")
        return {'missions_started': 0, 'missions_completed': 0, 'total_reward': 0, 'total_pts': 0}


def update_daily_stats(user_id, started=0, completed=0, reward=0, pts=0):
    """Actualizar estadísticas diarias del usuario."""
    from db import get_cursor
    today = datetime.utcnow().date()

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO shrinkearn_daily_stats
                    (user_id, stat_date, missions_started, missions_completed, total_reward, total_pts)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    missions_started = missions_started + VALUES(missions_started),
                    missions_completed = missions_completed + VALUES(missions_completed),
                    total_reward = total_reward + VALUES(total_reward),
                    total_pts = total_pts + VALUES(total_pts)
            """, (user_id, today, started, completed, reward, pts))
            return True
    except Exception as e:
        logger.error(f"Error updating daily stats for user {user_id}: {e}")
        return False


def get_last_mission_time(user_id, mission_type):
    """Obtener el tiempo de la última misión del usuario para calcular cooldown."""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT started_at FROM shrinkearn_tasks
                WHERE user_id = %s AND mission_type = %s
                ORDER BY started_at DESC LIMIT 1
            """, (user_id, mission_type))
            result = cursor.fetchone()
            return result['started_at'] if result else None
    except Exception as e:
        logger.error(f"Error getting last mission time: {e}")
        return None


def check_cooldown(user_id, mission_type):
    """
    Verificar si el usuario puede iniciar una nueva misión.
    Retorna (can_start, seconds_remaining)
    """
    mission_config = SHRINKEARN_MISSIONS.get(mission_type, {})
    cooldown = mission_config.get('cooldown', SHRINKEARN_CONFIG['mission_cooldown'])

    last_time = get_last_mission_time(user_id, mission_type)

    if not last_time:
        return True, 0

    elapsed = (datetime.utcnow() - last_time).total_seconds()

    if elapsed >= cooldown:
        return True, 0

    return False, int(cooldown - elapsed)


def call_shrinkearn_api(destination_url):
    """
    Llamar a la API de ShrinkEarn para acortar un enlace.

    Args:
        destination_url: La URL final a donde ShrinkEarn redirigirá

    Returns:
        dict: {'success': bool, 'shortened_url': str or None, 'error': str or None}
    """
    api_key = get_shrinkearn_config('api_key', SHRINKEARN_CONFIG['api_key'])

    # Construir la URL de la API
    params = {
        'api': api_key,
        'url': destination_url,
    }

    api_url = f"{SHRINKEARN_CONFIG['api_endpoint']}?{urlencode(params)}"

    try:
        response = requests.get(api_url, timeout=15)
        data = response.json()

        if data.get('status') == 'success':
            return {
                'success': True,
                'shortened_url': data.get('shortenedUrl'),
                'error': None
            }
        else:
            error_msg = data.get('message', 'Unknown error from ShrinkEarn API')
            logger.error(f"ShrinkEarn API error: {error_msg}")
            return {
                'success': False,
                'shortened_url': None,
                'error': error_msg
            }

    except requests.exceptions.Timeout:
        logger.error("ShrinkEarn API timeout")
        return {'success': False, 'shortened_url': None, 'error': 'API timeout'}
    except requests.exceptions.RequestException as e:
        logger.error(f"ShrinkEarn API request error: {e}")
        return {'success': False, 'shortened_url': None, 'error': str(e)}
    except ValueError as e:
        logger.error(f"ShrinkEarn API JSON parse error: {e}")
        return {'success': False, 'shortened_url': None, 'error': 'Invalid API response'}


def credit_reward_to_user(user_id, reward_doge, reward_pts=0):
    """
    Acreditar recompensa al usuario.

    Args:
        user_id: ID del usuario
        reward_doge: Cantidad de DOGE a acreditar
        reward_pts: Cantidad de PTS a acreditar (opcional)

    Returns:
        bool: True si se acreditó correctamente
    """
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            # Acreditar DOGE al balance del usuario
            if reward_doge > 0:
                cursor.execute("""
                    UPDATE users
                    SET doge_balance = doge_balance + %s
                    WHERE user_id = %s
                """, (reward_doge, user_id))

            # Acreditar PTS si corresponde
            if reward_pts > 0:
                try:
                    cursor.execute("""
                        INSERT INTO user_pts (user_id, pts_balance, pts_total_earned)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            pts_balance = pts_balance + VALUES(pts_balance),
                            pts_total_earned = pts_total_earned + VALUES(pts_total_earned)
                    """, (user_id, reward_pts, reward_pts))
                except Exception as pts_error:
                    logger.warning(f"⚠️ Could not credit PTS (table may not exist): {pts_error}")

            logger.info(f"✅ Credited {reward_doge} DOGE + {reward_pts} PTS to user {user_id}")
            return True

    except Exception as e:
        logger.error(f"❌ Error crediting reward to user {user_id}: {e}")
        return False


# ============================================
# RUTAS DEL BLUEPRINT
# ============================================

@shrinkearn_bp.route('/status', methods=['GET'])
def shrinkearn_status():
    """Obtener estado del sistema y misiones disponibles."""
    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    try:
        user_id = int(user_id)
    except:
        return jsonify({'error': 'Invalid user_id'}), 400

    # Verificar si sistema está habilitado
    enabled = is_shrinkearn_enabled()

    # Obtener estadísticas diarias
    daily_stats = get_user_daily_stats(user_id)
    daily_limit = int(get_shrinkearn_config('daily_limit', SHRINKEARN_CONFIG['daily_mission_limit']))

    # Construir lista de misiones disponibles
    missions = []
    for mission_id, mission_config in SHRINKEARN_MISSIONS.items():
        if not mission_config.get('enabled', True):
            continue

        can_start, cooldown_remaining = check_cooldown(user_id, mission_id)

        missions.append({
            'id': mission_id,
            'name': mission_config['name'],
            'name_es': mission_config['name_es'],
            'description': mission_config['description'],
            'description_es': mission_config['description_es'],
            'reward': mission_config['reward'],
            'reward_pts': mission_config.get('reward_pts', 0),
            'icon': mission_config['icon'],
            'available': can_start and daily_stats['missions_started'] < daily_limit,
            'cooldown_remaining': cooldown_remaining,
        })

    return jsonify({
        'success': True,
        'enabled': enabled,
        'daily_stats': {
            'started': daily_stats['missions_started'],
            'completed': daily_stats['missions_completed'],
            'earned_doge': float(daily_stats['total_reward']),
            'earned_pts': daily_stats['total_pts'],
            'limit': daily_limit,
            'remaining': max(0, daily_limit - daily_stats['missions_started']),
        },
        'missions': missions
    })


@shrinkearn_bp.route('/start', methods=['POST'])
def start_mission():
    """
    Iniciar una nueva misión ShrinkEarn.

    Body JSON:
        - user_id: ID del usuario
        - mission_type: Tipo de misión (short_ad, standard_ad, premium_ad)

    Returns:
        - shortened_url: URL acortada de ShrinkEarn para redirigir al usuario
    """
    from db import get_cursor

    data = request.get_json() or {}
    user_id = data.get('user_id')
    mission_type = data.get('mission_type', 'standard_ad')

    # Validaciones básicas
    if not user_id:
        return jsonify({'success': False, 'error': 'user_id required'}), 400

    try:
        user_id = int(user_id)
    except:
        return jsonify({'success': False, 'error': 'Invalid user_id'}), 400

    # Verificar si sistema está habilitado
    if not is_shrinkearn_enabled():
        return jsonify({'success': False, 'error': 'ShrinkEarn system is disabled'}), 503

    # Verificar misión válida
    if mission_type not in SHRINKEARN_MISSIONS:
        return jsonify({'success': False, 'error': 'Invalid mission type'}), 400

    mission_config = SHRINKEARN_MISSIONS[mission_type]

    if not mission_config.get('enabled', True):
        return jsonify({'success': False, 'error': 'This mission is not available'}), 400

    # Verificar límite diario
    daily_stats = get_user_daily_stats(user_id)
    daily_limit = int(get_shrinkearn_config('daily_limit', SHRINKEARN_CONFIG['daily_mission_limit']))

    if daily_stats['missions_started'] >= daily_limit:
        return jsonify({
            'success': False,
            'error': 'Daily limit reached',
            'error_es': 'Límite diario alcanzado',
            'daily_limit': daily_limit
        }), 429

    # Verificar cooldown
    can_start, cooldown_remaining = check_cooldown(user_id, mission_type)
    if not can_start:
        return jsonify({
            'success': False,
            'error': f'Please wait {cooldown_remaining} seconds',
            'error_es': f'Por favor espera {cooldown_remaining} segundos',
            'cooldown_remaining': cooldown_remaining
        }), 429

    # Generar token único
    token = generate_secure_token()
    reward = mission_config['reward']
    reward_pts = mission_config.get('reward_pts', 0)

    # Construir URL de verificación (donde ShrinkEarn redirigirá al completar)
    verify_url = f"{SHRINKEARN_CONFIG['webapp_url']}/shrinkearn/verify?token={token}"

    # Llamar a la API de ShrinkEarn
    api_result = call_shrinkearn_api(verify_url)

    if not api_result['success']:
        return jsonify({
            'success': False,
            'error': 'Could not generate task link',
            'error_es': 'No se pudo generar el enlace de la tarea',
            'details': api_result['error']
        }), 502

    shortened_url = api_result['shortened_url']

    # Guardar la misión en base de datos
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO shrinkearn_tasks
                    (user_id, token, mission_type, reward, reward_pts, status, shortened_url, ip_address, user_agent, started_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s, NOW())
            """, (
                user_id,
                token,
                mission_type,
                reward,
                reward_pts,
                shortened_url,
                request.remote_addr,
                request.headers.get('User-Agent', '')[:255]
            ))

        # Actualizar estadísticas diarias
        update_daily_stats(user_id, started=1)

        logger.info(f"✅ Mission started: user={user_id}, type={mission_type}, token={token[:8]}...")

        return jsonify({
            'success': True,
            'shortened_url': shortened_url,
            'token': token,
            'mission': {
                'type': mission_type,
                'name': mission_config['name'],
                'name_es': mission_config['name_es'],
                'reward': reward,
                'reward_pts': reward_pts,
                'icon': mission_config['icon'],
            }
        })

    except Exception as e:
        logger.error(f"❌ Error creating mission: {e}")
        return jsonify({
            'success': False,
            'error': 'Database error',
            'error_es': 'Error de base de datos'
        }), 500


@shrinkearn_bp.route('/verify', methods=['GET'])
def verify_mission():
    """
    Endpoint de verificación - ShrinkEarn redirige aquí cuando el usuario completa.

    Este endpoint ES la confirmación de que el usuario completó el flujo.
    ShrinkEarn SOLO redirige aquí si el usuario terminó todos los anuncios.

    Query params:
        - token: Token único de la misión
    """
    from db import get_cursor

    token = request.args.get('token')

    # Obtener user_id de Telegram si está disponible
    tg_user_id = request.args.get('tgWebAppStartParam') or request.args.get('user_id')

    if not token:
        return render_template('shrinkearn_verify.html',
            success=False,
            error='Invalid verification link',
            error_es='Enlace de verificación inválido'
        )

    try:
        with get_cursor() as cursor:
            # Buscar la misión por token
            cursor.execute("""
                SELECT id, user_id, mission_type, reward, reward_pts, status, started_at
                FROM shrinkearn_tasks
                WHERE token = %s
                FOR UPDATE
            """, (token,))

            task = cursor.fetchone()

            # Validación 1: Token existe
            if not task:
                logger.warning(f"⚠️ Invalid token attempted: {token[:16]}...")
                return render_template('shrinkearn_verify.html',
                    success=False,
                    error='Invalid or expired token',
                    error_es='Token inválido o expirado'
                )

            # Validación 2: Estado pending (no completado antes)
            if task['status'] != 'pending':
                logger.warning(f"⚠️ Token already used: {token[:16]}...")
                return render_template('shrinkearn_verify.html',
                    success=False,
                    error='This task has already been completed',
                    error_es='Esta tarea ya fue completada',
                    already_completed=True
                )

            # Validación 3: Tiempo mínimo transcurrido
            min_time = int(get_shrinkearn_config('min_completion_time', SHRINKEARN_CONFIG['min_completion_time']))
            elapsed = (datetime.utcnow() - task['started_at']).total_seconds()

            if elapsed < min_time:
                logger.warning(f"⚠️ Task completed too fast: {elapsed:.1f}s < {min_time}s")
                return render_template('shrinkearn_verify.html',
                    success=False,
                    error='Task completed too quickly. Please complete all ads.',
                    error_es='Tarea completada muy rápido. Por favor completa todos los anuncios.',
                    too_fast=True
                )

            # Validación 4: Token no expirado
            expiry_time = SHRINKEARN_CONFIG['token_expiry_time']
            if elapsed > expiry_time:
                # Marcar como expirado
                cursor.execute("""
                    UPDATE shrinkearn_tasks
                    SET status = 'expired'
                    WHERE id = %s
                """, (task['id'],))

                logger.warning(f"⚠️ Token expired: {token[:16]}...")
                return render_template('shrinkearn_verify.html',
                    success=False,
                    error='This task has expired',
                    error_es='Esta tarea ha expirado',
                    expired=True
                )

            # ✅ Todas las validaciones pasaron - Completar la misión
            user_id = task['user_id']
            reward_doge = float(task['reward'])
            reward_pts = task['reward_pts']
            mission_type = task['mission_type']
            mission_config = SHRINKEARN_MISSIONS.get(mission_type, {})

            # Marcar como completada
            cursor.execute("""
                UPDATE shrinkearn_tasks
                SET status = 'completed',
                    completed_at = NOW()
                WHERE id = %s AND status = 'pending'
            """, (task['id'],))

            # Verificar que se actualizó (protección contra race condition)
            if cursor.rowcount == 0:
                logger.warning(f"⚠️ Race condition detected for token: {token[:16]}...")
                return render_template('shrinkearn_verify.html',
                    success=False,
                    error='This task has already been completed',
                    error_es='Esta tarea ya fue completada',
                    already_completed=True
                )

            # ✅ Acreditar DOGE directamente en el mismo cursor (IMPORTANTE!)
            credit_success = True
            user_id_str = str(user_id)

            if reward_doge > 0:
                cursor.execute("""
                    UPDATE users
                    SET doge_balance = doge_balance + %s
                    WHERE user_id = %s
                """, (reward_doge, user_id_str))

                rows_affected = cursor.rowcount
                logger.info(f"📊 DOGE CREDIT: user={user_id_str}, amount={reward_doge}, rows_affected={rows_affected}")

                if rows_affected == 0:
                    logger.error(f"❌ No rows updated for DOGE credit to user {user_id_str}")
                    credit_success = False

            # ✅ Acreditar PTS directamente en el mismo cursor
            if reward_pts > 0:
                try:
                    cursor.execute("""
                        INSERT INTO user_pts (user_id, pts_balance, pts_total_earned)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            pts_balance = pts_balance + VALUES(pts_balance),
                            pts_total_earned = pts_total_earned + VALUES(pts_total_earned)
                    """, (user_id_str, reward_pts, reward_pts))
                    logger.info(f"📊 PTS CREDIT: user={user_id_str}, pts={reward_pts}")
                except Exception as pts_error:
                    logger.warning(f"⚠️ Could not credit PTS: {pts_error}")

            if not credit_success:
                # Revertir el estado si no se pudo acreditar
                cursor.execute("""
                    UPDATE shrinkearn_tasks
                    SET status = 'pending', completed_at = NULL
                    WHERE id = %s
                """, (task['id'],))

                logger.error(f"❌ Failed to credit reward for user {user_id}")
                return render_template('shrinkearn_verify.html',
                    success=False,
                    error='Error processing reward. Please contact support.',
                    error_es='Error procesando recompensa. Por favor contacta soporte.'
                )

            # Actualizar estadísticas diarias
            update_daily_stats(user_id, completed=1, reward=reward_doge, pts=reward_pts)

            logger.info(f"✅ Mission completed: user={user_id}, reward={reward_doge} DOGE + {reward_pts} PTS")

            # Mostrar página de éxito
            return render_template('shrinkearn_verify.html',
                success=True,
                reward_doge=reward_doge,
                reward_pts=reward_pts,
                mission_name=mission_config.get('name', 'Task'),
                mission_name_es=mission_config.get('name_es', 'Tarea'),
                mission_icon=mission_config.get('icon', '🎯'),
                user_id=user_id
            )

    except Exception as e:
        logger.error(f"❌ Error in verify_mission: {e}")
        return render_template('shrinkearn_verify.html',
            success=False,
            error='An error occurred. Please try again.',
            error_es='Ocurrió un error. Por favor intenta de nuevo.'
        )


@shrinkearn_bp.route('/history', methods=['GET'])
def get_mission_history():
    """Obtener historial de misiones del usuario."""
    from db import get_cursor

    user_id = request.args.get('user_id')
    limit = min(int(request.args.get('limit', 1)), 100)
    offset = int(request.args.get('offset', 0))

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, mission_type, reward, reward_pts, status, started_at, completed_at
                FROM shrinkearn_tasks
                WHERE user_id = %s
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
            """, (user_id, limit, offset))

            tasks = cursor.fetchall()

            # Formatear resultados
            history = []
            for task in tasks:
                mission_config = SHRINKEARN_MISSIONS.get(task['mission_type'], {})
                history.append({
                    'id': task['id'],
                    'mission_type': task['mission_type'],
                    'mission_name': mission_config.get('name', task['mission_type']),
                    'mission_name_es': mission_config.get('name_es', task['mission_type']),
                    'icon': mission_config.get('icon', '🎯'),
                    'reward': float(task['reward']),
                    'reward_pts': task['reward_pts'],
                    'status': task['status'],
                    'started_at': task['started_at'].isoformat() if task['started_at'] else None,
                    'completed_at': task['completed_at'].isoformat() if task['completed_at'] else None,
                })

            # Contar total
            cursor.execute(
                "SELECT COUNT(*) as total FROM shrinkearn_tasks WHERE user_id = %s",
                (user_id,)
            )
            total = cursor.fetchone()['total']

            return jsonify({
                'success': True,
                'history': history,
                'total': total,
                'limit': limit,
                'offset': offset
            })

    except Exception as e:
        logger.error(f"Error getting mission history: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@shrinkearn_bp.route('/stats', methods=['GET'])
def get_user_stats():
    """Obtener estadísticas completas del usuario."""
    from db import get_cursor

    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    try:
        with get_cursor() as cursor:
            # Estadísticas totales
            cursor.execute("""
                SELECT
                    COUNT(*) as total_missions,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'completed' THEN reward ELSE 0 END) as total_earned_doge,
                    SUM(CASE WHEN status = 'completed' THEN reward_pts ELSE 0 END) as total_earned_pts
                FROM shrinkearn_tasks
                WHERE user_id = %s
            """, (user_id,))

            total_stats = cursor.fetchone()

            # Estadísticas de hoy
            daily_stats = get_user_daily_stats(user_id)

            return jsonify({
                'success': True,
                'total': {
                    'missions': total_stats['total_missions'] or 0,
                    'completed': total_stats['completed'] or 0,
                    'earned_doge': float(total_stats['total_earned_doge'] or 0),
                    'earned_pts': total_stats['total_earned_pts'] or 0,
                    'completion_rate': round(
                        (total_stats['completed'] / total_stats['total_missions'] * 100)
                        if total_stats['total_missions'] > 0 else 0, 1
                    )
                },
                'today': {
                    'started': daily_stats['missions_started'],
                    'completed': daily_stats['missions_completed'],
                    'earned_doge': float(daily_stats['total_reward']),
                    'earned_pts': daily_stats['total_pts'],
                }
            })

    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


# ============================================
# FUNCIÓN DE REGISTRO DEL BLUEPRINT
# ============================================

def register_shrinkearn_routes(app):
    """
    Registrar el blueprint de ShrinkEarn en la aplicación Flask.

    Usage en app.py:
        from shrinkearn_system import register_shrinkearn_routes, init_shrinkearn_tables
        register_shrinkearn_routes(app)
        init_shrinkearn_tables()
    """
    app.register_blueprint(shrinkearn_bp)
    logger.info("✅ ShrinkEarn routes registered: /shrinkearn/*")


# ============================================
# CLEANUP DE TOKENS EXPIRADOS (para cron job)
# ============================================

def cleanup_expired_tokens():
    """
    Limpiar tokens expirados. Ejecutar periódicamente (cron).
    Marca como 'expired' las misiones pending que superaron el tiempo límite.
    """
    from db import get_cursor

    expiry_time = SHRINKEARN_CONFIG['token_expiry_time']
    expiry_threshold = datetime.utcnow() - timedelta(seconds=expiry_time)

    try:
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE shrinkearn_tasks
                SET status = 'expired'
                WHERE status = 'pending'
                AND started_at < %s
            """, (expiry_threshold,))

            expired_count = cursor.rowcount
            if expired_count > 0:
                logger.info(f"🧹 Cleaned up {expired_count} expired ShrinkEarn tokens")

            return expired_count

    except Exception as e:
        logger.error(f"Error cleaning up expired tokens: {e}")
        return 0


# ============================================
# AUTO-INICIALIZACIÓN
# ============================================

if __name__ == '__main__':
    # Test de inicialización
    print("🔧 Testing ShrinkEarn system...")
    init_shrinkearn_tables()
    print("✅ Tables initialized")
