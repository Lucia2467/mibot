"""
migrate_railway.py — VERSIÓN COMPLETA
======================================
Agrega todas las columnas faltantes en todas las tablas.
Soluciona errores tipo: Unknown column 'X' in 'where clause'

Ejecutar al arrancar la app (web.py y main.py lo llaman automáticamente).
También se puede correr manualmente: python migrate_railway.py
"""

import logging
from db import execute_query, get_cursor, test_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def column_exists(table: str, column: str) -> bool:
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME   = %s
                  AND COLUMN_NAME  = %s
            """, (table, column))
            row = cursor.fetchone()
            cnt = row.get('cnt', 0) if isinstance(row, dict) else row[0]
            return int(cnt) > 0
    except Exception as e:
        logger.error(f"Error verificando columna {table}.{column}: {e}")
        return False


def table_exists(table: str) -> bool:
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME   = %s
            """, (table,))
            row = cursor.fetchone()
            cnt = row.get('cnt', 0) if isinstance(row, dict) else row[0]
            return int(cnt) > 0
    except Exception as e:
        logger.error(f"Error verificando tabla {table}: {e}")
        return False


def safe_alter(description: str, sql: str):
    try:
        execute_query(sql)
        logger.info(f"  OK {description}")
        return True
    except Exception as e:
        err = str(e)
        if '1060' in err or 'Duplicate column' in err.lower() or 'already exists' in err.lower():
            logger.info(f"  -- {description} (ya existia)")
            return True
        logger.error(f"  ERROR {description}: {e}")
        return False


def ensure_columns(table: str, cols: dict):
    if not table_exists(table):
        logger.info(f"  SKIP Tabla {table} no existe aun")
        return
    for col, sql in cols.items():
        if not column_exists(table, col):
            safe_alter(f"{table}.{col}", sql)
        else:
            logger.info(f"  -- {table}.{col} ya existe")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: activa → active
# ─────────────────────────────────────────────────────────────

def rename_activa_to_active(table: str, col_type: str = "TINYINT(1) DEFAULT 1"):
    has_activa = column_exists(table, 'activa')
    has_active = column_exists(table, 'active')

    if has_active and has_activa:
        safe_alter(f"{table}: DROP activa", f"ALTER TABLE `{table}` DROP COLUMN activa")
    elif has_activa and not has_active:
        safe_alter(f"{table}: RENAME activa->active",
                   f"ALTER TABLE `{table}` CHANGE COLUMN activa `active` {col_type}")
    elif not has_active:
        safe_alter(f"{table}: ADD active",
                   f"ALTER TABLE `{table}` ADD COLUMN `active` {col_type}")
    else:
        logger.info(f"  -- {table}.active ya existe")


def migrate_activa_columns():
    logger.info("\n[1] Columna active en todas las tablas")
    for table, col_type in [
        ('tasks',             "TINYINT(1) DEFAULT 1"),
        ('promo_codes',       "TINYINT(1) DEFAULT 1"),
        ('referral_missions', "TINYINT(1) DEFAULT 1"),
        ('user_tasks',        "TINYINT(1) DEFAULT 1"),
        ('shrinkearn_tasks',  "TINYINT(1) DEFAULT 1"),
        ('ad_task_progress',  "TINYINT(1) DEFAULT 0"),
        ('mining_machines',   "TINYINT(1) DEFAULT 1"),
        ('user_bans',         "TINYINT(1) DEFAULT 1"),
    ]:
        if table_exists(table):
            rename_activa_to_active(table, col_type)


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: stats
# ─────────────────────────────────────────────────────────────

