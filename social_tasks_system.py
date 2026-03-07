"""
SISTEMA DE TAREAS SOCIALES CON CAPTURA DE PANTALLA
- Admin crea tareas (TikTok, Twitter, Instagram, Facebook, Binance, YouTube, etc.)
- Usuario completa la tarea y sube captura de pantalla
- Admin revisa y aprueba/rechaza
- Se acredita recompensa automáticamente al aprobar
"""

import uuid
import base64
import os
from datetime import datetime
from database import execute_query, fetch_one, fetch_all, update_balance

# ============================================================
# PLATAFORMAS DISPONIBLES (admin puede activar/desactivar)
# ============================================================
DEFAULT_PLATFORMS = [
    {'id': 'tiktok',    'name': 'TikTok',     'icon': '🎵', 'color': '#010101'},
    {'id': 'twitter',   'name': 'X (Twitter)','icon': '🐦', 'color': '#1DA1F2'},
    {'id': 'instagram', 'name': 'Instagram',  'icon': '📷', 'color': '#E1306C'},
    {'id': 'facebook',  'name': 'Facebook',   'icon': '📘', 'color': '#1877F2'},
    {'id': 'youtube',   'name': 'YouTube',    'icon': '▶️', 'color': '#FF0000'},
    {'id': 'binance',   'name': 'Binance',    'icon': '🔶', 'color': '#F0B90B'},
    {'id': 'telegram',  'name': 'Telegram',   'icon': '✈️', 'color': '#2AABEE'},
    {'id': 'discord',   'name': 'Discord',    'icon': '🎮', 'color': '#5865F2'},
    {'id': 'other',     'name': 'Otro',       'icon': '🔗', 'color': '#666666'},
]

TASK_ACTIONS = [
    {'id': 'follow',    'name': 'Seguir / Suscribirse'},
    {'id': 'like',      'name': 'Dar Me Gusta'},
    {'id': 'comment',   'name': 'Comentar'},
    {'id': 'share',     'name': 'Compartir / Repostear'},
    {'id': 'register',  'name': 'Registrarse'},
    {'id': 'join',      'name': 'Unirse a grupo/comunidad'},
    {'id': 'watch',     'name': 'Ver video'},
    {'id': 'custom',    'name': 'Personalizado'},
]

# Directorio para guardar capturas
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'social_task_uploads')


