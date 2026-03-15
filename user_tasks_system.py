"""
user_tasks_system.py - Sistema de Tareas Promocionadas por Usuarios
Incluye sistema de verificación de permanencia (3 días) y penalizaciones
"""

import uuid
import json
import os
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from db import execute_query, get_cursor

# ============== CONFIGURACIÓN ==============
STAY_DAYS_REQUIRED = 3  # Días que debe permanecer en el canal
USER_TASK_COMPLETION_REWARD = 50  # PXC por tarea completada

# ============== PRECIOS DE PAQUETES ==============
USER_TASK_PACKAGES = {
    'starter': {
        'id': 'starter',
        'name': 'Starter',
        'price_se': 20,
        'max_completions': 100,
        'description': 'Ideal para empezar',
        'icon': '🚀',
        'popular': False
    },
    'basic': {
        'id': 'basic',
        'name': 'Basic',
        'price_se': 50,
        'max_completions': 300,
        'description': 'Para canales pequeños',
        'icon': '⭐',
        'popular': False
    },
    'standard': {
        'id': 'standard',
        'name': 'Standard',
        'price_se': 100,
        'max_completions': 700,
        'description': 'Mejor valor',
        'icon': '💎',
        'popular': True
    },
    'premium': {
        'id': 'premium',
        'name': 'Premium',
        'price_se': 200,
        'max_completions': 1500,
        'description': 'Para proyectos serios',
        'icon': '👑',
        'popular': False
    },
    'enterprise': {
        'id': 'enterprise',
        'name': 'Enterprise',
        'price_se': 500,
        'max_completions': 4000,
        'description': 'Máxima exposición',
        'icon': '🏆',
        'popular': False
    }
}

