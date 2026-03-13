"""
social_tasks_system.py - Sistema de Tareas Sociales (admin-created, screenshot-verified)
Las tareas son creadas por el admin con recompensas en SE, DOGE o TON.
Los usuarios las completan enviando una captura de pantalla o simplemente haciendo clic.
El admin aprueba o rechaza los envíos manualmente.
"""

import uuid
from datetime import datetime
from db import execute_query, get_cursor
from database import update_balance


# ============== PLATAFORMAS SOPORTADAS ==============
SOCIAL_PLATFORMS = [
    {'id': 'telegram',  'name': 'Telegram',  'icon': '✈️',  'color': '#0088cc'},
    {'id': 'twitter',   'name': 'Twitter/X', 'icon': '🐦',  'color': '#1da1f2'},
    {'id': 'youtube',   'name': 'YouTube',   'icon': '▶️',  'color': '#ff0000'},
    {'id': 'instagram', 'name': 'Instagram', 'icon': '📸',  'color': '#e1306c'},
    {'id': 'tiktok',    'name': 'TikTok',    'icon': '🎵',  'color': '#010101'},
    {'id': 'facebook',  'name': 'Facebook',  'icon': '👍',  'color': '#1877f2'},
    {'id': 'discord',   'name': 'Discord',   'icon': '💬',  'color': '#5865f2'},
    {'id': 'other',     'name': 'Otro',      'icon': '🔗',  'color': '#6b7280'},
]

SOCIAL_ACTIONS = [
    {'id': 'follow',    'name': 'Seguir / Suscribirse'},
    {'id': 'like',      'name': 'Dar Like'},
    {'id': 'comment',   'name': 'Comentar'},
    {'id': 'share',     'name': 'Compartir'},
    {'id': 'join',      'name': 'Unirse al grupo'},
    {'id': 'watch',     'name': 'Ver video'},
    {'id': 'repost',    'name': 'Repostear'},
    {'id': 'other',     'name': 'Otro'},
]

PLATFORMS_MAP = {p['id']: p for p in SOCIAL_PLATFORMS}


