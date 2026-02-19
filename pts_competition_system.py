"""
pts_competition_system.py - Sistema de Competencia Semanal de PTS
Implementa el ciclo completo de competencias con estados automaticos

ESTADOS DEL SISTEMA:
- ACTIVE: Competencia en curso
- ENDED: Competencia finalizada, ranking congelado
- DISTRIBUTING: Distribuyendo recompensas (30 minutos)
- DISTRIBUTED: Recompensas entregadas
- PREPARATION: Preparacion para nueva competencia (1 hora)
"""

import logging
import os
import requests
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from decimal import Decimal

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACION DEL SISTEMA
# ============================================

COMPETITION_CONFIG = {
    'period': 'weekly',
    'distribution_duration_minutes': 30,
    'preparation_duration_minutes': 60,
    'min_pts_qualify': 4000,
    'prize_positions': 5,
    'rewards': {
        1: Decimal('10.0'),
        2: Decimal('5.0'),
        3: Decimal('2.0'),
        4: Decimal('1.0'),
        5: Decimal('0.5')
    }
}

# Estados del sistema
class CompetitionState:
    ACTIVE = 'ACTIVE'
    ENDED = 'ENDED'
    DISTRIBUTING = 'DISTRIBUTING'
    DISTRIBUTED = 'DISTRIBUTED'
    PREPARATION = 'PREPARATION'

# Mensajes por estado (sin emojis, profesional)
STATE_MESSAGES = {
    CompetitionState.ACTIVE: {
        'title': 'Competencia Activa',
        'message': 'Acumula puntos para escalar en el ranking y ganar recompensas.',
        'can_earn_pts': True
    },
    CompetitionState.ENDED: {
        'title': 'Competencia Finalizada',
        'message': 'La competencia semanal ha finalizado. Iniciando proceso de distribucion de recompensas.',
        'can_earn_pts': False
    },
    CompetitionState.DISTRIBUTING: {
        'title': 'Distribuyendo Recompensas',
        'message': 'El sistema esta distribuyendo las recompensas segun la posicion obtenida. Este proceso puede tardar hasta 30 minutos.',
        'can_earn_pts': False
    },
    CompetitionState.DISTRIBUTED: {
        'title': 'Recompensas Entregadas',
        'message': 'Las recompensas han sido distribuidas correctamente. Gracias por participar en la competencia semanal.',
        'can_earn_pts': False
    },
    CompetitionState.PREPARATION: {
        'title': 'Preparacion del Sistema',
        'message': 'El sistema se esta preparando para la proxima competencia semanal. La nueva competencia iniciara en aproximadamente una hora.',
        'can_earn_pts': False
    }
}

pts_competition_bp = Blueprint('pts_competition', __name__)

# ============================================
# INICIALIZACION DE TABLAS
# ============================================

def init_competition_tables():
    """Crear tablas del sistema de competencias"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            # Tabla principal de competencias
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pts_competitions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    competition_number INT NOT NULL,
                    state VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                    period_start DATETIME NOT NULL,
                    period_end DATETIME NOT NULL,
                    ended_at DATETIME DEFAULT NULL,
                    distribution_started_at DATETIME DEFAULT NULL,
                    distribution_completed_at DATETIME DEFAULT NULL,
                    preparation_started_at DATETIME DEFAULT NULL,
                    completed_at DATETIME DEFAULT NULL,
                    rewards_distributed TINYINT(1) DEFAULT 0,
                    pts_reset_done TINYINT(1) DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_state (state),
                    INDEX idx_period (period_start, period_end),
                    UNIQUE KEY unique_competition_number (competition_number)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Historial de ranking final por competencia
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pts_competition_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    competition_id INT NOT NULL,
                    user_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                    final_position INT NOT NULL,
                    pts_earned INT NOT NULL,
                    reward_doge DECIMAL(10,4) DEFAULT 0,
                    qualified TINYINT(1) DEFAULT 0,
                    reward_credited TINYINT(1) DEFAULT 0,
                    credited_at DATETIME DEFAULT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_competition (competition_id),
                    INDEX idx_user (user_id),
                    UNIQUE KEY unique_competition_user (competition_id, user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Log de transiciones de estado
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pts_competition_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    competition_id INT NOT NULL,
                    previous_state VARCHAR(20),
                    new_state VARCHAR(20) NOT NULL,
                    action VARCHAR(100),
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_competition_log (competition_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Historial de resets de PTS
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pts_reset_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    competition_id INT NOT NULL,
                    users_affected INT NOT NULL DEFAULT 0,
                    total_pts_reset BIGINT NOT NULL DEFAULT 0,
                    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_competition_reset (competition_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            logger.info("[PTS Competition] Tablas inicializadas correctamente")
            return True
    except Exception as e:
        logger.error(f"[PTS Competition] Error inicializando tablas: {e}")
        return False


# ============================================
# FUNCIONES DE COMPETENCIA
# ============================================

def get_current_competition():
    """Obtiene la competencia actual o crea una nueva si no existe"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            # Buscar competencia activa o en proceso
            cursor.execute("""
                SELECT * FROM pts_competitions
                WHERE state IN ('ACTIVE', 'ENDED', 'DISTRIBUTING', 'DISTRIBUTED', 'PREPARATION')
                ORDER BY id DESC LIMIT 1
            """)
            competition = cursor.fetchone()

            if competition:
                return dict(competition)

            # Crear primera competencia si no existe
            return create_new_competition()
    except Exception as e:
        logger.error(f"[PTS Competition] Error obteniendo competencia: {e}")
        return None