def init_user_tasks_table():
    """Crea las tablas necesarias"""
    try:
        # Tabla principal de tareas
        execute_query("""
            CREATE TABLE IF NOT EXISTS user_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_id VARCHAR(50) UNIQUE NOT NULL,
                creator_id VARCHAR(50) NOT NULL,
                task_type ENUM('telegram_channel', 'telegram_group', 'website', 'social', 'other') DEFAULT 'telegram_channel',
                title VARCHAR(255) NOT NULL,
                description TEXT,
                url VARCHAR(500) NOT NULL,
                channel_username VARCHAR(100) DEFAULT NULL,
                requires_join TINYINT(1) DEFAULT 0,
                package_id VARCHAR(50) NOT NULL,
                price_paid DECIMAL(20,8) NOT NULL,
                max_completions INT NOT NULL,
                current_completions INT DEFAULT 0,
                reward_per_completion DECIMAL(10,4) DEFAULT 50,
                status ENUM('pending', 'active', 'paused', 'completed', 'rejected', 'expired') DEFAULT 'active',
                rejection_reason TEXT DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                approved_at DATETIME DEFAULT NULL,
                completed_at DATETIME DEFAULT NULL,
                expires_at DATETIME DEFAULT NULL,
                INDEX idx_creator (creator_id),
                INDEX idx_status (status),
                INDEX idx_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Tabla de completaciones con sistema de verificación
        execute_query("""
            CREATE TABLE IF NOT EXISTS user_task_completions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_id VARCHAR(50) NOT NULL,
                user_id VARCHAR(50) NOT NULL,
                completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reward_earned DECIMAL(10,4) DEFAULT 0,
                verified TINYINT(1) DEFAULT 0,
                must_stay_until DATETIME DEFAULT NULL,
                left_channel TINYINT(1) DEFAULT 0,
                left_at DATETIME DEFAULT NULL,
                penalty_applied TINYINT(1) DEFAULT 0,
                penalty_amount DECIMAL(10,4) DEFAULT 0,
                penalty_notified TINYINT(1) DEFAULT 0,
                UNIQUE KEY unique_completion (task_id, user_id),
                INDEX idx_task (task_id),
                INDEX idx_user (user_id),
                INDEX idx_stay (must_stay_until, left_channel)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Tabla de penalizaciones
        execute_query("""
            CREATE TABLE IF NOT EXISTS user_task_penalties (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                task_id VARCHAR(50) NOT NULL,
                channel_username VARCHAR(100),
                penalty_amount DECIMAL(10,4) NOT NULL,
                reason TEXT,
                notified TINYINT(1) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user (user_id),
                INDEX idx_notified (notified)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        print("[user_tasks] ✅ Tablas creadas correctamente")
        return True
    except Exception as e:
        print(f"[user_tasks] ❌ Error creando tablas: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_packages():
    return USER_TASK_PACKAGES

def get_package(package_id):
    return USER_TASK_PACKAGES.get(package_id)

def create_user_task(creator_id, task_type, title, description, url, channel_username, requires_join, package_id):
    """Crea una nueva tarea de usuario"""
    from database import get_user, update_balance
    
    package = get_package(package_id)
    if not package:
        return False, "Paquete no válido", None
    
    user = get_user(creator_id)
    if not user:
        return False, "Usuario no encontrado", None
    
    se_balance = float(user.get('se_balance', 0))
    price = package['price_se']
    
    if se_balance < price:
        return False, f"Balance insuficiente. Necesitas {price} PXC, tienes {se_balance:.4f} PXC", None
    
    task_id = f"ut_{uuid.uuid4().hex[:12]}"
    
    # Limpiar channel_username
    if channel_username:
        channel_username = channel_username.strip()
        if channel_username.startswith('@'):
            channel_username = channel_username[1:]
        if channel_username.startswith('https://t.me/'):
            channel_username = channel_username.replace('https://t.me/', '')
    
    try:
        # Descontar DOGE
        success = update_balance(creator_id, 'se', price, 'subtract', f'User task: {task_id}')
        if not success:
            return False, "Error al procesar el pago", None
        
        # Crear la tarea
        execute_query("""
            INSERT INTO user_tasks 
            (task_id, creator_id, task_type, title, description, url, channel_username, 
             requires_join, package_id, price_paid, max_completions, reward_per_completion, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
        """, (
            task_id, str(creator_id), task_type, title, description, url, channel_username,
            1 if requires_join else 0, package_id, price, package['max_completions'],
            USER_TASK_COMPLETION_REWARD
        ))
        
        print(f"[user_tasks] ✅ Tarea {task_id} creada por {creator_id}")
        return True, f"¡Tarea creada! ID: {task_id}", task_id
        
    except Exception as e:
        print(f"[user_tasks] ❌ Error: {e}")
        try:
            update_balance(creator_id, 'se', price, 'add', f'Refund: {task_id}')
        except:
            pass
        return False, str(e), None

def get_active_user_tasks(exclude_creator=None, exclude_completed_by=None):
    """Obtiene tareas activas para completar"""
    try:
        with get_cursor() as cursor:
            query = """
                SELECT * FROM user_tasks 
                WHERE status = 'active' 
                AND current_completions < max_completions
            """
            params = []
            
            if exclude_creator:
                query += " AND creator_id != %s"
                params.append(str(exclude_creator))
            
            if exclude_completed_by:
                query += """ AND task_id NOT IN (
                    SELECT task_id FROM user_task_completions WHERE user_id = %s
                )"""
                params.append(str(exclude_completed_by))
            
            query += " ORDER BY created_at DESC LIMIT 50"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                if isinstance(row, dict):
                    row['requires_join'] = bool(row.get('requires_join', 0))
                    result.append(row)
                else:
                    cols = [col[0] for col in cursor.description]
                    d = dict(zip(cols, row))
                    d['requires_join'] = bool(d.get('requires_join', 0))
                    result.append(d)
            
            return result
    except Exception as e:
        print(f"[user_tasks] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_user_task(task_id):
    """Obtiene una tarea por ID"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM user_tasks WHERE task_id = %s", (task_id,))
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    row['requires_join'] = bool(row.get('requires_join', 0))
                    return row
                cols = [col[0] for col in cursor.description]
                d = dict(zip(cols, row))
                d['requires_join'] = bool(d.get('requires_join', 0))
                return d
            return None
    except Exception as e:
        print(f"[user_tasks] ❌ Error: {e}")
        return None

def get_user_created_tasks(user_id):
    """Obtiene tareas creadas por un usuario"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM user_tasks WHERE creator_id = %s ORDER BY created_at DESC
            """, (str(user_id),))
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                if isinstance(row, dict):
                    row['requires_join'] = bool(row.get('requires_join', 0))
                    result.append(row)
                else:
                    cols = [col[0] for col in cursor.description]
                    d = dict(zip(cols, row))
                    d['requires_join'] = bool(d.get('requires_join', 0))
                    result.append(d)
            return result
    except Exception as e:
        print(f"[user_tasks] ❌ Error: {e}")
        return []

def is_user_task_completed(task_id, user_id):
    """Verifica si ya completó la tarea"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count FROM user_task_completions 
                WHERE task_id = %s AND user_id = %s
            """, (task_id, str(user_id)))
            row = cursor.fetchone()
            if isinstance(row, dict):
                return row.get('count', 0) > 0
            return row[0] > 0 if row else False
    except:
        return False

