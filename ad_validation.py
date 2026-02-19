"""
ad_validation.py - Sistema de Validación de Anuncios para SALLY-E
=================================================================
Este módulo implementa un sistema robusto de validación de anuncios
que previene el fraude y asegura que solo se den recompensas cuando
el anuncio realmente se ha visto.

FLUJO DE VALIDACIÓN:
1. Usuario solicita ver anuncio -> Se genera token único
2. Frontend muestra anuncio de Telega.io con el token
3. Telega.io envía callback a /api/telega/callback con el token
4. Backend marca el token como "completado"
5. Usuario solicita recompensa -> Solo si token está completado

INSTALACIÓN:
1. Ejecutar create_ad_validation_tables() o el SQL de migración
2. Registrar las rutas en app.py
3. Configurar Reward URL en Telega.io: https://tudominio.com/api/telega/callback
"""

import uuid
import hashlib
import hmac
import time
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN
# ============================================

# Tiempo de vida del token en segundos (2 minutos)
TOKEN_LIFETIME_SECONDS = 120

# Cooldown entre anuncios en segundos
AD_COOLDOWN_SECONDS = 30

# Máximo de anuncios por día
MAX_ADS_PER_DAY = 50

# Recompensa por anuncio visto
REWARD_PER_AD = 0.003  # DOGE

# Secret para validar callbacks de Telega.io (CAMBIAR EN PRODUCCIÓN)
TELEGA_WEBHOOK_SECRET = "tu_secret_de_telega_aqui"


# ============================================
# SQL DE MIGRACIÓN
# ============================================

MIGRATION_SQL = """
-- Tabla para tokens de solicitud de anuncios
CREATE TABLE IF NOT EXISTS ad_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token VARCHAR(64) NOT NULL UNIQUE,
    user_id VARCHAR(50) NOT NULL,
    ad_type VARCHAR(20) DEFAULT 'rewarded',
    ad_block_uuid VARCHAR(100) DEFAULT NULL,
    
    -- Estados: pending, completed, claimed, expired
    status ENUM('pending', 'completed', 'claimed', 'expired') DEFAULT 'pending',
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME DEFAULT NULL,
    claimed_at DATETIME DEFAULT NULL,
    expires_at DATETIME NOT NULL,
    
    -- Info adicional
    ip_address VARCHAR(50) DEFAULT NULL,
    user_agent TEXT DEFAULT NULL,
    telega_response TEXT DEFAULT NULL,
    
    INDEX idx_token (token),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla para estadísticas diarias de anuncios por usuario
CREATE TABLE IF NOT EXISTS ad_daily_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    stat_date DATE NOT NULL,
    
    ads_requested INT DEFAULT 0,
    ads_completed INT DEFAULT 0,
    ads_claimed INT DEFAULT 0,
    total_earned DECIMAL(20, 8) DEFAULT 0.00000000,
    
    last_ad_at DATETIME DEFAULT NULL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_user_date (user_id, stat_date),
    INDEX idx_user_id (user_id),
    INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla para logs de callbacks de Telega.io
CREATE TABLE IF NOT EXISTS telega_callbacks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token VARCHAR(64) DEFAULT NULL,
    user_id VARCHAR(50) DEFAULT NULL,
    
    -- Datos del callback
    callback_data TEXT,
    ip_address VARCHAR(50) DEFAULT NULL,
    
    -- Resultado
    valid TINYINT(1) DEFAULT 0,
    error_message VARCHAR(255) DEFAULT NULL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_token (token),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


# ============================================
# FUNCIONES DE BASE DE DATOS
# ============================================

def create_ad_validation_tables():
    """Crea las tablas necesarias para la validación de anuncios"""
    from db import execute_query
    
    statements = [s.strip() for s in MIGRATION_SQL.split(';') if s.strip()]
    
    for statement in statements:
        try:
            execute_query(statement)
            logger.info(f"✅ Ejecutado: {statement[:50]}...")
        except Exception as e:
            logger.warning(f"⚠️ Error en migración: {e}")
    
    logger.info("✅ Tablas de validación de anuncios creadas/actualizadas")
    return True


def generate_ad_token(user_id, ad_type='rewarded', ad_block_uuid=None):
    """
    Genera un token único para una solicitud de anuncio.
    
    Args:
        user_id: ID del usuario
        ad_type: Tipo de anuncio (rewarded, interstitial)
        ad_block_uuid: UUID del bloque de anuncios de Telega.io
    
    Returns:
        dict con token y expires_at, o None si hay error
    """
    from db import execute_query, get_cursor
    
    try:
        # Generar token único
        raw_token = f"{user_id}-{time.time()}-{uuid.uuid4().hex}"
        token = hashlib.sha256(raw_token.encode()).hexdigest()[:32]
        
        # Calcular expiración
        expires_at = datetime.now() + timedelta(seconds=TOKEN_LIFETIME_SECONDS)
        
        # Obtener IP del usuario
        ip_address = request.remote_addr if request else None
        user_agent = request.user_agent.string if request and request.user_agent else None
        
        # Insertar token en la base de datos
        execute_query("""
            INSERT INTO ad_tokens 
            (token, user_id, ad_type, ad_block_uuid, status, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s)
        """, (token, str(user_id), ad_type, ad_block_uuid, expires_at, ip_address, user_agent))
        
        # Actualizar estadísticas diarias
        today = datetime.now().date()
        execute_query("""
            INSERT INTO ad_daily_stats (user_id, stat_date, ads_requested)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE ads_requested = ads_requested + 1
        """, (str(user_id), today))
        
        logger.info(f"[AdToken] Generated token {token[:8]}... for user {user_id}")
        
        return {
            'token': token,
            'expires_at': expires_at.isoformat(),
            'expires_in': TOKEN_LIFETIME_SECONDS
        }
        
    except Exception as e:
        logger.error(f"[AdToken] Error generating token: {e}")
        return None


def validate_token(token):
    """
    Valida un token y retorna su información.
    
    Returns:
        dict con info del token, o None si no es válido
    """
    from db import get_cursor, row_to_dict
    
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM ad_tokens 
                WHERE token = %s
            """, (token,))
            
            result = row_to_dict(cursor, cursor.fetchone())
            
            if not result:
                return None
            
            # Verificar si ha expirado
            expires_at = result.get('expires_at')
            if expires_at:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                if datetime.now() > expires_at:
                    result['status'] = 'expired'
            
            return result
            
    except Exception as e:
        logger.error(f"[AdToken] Error validating token: {e}")
        return None