def create_new_competition():
    """Crea una nueva competencia semanal"""
    from db import get_cursor
    try:
        now = datetime.now()
        # Calcular inicio de semana (lunes)
        days_since_monday = now.weekday()
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        period_end = period_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        with get_cursor() as cursor:
            # Obtener siguiente numero de competencia
            cursor.execute("SELECT MAX(competition_number) as max_num FROM pts_competitions")
            result = cursor.fetchone()
            next_number = (result['max_num'] or 0) + 1

            cursor.execute("""
                INSERT INTO pts_competitions
                (competition_number, state, period_start, period_end)
                VALUES (%s, %s, %s, %s)
            """, (next_number, CompetitionState.ACTIVE, period_start, period_end))

            competition_id = cursor.lastrowid

            # Log de creacion
            log_state_change(competition_id, None, CompetitionState.ACTIVE,
                           'competition_created', f'Competencia #{next_number} iniciada')

            logger.info(f"[PTS Competition] Nueva competencia #{next_number} creada")

            return {
                'id': competition_id,
                'competition_number': next_number,
                'state': CompetitionState.ACTIVE,
                'period_start': period_start,
                'period_end': period_end,
                'rewards_distributed': 0,
                'pts_reset_done': 0
            }
    except Exception as e:
        logger.error(f"[PTS Competition] Error creando competencia: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_competition_state():
    """Obtiene el estado actual del sistema de competencias"""
    competition = get_current_competition()
    if not competition:
        return {
            'state': CompetitionState.ACTIVE,
            'can_earn_pts': True,
            'message': STATE_MESSAGES[CompetitionState.ACTIVE]
        }

    state = competition['state']
    message_info = STATE_MESSAGES.get(state, STATE_MESSAGES[CompetitionState.ACTIVE])

    # Calcular tiempos restantes segun estado
    remaining_info = calculate_remaining_time(competition)

    return {
        'state': state,
        'competition_id': competition['id'],
        'competition_number': competition['competition_number'],
        'can_earn_pts': message_info['can_earn_pts'],
        'title': message_info['title'],
        'message': message_info['message'],
        'period_start': competition['period_start'].strftime('%Y-%m-%d %H:%M') if competition['period_start'] else None,
        'period_end': competition['period_end'].strftime('%Y-%m-%d %H:%M') if competition['period_end'] else None,
        **remaining_info
    }


def calculate_remaining_time(competition):
    """Calcula tiempos restantes segun el estado"""
    now = datetime.now()
    state = competition['state']

    if state == CompetitionState.ACTIVE:
        if competition['period_end']:
            remaining = competition['period_end'] - now
            if remaining.total_seconds() > 0:
                days = remaining.days
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                return {
                    'remaining_days': days,
                    'remaining_hours': hours,
                    'remaining_minutes': minutes,
                    'remaining_total_seconds': int(remaining.total_seconds())
                }

    elif state == CompetitionState.DISTRIBUTING:
        if competition['distribution_started_at']:
            end_time = competition['distribution_started_at'] + timedelta(minutes=COMPETITION_CONFIG['distribution_duration_minutes'])
            remaining = end_time - now
            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() // 60)
                seconds = int(remaining.total_seconds() % 60)
                return {
                    'distribution_remaining_minutes': minutes,
                    'distribution_remaining_seconds': seconds
                }

    elif state == CompetitionState.PREPARATION:
        if competition['preparation_started_at']:
            end_time = competition['preparation_started_at'] + timedelta(minutes=COMPETITION_CONFIG['preparation_duration_minutes'])
            remaining = end_time - now
            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() // 60)
                seconds = int(remaining.total_seconds() % 60)
                return {
                    'preparation_remaining_minutes': minutes,
                    'preparation_remaining_seconds': seconds
                }

    return {}


def log_state_change(competition_id, previous_state, new_state, action, details=None):
    """Registra cambio de estado en el log"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO pts_competition_log
                (competition_id, previous_state, new_state, action, details)
                VALUES (%s, %s, %s, %s, %s)
            """, (competition_id, previous_state, new_state, action, details))
    except Exception as e:
        logger.error(f"[PTS Competition] Error logging: {e}")