def init_social_tasks_tables():
    """Crea las tablas necesarias para el sistema de tareas sociales"""
    try:
        # Tabla de tareas sociales
        execute_query("""
            CREATE TABLE IF NOT EXISTS social_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_id VARCHAR(50) UNIQUE NOT NULL,
                platform VARCHAR(50) NOT NULL,
                action_type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                target_url VARCHAR(500),
                target_username VARCHAR(255),
                instructions TEXT,
                reward_amount DECIMAL(18,6) NOT NULL DEFAULT 1.0,
                reward_currency ENUM('se','doge') NOT NULL DEFAULT 'se',
                max_completions INT NOT NULL DEFAULT 100,
                current_completions INT NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                requires_screenshot BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        # Tabla de envíos de usuarios
        execute_query("""
            CREATE TABLE IF NOT EXISTS social_task_submissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                submission_id VARCHAR(50) UNIQUE NOT NULL,
                task_id VARCHAR(50) NOT NULL,
                user_id VARCHAR(50) NOT NULL,
                screenshot_path VARCHAR(500),
                screenshot_data MEDIUMTEXT,
                user_note TEXT,
                status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
                admin_note TEXT,
                reviewed_by VARCHAR(50),
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP NULL,
                reward_credited BOOLEAN NOT NULL DEFAULT FALSE,
                UNIQUE KEY unique_user_task (task_id, user_id)
            )
        """)

        print("[SocialTasks] ✅ Tablas inicializadas")
        return True
    except Exception as e:
        print(f"[SocialTasks] ❌ Error inicializando tablas: {e}")
        return False


# ============================================================
# FUNCIONES ADMIN
# ============================================================

def admin_create_social_task(platform, action_type, title, description,
                              target_url, target_username, instructions,
                              reward_amount, reward_currency, max_completions,
                              requires_screenshot=True):
    try:
        task_id = f"st_{uuid.uuid4().hex[:12]}"
        execute_query("""
            INSERT INTO social_tasks
            (task_id, platform, action_type, title, description, target_url,
             target_username, instructions, reward_amount, reward_currency,
             max_completions, requires_screenshot)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (task_id, platform, action_type, title, description, target_url,
              target_username, instructions, float(reward_amount), reward_currency,
              int(max_completions), bool(requires_screenshot)))
        return {'success': True, 'task_id': task_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def admin_update_social_task(task_id, **kwargs):
    try:
        allowed = ['title','description','target_url','target_username','instructions',
                   'reward_amount','reward_currency','max_completions','is_active','requires_screenshot']
        sets, vals = [], []
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k} = %s")
                vals.append(v)
        if not sets:
            return {'success': False, 'error': 'Nada que actualizar'}
        vals.append(task_id)
        execute_query(f"UPDATE social_tasks SET {', '.join(sets)} WHERE task_id = %s", vals)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def admin_delete_social_task(task_id):
    try:
        execute_query("UPDATE social_tasks SET is_active = FALSE WHERE task_id = %s", (task_id,))
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def admin_get_all_tasks(include_inactive=True):
    try:
        sql = "SELECT * FROM social_tasks"
        if not include_inactive:
            sql += " WHERE is_active = TRUE"
        sql += " ORDER BY created_at DESC"
        return fetch_all(sql) or []
    except Exception as e:
        print(f"[SocialTasks] Error: {e}")
        return []


def admin_get_pending_submissions(task_id=None):
    try:
        if task_id:
            rows = fetch_all("""
                SELECT s.*, t.title as task_title, t.platform, t.action_type,
                       t.reward_amount, t.reward_currency,
                       u.first_name, u.username
                FROM social_task_submissions s
                JOIN social_tasks t ON s.task_id = t.task_id
                LEFT JOIN users u ON s.user_id = u.user_id
                WHERE s.task_id = %s AND s.status = 'pending'
                ORDER BY s.submitted_at ASC
            """, (task_id,))
        else:
            rows = fetch_all("""
                SELECT s.*, t.title as task_title, t.platform, t.action_type,
                       t.reward_amount, t.reward_currency,
                       u.first_name, u.username
                FROM social_task_submissions s
                JOIN social_tasks t ON s.task_id = t.task_id
                LEFT JOIN users u ON s.user_id = u.user_id
                WHERE s.status = 'pending'
                ORDER BY s.submitted_at ASC
            """)
        return rows or []
    except Exception as e:
        print(f"[SocialTasks] Error: {e}")
        return []


def admin_get_all_submissions(status=None, limit=100):
    try:
        sql = """
            SELECT s.*, t.title as task_title, t.platform, t.action_type,
                   t.reward_amount, t.reward_currency,
                   u.first_name, u.username
            FROM social_task_submissions s
            JOIN social_tasks t ON s.task_id = t.task_id
            LEFT JOIN users u ON s.user_id = u.user_id
        """
        params = []
        if status:
            sql += " WHERE s.status = %s"
            params.append(status)
        sql += " ORDER BY s.submitted_at DESC LIMIT %s"
        params.append(limit)
        return fetch_all(sql, params) or []
    except Exception as e:
        return []