def mark_token_completed(token, telega_response=None):
    """
    Marca un token como completado (anuncio visto).
    Solo se puede marcar tokens en estado 'pending'.
    
    Args:
        token: Token a marcar
        telega_response: Respuesta de Telega.io (opcional)
    
    Returns:
        True si se marcó correctamente, False si no
    """
    from db import execute_query, get_cursor
    
    try:
        # Verificar estado actual
        token_info = validate_token(token)
        if not token_info:
            logger.warning(f"[AdToken] Token not found: {token[:8]}...")
            return False
        
        if token_info['status'] != 'pending':
            logger.warning(f"[AdToken] Token {token[:8]}... not pending (status: {token_info['status']})")
            return False
        
        if token_info.get('status') == 'expired':
            logger.warning(f"[AdToken] Token {token[:8]}... expired")
            return False
        
        # Marcar como completado
        execute_query("""
            UPDATE ad_tokens 
            SET status = 'completed', 
                completed_at = NOW(),
                telega_response = %s
            WHERE token = %s AND status = 'pending'
        """, (telega_response, token))
        
        # Actualizar estadísticas diarias
        user_id = token_info['user_id']
        today = datetime.now().date()
        execute_query("""
            INSERT INTO ad_daily_stats (user_id, stat_date, ads_completed, last_ad_at)
            VALUES (%s, %s, 1, NOW())
            ON DUPLICATE KEY UPDATE 
                ads_completed = ads_completed + 1,
                last_ad_at = NOW()
        """, (str(user_id), today))
        
        logger.info(f"[AdToken] Token {token[:8]}... marked as completed")
        return True
        
    except Exception as e:
        logger.error(f"[AdToken] Error marking token completed: {e}")
        return False