def complete_user_task(task_id, user_id):
    """Completa una tarea y registra para verificación de permanencia"""
    from database import update_balance
    
    task = get_user_task(task_id)
    if not task:
        return False, "task_not_found", 0
    
    if task['status'] != 'active':
        return False, "task_not_active", 0
    
    if str(task['creator_id']) == str(user_id):
        return False, "cannot_complete_own_task", 0
    
    if is_user_task_completed(task_id, user_id):
        return False, "task_already_completed", 0
    
    if task['current_completions'] >= task['max_completions']:
        return False, "task_exhausted", 0
    
    reward = float(task.get('reward_per_completion', USER_TASK_COMPLETION_REWARD))
    requires_join = task.get('requires_join', False)
    
    # Calcular fecha límite de permanencia (3 días)
    must_stay_until = datetime.now() + timedelta(days=STAY_DAYS_REQUIRED) if requires_join else None
    
    try:
        # Registrar completación
        execute_query("""
            INSERT INTO user_task_completions 
            (task_id, user_id, reward_earned, verified, must_stay_until, left_channel)
            VALUES (%s, %s, %s, 1, %s, 0)
        """, (task_id, str(user_id), reward, must_stay_until))
        
        # Actualizar contador
        execute_query("""
            UPDATE user_tasks SET current_completions = current_completions + 1 WHERE task_id = %s
        """, (task_id,))
        
        # Verificar si se completó
        if task['current_completions'] + 1 >= task['max_completions']:
            execute_query("""
                UPDATE user_tasks SET status = 'completed', completed_at = NOW() WHERE task_id = %s
            """, (task_id,))
        
        # Pagar recompensa
        update_balance(user_id, 'se', reward, 'add', f'Task: {task_id}')

        # Notificar al usuario vía bot
        print(f"[user_tasks] 🔔 Enviando notificación de completado a {user_id}...")
        try:
            from task_notifications import notify_task_completed
            notify_task_completed(user_id, task.get('title', ''), reward)
        except Exception as _ne:
            import traceback
            print(f"[user_tasks] ❌ Error notificación completado: {_ne}")
            traceback.print_exc()

        print(f"[user_tasks] ✅ {user_id} completó {task_id}, +{reward} PXC")
        return True, f"task_completed:{reward}", reward
        
    except Exception as e:
        print(f"[user_tasks] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, "task_error", 0

def get_user_task_stats(user_id):
    """Estadísticas del usuario"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    COALESCE(SUM(current_completions), 0) as completions,
                    COALESCE(SUM(price_paid), 0) as spent
                FROM user_tasks WHERE creator_id = %s
            """, (str(user_id),))
            created = cursor.fetchone()
            
            cursor.execute("""
                SELECT COUNT(*) as done, COALESCE(SUM(reward_earned), 0) as earned
                FROM user_task_completions WHERE user_id = %s
            """, (str(user_id),))
            completed = cursor.fetchone()
            
            if isinstance(created, dict):
                return {
                    'created': {
                        'total': int(created.get('total') or 0),
                        'active': int(created.get('active') or 0),
                        'completed': int(created.get('completed') or 0),
                        'total_completions': int(created.get('completions') or 0),
                        'total_spent': float(created.get('spent') or 0)
                    },
                    'completed': {
                        'total': int(completed.get('done') or 0) if completed else 0,
                        'total_earned': float(completed.get('earned') or 0) if completed else 0
                    }
                }
            return {'created': {}, 'completed': {}}
    except Exception as e:
        print(f"[user_tasks] ❌ Error stats: {e}")
        return {'created': {}, 'completed': {}}

def pause_user_task(task_id, user_id):
    """Pausa una tarea"""
    task = get_user_task(task_id)
    if not task or str(task['creator_id']) != str(user_id):
        return False, "No autorizado"
    if task['status'] != 'active':
        return False, "Solo puedes pausar tareas activas"
    execute_query("UPDATE user_tasks SET status = 'paused' WHERE task_id = %s", (task_id,))
    return True, "Tarea pausada"