# ============================================
# TRANSICIONES DE ESTADO
# ============================================

def end_competition(competition_id):
    """Finaliza la competencia y congela el ranking"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            # Verificar estado actual
            cursor.execute("SELECT state FROM pts_competitions WHERE id = %s", (competition_id,))
            result = cursor.fetchone()
            if not result or result['state'] != CompetitionState.ACTIVE:
                return False, "La competencia no esta activa"

            now = datetime.now()

            # Guardar ranking final
            save_final_ranking(competition_id)

            # Actualizar estado
            cursor.execute("""
                UPDATE pts_competitions
                SET state = %s, ended_at = %s
                WHERE id = %s
            """, (CompetitionState.ENDED, now, competition_id))

            log_state_change(competition_id, CompetitionState.ACTIVE, CompetitionState.ENDED,
                           'competition_ended', 'Ranking congelado')

            logger.info(f"[PTS Competition] Competencia {competition_id} finalizada")
            return True, "Competencia finalizada"
    except Exception as e:
        logger.error(f"[PTS Competition] Error finalizando: {e}")
        return False, str(e)


def save_final_ranking(competition_id):
    """Guarda el ranking final de la competencia"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            # Obtener competencia
            cursor.execute("SELECT period_start FROM pts_competitions WHERE id = %s", (competition_id,))
            competition = cursor.fetchone()
            if not competition:
                return False

            period_start = competition['period_start'].date() if isinstance(competition['period_start'], datetime) else competition['period_start']

            # Obtener ranking actual
            cursor.execute("""
                SELECT r.user_id, r.pts_earned
                FROM pts_ranking r
                WHERE r.period_type = 'weekly' AND r.period_start = %s
                ORDER BY r.pts_earned DESC
                LIMIT 100
            """, (period_start,))

            rankings = cursor.fetchall()
            min_pts = COMPETITION_CONFIG['min_pts_qualify']

            for i, row in enumerate(rankings, 1):
                pts_earned = int(row['pts_earned'])
                reward_doge = COMPETITION_CONFIG['rewards'].get(i, Decimal('0')) if i <= 5 else Decimal('0')
                qualified = i <= 5 and pts_earned >= min_pts

                cursor.execute("""
                    INSERT INTO pts_competition_results
                    (competition_id, user_id, final_position, pts_earned, reward_doge, qualified)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    final_position = VALUES(final_position),
                    pts_earned = VALUES(pts_earned),
                    reward_doge = VALUES(reward_doge),
                    qualified = VALUES(qualified)
                """, (competition_id, row['user_id'], i, pts_earned, reward_doge, qualified))

            logger.info(f"[PTS Competition] Ranking final guardado: {len(rankings)} usuarios")
            return True
    except Exception as e:
        logger.error(f"[PTS Competition] Error guardando ranking: {e}")
        return False