def claim_reward(token, user_id):
    """
    Reclama la recompensa de un token completado.
    
    Args:
        token: Token a reclamar
        user_id: ID del usuario que reclama
    
    Returns:
        dict con resultado, o None si hay error
    """
    from db import execute_query
    from database import update_balance, get_user
    
    pts_reward = 7  # PTS por anuncio Telega (es mayor porque paga más DOGE)
    
    try:
        # Validar token
        token_info = validate_token(token)
        if not token_info:
            return {'success': False, 'error': 'Token not found'}
        
        # Verificar que el token pertenece al usuario
        if str(token_info['user_id']) != str(user_id):
            logger.warning(f"[AdToken] User {user_id} tried to claim token of user {token_info['user_id']}")
            return {'success': False, 'error': 'Token does not belong to user'}
        
        # Verificar estado
        if token_info['status'] == 'expired':
            return {'success': False, 'error': 'Token expired'}
        
        if token_info['status'] == 'pending':
            return {'success': False, 'error': 'Ad not completed yet'}
        
        if token_info['status'] == 'claimed':
            return {'success': False, 'error': 'Reward already claimed'}
        
        if token_info['status'] != 'completed':
            return {'success': False, 'error': f'Invalid token status: {token_info["status"]}'}
        
        # Marcar como reclamado
        execute_query("""
            UPDATE ad_tokens 
            SET status = 'claimed', claimed_at = NOW()
            WHERE token = %s AND status = 'completed'
        """, (token,))
        
        # Dar recompensa
        update_balance(user_id, 'doge', REWARD_PER_AD, 'add', 'Telega.io ad reward')
        
        # Agregar PTS al ranking
        try:
            from onclicka_pts_system import add_pts
            add_pts(user_id, pts_reward, 'ad_watched', 'Telega.io ad')
        except Exception as pts_error:
            logger.warning(f"[AdToken] Error adding PTS: {pts_error}")
        
        # Actualizar estadísticas diarias
        today = datetime.now().date()
        execute_query("""
            INSERT INTO ad_daily_stats (user_id, stat_date, ads_claimed, total_earned)
            VALUES (%s, %s, 1, %s)
            ON DUPLICATE KEY UPDATE 
                ads_claimed = ads_claimed + 1,
                total_earned = total_earned + %s
        """, (str(user_id), today, REWARD_PER_AD, REWARD_PER_AD))
        
        # Obtener balance actualizado
        user = get_user(user_id)
        new_balance = float(user.get('doge_balance', 0)) if user else 0
        
        logger.info(f"[AdToken] User {user_id} claimed reward for token {token[:8]}... +{REWARD_PER_AD} DOGE +{pts_reward} PTS")
        
        return {
            'success': True,
            'reward': REWARD_PER_AD,
            'pts_reward': pts_reward,
            'new_balance': new_balance,
            'message': f'+{REWARD_PER_AD} DOGE +{pts_reward} PTS'
        }
        
    except Exception as e:
        logger.error(f"[AdToken] Error claiming reward: {e}")
        return {'success': False, 'error': 'Database error'}


def check_user_can_watch_ad(user_id):
    """
    Verifica si el usuario puede ver otro anuncio.
    
    Returns:
        dict con can_watch (bool), reason (str si no puede), cooldown_remaining (int)
    """
    from db import get_cursor, row_to_dict
    
    try:
        today = datetime.now().date()
        
        with get_cursor() as cursor:
            # Obtener estadísticas del día
            cursor.execute("""
                SELECT ads_completed, last_ad_at 
                FROM ad_daily_stats 
                WHERE user_id = %s AND stat_date = %s
            """, (str(user_id), today))
            
            stats = row_to_dict(cursor, cursor.fetchone())
        
        if not stats:
            return {'can_watch': True, 'cooldown_remaining': 0}
        
        # Verificar límite diario
        ads_today = stats.get('ads_completed', 0)
        if ads_today >= MAX_ADS_PER_DAY:
            return {
                'can_watch': False, 
                'reason': 'Daily limit reached',
                'ads_today': ads_today,
                'max_ads': MAX_ADS_PER_DAY
            }
        
        # Verificar cooldown
        last_ad_at = stats.get('last_ad_at')
        if last_ad_at:
            if isinstance(last_ad_at, str):
                last_ad_at = datetime.fromisoformat(last_ad_at)
            
            elapsed = (datetime.now() - last_ad_at).total_seconds()
            if elapsed < AD_COOLDOWN_SECONDS:
                remaining = int(AD_COOLDOWN_SECONDS - elapsed)
                return {
                    'can_watch': False,
                    'reason': 'Cooldown active',
                    'cooldown_remaining': remaining
                }
        
        return {
            'can_watch': True,
            'cooldown_remaining': 0,
            'ads_today': ads_today,
            'max_ads': MAX_ADS_PER_DAY
        }
        
    except Exception as e:
        logger.error(f"[AdToken] Error checking user status: {e}")
        return {'can_watch': True, 'cooldown_remaining': 0}