# ============== INICIALIZAR TABLAS ==============
def init_social_tasks_tables():
    """Crea las tablas necesarias si no existen."""

    execute_query("""
        CREATE TABLE IF NOT EXISTS social_tasks (
            task_id        VARCHAR(36)    NOT NULL PRIMARY KEY,
            title          VARCHAR(200)   NOT NULL,
            description    TEXT           DEFAULT NULL,
            platform       VARCHAR(50)    NOT NULL DEFAULT 'other',
            action_type    VARCHAR(50)    NOT NULL DEFAULT 'follow',
            target_url     VARCHAR(500)   DEFAULT NULL,
            instructions   TEXT           DEFAULT NULL,
            reward_amount  DECIMAL(18,6)  NOT NULL DEFAULT 1.0,
            reward_currency VARCHAR(10)   NOT NULL DEFAULT 'se',
            max_completions INT           NOT NULL DEFAULT 100,
            current_completions INT       NOT NULL DEFAULT 0,
            requires_screenshot TINYINT(1) NOT NULL DEFAULT 1,
            is_active      TINYINT(1)    NOT NULL DEFAULT 1,
            translations   JSON           DEFAULT NULL,
            created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    execute_query("""
        CREATE TABLE IF NOT EXISTS social_task_submissions (
            submission_id  VARCHAR(36)   NOT NULL PRIMARY KEY,
            task_id        VARCHAR(36)   NOT NULL,
            user_id        VARCHAR(64)   NOT NULL,
            screenshot_data LONGTEXT     DEFAULT NULL,
            user_note      TEXT          DEFAULT NULL,
            status         ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
            admin_note     TEXT          DEFAULT NULL,
            submitted_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at    DATETIME     DEFAULT NULL,
            INDEX idx_task_id  (task_id),
            INDEX idx_user_id  (user_id),
            INDEX idx_status   (status),
            UNIQUE KEY uq_user_task (task_id, user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Migración: agregar translations si tabla ya existe
    try:
        execute_query("ALTER TABLE social_tasks ADD COLUMN translations JSON DEFAULT NULL")
    except:
        pass

    print("[social_tasks] ✅ Tablas inicializadas")


# ============== CRUD TAREAS (ADMIN) ==============

def get_all_social_tasks():
    """Retorna todas las tareas sociales (admin view)."""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM social_tasks
                ORDER BY created_at DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"[social_tasks] get_all: {e}")
        return []


def get_active_social_tasks(user_id=None):
    """
    Retorna tareas activas con cupos disponibles.
    Si se pasa user_id, agrega el estado de envío del usuario en task.user_status.
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT t.*
                FROM social_tasks t
                WHERE t.is_active = 1
                  AND t.current_completions < t.max_completions
                ORDER BY t.created_at DESC
            """)
            tasks = cursor.fetchall()

        if user_id and tasks:
            # Obtener submissions del usuario para estas tareas
            task_ids = [t['task_id'] for t in tasks]
            placeholders = ','.join(['%s'] * len(task_ids))
            with get_cursor() as cursor:
                cursor.execute(f"""
                    SELECT task_id, status
                    FROM social_task_submissions
                    WHERE user_id = %s AND task_id IN ({placeholders})
                """, [user_id] + task_ids)
                subs = {r['task_id']: r['status'] for r in cursor.fetchall()}

            for t in tasks:
                t['user_status'] = subs.get(t['task_id'])

        return tasks
    except Exception as e:
        print(f"[social_tasks] get_active: {e}")
        return []


def get_social_task(task_id):
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM social_tasks WHERE task_id = %s", (task_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"[social_tasks] get_task: {e}")
        return None


def create_social_task(data):
    """Crea una tarea social. Retorna task_id o None."""
    import json as _json
    try:
        task_id = str(uuid.uuid4())
        translations = data.get('translations')
        translations_json = _json.dumps(translations, ensure_ascii=False) if translations else None
        execute_query("""
            INSERT INTO social_tasks
                (task_id, title, description, platform, action_type,
                 target_url, instructions, reward_amount, reward_currency,
                 max_completions, requires_screenshot, is_active, translations)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
        """, (
            task_id,
            data.get('title', '').strip(),
            data.get('description', '').strip() or None,
            data.get('platform', 'other'),
            data.get('action_type', 'follow'),
            data.get('target_url', '').strip() or None,
            data.get('instructions', '').strip() or None,
            float(data.get('reward_amount', 1.0)),
            data.get('reward_currency', 'se').lower(),
            int(data.get('max_completions', 100)),
            1 if data.get('requires_screenshot') else 0,
            translations_json,
        ))
        return task_id
    except Exception as e:
        print(f"[social_tasks] create: {e}")
        return None


def update_social_task(task_id, data):
    import json as _json
    try:
        translations = data.get('translations')
        translations_json = _json.dumps(translations, ensure_ascii=False) if translations else None
        execute_query("""
            UPDATE social_tasks SET
                title = %s, description = %s, platform = %s, action_type = %s,
                target_url = %s, instructions = %s, reward_amount = %s,
                reward_currency = %s, max_completions = %s, requires_screenshot = %s,
                translations = COALESCE(%s, translations)
            WHERE task_id = %s
        """, (
            data.get('title', '').strip(),
            data.get('description', '').strip() or None,
            data.get('platform', 'other'),
            data.get('action_type', 'follow'),
            data.get('target_url', '').strip() or None,
            data.get('instructions', '').strip() or None,
            float(data.get('reward_amount', 1.0)),
            data.get('reward_currency', 'se').lower(),
            int(data.get('max_completions', 100)),
            1 if data.get('requires_screenshot') else 0,
            translations_json,
            task_id,
        ))
        return True
    except Exception as e:
        print(f"[social_tasks] update: {e}")
        return False


def toggle_social_task(task_id, active: bool):
    try:
        execute_query(
            "UPDATE social_tasks SET is_active = %s WHERE task_id = %s",
            (1 if active else 0, task_id)
        )
        return True
    except Exception as e:
        print(f"[social_tasks] toggle: {e}")
        return False


def delete_social_task(task_id):
    try:
        execute_query("DELETE FROM social_task_submissions WHERE task_id = %s", (task_id,))
        execute_query("DELETE FROM social_tasks WHERE task_id = %s", (task_id,))
        return True
    except Exception as e:
        print(f"[social_tasks] delete: {e}")
        return False


# ============== SUBMISSIONS (USUARIOS) ==============

def submit_social_task(task_id, user_id, screenshot_data=None, user_note=None):
    """
    El usuario envía la tarea.
    Retorna (True, submission_id) o (False, 'motivo del error')
    """
    try:
        # Verificar que la tarea existe y tiene cupos
        task = get_social_task(task_id)
        if not task:
            return False, 'Tarea no encontrada'
        if not task['is_active']:
            return False, 'Tarea inactiva'
        if task['current_completions'] >= task['max_completions']:
            return False, 'Sin cupos disponibles'

        # Verificar que el usuario no haya enviado ya
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT submission_id, status FROM social_task_submissions WHERE task_id=%s AND user_id=%s",
                (task_id, user_id)
            )
            existing = cursor.fetchone()

        if existing:
            if existing['status'] == 'pending':
                return False, 'Ya tienes un envío pendiente para esta tarea'
            elif existing['status'] == 'approved':
                return False, 'Ya completaste esta tarea'
            # rejected → permitir reenvío (eliminar el anterior)
            execute_query(
                "DELETE FROM social_task_submissions WHERE task_id=%s AND user_id=%s",
                (task_id, user_id)
            )

        submission_id = str(uuid.uuid4())
        execute_query("""
            INSERT INTO social_task_submissions
                (submission_id, task_id, user_id, screenshot_data, user_note, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """, (submission_id, task_id, user_id, screenshot_data, user_note))

        return True, submission_id

    except Exception as e:
        print(f"[social_tasks] submit: {e}")
        return False, 'Error interno'