def resume_user_task(task_id, user_id):
    """Reactiva una tarea"""
    task = get_user_task(task_id)
    if not task or str(task['creator_id']) != str(user_id):
        return False, "No autorizado"
    if task['status'] != 'paused':
        return False, "Solo puedes reactivar tareas pausadas"
    execute_query("UPDATE user_tasks SET status = 'active' WHERE task_id = %s", (task_id,))
    return True, "Tarea reactivada"

def delete_user_task(task_id, user_id):
    """Elimina una tarea (solo el creador puede hacerlo)"""
    from database import update_balance
    task = get_user_task(task_id)
    if not task or str(task['creator_id']) != str(user_id):
        return False, "No autorizado"
    # Reembolso proporcional si quedan cupos sin completar
    completed = int(task.get('current_completions', 0))
    max_comp   = int(task.get('max_completions', 0))
    price_paid = float(task.get('price_paid', 0))
    if price_paid > 0 and max_comp > 0 and completed < max_comp:
        remaining_ratio = (max_comp - completed) / max_comp
        refund = round(price_paid * remaining_ratio, 4)
        update_balance(user_id, 'se', refund, 'add', f'Refund delete: {task_id}')
    execute_query("DELETE FROM user_tasks WHERE task_id = %s", (task_id,))
    return True, "Tarea eliminada"

# ============== SISTEMA DE VERIFICACIÓN Y PENALIZACIÓN ==============

def check_channel_membership(user_id, channel_username):
    """Verifica si el usuario sigue en el canal"""
    try:
        BOT_TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
        if not BOT_TOKEN:
            print(f"[user_tasks] ⚠️ BOT_TOKEN no configurado, no se puede verificar")
            return True  # No podemos verificar
        
        chat_id = f"@{channel_username}" if not channel_username.startswith('@') else channel_username
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        response = requests.get(url, params={
            'chat_id': chat_id,
            'user_id': user_id
        }, timeout=10)
        
        result = response.json()
        print(f"[user_tasks] Verificación @{channel_username} para {user_id}: {result.get('ok')}, status={result.get('result', {}).get('status', 'N/A')}")
        
        if result.get('ok'):
            status = result.get('result', {}).get('status', '')
            is_member = status in ['member', 'administrator', 'creator']
            print(f"[user_tasks] Usuario {user_id} en @{channel_username}: is_member={is_member}, status={status}")
            return is_member
        else:
            # Error de API - puede ser que el bot no tiene permisos o canal no existe
            error_desc = result.get('description', '')
            print(f"[user_tasks] ⚠️ Error API Telegram: {error_desc}")
            # Si el usuario dejó el chat o fue baneado, no es miembro
            if 'user not found' in error_desc.lower() or 'left' in error_desc.lower() or 'kicked' in error_desc.lower():
                return False
            return True  # En caso de otros errores, no penalizar
    except Exception as e:
        print(f"[user_tasks] ❌ Error verificando canal @{channel_username}: {e}")
        import traceback
        traceback.print_exc()
        return True  # En caso de error, no penalizar