def start_distribution(competition_id):
    """Inicia la fase de distribucion de recompensas"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT state FROM pts_competitions WHERE id = %s", (competition_id,))
            result = cursor.fetchone()
            if not result or result['state'] != CompetitionState.ENDED:
                return False, "La competencia debe estar finalizada"

            now = datetime.now()

            cursor.execute("""
                UPDATE pts_competitions
                SET state = %s, distribution_started_at = %s
                WHERE id = %s
            """, (CompetitionState.DISTRIBUTING, now, competition_id))

            log_state_change(competition_id, CompetitionState.ENDED, CompetitionState.DISTRIBUTING,
                           'distribution_started', 'Iniciando distribucion de recompensas')

            logger.info(f"[PTS Competition] Distribucion iniciada para competencia {competition_id}")
            return True, "Distribucion iniciada"
    except Exception as e:
        logger.error(f"[PTS Competition] Error iniciando distribucion: {e}")
        return False, str(e)


def complete_distribution(competition_id):
    """Completa la distribucion de recompensas"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT state, rewards_distributed FROM pts_competitions WHERE id = %s", (competition_id,))
            result = cursor.fetchone()
            if not result:
                return False, "Competencia no encontrada"
            if result['rewards_distributed']:
                return False, "Recompensas ya fueron distribuidas"
            if result['state'] != CompetitionState.DISTRIBUTING:
                return False, "No esta en fase de distribucion"

            # Distribuir recompensas
            success, message = distribute_rewards(competition_id)
            if not success:
                return False, message

            now = datetime.now()

            cursor.execute("""
                UPDATE pts_competitions
                SET state = %s, distribution_completed_at = %s, rewards_distributed = 1
                WHERE id = %s
            """, (CompetitionState.DISTRIBUTED, now, competition_id))

            log_state_change(competition_id, CompetitionState.DISTRIBUTING, CompetitionState.DISTRIBUTED,
                           'distribution_completed', 'Recompensas distribuidas correctamente')

            logger.info(f"[PTS Competition] Distribucion completada para competencia {competition_id}")
            return True, "Recompensas distribuidas"
    except Exception as e:
        logger.error(f"[PTS Competition] Error completando distribucion: {e}")
        return False, str(e)