def get_user_submissions(user_id):
    """Historial de submissions de un usuario."""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT s.*, t.title AS task_title, t.platform, t.action_type,
                       t.reward_amount, t.reward_currency
                FROM social_task_submissions s
                JOIN social_tasks t ON t.task_id = s.task_id
                WHERE s.user_id = %s
                ORDER BY s.submitted_at DESC
            """, (user_id,))
            return cursor.fetchall()
    except Exception as e:
        print(f"[social_tasks] get_user_subs: {e}")
        return []


# ============== ADMIN: REVIEW SUBMISSIONS ==============

def get_all_submissions(status=None, task_id=None):
    """Submissions para el panel admin."""
    try:
        conditions = []
        params = []
        if status:
            conditions.append("s.status = %s")
            params.append(status)
        if task_id:
            conditions.append("s.task_id = %s")
            params.append(task_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with get_cursor() as cursor:
            cursor.execute(f"""
                SELECT s.*,
                       t.title AS task_title, t.platform, t.action_type,
                       t.reward_amount, t.reward_currency,
                       u.first_name, u.username
                FROM social_task_submissions s
                JOIN social_tasks t ON t.task_id = s.task_id
                LEFT JOIN users u ON u.user_id = s.user_id
                {where}
                ORDER BY s.submitted_at DESC
                LIMIT 200
            """, params)
            return cursor.fetchall()
    except Exception as e:
        print(f"[social_tasks] get_all_subs: {e}")
        return []


def approve_submission(submission_id, admin_note=None):
    """
    Aprueba un envío: da la recompensa al usuario y aumenta current_completions.
    Retorna (True, mensaje) o (False, error)
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT s.*, t.reward_amount, t.reward_currency, t.task_id
                FROM social_task_submissions s
                JOIN social_tasks t ON t.task_id = s.task_id
                WHERE s.submission_id = %s
            """, (submission_id,))
            sub = cursor.fetchone()

        if not sub:
            return False, 'Envío no encontrado'
        if sub['status'] != 'pending':
            return False, f'Ya fue {sub["status"]}'

        # Marcar como aprobado
        execute_query("""
            UPDATE social_task_submissions
            SET status = 'approved', admin_note = %s, reviewed_at = NOW()
            WHERE submission_id = %s
        """, (admin_note, submission_id))

        # Dar recompensa
        update_balance(
            user_id=sub['user_id'],
            currency=sub['reward_currency'],
            amount=float(sub['reward_amount']),
            operation='add',
            description=f"Tarea social completada (#{submission_id[:8]})"
        )

        # Incrementar contador
        execute_query(
            "UPDATE social_tasks SET current_completions = current_completions + 1 WHERE task_id = %s",
            (sub['task_id'],)
        )

        return True, 'Aprobado y recompensa enviada'

    except Exception as e:
        print(f"[social_tasks] approve: {e}")
        return False, 'Error interno'


def reject_submission(submission_id, admin_note=None):
    """Rechaza un envío."""
    try:
        execute_query("""
            UPDATE social_task_submissions
            SET status = 'rejected', admin_note = %s, reviewed_at = NOW()
            WHERE submission_id = %s AND status = 'pending'
        """, (admin_note, submission_id))
        return True, 'Rechazado'
    except Exception as e:
        print(f"[social_tasks] reject: {e}")
        return False, 'Error interno'