def check_and_penalize_leavers():
    """
    Verifica usuarios que salieron del canal antes de tiempo y aplica penalizaciones.
    Debe ejecutarse periódicamente (cron job).
    """
    from database import update_balance
    
    try:
        with get_cursor() as cursor:
            # Obtener completaciones que requieren verificación
            cursor.execute("""
                SELECT utc.*, ut.channel_username, ut.title
                FROM user_task_completions utc
                JOIN user_tasks ut ON utc.task_id = ut.task_id
                WHERE utc.must_stay_until IS NOT NULL
                AND utc.must_stay_until > NOW()
                AND utc.left_channel = 0
                AND utc.penalty_applied = 0
                AND ut.requires_join = 1
                AND ut.channel_username IS NOT NULL
            """)
            
            completions = cursor.fetchall()
            
            penalties_to_notify = []
            
            for comp in completions:
                if isinstance(comp, dict):
                    user_id = comp['user_id']
                    task_id = comp['task_id']
                    channel = comp['channel_username']
                    reward = float(comp.get('reward_earned', 0))
                    title = comp.get('title', '')
                else:
                    continue
                
                # Verificar si sigue en el canal
                is_member = check_channel_membership(user_id, channel)
                
                if not is_member:
                    # Usuario salió del canal - PENALIZAR CON EL DOBLE
                    penalty_amount = 100  # Penalización fija de 100 PXC
                    print(f"[user_tasks] ⚠️ Usuario {user_id} salió de @{channel} - Penalización: {penalty_amount} PXC (sanción fija)")
                    
                    # Marcar como salido
                    execute_query("""
                        UPDATE user_task_completions 
                        SET left_channel = 1, left_at = NOW(), penalty_applied = 1, penalty_amount = %s
                        WHERE task_id = %s AND user_id = %s
                    """, (penalty_amount, task_id, user_id))
                    
                    # Descontar 100 PXC (sanción fija, permite saldo negativo)
                    update_balance(user_id, 'se', penalty_amount, 'subtract', f'Penalty (100 PXC): left @{channel}', allow_negative=True)
                    
                    # Registrar penalización
                    execute_query("""
                        INSERT INTO user_task_penalties 
                        (user_id, task_id, channel_username, penalty_amount, reason, notified)
                        VALUES (%s, %s, %s, %s, %s, 0)
                    """, (user_id, task_id, channel, penalty_amount, f'Salió del canal @{channel} antes de {STAY_DAYS_REQUIRED} días (penalización 2x)'))
                    
                    penalties_to_notify.append({
                        'user_id': user_id,
                        'channel': channel,
                        'amount': reward,
                        'title': title
                    })
            
            return penalties_to_notify
            
    except Exception as e:
        print(f"[user_tasks] ❌ Error verificando: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_pending_penalty_notifications():
    """Obtiene penalizaciones pendientes de notificar"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM user_task_penalties 
                WHERE notified = 0 
                ORDER BY created_at ASC
            """)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append(row)
                else:
                    cols = [col[0] for col in cursor.description]
                    result.append(dict(zip(cols, row)))
            return result
    except:
        return []

def mark_penalty_notified(penalty_id):
    """Marca una penalización como notificada"""
    try:
        execute_query("UPDATE user_task_penalties SET notified = 1 WHERE id = %s", (penalty_id,))
        return True
    except:
        return False