def send_reward_notification(user_id, position, reward_doge, competition_number=None):
    """Envía notificación de recompensa al usuario via Telegram Bot"""
    try:
        BOT_TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
        if not BOT_TOKEN:
            logger.warning(f"[PTS Competition] BOT_TOKEN no configurado, no se puede enviar mensaje")
            return False
        
        # Emojis de medalla según posición
        position_medals = {
            1: '🥇',
            2: '🥈', 
            3: '🥉',
            4: '🏅',
            5: '🎖️'
        }
        medal = position_medals.get(position, '🏆')
        
        competition_text = f" #{competition_number}" if competition_number else ""
        
        message = f"""🎉 <b>¡FELICIDADES! RECOMPENSA ACREDITADA</b>

{medal} <b>Has clasificado en el Top {position}</b> de la Competencia Semanal{competition_text} de PTS.

💰 <b>Recompensa: +{reward_doge:.4f} DOGE</b>

Tu premio ha sido acreditado automáticamente a tu balance de DOGE.

📊 Sigue acumulando PTS para ganar más recompensas en la próxima competencia.

¡Gracias por participar! 🚀

<i>— SALLY-E Bot 🤖</i>"""

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        response = requests.post(url, json={
            'chat_id': user_id,
            'text': message,
            'parse_mode': 'HTML'
        }, timeout=10)
        
        result = response.json()
        if result.get('ok'):
            logger.info(f"[PTS Competition] ✅ Notificación de recompensa enviada a {user_id} (Top {position})")
            return True
        else:
            logger.error(f"[PTS Competition] ❌ Error enviando mensaje: {result.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        logger.error(f"[PTS Competition] ❌ Error enviando notificación: {e}")
        return False


def distribute_rewards(competition_id):
    """Distribuye las recompensas a los usuarios calificados"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            # Obtener número de competencia
            cursor.execute("""
                SELECT competition_number FROM pts_competitions WHERE id = %s
            """, (competition_id,))
            comp_info = cursor.fetchone()
            competition_number = comp_info['competition_number'] if comp_info else None
            
            # Obtener usuarios calificados
            cursor.execute("""
                SELECT user_id, final_position, reward_doge, qualified, reward_credited
                FROM pts_competition_results
                WHERE competition_id = %s AND qualified = 1 AND reward_credited = 0
                ORDER BY final_position ASC
            """, (competition_id,))

            results = cursor.fetchall()
            credited_count = 0
            notified_count = 0

            for result in results:
                user_id = result['user_id']
                reward_doge = float(result['reward_doge'])
                position = result['final_position']

                if reward_doge > 0:
                    # Acreditar DOGE al usuario
                    cursor.execute("""
                        UPDATE users
                        SET doge_balance = doge_balance + %s
                        WHERE user_id = %s
                    """, (reward_doge, user_id))

                    # Registrar transaccion
                    cursor.execute("""
                        INSERT INTO transactions
                        (user_id, amount, currency, tx_type, status, description)
                        VALUES (%s, %s, 'DOGE', 'competition_reward', 'completed', %s)
                    """, (user_id, reward_doge, f'Premio Top {position} Competencia Semanal'))

                    # Marcar como acreditado
                    cursor.execute("""
                        UPDATE pts_competition_results
                        SET reward_credited = 1, credited_at = NOW()
                        WHERE competition_id = %s AND user_id = %s
                    """, (competition_id, user_id))

                    credited_count += 1
                    logger.info(f"[PTS Competition] +{reward_doge} DOGE a usuario {user_id} (Top {position})")
                    
                    # Enviar notificación por Telegram
                    if send_reward_notification(user_id, position, reward_doge, competition_number):
                        notified_count += 1

            return True, f"{credited_count} recompensas distribuidas, {notified_count} notificaciones enviadas"
    except Exception as e:
        logger.error(f"[PTS Competition] Error distribuyendo: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def start_preparation(competition_id):
    """Inicia la fase de preparacion"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT state FROM pts_competitions WHERE id = %s", (competition_id,))
            result = cursor.fetchone()
            if not result or result['state'] != CompetitionState.DISTRIBUTED:
                return False, "Las recompensas deben estar distribuidas"

            now = datetime.now()

            cursor.execute("""
                UPDATE pts_competitions
                SET state = %s, preparation_started_at = %s
                WHERE id = %s
            """, (CompetitionState.PREPARATION, now, competition_id))

            log_state_change(competition_id, CompetitionState.DISTRIBUTED, CompetitionState.PREPARATION,
                           'preparation_started', 'Preparando nueva competencia')

            logger.info(f"[PTS Competition] Preparacion iniciada para competencia {competition_id}")
            return True, "Preparacion iniciada"
    except Exception as e:
        logger.error(f"[PTS Competition] Error iniciando preparacion: {e}")
        return False, str(e)