def migrate_stats():
    logger.info("\n[2] stats")
    if not table_exists('stats'):
        return
    if column_exists('stats', 'key') and not column_exists('stats', 'stat_key'):
        safe_alter("RENAME key->stat_key", "ALTER TABLE stats CHANGE COLUMN `key` stat_key VARCHAR(100) NOT NULL")
    elif column_exists('stats', 'name') and not column_exists('stats', 'stat_key'):
        safe_alter("RENAME name->stat_key", "ALTER TABLE stats CHANGE COLUMN `name` stat_key VARCHAR(100) NOT NULL")
    elif not column_exists('stats', 'stat_key'):
        safe_alter("ADD stat_key", "ALTER TABLE stats ADD COLUMN stat_key VARCHAR(100) NOT NULL DEFAULT ''")

    if column_exists('stats', 'value') and not column_exists('stats', 'stat_value'):
        safe_alter("RENAME value->stat_value", "ALTER TABLE stats CHANGE COLUMN `value` stat_value BIGINT DEFAULT 0")
    elif not column_exists('stats', 'stat_value'):
        safe_alter("ADD stat_value", "ALTER TABLE stats ADD COLUMN stat_value BIGINT DEFAULT 0")

    if not column_exists('stats', 'updated_at'):
        safe_alter("ADD updated_at", "ALTER TABLE stats ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

    try:
        execute_query("ALTER TABLE stats ADD UNIQUE KEY unique_stat_key (stat_key)")
    except Exception as e:
        if '1061' not in str(e) and 'Duplicate key' not in str(e):
            logger.error(f"  ERROR UNIQUE KEY: {e}")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: config
# ─────────────────────────────────────────────────────────────

def migrate_config():
    logger.info("\n[3] config")
    if not table_exists('config'):
        return
    if column_exists('config', 'key_name') and not column_exists('config', 'config_key'):
        safe_alter("RENAME key_name->config_key", "ALTER TABLE config CHANGE COLUMN key_name config_key VARCHAR(100) NOT NULL")
    elif column_exists('config', 'key') and not column_exists('config', 'config_key'):
        safe_alter("RENAME key->config_key", "ALTER TABLE config CHANGE COLUMN `key` config_key VARCHAR(100) NOT NULL")
    if column_exists('config', 'value') and not column_exists('config', 'config_value'):
        safe_alter("RENAME value->config_value", "ALTER TABLE config CHANGE COLUMN `value` config_value TEXT DEFAULT NULL")
    if not column_exists('config', 'updated_at'):
        safe_alter("ADD updated_at", "ALTER TABLE config ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: users
# ─────────────────────────────────────────────────────────────

def migrate_users():
    logger.info("\n[4] users")
    ensure_columns('users', {
        'ton_balance':        "ALTER TABLE users ADD COLUMN ton_balance DECIMAL(20,9) DEFAULT 0.000000000",
        'pending_referrer':   "ALTER TABLE users ADD COLUMN pending_referrer VARCHAR(50) DEFAULT NULL",
        'referral_validated': "ALTER TABLE users ADD COLUMN referral_validated TINYINT(1) DEFAULT 0",
        'wallet_linked_at':   "ALTER TABLE users ADD COLUMN wallet_linked_at DATETIME DEFAULT NULL",
        'ban_reason':         "ALTER TABLE users ADD COLUMN ban_reason VARCHAR(255) DEFAULT NULL",
        'last_ip':            "ALTER TABLE users ADD COLUMN last_ip VARCHAR(50) DEFAULT NULL",
        'is_admin':           "ALTER TABLE users ADD COLUMN is_admin TINYINT(1) DEFAULT 0",
        'completed_tasks':    "ALTER TABLE users ADD COLUMN completed_tasks JSON DEFAULT NULL",
        'last_interaction':   "ALTER TABLE users ADD COLUMN last_interaction DATETIME DEFAULT NULL",
        'updated_at':         "ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        'photo_url':          "ALTER TABLE users ADD COLUMN photo_url TEXT DEFAULT NULL",
        'language_code':      "ALTER TABLE users ADD COLUMN language_code VARCHAR(10) DEFAULT NULL",
        'mining_power':       "ALTER TABLE users ADD COLUMN mining_power DECIMAL(10,4) DEFAULT 1.0000",
        'mining_level':       "ALTER TABLE users ADD COLUMN mining_level INT DEFAULT 1",
        'total_mined':        "ALTER TABLE users ADD COLUMN total_mined DECIMAL(20,8) DEFAULT 0.00000000",
        'last_claim':         "ALTER TABLE users ADD COLUMN last_claim DATETIME DEFAULT NULL",
        'referral_count':     "ALTER TABLE users ADD COLUMN referral_count INT DEFAULT 0",
        'se_balance':         "ALTER TABLE users ADD COLUMN se_balance DECIMAL(20,8) DEFAULT 0.00000000",
        'usdt_balance':       "ALTER TABLE users ADD COLUMN usdt_balance DECIMAL(20,8) DEFAULT 0.00000000",
        'doge_balance':       "ALTER TABLE users ADD COLUMN doge_balance DECIMAL(20,8) DEFAULT 0.00000000",
        'banned':             "ALTER TABLE users ADD COLUMN banned TINYINT(1) DEFAULT 0",
        'wallet_address':     "ALTER TABLE users ADD COLUMN wallet_address VARCHAR(200) DEFAULT NULL",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: tasks
# ─────────────────────────────────────────────────────────────

def migrate_tasks():
    logger.info("\n[5] tasks")
    ensure_columns('tasks', {
        'task_type':             "ALTER TABLE tasks ADD COLUMN task_type VARCHAR(50) DEFAULT 'link'",
        'active':                "ALTER TABLE tasks ADD COLUMN `active` TINYINT(1) DEFAULT 1",
        'requires_channel_join': "ALTER TABLE tasks ADD COLUMN requires_channel_join TINYINT(1) DEFAULT 0",
        'channel_username':      "ALTER TABLE tasks ADD COLUMN channel_username VARCHAR(100) DEFAULT NULL",
        'max_completions':       "ALTER TABLE tasks ADD COLUMN max_completions INT DEFAULT NULL",
        'current_completions':   "ALTER TABLE tasks ADD COLUMN current_completions INT DEFAULT 0",
        'updated_at':            "ALTER TABLE tasks ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        'description':           "ALTER TABLE tasks ADD COLUMN description TEXT DEFAULT NULL",
        'url':                   "ALTER TABLE tasks ADD COLUMN url VARCHAR(500) DEFAULT NULL",
        'reward':                "ALTER TABLE tasks ADD COLUMN reward DECIMAL(10,4) DEFAULT 0.0000",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: promo_codes
# ─────────────────────────────────────────────────────────────

def migrate_promo_codes():
    logger.info("\n[6] promo_codes")
    ensure_columns('promo_codes', {
        'reward':       "ALTER TABLE promo_codes ADD COLUMN reward DECIMAL(10,4) NOT NULL DEFAULT 0.0000",
        'currency':     "ALTER TABLE promo_codes ADD COLUMN currency VARCHAR(10) DEFAULT 'SE'",
        'max_uses':     "ALTER TABLE promo_codes ADD COLUMN max_uses INT DEFAULT 100",
        'current_uses': "ALTER TABLE promo_codes ADD COLUMN current_uses INT DEFAULT 0",
        'active':       "ALTER TABLE promo_codes ADD COLUMN `active` TINYINT(1) DEFAULT 1",
        'expires_at':   "ALTER TABLE promo_codes ADD COLUMN expires_at DATETIME DEFAULT NULL",
        'created_at':   "ALTER TABLE promo_codes ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: referral_missions
# ─────────────────────────────────────────────────────────────

def migrate_referral_missions():
    logger.info("\n[7] referral_missions")
    ensure_columns('referral_missions', {
        'title':              "ALTER TABLE referral_missions ADD COLUMN title VARCHAR(200) NOT NULL DEFAULT ''",
        'description':        "ALTER TABLE referral_missions ADD COLUMN description TEXT DEFAULT NULL",
        'required_referrals': "ALTER TABLE referral_missions ADD COLUMN required_referrals INT NOT NULL DEFAULT 3",
        'reward_amount':      "ALTER TABLE referral_missions ADD COLUMN reward_amount DECIMAL(20,8) NOT NULL DEFAULT 0.5",
        'reward_currency':    "ALTER TABLE referral_missions ADD COLUMN reward_currency VARCHAR(10) DEFAULT 'DOGE'",
        'active':             "ALTER TABLE referral_missions ADD COLUMN `active` TINYINT(1) DEFAULT 1",
        'display_order':      "ALTER TABLE referral_missions ADD COLUMN display_order INT DEFAULT 0",
        'created_at':         "ALTER TABLE referral_missions ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        'updated_at':         "ALTER TABLE referral_missions ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: mining_machines
# ─────────────────────────────────────────────────────────────

def migrate_mining_machines():
    logger.info("\n[8] mining_machines")
    ensure_columns('mining_machines', {
        'machine_type':   "ALTER TABLE mining_machines ADD COLUMN machine_type VARCHAR(50) DEFAULT 'basic'",
        'price_paid':     "ALTER TABLE mining_machines ADD COLUMN price_paid DECIMAL(20,8) DEFAULT 0",
        'total_earnings': "ALTER TABLE mining_machines ADD COLUMN total_earnings DECIMAL(20,8) DEFAULT 0",
        'duration_days':  "ALTER TABLE mining_machines ADD COLUMN duration_days INT DEFAULT 30",
        'daily_rate':     "ALTER TABLE mining_machines ADD COLUMN daily_rate DECIMAL(20,8) DEFAULT 0",
        'earned_so_far':  "ALTER TABLE mining_machines ADD COLUMN earned_so_far DECIMAL(20,8) DEFAULT 0",
        'last_claim_at':  "ALTER TABLE mining_machines ADD COLUMN last_claim_at DATETIME DEFAULT NULL",
        'started_at':     "ALTER TABLE mining_machines ADD COLUMN started_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        'ends_at':        "ALTER TABLE mining_machines ADD COLUMN ends_at DATETIME DEFAULT NULL",
        'is_active':      "ALTER TABLE mining_machines ADD COLUMN is_active TINYINT(1) DEFAULT 1",
        'is_completed':   "ALTER TABLE mining_machines ADD COLUMN is_completed TINYINT(1) DEFAULT 0",
        'created_at':     "ALTER TABLE mining_machines ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        'updated_at':     "ALTER TABLE mining_machines ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: withdrawals
# ─────────────────────────────────────────────────────────────

def migrate_withdrawals():
    logger.info("\n[9] withdrawals")
    ensure_columns('withdrawals', {
        'fee':           "ALTER TABLE withdrawals ADD COLUMN fee DECIMAL(20,8) DEFAULT 0.00000000",
        'tx_hash':       "ALTER TABLE withdrawals ADD COLUMN tx_hash VARCHAR(200) DEFAULT NULL",
        'error_message': "ALTER TABLE withdrawals ADD COLUMN error_message TEXT DEFAULT NULL",
        'processed_at':  "ALTER TABLE withdrawals ADD COLUMN processed_at DATETIME DEFAULT NULL",
        'updated_at':    "ALTER TABLE withdrawals ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        'currency':      "ALTER TABLE withdrawals ADD COLUMN currency VARCHAR(10) DEFAULT 'USDT'",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: referrals
# ─────────────────────────────────────────────────────────────

def migrate_referrals():
    logger.info("\n[10] referrals")
    ensure_columns('referrals', {
        'referred_username':   "ALTER TABLE referrals ADD COLUMN referred_username VARCHAR(100) DEFAULT NULL",
        'referred_first_name': "ALTER TABLE referrals ADD COLUMN referred_first_name VARCHAR(100) DEFAULT 'Usuario'",
        'validated':           "ALTER TABLE referrals ADD COLUMN validated TINYINT(1) DEFAULT 0",
        'bonus_paid':          "ALTER TABLE referrals ADD COLUMN bonus_paid DECIMAL(10,4) DEFAULT 0.0000",
        'validated_at':        "ALTER TABLE referrals ADD COLUMN validated_at DATETIME DEFAULT NULL",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: user_ips
# ─────────────────────────────────────────────────────────────

def migrate_user_ips():
    logger.info("\n[11] user_ips")
    ensure_columns('user_ips', {
        'first_seen': "ALTER TABLE user_ips ADD COLUMN first_seen DATETIME DEFAULT CURRENT_TIMESTAMP",
        'last_seen':  "ALTER TABLE user_ips ADD COLUMN last_seen DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        'times_seen': "ALTER TABLE user_ips ADD COLUMN times_seen INT DEFAULT 1",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: user_device_history
# ─────────────────────────────────────────────────────────────

def migrate_user_device_history():
    logger.info("\n[12] user_device_history")
    ensure_columns('user_device_history', {
        'user_agent':  "ALTER TABLE user_device_history ADD COLUMN user_agent TEXT",
        'screen_info': "ALTER TABLE user_device_history ADD COLUMN screen_info JSON",
        'timezone':    "ALTER TABLE user_device_history ADD COLUMN timezone VARCHAR(50)",
        'platform':    "ALTER TABLE user_device_history ADD COLUMN platform VARCHAR(50)",
        'first_seen':  "ALTER TABLE user_device_history ADD COLUMN first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        'last_seen':   "ALTER TABLE user_device_history ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    })


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN: user_tasks
# ─────────────────────────────────────────────────────────────

def migrate_user_tasks():
    logger.info("\n[13] user_tasks")
    ensure_columns('user_tasks', {
        'task_type':             "ALTER TABLE user_tasks ADD COLUMN task_type VARCHAR(50) DEFAULT 'telegram_channel'",
        'description':           "ALTER TABLE user_tasks ADD COLUMN description TEXT",
        'channel_username':      "ALTER TABLE user_tasks ADD COLUMN channel_username VARCHAR(100) DEFAULT NULL",
        'requires_join':         "ALTER TABLE user_tasks ADD COLUMN requires_join TINYINT(1) DEFAULT 0",
        'package_id':            "ALTER TABLE user_tasks ADD COLUMN package_id VARCHAR(50) DEFAULT ''",
        'price_paid':            "ALTER TABLE user_tasks ADD COLUMN price_paid DECIMAL(20,8) DEFAULT 0",
        'max_completions':       "ALTER TABLE user_tasks ADD COLUMN max_completions INT DEFAULT 100",
        'current_completions':   "ALTER TABLE user_tasks ADD COLUMN current_completions INT DEFAULT 0",
        'reward_per_completion': "ALTER TABLE user_tasks ADD COLUMN reward_per_completion DECIMAL(10,4) DEFAULT 0.5",
        'rejection_reason':      "ALTER TABLE user_tasks ADD COLUMN rejection_reason TEXT DEFAULT NULL",
        'approved_at':           "ALTER TABLE user_tasks ADD COLUMN approved_at DATETIME DEFAULT NULL",
        'completed_at':          "ALTER TABLE user_tasks ADD COLUMN completed_at DATETIME DEFAULT NULL",
        'expires_at':            "ALTER TABLE user_tasks ADD COLUMN expires_at DATETIME DEFAULT NULL",
    })


# ─────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────

def run_migrations():
    logger.info("=" * 60)
    logger.info("MIGRACIONES DE BASE DE DATOS - INICIO")
    logger.info("=" * 60)

    if not test_connection():
        logger.error("Sin conexion a la base de datos")
        return False

    migrate_stats()
    migrate_config()
    migrate_activa_columns()
    migrate_users()
    migrate_tasks()
    migrate_promo_codes()
    migrate_referral_missions()
    migrate_mining_machines()
    migrate_withdrawals()
    migrate_referrals()
    migrate_user_ips()
    migrate_user_device_history()
    migrate_user_tasks()

    logger.info("\n" + "=" * 60)
    logger.info("MIGRACIONES COMPLETADAS")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    run_migrations()
