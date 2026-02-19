"""
referral_missions.py - Módulo de Misiones de Referidos
Sistema independiente para gestionar misiones basadas en referidos
NO MODIFICA ninguna lógica existente de la aplicación
"""

import logging
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash

from db import execute_query, get_cursor

logger = logging.getLogger(__name__)

# Crear Blueprint para aislar las rutas
referral_missions_bp = Blueprint('referral_missions', __name__)

# ============================================
# FUNCIONES HELPER DE BASE DE DATOS
# ============================================

def db_fetch_one(query, params=None):
    """Ejecuta una consulta SELECT y retorna una fila"""
    try:
        with get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error en db_fetch_one: {e}")
        return None


def db_fetch_all(query, params=None):
    """Ejecuta una consulta SELECT y retorna todas las filas"""
    try:
        with get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error en db_fetch_all: {e}")
        return []


def db_execute(query, params=None):
    """Ejecuta una consulta INSERT/UPDATE/DELETE"""
    try:
        return execute_query(query, params)
    except Exception as e:
        logger.error(f"Error en db_execute: {e}")
        return None


# ============================================
# FUNCIONES DE BASE DE DATOS - MISIONES
# ============================================

def init_referral_missions_tables():
    """
    Inicializa las tablas necesarias para el módulo de misiones de referidos.
    Se ejecuta al iniciar la aplicación si las tablas no existen.
    """
    # Tabla de misiones de referidos
    create_missions_table = """
    CREATE TABLE IF NOT EXISTS referral_missions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        mission_id VARCHAR(50) NOT NULL UNIQUE,
        title VARCHAR(200) NOT NULL,
        description TEXT DEFAULT NULL,
        required_referrals INT NOT NULL DEFAULT 3,
        reward_amount DECIMAL(20, 8) NOT NULL DEFAULT 0.5,
        reward_currency VARCHAR(10) DEFAULT 'DOGE',
        active TINYINT(1) DEFAULT 1,
        display_order INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_mission_id (mission_id),
        INDEX idx_active (active),
        INDEX idx_display_order (display_order)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    # Tabla de progreso de usuario en misiones
    create_progress_table = """
    CREATE TABLE IF NOT EXISTS referral_mission_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL,
        mission_id VARCHAR(50) NOT NULL,
        referrals_count INT DEFAULT 0,
        status ENUM('in_progress', 'completed', 'claimed') DEFAULT 'in_progress',
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME DEFAULT NULL,
        claimed_at DATETIME DEFAULT NULL,
        reward_paid DECIMAL(20, 8) DEFAULT 0.00000000,
        UNIQUE KEY unique_user_mission (user_id, mission_id),
        INDEX idx_user_id (user_id),
        INDEX idx_mission_id (mission_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    # Tabla de referidos contados para misiones (evita duplicados y fraude)
    create_mission_referrals_table = """
    CREATE TABLE IF NOT EXISTS referral_mission_referrals (
        id INT AUTO_INCREMENT PRIMARY KEY,
        referrer_id VARCHAR(50) NOT NULL,
        referred_id VARCHAR(50) NOT NULL,
        mission_id VARCHAR(50) NOT NULL,
        referred_username VARCHAR(100) DEFAULT NULL,
        is_valid TINYINT(1) DEFAULT 1,
        validation_status VARCHAR(50) DEFAULT 'pending',
        validation_reason TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        validated_at DATETIME DEFAULT NULL,
        UNIQUE KEY unique_mission_referral (referrer_id, referred_id, mission_id),
        INDEX idx_referrer_id (referrer_id),
        INDEX idx_referred_id (referred_id),
        INDEX idx_mission_id (mission_id),
        INDEX idx_is_valid (is_valid)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    # Tabla de logs de auditoría
    create_audit_table = """
    CREATE TABLE IF NOT EXISTS referral_mission_audit (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(50) DEFAULT NULL,
        action VARCHAR(100) NOT NULL,
        mission_id VARCHAR(50) DEFAULT NULL,
        referred_id VARCHAR(50) DEFAULT NULL,
        details TEXT DEFAULT NULL,
        ip_address VARCHAR(50) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_action (action),
        INDEX idx_mission_id (mission_id),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    try:
        db_execute(create_missions_table)
        db_execute(create_progress_table)
        db_execute(create_mission_referrals_table)
        db_execute(create_audit_table)
        logger.info("✅ Tablas de misiones de referidos inicializadas correctamente")
        
        # Insertar misiones por defecto si no existen
        _insert_default_missions()
        
        return True
    except Exception as e:
        logger.error(f"❌ Error al inicializar tablas de misiones: {e}")
        return False


def _insert_default_missions():
    """Inserta las 3 misiones por defecto si no existen"""
    default_missions = [
        ('mission_3_refs', 'Invitar 3 amigos', 'Invita a 3 nuevos usuarios y gana DOGE', 3, 0.5, 'DOGE', 1),
        ('mission_5_refs', 'Invitar 5 amigos', 'Invita a 5 nuevos usuarios y gana DOGE', 5, 1.0, 'DOGE', 2),
        ('mission_10_refs', 'Invitar 10 amigos', 'Invita a 10 nuevos usuarios y gana DOGE', 10, 2.0, 'DOGE', 3),
    ]
    
    for mission_id, title, description, required, reward, currency, order in default_missions:
        query = """
        INSERT IGNORE INTO referral_missions 
        (mission_id, title, description, required_referrals, reward_amount, reward_currency, display_order, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
        """
        try:
            db_execute(query, (mission_id, title, description, required, reward, currency, order))
        except Exception as e:
            logger.warning(f"No se pudo insertar misión {mission_id}: {e}")


# ============================================
# FUNCIONES CRUD DE MISIONES
# ============================================

def get_all_missions(active_only=False):
    """Obtiene todas las misiones ordenadas por display_order"""
    if active_only:
        query = "SELECT * FROM referral_missions WHERE active = 1 ORDER BY display_order ASC"
    else:
        query = "SELECT * FROM referral_missions ORDER BY display_order ASC"
    return db_fetch_all(query) or []


def get_mission(mission_id):
    """Obtiene una misión por su ID"""
    query = "SELECT * FROM referral_missions WHERE mission_id = %s"
    return db_fetch_one(query, (mission_id,))


def get_mission_by_id(id):
    """Obtiene una misión por su ID numérico"""
    query = "SELECT * FROM referral_missions WHERE id = %s"
    return db_fetch_one(query, (id,))


def create_mission(mission_id, title, description, required_referrals, reward_amount, reward_currency='DOGE', display_order=0):
    """Crea una nueva misión"""
    query = """
    INSERT INTO referral_missions 
    (mission_id, title, description, required_referrals, reward_amount, reward_currency, display_order, active)
    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
    """
    try:
        db_execute(query, (mission_id, title, description, required_referrals, reward_amount, reward_currency, display_order))
        log_audit(None, 'mission_created', mission_id=mission_id, details=f"Nueva misión: {title}")
        return True
    except Exception as e:
        logger.error(f"Error al crear misión: {e}")
        return False


def update_mission(mission_id, **kwargs):
    """Actualiza una misión existente"""
    allowed_fields = ['title', 'description', 'required_referrals', 'reward_amount', 'reward_currency', 'active', 'display_order']
    updates = []
    values = []
    
    for field in allowed_fields:
        if field in kwargs:
            updates.append(f"{field} = %s")
            values.append(kwargs[field])
    
    if not updates:
        return False
    
    values.append(mission_id)
    query = f"UPDATE referral_missions SET {', '.join(updates)} WHERE mission_id = %s"
    
    try:
        db_execute(query, tuple(values))
        log_audit(None, 'mission_updated', mission_id=mission_id, details=str(kwargs))
        return True
    except Exception as e:
        logger.error(f"Error al actualizar misión: {e}")
        return False


def delete_mission(mission_id):
    """Elimina una misión (solo si no tiene progreso)"""
    # Verificar si hay usuarios con progreso
    check_query = "SELECT COUNT(*) as count FROM referral_mission_progress WHERE mission_id = %s"
    result = db_fetch_one(check_query, (mission_id,))
    
    if result and result.get('count', 0) > 0:
        return False, "No se puede eliminar: hay usuarios con progreso en esta misión"
    
    try:
        db_execute("DELETE FROM referral_missions WHERE mission_id = %s", (mission_id,))
        log_audit(None, 'mission_deleted', mission_id=mission_id)
        return True, "Misión eliminada correctamente"
    except Exception as e:
        logger.error(f"Error al eliminar misión: {e}")
        return False, str(e)


def toggle_mission(mission_id):
    """Activa/desactiva una misión"""
    query = "UPDATE referral_missions SET active = NOT active WHERE mission_id = %s"
    try:
        db_execute(query, (mission_id,))
        log_audit(None, 'mission_toggled', mission_id=mission_id)
        return True
    except Exception as e:
        logger.error(f"Error al cambiar estado de misión: {e}")
        return False


# ============================================
# FUNCIONES DE PROGRESO DE USUARIO
# ============================================

def get_user_mission_progress(user_id, mission_id):
    """Obtiene el progreso de un usuario en una misión específica"""
    query = """
    SELECT rmp.*, rm.required_referrals, rm.reward_amount, rm.reward_currency, rm.title
    FROM referral_mission_progress rmp
    JOIN referral_missions rm ON rmp.mission_id = rm.mission_id
    WHERE rmp.user_id = %s AND rmp.mission_id = %s
    """
    return db_fetch_one(query, (user_id, mission_id))


def get_all_user_missions_progress(user_id):
    """Obtiene el progreso de un usuario en todas las misiones activas"""
    query = """
    SELECT 
        rm.mission_id,
        rm.title,
        rm.description,
        rm.required_referrals,
        rm.reward_amount,
        rm.reward_currency,
        rm.display_order,
        COALESCE(rmp.referrals_count, 0) as referrals_count,
        COALESCE(rmp.status, 'in_progress') as status,
        rmp.started_at,
        rmp.completed_at,
        rmp.claimed_at
    FROM referral_missions rm
    LEFT JOIN referral_mission_progress rmp ON rm.mission_id = rmp.mission_id AND rmp.user_id = %s
    WHERE rm.active = 1
    ORDER BY rm.display_order ASC
    """
    return db_fetch_all(query, (user_id,)) or []


def init_user_mission_progress(user_id, mission_id):
    """Inicializa el progreso de un usuario en una misión si no existe"""
    query = """
    INSERT IGNORE INTO referral_mission_progress (user_id, mission_id, referrals_count, status)
    VALUES (%s, %s, 0, 'in_progress')
    """
    try:
        db_execute(query, (user_id, mission_id))
        return True
    except Exception as e:
        logger.error(f"Error al inicializar progreso: {e}")
        return False


def get_valid_referrals_for_mission(user_id, mission_id):
    """Cuenta los referidos válidos de un usuario para una misión específica"""
    query = """
    SELECT COUNT(*) as count 
    FROM referral_mission_referrals 
    WHERE referrer_id = %s AND mission_id = %s AND is_valid = 1
    """
    result = db_fetch_one(query, (user_id, mission_id))
    return result.get('count', 0) if result else 0


def add_referral_to_mission(referrer_id, referred_id, referred_username=None, ip_address=None):
    """
    Registra un nuevo referido para las misiones activas.
    Valida que no sea auto-referido, duplicado o fraude.
    Retorna (success, message)
    """
    # Validación 1: No auto-referidos
    if referrer_id == referred_id:
        log_audit(referrer_id, 'referral_rejected', referred_id=referred_id, 
                  details="Auto-referido detectado", ip_address=ip_address)
        return False, "No puedes referirte a ti mismo"
    
    # Validación 2: Verificar que el usuario referido existe
    check_user = db_fetch_one("SELECT user_id FROM users WHERE user_id = %s", (referred_id,))
    if not check_user:
        return False, "Usuario referido no encontrado"
    
    # Validación 3: Verificar que el referidor existe
    check_referrer = db_fetch_one("SELECT user_id FROM users WHERE user_id = %s", (referrer_id,))
    if not check_referrer:
        return False, "Usuario referidor no encontrado"
    
    # Obtener misiones activas
    active_missions = get_all_missions(active_only=True)
    
    if not active_missions:
        return False, "No hay misiones activas"
    
    added_count = 0
    
    for mission in active_missions:
        mission_id = mission['mission_id']
        
        # Verificar si ya existe este referido para esta misión
        check_exists = """
        SELECT id FROM referral_mission_referrals 
        WHERE referrer_id = %s AND referred_id = %s AND mission_id = %s
        """
        existing = db_fetch_one(check_exists, (referrer_id, referred_id, mission_id))
        
        if existing:
            continue  # Ya existe, saltar
        
        # Insertar el referido para esta misión
        insert_query = """
        INSERT INTO referral_mission_referrals 
        (referrer_id, referred_id, mission_id, referred_username, is_valid, validation_status, validated_at)
        VALUES (%s, %s, %s, %s, 1, 'validated', NOW())
        """
        try:
            db_execute(insert_query, (referrer_id, referred_id, mission_id, referred_username))
            added_count += 1
            
            # Actualizar progreso del usuario
            _update_mission_progress(referrer_id, mission_id)
            
            log_audit(referrer_id, 'referral_added', mission_id=mission_id, referred_id=referred_id,
                      details=f"Referido válido: {referred_username or referred_id}", ip_address=ip_address)
                      
        except Exception as e:
            logger.error(f"Error al agregar referido a misión {mission_id}: {e}")
    
    if added_count > 0:
        return True, f"Referido agregado a {added_count} misiones"
    else:
        return False, "El referido ya estaba registrado en todas las misiones"


def _update_mission_progress(user_id, mission_id):
    """Actualiza el progreso de un usuario en una misión"""
    # Contar referidos válidos
    valid_count = get_valid_referrals_for_mission(user_id, mission_id)
    
    # Obtener misión para verificar requisitos
    mission = get_mission(mission_id)
    if not mission:
        return
    
    required = mission['required_referrals']
    
    # Determinar nuevo estado
    if valid_count >= required:
        new_status = 'completed'
    else:
        new_status = 'in_progress'
    
    # Verificar si ya existe progreso
    existing = get_user_mission_progress(user_id, mission_id)
    
    if existing:
        # Si ya está claimed, no cambiar nada
        if existing.get('status') == 'claimed':
            return
        
        # Actualizar progreso
        update_query = """
        UPDATE referral_mission_progress 
        SET referrals_count = %s, status = %s, completed_at = IF(%s = 'completed' AND completed_at IS NULL, NOW(), completed_at)
        WHERE user_id = %s AND mission_id = %s
        """
        db_execute(update_query, (valid_count, new_status, new_status, user_id, mission_id))
    else:
        # Crear nuevo progreso
        insert_query = """
        INSERT INTO referral_mission_progress 
        (user_id, mission_id, referrals_count, status, completed_at)
        VALUES (%s, %s, %s, %s, IF(%s = 'completed', NOW(), NULL))
        """
        db_execute(insert_query, (user_id, mission_id, valid_count, new_status, new_status))


def claim_mission_reward(user_id, mission_id, ip_address=None):
    """
    Reclama la recompensa de una misión completada.
    Retorna (success, message, reward_amount, reward_currency)
    """
    # Obtener progreso
    progress = get_user_mission_progress(user_id, mission_id)
    
    if not progress:
        return False, "No tienes progreso en esta misión", 0, None
    
    if progress['status'] == 'claimed':
        return False, "Ya has reclamado esta recompensa", 0, None
    
    if progress['status'] != 'completed':
        remaining = progress['required_referrals'] - progress['referrals_count']
        return False, f"Misión incompleta. Faltan {remaining} referidos", 0, None
    
    # Obtener misión para la recompensa
    mission = get_mission(mission_id)
    if not mission:
        return False, "Misión no encontrada", 0, None
    
    reward_amount = float(mission['reward_amount'])
    reward_currency = mission['reward_currency']
    
    # Determinar campo de balance según moneda
    balance_field_map = {
        'DOGE': 'doge_balance',
        'SE': 'se_balance',
        'USDT': 'usdt_balance'
    }
    balance_field = balance_field_map.get(reward_currency, 'doge_balance')
    
    try:
        # Actualizar balance del usuario
        update_balance_query = f"""
        UPDATE users SET {balance_field} = {balance_field} + %s WHERE user_id = %s
        """
        db_execute(update_balance_query, (reward_amount, user_id))
        
        # Marcar como reclamada
        claim_query = """
        UPDATE referral_mission_progress 
        SET status = 'claimed', claimed_at = NOW(), reward_paid = %s
        WHERE user_id = %s AND mission_id = %s
        """
        db_execute(claim_query, (reward_amount, user_id, mission_id))
        
        # Registrar en historial de balance
        history_query = """
        INSERT INTO balance_history (user_id, action, currency, amount, description)
        VALUES (%s, 'mission_reward', %s, %s, %s)
        """
        description = f"Recompensa de misión: {mission['title']}"
        db_execute(history_query, (user_id, reward_currency, reward_amount, description))
        
        log_audit(user_id, 'reward_claimed', mission_id=mission_id, 
                  details=f"Recompensa: {reward_amount} {reward_currency}", ip_address=ip_address)
        
        return True, f"¡Felicidades! Has recibido {reward_amount} {reward_currency}", reward_amount, reward_currency
        
    except Exception as e:
        logger.error(f"Error al reclamar recompensa: {e}")
        return False, "Error al procesar la recompensa", 0, None


# ============================================
# FUNCIONES DE AUDITORÍA
# ============================================

def log_audit(user_id, action, mission_id=None, referred_id=None, details=None, ip_address=None):
    """Registra una acción en el log de auditoría"""
    query = """
    INSERT INTO referral_mission_audit 
    (user_id, action, mission_id, referred_id, details, ip_address)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    try:
        db_execute(query, (user_id, action, mission_id, referred_id, details, ip_address))
    except Exception as e:
        logger.error(f"Error al registrar auditoría: {e}")


def get_audit_logs(limit=100, user_id=None, mission_id=None):
    """Obtiene logs de auditoría con filtros opcionales"""
    query = "SELECT * FROM referral_mission_audit WHERE 1=1"
    params = []
    
    if user_id:
        query += " AND user_id = %s"
        params.append(user_id)
    
    if mission_id:
        query += " AND mission_id = %s"
        params.append(mission_id)
    
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    
    return db_fetch_all(query, tuple(params)) or []


# ============================================
# ESTADÍSTICAS DE MISIONES
# ============================================

def get_mission_stats():
    """Obtiene estadísticas generales de las misiones"""
    stats = {}
    
    # Total misiones
    result = db_fetch_one("SELECT COUNT(*) as count FROM referral_missions")
    stats['total_missions'] = result.get('count', 0) if result else 0
    
    # Misiones activas
    result = db_fetch_one("SELECT COUNT(*) as count FROM referral_missions WHERE active = 1")
    stats['active_missions'] = result.get('count', 0) if result else 0
    
    # Total usuarios con progreso
    result = db_fetch_one("SELECT COUNT(DISTINCT user_id) as count FROM referral_mission_progress")
    stats['users_with_progress'] = result.get('count', 0) if result else 0
    
    # Misiones completadas
    result = db_fetch_one("SELECT COUNT(*) as count FROM referral_mission_progress WHERE status IN ('completed', 'claimed')")
    stats['total_completions'] = result.get('count', 0) if result else 0
    
    # Recompensas reclamadas
    result = db_fetch_one("SELECT COUNT(*) as count FROM referral_mission_progress WHERE status = 'claimed'")
    stats['total_claimed'] = result.get('count', 0) if result else 0
    
    # Total recompensas pagadas
    result = db_fetch_one("SELECT SUM(reward_paid) as total FROM referral_mission_progress WHERE status = 'claimed'")
    stats['total_rewards_paid'] = float(result.get('total', 0) or 0) if result else 0
    
    # Total referidos válidos
    result = db_fetch_one("SELECT COUNT(*) as count FROM referral_mission_referrals WHERE is_valid = 1")
    stats['total_valid_referrals'] = result.get('count', 0) if result else 0
    
    return stats


def get_mission_details_stats(mission_id):
    """Obtiene estadísticas detalladas de una misión específica"""
    stats = {}
    
    # Progreso de usuarios
    progress_query = """
    SELECT status, COUNT(*) as count 
    FROM referral_mission_progress 
    WHERE mission_id = %s 
    GROUP BY status
    """
    results = db_fetch_all(progress_query, (mission_id,)) or []
    stats['progress'] = {r['status']: r['count'] for r in results}
    
    # Top referidores
    top_query = """
    SELECT rmp.user_id, rmp.referrals_count, rmp.status, u.username, u.first_name
    FROM referral_mission_progress rmp
    LEFT JOIN users u ON rmp.user_id = u.user_id
    WHERE rmp.mission_id = %s
    ORDER BY rmp.referrals_count DESC
    LIMIT 10
    """
    stats['top_referrers'] = db_fetch_all(top_query, (mission_id,)) or []
    
    return stats


# ============================================
# RUTAS API - USUARIO
# ============================================

def get_user_id_from_request():
    """Obtiene el user_id de la request"""
    user_id = request.args.get('user_id')
    if not user_id:
        user_id = request.form.get('user_id')
    if not user_id:
        try:
            data = request.get_json()
            if data:
                user_id = data.get('user_id')
        except:
            pass
    return user_id


def get_client_ip():
    """Obtiene la IP del cliente"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr


@referral_missions_bp.route('/api/referral-missions/list')
def api_get_missions():
    """API: Obtiene las misiones disponibles con el progreso del usuario"""
    user_id = get_user_id_from_request()
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    try:
        missions = get_all_user_missions_progress(user_id)
        
        # Formatear respuesta
        formatted_missions = []
        for m in missions:
            progress_percent = 0
            if m['required_referrals'] > 0:
                progress_percent = min(100, (m['referrals_count'] / m['required_referrals']) * 100)
            
            formatted_missions.append({
                'mission_id': m['mission_id'],
                'title': m['title'],
                'description': m['description'],
                'required_referrals': m['required_referrals'],
                'current_referrals': m['referrals_count'],
                'progress_percent': round(progress_percent, 1),
                'reward_amount': float(m['reward_amount']),
                'reward_currency': m['reward_currency'],
                'status': m['status'],
                'can_claim': m['status'] == 'completed',
                'is_claimed': m['status'] == 'claimed',
                'completed_at': m['completed_at'].isoformat() if m['completed_at'] else None,
                'claimed_at': m['claimed_at'].isoformat() if m['claimed_at'] else None
            })
        
        return jsonify({
            'success': True,
            'missions': formatted_missions
        })
        
    except Exception as e:
        logger.error(f"Error al obtener misiones: {e}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@referral_missions_bp.route('/api/referral-missions/claim', methods=['POST'])
def api_claim_reward():
    """API: Reclama la recompensa de una misión completada"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        mission_id = data.get('mission_id')
        
        if not user_id or not mission_id:
            return jsonify({'success': False, 'error': 'Faltan parámetros'}), 400
        
        ip_address = get_client_ip()
        success, message, reward_amount, reward_currency = claim_mission_reward(user_id, mission_id, ip_address)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'reward_amount': reward_amount,
                'reward_currency': reward_currency
            })
        else:
            return jsonify({'success': False, 'error': message})
            
    except Exception as e:
        logger.error(f"Error al reclamar recompensa: {e}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@referral_missions_bp.route('/api/referral-missions/check-active')
def api_check_active():
    """API: Verifica si hay misiones activas (para mostrar el botón flotante)"""
    try:
        missions = get_all_missions(active_only=True)
        return jsonify({
            'success': True,
            'has_active_missions': len(missions) > 0,
            'missions_count': len(missions)
        })
    except Exception as e:
        logger.error(f"Error al verificar misiones activas: {e}")
        return jsonify({'success': False, 'has_active_missions': False})


# ============================================
# RUTAS ADMIN - PANEL DE ADMINISTRACIÓN
# ============================================

def admin_required(f):
    """Decorador para verificar acceso de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session or not session['admin_logged_in']:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


@referral_missions_bp.route('/admin/referral-missions')
@admin_required
def admin_missions():
    """Panel de administración de misiones"""
    missions = get_all_missions()
    stats = get_mission_stats()
    return render_template('admin_referral_missions.html', missions=missions, stats=stats)


@referral_missions_bp.route('/admin/referral-missions/new')
@admin_required
def admin_mission_new():
    """Formulario para crear nueva misión"""
    return render_template('admin_referral_mission_form.html', mission=None)


@referral_missions_bp.route('/admin/referral-missions/create', methods=['POST'])
@admin_required
def admin_mission_create():
    """Procesa la creación de nueva misión"""
    try:
        mission_id = request.form.get('mission_id', '').strip()
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        required_referrals = int(request.form.get('required_referrals', 3))
        reward_amount = float(request.form.get('reward_amount', 0.5))
        reward_currency = request.form.get('reward_currency', 'DOGE')
        display_order = int(request.form.get('display_order', 0))
        
        if not mission_id or not title:
            flash('ID y título son obligatorios', 'error')
            return redirect(url_for('referral_missions.admin_mission_new'))
        
        if create_mission(mission_id, title, description, required_referrals, reward_amount, reward_currency, display_order):
            flash('Misión creada correctamente', 'success')
        else:
            flash('Error al crear la misión', 'error')
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('referral_missions.admin_missions'))


@referral_missions_bp.route('/admin/referral-missions/edit/<mission_id>')
@admin_required
def admin_mission_edit(mission_id):
    """Formulario para editar misión"""
    mission = get_mission(mission_id)
    if not mission:
        flash('Misión no encontrada', 'error')
        return redirect(url_for('referral_missions.admin_missions'))
    
    details = get_mission_details_stats(mission_id)
    return render_template('admin_referral_mission_form.html', mission=mission, details=details)


@referral_missions_bp.route('/admin/referral-missions/update/<mission_id>', methods=['POST'])
@admin_required
def admin_mission_update(mission_id):
    """Procesa la actualización de una misión"""
    try:
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        required_referrals = int(request.form.get('required_referrals', 3))
        reward_amount = float(request.form.get('reward_amount', 0.5))
        reward_currency = request.form.get('reward_currency', 'DOGE')
        display_order = int(request.form.get('display_order', 0))
        active = request.form.get('active') == 'on'
        
        if update_mission(mission_id, 
                         title=title, 
                         description=description,
                         required_referrals=required_referrals,
                         reward_amount=reward_amount,
                         reward_currency=reward_currency,
                         display_order=display_order,
                         active=active):
            flash('Misión actualizada correctamente', 'success')
        else:
            flash('Error al actualizar la misión', 'error')
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('referral_missions.admin_missions'))


@referral_missions_bp.route('/admin/referral-missions/toggle/<mission_id>', methods=['POST'])
@admin_required
def admin_mission_toggle(mission_id):
    """Activa/desactiva una misión"""
    if toggle_mission(mission_id):
        flash('Estado de la misión actualizado', 'success')
    else:
        flash('Error al cambiar el estado', 'error')
    return redirect(url_for('referral_missions.admin_missions'))


@referral_missions_bp.route('/admin/referral-missions/delete/<mission_id>', methods=['POST'])
@admin_required
def admin_mission_delete(mission_id):
    """Elimina una misión"""
    success, message = delete_mission(mission_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('referral_missions.admin_missions'))


@referral_missions_bp.route('/admin/referral-missions/audit')
@admin_required
def admin_missions_audit():
    """Vista de logs de auditoría"""
    user_filter = request.args.get('user_id')
    mission_filter = request.args.get('mission_id')
    
    logs = get_audit_logs(limit=200, user_id=user_filter, mission_id=mission_filter)
    missions = get_all_missions()
    
    return render_template('admin_referral_missions_audit.html', logs=logs, missions=missions)


# ============================================
# FUNCIÓN DE HOOK PARA NUEVOS REFERIDOS
# ============================================

def on_new_referral(referrer_id, referred_id, referred_username=None, ip_address=None):
    """
    Hook que se llama cuando un nuevo usuario es referido.
    Esta función debe ser llamada desde el sistema principal de referidos
    sin modificar la lógica existente (solo agregando esta llamada).
    """
    try:
        success, message = add_referral_to_mission(referrer_id, referred_id, referred_username, ip_address)
        if success:
            logger.info(f"✅ Referido {referred_id} agregado a misiones del usuario {referrer_id}")
        return success, message
    except Exception as e:
        logger.error(f"Error en hook de nuevo referido: {e}")
        return False, str(e)