def get_user_ad_stats(user_id):
    """Obtiene las estadísticas de anuncios del usuario para hoy"""
    from db import get_cursor, row_to_dict
    
    try:
        today = datetime.now().date()
        
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM ad_daily_stats 
                WHERE user_id = %s AND stat_date = %s
            """, (str(user_id), today))
            
            stats = row_to_dict(cursor, cursor.fetchone())
        
        if not stats:
            return {
                'ads_completed': 0,
                'ads_claimed': 0,
                'total_earned': 0,
                'max_ads': MAX_ADS_PER_DAY,
                'reward_per_ad': REWARD_PER_AD
            }
        
        return {
            'ads_completed': stats.get('ads_completed', 0),
            'ads_claimed': stats.get('ads_claimed', 0),
            'total_earned': float(stats.get('total_earned', 0)),
            'max_ads': MAX_ADS_PER_DAY,
            'reward_per_ad': REWARD_PER_AD
        }
        
    except Exception as e:
        logger.error(f"[AdToken] Error getting user stats: {e}")
        return {
            'ads_completed': 0,
            'ads_claimed': 0,
            'total_earned': 0,
            'max_ads': MAX_ADS_PER_DAY,
            'reward_per_ad': REWARD_PER_AD
        }


def log_telega_callback(token, user_id, callback_data, ip_address, valid, error_message=None):
    """Registra un callback de Telega.io para auditoría"""
    from db import execute_query
    import json
    
    try:
        if isinstance(callback_data, dict):
            callback_data = json.dumps(callback_data)
        
        execute_query("""
            INSERT INTO telega_callbacks 
            (token, user_id, callback_data, ip_address, valid, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (token, str(user_id) if user_id else None, callback_data, ip_address, valid, error_message))
        
    except Exception as e:
        logger.error(f"[AdToken] Error logging callback: {e}")