def complete_preparation_and_start_new(competition_id):
    """Completa la preparacion, resetea PTS e inicia nueva competencia"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT state, pts_reset_done FROM pts_competitions WHERE id = %s", (competition_id,))
            result = cursor.fetchone()
            if not result:
                return False, "Competencia no encontrada"
            if result['pts_reset_done']:
                return False, "PTS ya fueron reseteados"
            if result['state'] != CompetitionState.PREPARATION:
                return False, "No esta en fase de preparacion"

            # RESET EXCLUSIVO DE PTS
            success, message = reset_pts_balances(competition_id)
            if not success:
                return False, message

            now = datetime.now()

            # Marcar competencia como completada
            cursor.execute("""
                UPDATE pts_competitions
                SET completed_at = %s, pts_reset_done = 1
                WHERE id = %s
            """, (now, competition_id))

            log_state_change(competition_id, CompetitionState.PREPARATION, 'COMPLETED',
                           'preparation_completed', 'PTS reseteados, competencia archivada')

            # Crear nueva competencia
            new_competition = create_new_competition()
            if new_competition:
                logger.info(f"[PTS Competition] Nueva competencia #{new_competition['competition_number']} iniciada")
                return True, f"Nueva competencia #{new_competition['competition_number']} iniciada"

            return False, "Error creando nueva competencia"
    except Exception as e:
        logger.error(f"[PTS Competition] Error completando preparacion: {e}")
        return False, str(e)


def reset_pts_balances(competition_id):
    """
    RESET EXCLUSIVO DE PTS
    SOLO modifica pts_balance en user_pts
    NO modifica ningun otro dato del sistema
    """
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            # Contar usuarios y PTS antes del reset
            cursor.execute("SELECT COUNT(*) as count, SUM(pts_balance) as total FROM user_pts WHERE pts_balance > 0")
            before = cursor.fetchone()
            users_affected = before['count'] or 0
            total_pts = before['total'] or 0

            # RESET EXCLUSIVO - Solo pts_balance
            cursor.execute("UPDATE user_pts SET pts_balance = 0, pts_today = 0")

            # Limpiar ranking actual (para nueva competencia)
            cursor.execute("DELETE FROM pts_ranking WHERE period_type = 'weekly'")

            # Registrar reset
            cursor.execute("""
                INSERT INTO pts_reset_history
                (competition_id, users_affected, total_pts_reset)
                VALUES (%s, %s, %s)
            """, (competition_id, users_affected, total_pts))

            logger.info(f"[PTS Competition] RESET PTS: {users_affected} usuarios, {total_pts} PTS total")
            return True, f"PTS reseteados: {users_affected} usuarios"
    except Exception as e:
        logger.error(f"[PTS Competition] Error reseteando PTS: {e}")
        return False, str(e)


# ============================================
# PROCESO AUTOMATICO
# ============================================

def check_and_process_competition():
    """
    Verifica y procesa automaticamente las transiciones de estado.
    Llamar periodicamente (cada minuto) desde un scheduler.
    """
    competition = get_current_competition()
    if not competition:
        return

    state = competition['state']
    competition_id = competition['id']
    now = datetime.now()

    # ACTIVE -> ENDED (cuando termina el periodo)
    if state == CompetitionState.ACTIVE:
        if competition['period_end'] and now >= competition['period_end']:
            end_competition(competition_id)
            start_distribution(competition_id)

    # DISTRIBUTING -> DISTRIBUTED (despues de 30 minutos)
    elif state == CompetitionState.DISTRIBUTING:
        if competition['distribution_started_at']:
            end_time = competition['distribution_started_at'] + timedelta(minutes=COMPETITION_CONFIG['distribution_duration_minutes'])
            if now >= end_time:
                complete_distribution(competition_id)
                start_preparation(competition_id)

    # PREPARATION -> NEW COMPETITION (despues de 1 hora)
    elif state == CompetitionState.PREPARATION:
        if competition['preparation_started_at']:
            end_time = competition['preparation_started_at'] + timedelta(minutes=COMPETITION_CONFIG['preparation_duration_minutes'])
            if now >= end_time:
                complete_preparation_and_start_new(competition_id)


def can_earn_pts():
    """Verifica si los usuarios pueden ganar PTS actualmente"""
    state = get_competition_state()
    return state.get('can_earn_pts', True)


# ============================================
# RANKING CON ESTADO DE COMPETENCIA
# ============================================

def get_competition_ranking(limit=10):
    """Obtiene el ranking actual o historial segun estado"""
    from db import get_cursor
    competition = get_current_competition()
    if not competition:
        return []

    state = competition['state']

    # Si esta activo, mostrar ranking en tiempo real
    if state == CompetitionState.ACTIVE:
        return get_live_ranking(competition, limit)

    # Si no esta activo, mostrar ranking congelado
    return get_frozen_ranking(competition['id'], limit)


def get_live_ranking(competition, limit=10):
    """Obtiene ranking en tiempo real"""
    from db import get_cursor
    try:
        period_start = competition['period_start'].date() if isinstance(competition['period_start'], datetime) else competition['period_start']

        with get_cursor() as cursor:
            cursor.execute("""
                SELECT r.user_id, r.pts_earned, u.username, u.first_name
                FROM pts_ranking r
                LEFT JOIN users u ON r.user_id COLLATE utf8mb4_unicode_ci = u.user_id COLLATE utf8mb4_unicode_ci
                WHERE r.period_type = 'weekly' AND r.period_start = %s
                ORDER BY r.pts_earned DESC
                LIMIT %s
            """, (period_start, limit))

            results = cursor.fetchall()
            min_pts = COMPETITION_CONFIG['min_pts_qualify']

            ranking = []
            for i, row in enumerate(results, 1):
                pts_earned = int(row['pts_earned'])
                reward_doge = float(COMPETITION_CONFIG['rewards'].get(i, Decimal('0'))) if i <= 5 else 0
                qualified = i <= 5 and pts_earned >= min_pts

                ranking.append({
                    'position': i,
                    'user_id': row['user_id'],
                    'username': row['username'] or 'Usuario',
                    'first_name': row['first_name'] or 'Usuario',
                    'pts': pts_earned,
                    'reward_doge': reward_doge,
                    'qualified': qualified,
                    'in_prize_zone': i <= 5,
                    'needs_pts': max(0, min_pts - pts_earned) if i <= 5 else 0
                })

            return ranking
    except Exception as e:
        logger.error(f"[PTS Competition] Error ranking live: {e}")
        return []


def get_frozen_ranking(competition_id, limit=10):
    """Obtiene ranking congelado de una competencia"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT cr.user_id, cr.final_position, cr.pts_earned, cr.reward_doge,
                       cr.qualified, cr.reward_credited, u.username, u.first_name
                FROM pts_competition_results cr
                LEFT JOIN users u ON cr.user_id COLLATE utf8mb4_unicode_ci = u.user_id COLLATE utf8mb4_unicode_ci
                WHERE cr.competition_id = %s
                ORDER BY cr.final_position ASC
                LIMIT %s
            """, (competition_id, limit))

            results = cursor.fetchall()
            min_pts = COMPETITION_CONFIG['min_pts_qualify']

            ranking = []
            for row in results:
                ranking.append({
                    'position': row['final_position'],
                    'user_id': row['user_id'],
                    'username': row['username'] or 'Usuario',
                    'first_name': row['first_name'] or 'Usuario',
                    'pts': int(row['pts_earned']),
                    'reward_doge': float(row['reward_doge']),
                    'qualified': bool(row['qualified']),
                    'reward_credited': bool(row['reward_credited']),
                    'in_prize_zone': row['final_position'] <= 5,
                    'needs_pts': max(0, min_pts - int(row['pts_earned'])) if row['final_position'] <= 5 else 0
                })

            return ranking
    except Exception as e:
        logger.error(f"[PTS Competition] Error ranking frozen: {e}")
        return []


def get_user_competition_rank(user_id):
    """Obtiene la posicion del usuario en la competencia actual"""
    from db import get_cursor
    competition = get_current_competition()
    if not competition:
        return {'position': 0, 'pts': 0, 'qualified': False}

    state = competition['state']

    if state == CompetitionState.ACTIVE:
        # Ranking en tiempo real
        try:
            period_start = competition['period_start'].date() if isinstance(competition['period_start'], datetime) else competition['period_start']

            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) + 1 AS position
                    FROM pts_ranking
                    WHERE period_type = 'weekly' AND period_start = %s
                    AND pts_earned > (
                        SELECT COALESCE(pts_earned, 0) FROM pts_ranking
                        WHERE user_id = %s AND period_type = 'weekly' AND period_start = %s
                    )
                """, (period_start, str(user_id), period_start))
                result = cursor.fetchone()
                position = int(result['position']) if result else 0

                cursor.execute("""
                    SELECT pts_earned FROM pts_ranking
                    WHERE user_id = %s AND period_type = 'weekly' AND period_start = %s
                """, (str(user_id), period_start))
                pts_result = cursor.fetchone()
                pts = int(pts_result['pts_earned']) if pts_result else 0

                min_pts = COMPETITION_CONFIG['min_pts_qualify']
                in_prize_zone = position <= 5 and position > 0
                qualified = in_prize_zone and pts >= min_pts
                reward_doge = float(COMPETITION_CONFIG['rewards'].get(position, Decimal('0'))) if in_prize_zone else 0

                return {
                    'position': position,
                    'pts': pts,
                    'in_prize_zone': in_prize_zone,
                    'qualified': qualified,
                    'reward_doge': reward_doge,
                    'needs_pts': max(0, min_pts - pts) if in_prize_zone else 0,
                    'min_pts_required': min_pts
                }
        except Exception as e:
            logger.error(f"[PTS Competition] Error user rank: {e}")
    else:
        # Ranking congelado
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT final_position, pts_earned, reward_doge, qualified, reward_credited
                    FROM pts_competition_results
                    WHERE competition_id = %s AND user_id = %s
                """, (competition['id'], str(user_id)))
                result = cursor.fetchone()

                if result:
                    return {
                        'position': result['final_position'],
                        'pts': int(result['pts_earned']),
                        'in_prize_zone': result['final_position'] <= 5,
                        'qualified': bool(result['qualified']),
                        'reward_doge': float(result['reward_doge']),
                        'reward_credited': bool(result['reward_credited']),
                        'needs_pts': 0,
                        'min_pts_required': COMPETITION_CONFIG['min_pts_qualify']
                    }
        except Exception as e:
            logger.error(f"[PTS Competition] Error user frozen rank: {e}")

    return {
        'position': 0,
        'pts': 0,
        'in_prize_zone': False,
        'qualified': False,
        'reward_doge': 0,
        'needs_pts': 0,
        'min_pts_required': COMPETITION_CONFIG['min_pts_qualify']
    }


def get_competition_history(limit=10):
    """Obtiene historial de competencias pasadas"""
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, competition_number, period_start, period_end,
                       rewards_distributed, completed_at
                FROM pts_competitions
                WHERE completed_at IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"[PTS Competition] Error historial: {e}")
        return []


# ============================================
# API ENDPOINTS
# ============================================

@pts_competition_bp.route('/api/competition/state', methods=['GET'])
def api_competition_state():
    """Obtiene el estado actual de la competencia"""
    state = get_competition_state()
    return jsonify({'success': True, **state})


@pts_competition_bp.route('/api/competition/ranking', methods=['GET'])
def api_competition_ranking():
    """Obtiene el ranking de la competencia actual"""
    user_id = request.args.get('user_id')
    limit = request.args.get('limit', 10, type=int)

    state = get_competition_state()
    ranking = get_competition_ranking(limit)
    user_rank = get_user_competition_rank(user_id) if user_id else None

    return jsonify({
        'success': True,
        'state': state,
        'ranking': ranking,
        'user_rank': user_rank,
        'config': {
            'min_pts_qualify': COMPETITION_CONFIG['min_pts_qualify'],
            'prize_positions': COMPETITION_CONFIG['prize_positions'],
            'rewards': {k: float(v) for k, v in COMPETITION_CONFIG['rewards'].items()}
        }
    })


@pts_competition_bp.route('/api/competition/history', methods=['GET'])
def api_competition_history():
    """Obtiene historial de competencias"""
    limit = request.args.get('limit', 10, type=int)
    history = get_competition_history(limit)
    return jsonify({'success': True, 'history': history})


# ============================================
# ADMIN ENDPOINTS
# ============================================

@pts_competition_bp.route('/api/admin/competition/end', methods=['POST'])
def api_admin_end_competition():
    """Finaliza la competencia actual (admin)"""
    competition = get_current_competition()
    if not competition:
        return jsonify({'success': False, 'error': 'No hay competencia activa'}), 400

    success, message = end_competition(competition['id'])
    if success:
        start_distribution(competition['id'])

    return jsonify({'success': success, 'message': message})


@pts_competition_bp.route('/api/admin/competition/distribute', methods=['POST'])
def api_admin_distribute():
    """Completa la distribucion (admin)"""
    competition = get_current_competition()
    if not competition:
        return jsonify({'success': False, 'error': 'No hay competencia'}), 400

    success, message = complete_distribution(competition['id'])
    if success:
        start_preparation(competition['id'])

    return jsonify({'success': success, 'message': message})


@pts_competition_bp.route('/api/admin/competition/start-new', methods=['POST'])
def api_admin_start_new():
    """Completa preparacion e inicia nueva competencia (admin)"""
    competition = get_current_competition()
    if not competition:
        return jsonify({'success': False, 'error': 'No hay competencia'}), 400

    success, message = complete_preparation_and_start_new(competition['id'])
    return jsonify({'success': success, 'message': message})


@pts_competition_bp.route('/api/admin/competition/process', methods=['POST'])
def api_admin_process():
    """Procesa automaticamente la competencia (admin)"""
    check_and_process_competition()
    state = get_competition_state()
    return jsonify({'success': True, 'state': state})
