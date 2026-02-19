"""
onclicka_pts_system.py - Sistema de PTS con Anuncios OnClickA
VERSIÓN CORREGIDA - Collation utf8mb4_unicode_ci
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

ONCLICKA_CONFIG = {
    'ad_code_id': 408797,
    'cooldown_seconds': 180,
    'min_user_id': 100000
}

PTS_CONFIG = {
    'daily_limit': 5000,
    'ad_reward': 5,
    'checkin_reward': 10,
    'checkin_double_reward': 20,
    'boost_pts_reward': 15,
    'daily_ad_limit': 10,
    'watch_5_ads_bonus': 20
}

BOOST_CONFIG = {
    'multiplier': 2.0,
    'duration_minutes': 30,
    'cooldown_minutes': 60,
    'max_daily_boosts': 3
}

RANKING_CONFIG = {
    'period': 'weekly',
    'top_count': 10,  # Mostrar top 10
    'prize_count': 5,  # Solo top 5 reciben premio
    'min_pts_qualify': 2000,  # Mínimo PTS para clasificar a premio
    'rewards': {
        1: {'doge': 5.0},
        2: {'doge': 2.0},
        3: {'doge': 1.0},
        4: {'doge': 0.5},
        5: {'doge': 0.2}
    }
}

onclicka_bp = Blueprint('onclicka_pts', __name__)

# ============================================
# INICIALIZACIÓN DE TABLAS
# ============================================

def init_pts_tables():
    """Crear tablas con utf8mb4_unicode_ci para compatibilidad"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            # Tabla de balance PTS
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_pts (
                    user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci PRIMARY KEY,
                    pts_balance INT DEFAULT 0,
                    pts_total_earned INT DEFAULT 0,
                    pts_today INT DEFAULT 0,
                    last_pts_date DATE DEFAULT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Historial PTS
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pts_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                    amount INT NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    description VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_date (user_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Progreso de tareas de anuncios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ad_tasks_progress (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                    task_type VARCHAR(50) NOT NULL,
                    ads_watched INT DEFAULT 0,
                    ads_target INT DEFAULT 5,
                    completed TINYINT(1) DEFAULT 0,
                    task_date DATE NOT NULL,
                    last_ad_at DATETIME DEFAULT NULL,
                    UNIQUE KEY unique_user_task_date (user_id, task_type, task_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Check-in diario
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_checkin (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                    checkin_date DATE NOT NULL,
                    base_reward INT NOT NULL,
                    doubled TINYINT(1) DEFAULT 0,
                    total_reward INT NOT NULL,
                    streak INT DEFAULT 1,
                    UNIQUE KEY unique_user_date (user_id, checkin_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Ranking semanal
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pts_ranking (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                    period_type VARCHAR(20) NOT NULL,
                    period_start DATE NOT NULL,
                    period_end DATE NOT NULL,
                    pts_earned INT DEFAULT 0,
                    final_rank INT DEFAULT NULL,
                    reward_doge DECIMAL(10,4) DEFAULT NULL,
                    UNIQUE KEY unique_user_period (user_id, period_type, period_start),
                    INDEX idx_period (period_type, period_start)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Boosts activos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS onclicka_boosts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                    multiplier FLOAT DEFAULT 2.0,
                    activated_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    INDEX idx_user_expires (user_id, expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Historial de boosts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS onclicka_boost_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                    boost_date DATE NOT NULL,
                    activated_at DATETIME NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            logger.info("✅ Tablas PTS inicializadas con utf8mb4_unicode_ci")
    except Exception as e:
        logger.error(f"❌ Error tablas PTS: {e}")


# ============================================
# FUNCIONES DE PTS
# ============================================

def get_user_pts(user_id):
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT pts_balance, pts_total_earned, pts_today, last_pts_date FROM user_pts WHERE user_id = %s", (str(user_id),))
            result = cursor.fetchone()
            if result:
                if str(result.get('last_pts_date', '')) != today:
                    cursor.execute("UPDATE user_pts SET pts_today = 0, last_pts_date = %s WHERE user_id = %s", (today, str(user_id)))
                    return {'balance': int(result['pts_balance']), 'total_earned': int(result['pts_total_earned']), 'today': 0}
                return {'balance': int(result['pts_balance']), 'total_earned': int(result['pts_total_earned']), 'today': int(result['pts_today'] or 0)}
            cursor.execute("INSERT INTO user_pts (user_id, pts_balance, pts_today, last_pts_date) VALUES (%s, 0, 0, %s)", (str(user_id), today))
            return {'balance': 0, 'total_earned': 0, 'today': 0}
    except Exception as e:
        logger.error(f"Error PTS: {e}")
        return {'balance': 0, 'total_earned': 0, 'today': 0}


def add_pts(user_id, amount, action, description=""):
    from db import get_cursor
    if amount <= 0:
        return False, "Cantidad inválida"

    # Check if PTS earning is allowed (competition state)
    try:
        from pts_competition_system import can_earn_pts
        if not can_earn_pts():
            return False, "La competencia no está activa"
    except ImportError:
        pass  # Competition system not available, allow PTS
    except Exception as e:
        logger.warning(f"Error checking competition state: {e}")
        pass  # Allow PTS on error to not break functionality

    try:
        today = datetime.now().strftime('%Y-%m-%d')
        pts_data = get_user_pts(user_id)

        # Acciones especiales que no tienen límite diario
        special_actions = ['referral', 'boost_activated', 'promo', 'mission']

        # Solo aplicar límite diario para acciones normales
        if action not in special_actions:
            if pts_data['today'] + amount > PTS_CONFIG['daily_limit']:
                remaining = PTS_CONFIG['daily_limit'] - pts_data['today']
                if remaining <= 0:
                    return False, f"Límite diario alcanzado"
                amount = remaining

        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_pts (user_id, pts_balance, pts_total_earned, pts_today, last_pts_date)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    pts_balance = pts_balance + %s,
                    pts_total_earned = pts_total_earned + %s,
                    pts_today = IF(last_pts_date = %s, pts_today + %s, %s),
                    last_pts_date = %s
            """, (str(user_id), amount, amount, amount, today, amount, amount, today, amount, amount, today))
            cursor.execute("INSERT INTO pts_history (user_id, amount, action, description) VALUES (%s, %s, %s, %s)", (str(user_id), amount, action, description))
            update_ranking_pts(user_id, amount)
        logger.info(f"[PTS] User {user_id}: +{amount} PTS ({action})")
        return True, f"+{amount} PTS"
    except Exception as e:
        logger.error(f"Error agregando PTS: {e}")
        import traceback
        traceback.print_exc()
        return False, "Error"


def update_ranking_pts(user_id, amount):
    from db import get_cursor
    try:
        today = datetime.now().date()
        period_start = today - timedelta(days=today.weekday()) if RANKING_CONFIG['period'] == 'weekly' else today.replace(day=1)
        period_end = period_start + timedelta(days=6) if RANKING_CONFIG['period'] == 'weekly' else (period_start.replace(day=28) + timedelta(days=4)) - timedelta(days=(period_start.replace(day=28) + timedelta(days=4)).day)
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO pts_ranking (user_id, period_type, period_start, period_end, pts_earned)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE pts_earned = pts_earned + %s
            """, (str(user_id), RANKING_CONFIG['period'], period_start, period_end, amount, amount))
    except Exception as e:
        logger.error(f"Error ranking: {e}")


def get_ad_task_progress(user_id, task_type='watch_5_ads'):
    from db import get_cursor
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT ads_watched, ads_target, completed, last_ad_at, task_date
                FROM ad_tasks_progress
                WHERE user_id = %s AND task_type = %s AND task_date = %s
            """, (str(user_id), task_type, today))
            result = cursor.fetchone()
            if result:
                # Verificar que la fecha sea de hoy
                task_date = result.get('task_date')
                if task_date:
                    if isinstance(task_date, str):
                        task_date_str = task_date
                    else:
                        task_date_str = task_date.strftime('%Y-%m-%d') if hasattr(task_date, 'strftime') else str(task_date)

                    if task_date_str == today:
                        return {
                            'ads_watched': int(result['ads_watched']),
                            'ads_target': int(result['ads_target']),
                            'completed': bool(result['completed']),
                            'last_ad_at': result['last_ad_at']
                        }
            # Si no hay registro para hoy, retornar valores por defecto
            return {'ads_watched': 0, 'ads_target': 5, 'completed': False, 'last_ad_at': None}
    except Exception as e:
        logger.error(f"Error get_ad_task_progress: {e}")
        return {'ads_watched': 0, 'ads_target': 5, 'completed': False, 'last_ad_at': None}


def get_daily_ads_count(user_id):
    from db import get_cursor
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        with get_cursor() as cursor:
            cursor.execute("SELECT SUM(ads_watched) as total FROM ad_tasks_progress WHERE user_id = %s AND task_date = %s", (str(user_id), today))
            result = cursor.fetchone()
            return int(result['total'] or 0) if result else 0
    except:
        return 0


def can_watch_ad(user_id):
    from db import get_cursor
    daily_count = get_daily_ads_count(user_id)
    if daily_count >= PTS_CONFIG['daily_ad_limit']:
        return False, f"Límite diario alcanzado"
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT last_ad_at FROM ad_tasks_progress WHERE user_id = %s ORDER BY last_ad_at DESC LIMIT 1", (str(user_id),))
            result = cursor.fetchone()
            if result and result['last_ad_at']:
                cooldown_end = result['last_ad_at'] + timedelta(seconds=ONCLICKA_CONFIG['cooldown_seconds'])
                if datetime.now() < cooldown_end:
                    remaining = int((cooldown_end - datetime.now()).total_seconds())
                    return False, f"Espera {remaining // 60}m {remaining % 60}s"
    except:
        pass
    return True, "OK"


def record_ad_watched(user_id, task_type='single_ad'):
    from db import get_cursor
    can_watch, reason = can_watch_ad(user_id)
    if not can_watch:
        return False, reason, 0
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now()
        pts_earned = PTS_CONFIG['ad_reward']
        bonus_earned = 0
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO ad_tasks_progress (user_id, task_type, ads_watched, ads_target, task_date, last_ad_at)
                VALUES (%s, 'watch_5_ads', 1, 5, %s, %s)
                ON DUPLICATE KEY UPDATE ads_watched = ads_watched + 1, last_ad_at = %s
            """, (str(user_id), today, now, now))
            progress = get_ad_task_progress(user_id, 'watch_5_ads')
            if progress['ads_watched'] >= 5 and not progress['completed']:
                cursor.execute("UPDATE ad_tasks_progress SET completed = 1 WHERE user_id = %s AND task_type = 'watch_5_ads' AND task_date = %s", (str(user_id), today))
                bonus_earned = PTS_CONFIG['watch_5_ads_bonus']
        total_pts = pts_earned + bonus_earned
        success, msg = add_pts(user_id, total_pts, 'ad_watched', f'Anuncio visto')
        if success:
            return True, "Anuncio completado", total_pts
        return False, msg, 0
    except Exception as e:
        logger.error(f"Error anuncio: {e}")
        return False, "Error", 0


# ============================================
# CHECK-IN DIARIO
# ============================================

def get_checkin_status(user_id):
    from db import get_cursor
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        with get_cursor() as cursor:
            # Verificar check-in de hoy
            cursor.execute("SELECT * FROM daily_checkin WHERE user_id = %s AND checkin_date = %s", (str(user_id), today))
            today_checkin = cursor.fetchone()

            # Obtener el último check-in para calcular el streak
            cursor.execute("SELECT streak, checkin_date FROM daily_checkin WHERE user_id = %s ORDER BY checkin_date DESC LIMIT 1", (str(user_id),))
            last_checkin = cursor.fetchone()

            # Calcular streak
            if today_checkin:
                # Si ya hizo check-in hoy, usar ese streak
                current_streak = int(today_checkin['streak']) if today_checkin.get('streak') else 1
            elif last_checkin:
                # Si no hizo check-in hoy, verificar si el último fue ayer
                last_date = last_checkin['checkin_date']
                if isinstance(last_date, str):
                    last_date_str = last_date
                else:
                    last_date_str = last_date.strftime('%Y-%m-%d') if hasattr(last_date, 'strftime') else str(last_date)

                if last_date_str == yesterday:
                    # Ayer hizo check-in, el streak continúa (+1 cuando haga check-in hoy)
                    current_streak = int(last_checkin['streak']) + 1
                else:
                    # No hizo check-in ayer, el streak se reinicia
                    current_streak = 1
            else:
                # Nunca ha hecho check-in
                current_streak = 1

            return {
                'done_today': bool(today_checkin),
                'doubled': bool(today_checkin['doubled']) if today_checkin else False,
                'can_double': bool(today_checkin and not today_checkin['doubled']),
                'streak': current_streak,
                'base_reward': PTS_CONFIG['checkin_reward'],
                'double_reward': PTS_CONFIG['checkin_double_reward'],
                'total_earned_today': int(today_checkin['total_reward']) if today_checkin else 0
            }
    except Exception as e:
        logger.error(f"Error get_checkin_status: {e}")
        return {'done_today': False, 'doubled': False, 'can_double': False, 'streak': 1, 'base_reward': PTS_CONFIG['checkin_reward'], 'double_reward': PTS_CONFIG['checkin_double_reward'], 'total_earned_today': 0}


def do_checkin(user_id):
    from db import get_cursor
    status = get_checkin_status(user_id)
    if status['done_today']:
        return False, "Ya hiciste check-in hoy", 0
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        reward = PTS_CONFIG['checkin_reward']
        streak = status['streak']
        with get_cursor() as cursor:
            cursor.execute("INSERT INTO daily_checkin (user_id, checkin_date, base_reward, total_reward, streak) VALUES (%s, %s, %s, %s, %s)", (str(user_id), today, reward, reward, streak))
        success, msg = add_pts(user_id, reward, 'checkin', f'Check-in racha {streak}')
        if success:
            return True, f"¡Check-in! Racha: {streak}", reward
        return False, msg, 0
    except Exception as e:
        logger.error(f"Error checkin: {e}")
        return False, "Error", 0


def double_checkin_reward(user_id):
    from db import get_cursor
    status = get_checkin_status(user_id)
    if not status['done_today']:
        return False, "Primero haz check-in", 0
    if status['doubled']:
        return False, "Ya duplicaste hoy", 0
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        bonus = PTS_CONFIG['checkin_reward']
        now = datetime.now()
        with get_cursor() as cursor:
            cursor.execute("UPDATE daily_checkin SET doubled = 1, total_reward = total_reward + %s WHERE user_id = %s AND checkin_date = %s", (bonus, str(user_id), today))
            cursor.execute("""
                INSERT INTO ad_tasks_progress (user_id, task_type, ads_watched, ads_target, task_date, last_ad_at)
                VALUES (%s, 'checkin_double', 1, 1, %s, %s)
                ON DUPLICATE KEY UPDATE ads_watched = ads_watched + 1, last_ad_at = %s
            """, (str(user_id), today, now, now))
        success, msg = add_pts(user_id, bonus, 'checkin_double', 'Check-in duplicado')
        if success:
            return True, "¡Recompensa duplicada!", bonus
        return False, msg, 0
    except Exception as e:
        logger.error(f"Error double: {e}")
        return False, "Error", 0


# ============================================
# RANKING - CON COLLATE PARA COMPATIBILIDAD
# ============================================

def get_current_ranking(limit=10):
    """
    Obtiene el ranking actual de PTS.

    Reglas del ranking:
    - Muestra top 10 usuarios ordenados por PTS
    - Solo top 5 reciben premio
    - Mínimo 2000 PTS para clasificar a premio
    - Premios: 1°=5 DOGE, 2°=2 DOGE, 3°=1 DOGE, 4°=0.5 DOGE, 5°=0.2 DOGE
    """
    from db import get_cursor
    try:
        today = datetime.now().date()
        period_start = today - timedelta(days=today.weekday()) if RANKING_CONFIG['period'] == 'weekly' else today.replace(day=1)

        with get_cursor() as cursor:
            cursor.execute("""
                SELECT r.user_id, r.pts_earned, u.username, u.first_name
                FROM pts_ranking r
                LEFT JOIN users u ON r.user_id COLLATE utf8mb4_unicode_ci = u.user_id COLLATE utf8mb4_unicode_ci
                WHERE r.period_type = %s AND r.period_start = %s
                ORDER BY r.pts_earned DESC
                LIMIT %s
            """, (RANKING_CONFIG['period'], period_start, limit))
            results = cursor.fetchall()

            ranking = []
            min_pts = RANKING_CONFIG['min_pts_qualify']
            prize_count = RANKING_CONFIG['prize_count']

            for i, row in enumerate(results, 1):
                pts_earned = int(row['pts_earned'])

                # Solo top 5 pueden recibir premio, y solo si tienen 2000+ PTS
                reward_info = RANKING_CONFIG['rewards'].get(i, None)
                reward_doge = reward_info['doge'] if reward_info and i <= prize_count else 0
                qualifies = i <= prize_count and pts_earned >= min_pts

                ranking.append({
                    'position': i,
                    'user_id': row['user_id'],
                    'username': row['username'] or 'Usuario',
                    'first_name': row['first_name'] or 'Usuario',
                    'pts': pts_earned,
                    'reward_doge': reward_doge,
                    'qualifies': qualifies,
                    'in_prize_zone': i <= prize_count,
                    'needs_pts': max(0, min_pts - pts_earned) if i <= prize_count else 0
                })
            return ranking
    except Exception as e:
        logger.error(f"Error ranking: {e}")
        return []


def get_user_rank(user_id):
    """
    Obtiene la posición y PTS del usuario en el ranking actual.
    Incluye información sobre si califica para premio.
    """
    from db import get_cursor
    try:
        today = datetime.now().date()
        period_start = today - timedelta(days=today.weekday()) if RANKING_CONFIG['period'] == 'weekly' else today.replace(day=1)

        with get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) + 1 AS user_position
                FROM pts_ranking
                WHERE period_type = %s AND period_start = %s
                AND pts_earned > (
                    SELECT COALESCE(pts_earned, 0) FROM pts_ranking
                    WHERE user_id = %s AND period_type = %s AND period_start = %s
                )
            """, (RANKING_CONFIG['period'], period_start, str(user_id), RANKING_CONFIG['period'], period_start))
            result = cursor.fetchone()
            position = int(result['user_position']) if result else 0

            cursor.execute("SELECT pts_earned FROM pts_ranking WHERE user_id = %s AND period_type = %s AND period_start = %s", (str(user_id), RANKING_CONFIG['period'], period_start))
            pts_result = cursor.fetchone()
            pts = int(pts_result['pts_earned']) if pts_result else 0

            # Calcular si califica para premio
            min_pts = RANKING_CONFIG['min_pts_qualify']
            prize_count = RANKING_CONFIG['prize_count']
            in_prize_zone = position <= prize_count and position > 0
            qualifies = in_prize_zone and pts >= min_pts
            reward_doge = RANKING_CONFIG['rewards'].get(position, {}).get('doge', 0) if in_prize_zone else 0
            needs_pts = max(0, min_pts - pts) if in_prize_zone else 0

            return {
                'position': position,
                'pts': pts,
                'in_prize_zone': in_prize_zone,
                'qualifies': qualifies,
                'reward_doge': reward_doge,
                'needs_pts': needs_pts,
                'min_pts_required': min_pts
            }
    except Exception as e:
        logger.error(f"Error posición: {e}")
        return {'position': 0, 'pts': 0, 'in_prize_zone': False, 'qualifies': False, 'reward_doge': 0, 'needs_pts': 0, 'min_pts_required': 2000}


def get_ranking_period_info():
    """Obtiene información del período actual del ranking"""
    today = datetime.now().date()
    period_start = today - timedelta(days=today.weekday()) if RANKING_CONFIG['period'] == 'weekly' else today.replace(day=1)
    period_end = period_start + timedelta(days=6) if RANKING_CONFIG['period'] == 'weekly' else (period_start.replace(day=28) + timedelta(days=4)) - timedelta(days=(period_start.replace(day=28) + timedelta(days=4)).day)
    return {
        'period_type': RANKING_CONFIG['period'],
        'period_start': period_start.strftime('%Y-%m-%d'),
        'period_end': period_end.strftime('%Y-%m-%d'),
        'days_remaining': (period_end - today).days,
        'rewards': RANKING_CONFIG['rewards'],
        'min_pts_qualify': RANKING_CONFIG['min_pts_qualify'],
        'prize_count': RANKING_CONFIG['prize_count'],
        'top_count': RANKING_CONFIG['top_count']
    }


# ============================================
# BOOST DE MINERÍA
# ============================================

def get_active_onclicka_boost(user_id):
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT multiplier, expires_at FROM onclicka_boosts WHERE user_id = %s AND expires_at > NOW() ORDER BY expires_at DESC LIMIT 1", (str(user_id),))
            result = cursor.fetchone()
            if result:
                return {'active': True, 'multiplier': float(result['multiplier']), 'expires_at': result['expires_at']}
    except:
        pass
    return {'active': False, 'multiplier': 1.0, 'expires_at': None}


def get_onclicka_boost_multiplier(user_id):
    boost = get_active_onclicka_boost(user_id)
    return boost['multiplier'] if boost['active'] else 1.0


def count_daily_onclicka_boosts(user_id):
    from db import get_cursor
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        with get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM onclicka_boost_history WHERE user_id = %s AND boost_date = %s", (str(user_id), today))
            result = cursor.fetchone()
            return int(result['count']) if result else 0
    except:
        return 0


def can_activate_onclicka_boost(user_id):
    from db import get_cursor
    boost = get_active_onclicka_boost(user_id)
    if boost['active']:
        return False, "Ya tienes boost activo"
    daily_count = count_daily_onclicka_boosts(user_id)
    if daily_count >= BOOST_CONFIG['max_daily_boosts']:
        return False, f"Límite diario alcanzado"
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT activated_at FROM onclicka_boost_history WHERE user_id = %s ORDER BY activated_at DESC LIMIT 1", (str(user_id),))
            result = cursor.fetchone()
            if result:
                cooldown_end = result['activated_at'] + timedelta(minutes=BOOST_CONFIG['cooldown_minutes'])
                if datetime.now() < cooldown_end:
                    remaining = int((cooldown_end - datetime.now()).total_seconds())
                    return False, f"Espera {remaining // 60}m {remaining % 60}s"
    except:
        pass
    return True, "OK"


def activate_onclicka_boost(user_id):
    from db import get_cursor
    can_activate, reason = can_activate_onclicka_boost(user_id)
    if not can_activate:
        return False, reason
    try:
        now = datetime.now()
        expires = now + timedelta(minutes=BOOST_CONFIG['duration_minutes'])
        today = now.strftime('%Y-%m-%d')
        with get_cursor() as cursor:
            cursor.execute("INSERT INTO onclicka_boosts (user_id, multiplier, activated_at, expires_at) VALUES (%s, %s, %s, %s)", (str(user_id), BOOST_CONFIG['multiplier'], now, expires))
            cursor.execute("INSERT INTO onclicka_boost_history (user_id, boost_date, activated_at) VALUES (%s, %s, %s)", (str(user_id), today, now))
            cursor.execute("""
                INSERT INTO ad_tasks_progress (user_id, task_type, ads_watched, ads_target, task_date, last_ad_at)
                VALUES (%s, 'boost_ad', 1, 1, %s, %s)
                ON DUPLICATE KEY UPDATE ads_watched = ads_watched + 1, last_ad_at = %s
            """, (str(user_id), today, now, now))
        add_pts(user_id, PTS_CONFIG['boost_pts_reward'], 'boost_activated', 'Boost activado')
        logger.info(f"[Boost] User {user_id} boost x{BOOST_CONFIG['multiplier']} hasta {expires}")
        return True, f"Boost x{int(BOOST_CONFIG['multiplier'])} por {BOOST_CONFIG['duration_minutes']} min"
    except Exception as e:
        logger.error(f"Error boost: {e}")
        return False, "Error"


def get_boost_status(user_id):
    boost = get_active_onclicka_boost(user_id)
    can_activate, reason = can_activate_onclicka_boost(user_id)
    daily_count = count_daily_onclicka_boosts(user_id)
    boost_remaining = 0
    if boost['active'] and boost['expires_at']:
        boost_remaining = max(0, int((boost['expires_at'] - datetime.now()).total_seconds()))
    return {'has_active_boost': boost['active'], 'multiplier': boost['multiplier'], 'boost_remaining_seconds': boost_remaining, 'daily_boosts_used': daily_count, 'daily_boosts_limit': BOOST_CONFIG['max_daily_boosts'], 'can_activate': can_activate, 'reason': reason if not can_activate else None}


# ============================================
# ENDPOINTS API
# ============================================

@onclicka_bp.route('/api/pts/status', methods=['GET'])
def api_pts_status():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    pts = get_user_pts(user_id)
    checkin = get_checkin_status(user_id)
    ad_progress = get_ad_task_progress(user_id, 'watch_5_ads')
    user_rank = get_user_rank(user_id)
    can_ad, ad_reason = can_watch_ad(user_id)
    boost = get_boost_status(user_id)
    ads_today = get_daily_ads_count(user_id)

    return jsonify({
        'success': True,
        'pts': pts,
        'pts_balance': pts,
        'checkin': checkin,
        # Campos de check-in en el nivel superior para compatibilidad con frontend
        'checkin_done': checkin.get('done_today', False),
        'checkin_doubled': checkin.get('doubled', False),
        'streak': checkin.get('streak', 0),
        # Otros campos
        'ad_task': ad_progress,
        'user_rank': user_rank,
        'can_watch_ad': can_ad,
        'ad_cooldown_reason': ad_reason if not can_ad else None,
        'daily_ad_limit': PTS_CONFIG['daily_ad_limit'],
        'ads_watched_today': ads_today,
        'ads_remaining': max(0, PTS_CONFIG['daily_ad_limit'] - ads_today),
        'boost': boost
    })


@onclicka_bp.route('/api/pts/ranking', methods=['GET'])
def api_pts_ranking():
    """Get PTS ranking - now uses competition system if available"""
    user_id = request.args.get('user_id')

    # Try to use competition system
    try:
        from pts_competition_system import (
            get_competition_state, get_competition_ranking,
            get_user_competition_rank
        )

        state = get_competition_state()
        ranking = get_competition_ranking(RANKING_CONFIG['top_count'])
        user_rank = get_user_competition_rank(user_id) if user_id else None

        return jsonify({
            'success': True,
            'state': state,
            'ranking': ranking,
            'user_rank': user_rank,
            'period_info': {
                'period_type': RANKING_CONFIG['period'],
                'days_remaining': state.get('remaining_days', 0),
                'min_pts_qualify': RANKING_CONFIG['min_pts_qualify'],
                'prize_count': RANKING_CONFIG['prize_count']
            }
        })
    except ImportError:
        # Fall back to original ranking if competition system not available
        ranking = get_current_ranking(RANKING_CONFIG['top_count'])
        user_rank = get_user_rank(user_id) if user_id else None
        period_info = get_ranking_period_info()
        return jsonify({'success': True, 'ranking': ranking, 'user_rank': user_rank, 'period_info': period_info})


@onclicka_bp.route('/api/checkin', methods=['POST'])
def api_checkin():
    user_id = request.args.get('user_id') or (request.json.get('user_id') if request.json else None)
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    success, message, pts = do_checkin(user_id)
    status = get_checkin_status(user_id)
    return jsonify({'success': success, 'message': message, 'pts_earned': pts, 'status': status})


@onclicka_bp.route('/api/checkin/double', methods=['POST'])
def api_checkin_double():
    user_id = request.args.get('user_id') or (request.json.get('user_id') if request.json else None)
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    success, message, pts = double_checkin_reward(user_id)
    status = get_checkin_status(user_id)
    return jsonify({'success': success, 'message': message, 'pts_earned': pts, 'status': status})


@onclicka_bp.route('/api/ad/watch', methods=['POST'])
def api_ad_watch():
    user_id = request.args.get('user_id') or (request.json.get('user_id') if request.json else None)
    task_type = request.json.get('task_type', 'single_ad') if request.json else 'single_ad'
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    success, message, pts = record_ad_watched(user_id, task_type)
    return jsonify({'success': success, 'message': message, 'pts_earned': pts, 'ad_progress': get_ad_task_progress(user_id, 'watch_5_ads')})


@onclicka_bp.route('/api/ad/can-watch', methods=['GET'])
def api_can_watch():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    can_watch, reason = can_watch_ad(user_id)
    return jsonify({'success': True, 'can_watch': can_watch, 'reason': reason if not can_watch else None, 'config': {'ad_code_id': ONCLICKA_CONFIG['ad_code_id'], 'cooldown_seconds': ONCLICKA_CONFIG['cooldown_seconds']}})


@onclicka_bp.route('/api/boost/onclicka/status', methods=['GET'])
def api_onclicka_boost_status():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    status = get_boost_status(user_id)
    return jsonify({'success': True, **status})


@onclicka_bp.route('/api/boost/onclicka/activate', methods=['POST'])
def api_activate_onclicka_boost():
    user_id = request.args.get('user_id') or (request.json.get('user_id') if request.json else None)
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    success, message = activate_onclicka_boost(user_id)
    status = get_boost_status(user_id)
    return jsonify({'success': success, 'message': message, 'status': status})


@onclicka_bp.route('/onclicka/callback', methods=['GET', 'POST'])
def onclicka_callback():
    user_id = request.args.get('user_id') or request.args.get('subid')
    if not user_id:
        return jsonify({'success': False}), 400
    try:
        if int(user_id) < ONCLICKA_CONFIG['min_user_id']:
            return jsonify({'success': True}), 200
    except:
        return jsonify({'success': False}), 400
    logger.info(f"[OnClickA] callback user_id={user_id}")
    return jsonify({'success': True})