def admin_approve_submission(submission_id, admin_note=''):
    try:
        sub = fetch_one("""
            SELECT s.*, t.reward_amount, t.reward_currency, t.task_id
            FROM social_task_submissions s
            JOIN social_tasks t ON s.task_id = t.task_id
            WHERE s.submission_id = %s AND s.status = 'pending'
        """, (submission_id,))

        if not sub:
            return {'success': False, 'error': 'Envío no encontrado o ya revisado'}

        # Acreditar recompensa
        currency = sub['reward_currency']
        amount = float(sub['reward_amount'])
        update_balance(sub['user_id'], currency, amount, 'add',
                       f"Tarea social aprobada: {sub['task_id']}")

        # Actualizar estado
        execute_query("""
            UPDATE social_task_submissions
            SET status='approved', admin_note=%s, reviewed_at=NOW(), reward_credited=TRUE
            WHERE submission_id=%s
        """, (admin_note, submission_id))

        # Incrementar contador de completaciones
        execute_query("""
            UPDATE social_tasks SET current_completions = current_completions + 1
            WHERE task_id = %s
        """, (sub['task_id'],))

        return {'success': True, 'rewarded': amount, 'currency': currency}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def admin_reject_submission(submission_id, admin_note=''):
    try:
        sub = fetch_one(
            "SELECT * FROM social_task_submissions WHERE submission_id=%s AND status='pending'",
            (submission_id,))
        if not sub:
            return {'success': False, 'error': 'Envío no encontrado o ya revisado'}

        execute_query("""
            UPDATE social_task_submissions
            SET status='rejected', admin_note=%s, reviewed_at=NOW()
            WHERE submission_id=%s
        """, (admin_note, submission_id))
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============================================================
# FUNCIONES USUARIO
# ============================================================

def get_active_social_tasks(user_id=None):
    try:
        rows = fetch_all("""
            SELECT t.*
            FROM social_tasks t
            WHERE t.is_active = TRUE
              AND t.current_completions < t.max_completions
            ORDER BY t.created_at DESC
        """) or []

        if user_id:
            # Marcar cuáles ya completó el usuario
            subs = fetch_all("""
                SELECT task_id, status FROM social_task_submissions
                WHERE user_id = %s
            """, (user_id,)) or []
            sub_map = {s['task_id']: s['status'] for s in subs}
            for t in rows:
                t['user_status'] = sub_map.get(t['task_id'], None)

        return rows
    except Exception as e:
        print(f"[SocialTasks] Error: {e}")
        return []


def get_social_task(task_id):
    try:
        return fetch_one("SELECT * FROM social_tasks WHERE task_id=%s", (task_id,))
    except:
        return None


def submit_social_task(task_id, user_id, screenshot_base64, user_note=''):
    try:
        task = fetch_one(
            "SELECT * FROM social_tasks WHERE task_id=%s AND is_active=TRUE", (task_id,))
        if not task:
            return {'success': False, 'error': 'Tarea no encontrada'}

        if task['current_completions'] >= task['max_completions']:
            return {'success': False, 'error': 'Esta tarea ya alcanzó el límite de completaciones'}

        # Verificar que no haya enviado antes
        existing = fetch_one(
            "SELECT * FROM social_task_submissions WHERE task_id=%s AND user_id=%s",
            (task_id, user_id))
        if existing:
            return {'success': False, 'error': 'Ya enviaste esta tarea', 'status': existing['status']}

        submission_id = f"sub_{uuid.uuid4().hex[:12]}"

        execute_query("""
            INSERT INTO social_task_submissions
            (submission_id, task_id, user_id, screenshot_data, user_note)
            VALUES (%s, %s, %s, %s, %s)
        """, (submission_id, task_id, user_id, screenshot_base64, user_note))

        return {'success': True, 'submission_id': submission_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_user_submissions(user_id):
    try:
        return fetch_all("""
            SELECT s.*, t.title, t.platform, t.action_type, t.reward_amount, t.reward_currency
            FROM social_task_submissions s
            JOIN social_tasks t ON s.task_id = t.task_id
            WHERE s.user_id = %s
            ORDER BY s.submitted_at DESC
        """, (user_id,)) or []
    except:
        return []


def get_platforms():
    return DEFAULT_PLATFORMS


def get_actions():
    return TASK_ACTIONS