def send_penalty_notification(user_id, channel, amount):
    """Envía mensaje de penalización al usuario via Telegram Bot"""
    try:
        BOT_TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
        if not BOT_TOKEN:
            print(f"[user_tasks] ⚠️ BOT_TOKEN no configurado, no se puede enviar mensaje")
            return False
        
        message = f"""😡 <b>¡PENALIZACIÓN APLICADA!</b>

🚫 Hemos detectado que te diste de baja del canal <b>@{channel}</b> antes de cumplir los 3 días requeridos.

💸 <b>Se han deducido -{amount:.4f} PXC de tu saldo.</b>
⚠️ <b>(Penalización = 2x la recompensa ganada)</b>

📋 Recuerda: Debes permanecer en los canales por al menos <b>3 días</b> después de completar una tarea.

❗ Si tu saldo queda negativo, deberás pagarlo antes de poder retirar.

¡No intentes hacer trampa! El sistema verifica automáticamente tu membresía.

<i>— SALLY-E Bot 🤖</i>"""

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        response = requests.post(url, json={
            'chat_id': user_id,
            'text': message,
            'parse_mode': 'HTML'
        }, timeout=10)
        
        result = response.json()
        if result.get('ok'):
            print(f"[user_tasks] ✅ Mensaje de penalización enviado a {user_id}")
            return True
        else:
            print(f"[user_tasks] ❌ Error enviando mensaje: {result.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"[user_tasks] ❌ Error enviando notificación: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_penalties_and_notify():
    """
    Función completa: verifica, penaliza y notifica.
    Llamar desde un cron job cada hora aproximadamente.
    """
    # Verificar y penalizar
    penalties = check_and_penalize_leavers()
    
    # Notificar penalizaciones pendientes
    pending = get_pending_penalty_notifications()
    
    for penalty in pending:
        if isinstance(penalty, dict):
            user_id = penalty.get('user_id')
            channel = penalty.get('channel_username', 'desconocido')
            amount = float(penalty.get('penalty_amount', 0))
            penalty_id = penalty.get('id')
            
            if send_penalty_notification(user_id, channel, amount):
                mark_penalty_notified(penalty_id)
                print(f"[user_tasks] ✅ Penalización notificada a {user_id}")
            else:
                print(f"[user_tasks] ⚠️ No se pudo notificar a {user_id}")
    
    return len(penalties), len(pending)


def check_user_channel_memberships(user_id):
    """
    Verifica si un usuario específico sigue en los canales de sus tareas completadas.
    Aplica penalizaciones si salió antes de tiempo y envía mensaje inmediatamente.
    Retorna lista de penalizaciones aplicadas.
    """
    from database import update_balance
    
    penalties_applied = []
    
    try:
        print(f"[user_tasks] 🔍 Verificando membresías para usuario {user_id}")
        
        with get_cursor() as cursor:
            # Obtener tareas completadas del usuario que requieren verificación
            cursor.execute("""
                SELECT utc.*, ut.channel_username, ut.title
                FROM user_task_completions utc
                JOIN user_tasks ut ON utc.task_id = ut.task_id
                WHERE utc.user_id = %s
                AND utc.must_stay_until IS NOT NULL
                AND utc.must_stay_until > NOW()
                AND utc.left_channel = 0
                AND utc.penalty_applied = 0
                AND ut.requires_join = 1
                AND ut.channel_username IS NOT NULL
            """, (str(user_id),))
            
            completions = cursor.fetchall()
            print(f"[user_tasks] Encontradas {len(completions)} tareas pendientes de verificación para {user_id}")
            
            for comp in completions:
                if isinstance(comp, dict):
                    task_id = comp['task_id']
                    channel = comp['channel_username']
                    reward = float(comp.get('reward_earned', 0))
                    title = comp.get('title', '')
                else:
                    # Convertir tuple a dict si es necesario
                    cols = [col[0] for col in cursor.description]
                    comp = dict(zip(cols, comp))
                    task_id = comp['task_id']
                    channel = comp['channel_username']
                    reward = float(comp.get('reward_earned', 0))
                    title = comp.get('title', '')
                
                print(f"[user_tasks] Verificando tarea {task_id}: @{channel}, reward={reward}")
                
                # Verificar si sigue en el canal
                is_member = check_channel_membership(user_id, channel)
                
                if not is_member:
                    # Usuario salió del canal - PENALIZAR CON EL DOBLE
                    penalty_amount = 100  # Penalización fija de 100 PXC
                    print(f"[user_tasks] ⚠️ PENALIZACIÓN: Usuario {user_id} salió de @{channel} - Penalización: 100 PXC (sanción fija)")
                    
                    # Marcar como salido
                    execute_query("""
                        UPDATE user_task_completions 
                        SET left_channel = 1, left_at = NOW(), penalty_applied = 1, penalty_amount = %s
                        WHERE task_id = %s AND user_id = %s
                    """, (penalty_amount, task_id, user_id))
                    
                    # Descontar 100 PXC (sanción fija, permite saldo negativo)
                    update_balance(user_id, 'se', penalty_amount, 'subtract', f'Penalty (100 PXC): left @{channel}', allow_negative=True)
                    print(f"[user_tasks] 💸 Descontados 100 PXC a usuario {user_id} (sanción fija)")
                    
                    # Registrar penalización como ya notificada (se notifica por el modal)
                    execute_query("""
                        INSERT INTO user_task_penalties 
                        (user_id, task_id, channel_username, penalty_amount, reason, notified)
                        VALUES (%s, %s, %s, %s, %s, 1)
                    """, (user_id, task_id, channel, penalty_amount, f'Salió del canal @{channel} antes de {STAY_DAYS_REQUIRED} días (penalización 2x)'))
                    
                    # ENVIAR MENSAJE DE TELEGRAM INMEDIATAMENTE
                    msg_sent = send_penalty_notification(user_id, channel, penalty_amount)
                    print(f"[user_tasks] 📨 Mensaje Telegram enviado: {msg_sent}")
                    
                    penalties_applied.append({
                        'channel': channel,
                        'amount': penalty_amount,
                        'title': title
                    })
                else:
                    print(f"[user_tasks] ✅ Usuario {user_id} sigue en @{channel}")
        
        print(f"[user_tasks] Verificación completa: {len(penalties_applied)} penalizaciones aplicadas")
        return penalties_applied
        
    except Exception as e:
        print(f"[user_tasks] ❌ Error verificando usuario {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_user_pending_warnings(user_id):
    """
    Obtiene las advertencias/penalizaciones pendientes de notificar para un usuario.
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM user_task_penalties 
                WHERE user_id = %s AND notified = 0 
                ORDER BY created_at DESC
            """, (str(user_id),))
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                if isinstance(row, dict):
                    result.append(row)
                else:
                    cols = [col[0] for col in cursor.description]
                    result.append(dict(zip(cols, row)))
            return result
    except:
        return []


# Inicializar tablas
try:
    init_user_tasks_table()
except:
    pass