def cleanup_expired_tokens():
    """Limpia tokens expirados (ejecutar periódicamente)"""
    from db import execute_query
    
    try:
        execute_query("""
            UPDATE ad_tokens 
            SET status = 'expired' 
            WHERE status = 'pending' AND expires_at < NOW()
        """)
        
        # Opcional: eliminar tokens muy antiguos
        execute_query("""
            DELETE FROM ad_tokens 
            WHERE created_at < DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        
        logger.info("[AdToken] Cleaned up expired tokens")
        
    except Exception as e:
        logger.error(f"[AdToken] Error cleaning up tokens: {e}")


# ============================================
# RUTAS FLASK
# ============================================

def register_ad_validation_routes(app):
    """Registra las rutas de validación de anuncios en la app Flask"""
    from database import get_user
    
    @app.route('/api/ads/request-token', methods=['POST'])
    def api_request_ad_token():
        """
        Solicita un token para ver un anuncio.
        El frontend debe llamar esta ruta ANTES de mostrar el anuncio.
        """
        data = request.get_json() or {}
        user_id = data.get('user_id')
        ad_type = data.get('ad_type', 'rewarded')
        ad_block_uuid = data.get('ad_block_uuid')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        # Verificar usuario
        user = get_user(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        if user.get('banned'):
            return jsonify({'success': False, 'error': 'User banned'}), 403
        
        # Verificar si puede ver anuncio
        check = check_user_can_watch_ad(user_id)
        if not check.get('can_watch'):
            return jsonify({
                'success': False,
                'error': check.get('reason', 'Cannot watch ad'),
                'cooldown_remaining': check.get('cooldown_remaining', 0)
            })
        
        # Generar token
        token_data = generate_ad_token(user_id, ad_type, ad_block_uuid)
        if not token_data:
            return jsonify({'success': False, 'error': 'Failed to generate token'}), 500
        
        return jsonify({
            'success': True,
            'token': token_data['token'],
            'expires_in': token_data['expires_in'],
            'reward': REWARD_PER_AD
        })
    
    
    @app.route('/api/ads/complete', methods=['POST'])
    def api_complete_ad():
        """
        Marca un anuncio como completado.
        MODO SIN CALLBACK: El frontend llama cuando el anuncio termina.
        Para producción, usar el callback de Telega.io en su lugar.
        """
        data = request.get_json() or {}
        token = data.get('token')
        user_id = data.get('user_id')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token required'}), 400
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        # Validar que el token pertenece al usuario
        token_info = validate_token(token)
        if not token_info:
            return jsonify({'success': False, 'error': 'Invalid token'}), 400
        
        if str(token_info['user_id']) != str(user_id):
            return jsonify({'success': False, 'error': 'Token mismatch'}), 403
        
        # Marcar como completado
        if not mark_token_completed(token):
            return jsonify({'success': False, 'error': 'Failed to complete token'}), 400
        
        return jsonify({
            'success': True,
            'message': 'Ad completed, ready to claim reward'
        })
    
    
    @app.route('/api/ads/claim', methods=['POST'])
    def api_claim_ad_reward():
        """
        Reclama la recompensa de un anuncio completado.
        """
        data = request.get_json() or {}
        token = data.get('token')
        user_id = data.get('user_id')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token required'}), 400
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        result = claim_reward(token, user_id)
        
        if result.get('success'):
            # Obtener estadísticas actualizadas
            stats = get_user_ad_stats(user_id)
            result['stats'] = stats
        
        return jsonify(result)
    
    
    @app.route('/api/ads/stats', methods=['GET'])
    def api_ad_stats():
        """Obtiene las estadísticas de anuncios del usuario"""
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        stats = get_user_ad_stats(user_id)
        check = check_user_can_watch_ad(user_id)
        
        return jsonify({
            'success': True,
            'stats': stats,
            'can_watch': check.get('can_watch', True),
            'cooldown_remaining': check.get('cooldown_remaining', 0)
        })
    
    
    @app.route('/api/telega/callback', methods=['POST', 'GET'])
    def api_telega_callback():
        """
        Callback de Telega.io cuando un anuncio se completa.
        Configura esta URL en el dashboard de Telega.io como Reward URL.
        
        Telega.io enviará datos del anuncio completado.
        """
        # Obtener datos del callback
        if request.method == 'POST':
            data = request.get_json() or request.form.to_dict()
        else:
            data = request.args.to_dict()
        
        ip_address = request.remote_addr
        
        logger.info(f"[Telega Callback] Received: {data}")
        
        # Extraer token y user_id del callback
        # NOTA: Los nombres de los campos dependen de cómo Telega.io envíe los datos
        token = data.get('token') or data.get('ad_token') or data.get('custom_data')
        user_id = data.get('user_id') or data.get('userId')
        
        if not token:
            log_telega_callback(None, None, data, ip_address, False, 'No token in callback')
            return jsonify({'success': False, 'error': 'No token'}), 400
        
        # Validar token
        token_info = validate_token(token)
        if not token_info:
            log_telega_callback(token, user_id, data, ip_address, False, 'Invalid token')
            return jsonify({'success': False, 'error': 'Invalid token'}), 400
        
        # Marcar como completado
        import json
        success = mark_token_completed(token, json.dumps(data))
        
        if success:
            log_telega_callback(token, token_info['user_id'], data, ip_address, True, None)
            logger.info(f"[Telega Callback] Token {token[:8]}... marked completed")
            return jsonify({'success': True})
        else:
            log_telega_callback(token, token_info['user_id'], data, ip_address, False, 'Failed to mark completed')
            return jsonify({'success': False, 'error': 'Failed to complete'}), 400
    
    
    @app.route('/api/ads/quick-reward', methods=['POST'])
    def api_quick_ad_reward():
        """
        Endpoint simplificado que combina complete + claim en uno.
        Usar cuando NO tienes callback de Telega.io configurado.
        Incluye validaciones básicas anti-fraude.
        """
        data = request.get_json() or {}
        token = data.get('token')
        user_id = data.get('user_id')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token required'}), 400
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        # Validar token
        token_info = validate_token(token)
        if not token_info:
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 400
        
        if str(token_info['user_id']) != str(user_id):
            return jsonify({'success': False, 'error': 'Token mismatch'}), 403
        
        if token_info['status'] == 'expired':
            return jsonify({'success': False, 'error': 'Token expired'}), 400
        
        if token_info['status'] == 'claimed':
            return jsonify({'success': False, 'error': 'Already claimed'}), 400
        
        # Si está pending, marcar como completed primero
        if token_info['status'] == 'pending':
            if not mark_token_completed(token):
                return jsonify({'success': False, 'error': 'Failed to complete'}), 400
        
        # Reclamar recompensa
        result = claim_reward(token, user_id)
        
        if result.get('success'):
            stats = get_user_ad_stats(user_id)
            result['stats'] = stats
        
        return jsonify(result)
    
    
    logger.info("✅ [AdValidation] Routes registered")
    return app


# ============================================
# INICIALIZACIÓN
# ============================================

if __name__ == "__main__":
    # Ejecutar migración
    create_ad_validation_tables()
    print("✅ Tablas de validación de anuncios creadas")
