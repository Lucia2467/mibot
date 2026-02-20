"""
migrate_railway.py
==================
Soluciona los errores de columnas en la base de datos Railway:
  - Columna desconocida 'first_seen'  → agrega a user_ips y user_device_history
  - Columna desconocida 'activa'      → renombra a 'active' en todas las tablas afectadas

Ejecutar UNA VEZ después de actualizar el código:
    python migrate_railway.py

También se puede importar y llamar al arrancar la app:
    from migrate_railway import run_migrations
    run_migrations()
"""

import logging
from db import execute_query, get_cursor, test_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────

def column_exists(table: str, column: str) -> bool:
    """Verifica si una columna existe en la tabla."""
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
    """Verifica si una tabla existe."""
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
    """Ejecuta un ALTER TABLE de forma segura, ignorando errores si ya existe."""
    try:
        execute_query(sql)
        logger.info(f"  ✅ {description}")
        return True
    except Exception as e:
        err = str(e)
        # Ignorar "Duplicate column name" o "already exists"
        if '1060' in err or 'Duplicate column' in err.lower() or 'already exists' in err.lower():
            logger.info(f"  ⏭️  {description} (ya existía)")
            return True
        logger.error(f"  ❌ {description}: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 1 — user_ips: agregar columnas faltantes
# ─────────────────────────────────────────────────────────────

def migrate_user_ips():
    logger.info("\n📋  user_ips — agregar columnas faltantes")

    if not table_exists('user_ips'):
        logger.info("  ⚠️  Tabla user_ips no existe, se creará en init_all_tables")
        return

    # first_seen
    if not column_exists('user_ips', 'first_seen'):
        safe_alter(
            "ADD COLUMN first_seen",
            "ALTER TABLE user_ips ADD COLUMN first_seen DATETIME DEFAULT CURRENT_TIMESTAMP"
        )
    else:
        logger.info("  ⏭️  first_seen ya existe")

    # last_seen
    if not column_exists('user_ips', 'last_seen'):
        safe_alter(
            "ADD COLUMN last_seen",
            "ALTER TABLE user_ips ADD COLUMN last_seen DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
    else:
        logger.info("  ⏭️  last_seen ya existe")

    # times_seen
    if not column_exists('user_ips', 'times_seen'):
        safe_alter(
            "ADD COLUMN times_seen",
            "ALTER TABLE user_ips ADD COLUMN times_seen INT DEFAULT 1"
        )
    else:
        logger.info("  ⏭️  times_seen ya existe")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 2 — user_device_history: agregar columnas faltantes
# ─────────────────────────────────────────────────────────────

def migrate_user_device_history():
    logger.info("\n📋  user_device_history — agregar columnas faltantes")

    if not table_exists('user_device_history'):
        logger.info("  ⚠️  Tabla no existe, se creará en init_all_tables")
        return

    cols = {
        'user_agent':  "ALTER TABLE user_device_history ADD COLUMN user_agent TEXT",
        'screen_info': "ALTER TABLE user_device_history ADD COLUMN screen_info JSON",
        'timezone':    "ALTER TABLE user_device_history ADD COLUMN timezone VARCHAR(50)",
        'platform':    "ALTER TABLE user_device_history ADD COLUMN platform VARCHAR(50)",
        'first_seen':  "ALTER TABLE user_device_history ADD COLUMN first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        'last_seen':   "ALTER TABLE user_device_history ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    }

    for col, sql in cols.items():
        if not column_exists('user_device_history', col):
            safe_alter(f"ADD COLUMN {col}", sql)
        else:
            logger.info(f"  ⏭️  {col} ya existe")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 3 — Renombrar columna 'activa' → 'active'
#               en tablas que puedan tenerla
# ─────────────────────────────────────────────────────────────

def rename_activa_to_active(table: str, col_type: str = "TINYINT(1) DEFAULT 1"):
    """
    - Si la tabla tiene 'activa' pero NO 'active' -> renombra.
    - Si tiene ambas -> elimina 'activa'.
    - Si no tiene ninguna -> agrega 'active' directamente.
    """
    has_activa = column_exists(table, 'activa')
    has_active = column_exists(table, 'active')

    if has_active and has_activa:
        safe_alter(
            f"{table}: DROP COLUMN activa (ya tiene active)",
            f"ALTER TABLE `{table}` DROP COLUMN activa"
        )
    elif has_activa and not has_active:
        safe_alter(
            f"{table}: RENAME activa -> active",
            f"ALTER TABLE `{table}` CHANGE COLUMN activa `active` {col_type}"
        )
    elif not has_active:
        # No tenia ninguna: agregar active con default 1
        safe_alter(
            f"{table}: ADD COLUMN active (no existia)",
            f"ALTER TABLE `{table}` ADD COLUMN `active` {col_type}"
        )
    else:
        logger.info(f"  ok  {table}: active ya existe")


def migrate_activa_columns():
    logger.info("\n📋  Renombrar columna 'activa' → 'active' en tablas afectadas")

    tablas = [
        ('tasks',              "TINYINT(1) DEFAULT 1"),
        ('promo_codes',        "TINYINT(1) DEFAULT 1"),
        ('referral_missions',  "TINYINT(1) DEFAULT 1"),
        ('user_tasks',         "TINYINT(1) DEFAULT 1"),
        ('shrinkearn_tasks',   "TINYINT(1) DEFAULT 1"),
        ('ad_task_progress',   "TINYINT(1) DEFAULT 0"),
        ('mining_machines',    "TINYINT(1) DEFAULT 1"),
    ]

    for table, col_type in tablas:
        if table_exists(table):
            rename_activa_to_active(table, col_type)
        else:
            logger.info(f"  ⏭️  {table}: no existe aún")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 4 — tasks: asegurar todas las columnas necesarias
# ─────────────────────────────────────────────────────────────

def migrate_tasks():
    logger.info("\n📋  tasks — verificar columnas completas")

    if not table_exists('tasks'):
        logger.info("  ⚠️  Tabla tasks no existe")
        return

    cols = {
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
    }

    for col, sql in cols.items():
        if not column_exists('tasks', col):
            safe_alter(f"ADD COLUMN {col}", sql)
        else:
            logger.info(f"  ⏭️  {col} ya existe")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 5 — users: asegurar columnas nuevas
# ─────────────────────────────────────────────────────────────

def migrate_users():
    logger.info("\n📋  users — verificar columnas nuevas")

    if not table_exists('users'):
        logger.info("  ⚠️  Tabla users no existe")
        return

    cols = {
        'ton_balance':       "ALTER TABLE users ADD COLUMN ton_balance DECIMAL(20,9) DEFAULT 0.000000000",
        'pending_referrer':  "ALTER TABLE users ADD COLUMN pending_referrer VARCHAR(50) DEFAULT NULL",
        'referral_validated':"ALTER TABLE users ADD COLUMN referral_validated TINYINT(1) DEFAULT 0",
        'wallet_linked_at':  "ALTER TABLE users ADD COLUMN wallet_linked_at DATETIME DEFAULT NULL",
        'ban_reason':        "ALTER TABLE users ADD COLUMN ban_reason VARCHAR(255) DEFAULT NULL",
        'last_ip':           "ALTER TABLE users ADD COLUMN last_ip VARCHAR(50) DEFAULT NULL",
        'is_admin':          "ALTER TABLE users ADD COLUMN is_admin TINYINT(1) DEFAULT 0",
        'completed_tasks':   "ALTER TABLE users ADD COLUMN completed_tasks JSON DEFAULT NULL",
        'last_interaction':  "ALTER TABLE users ADD COLUMN last_interaction DATETIME DEFAULT NULL",
        'updated_at':        "ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        'photo_url':         "ALTER TABLE users ADD COLUMN photo_url TEXT DEFAULT NULL",
        'language_code':     "ALTER TABLE users ADD COLUMN language_code VARCHAR(10) DEFAULT NULL",
        'mining_power':      "ALTER TABLE users ADD COLUMN mining_power DECIMAL(10,4) DEFAULT 1.0000",
        'mining_level':      "ALTER TABLE users ADD COLUMN mining_level INT DEFAULT 1",
        'total_mined':       "ALTER TABLE users ADD COLUMN total_mined DECIMAL(20,8) DEFAULT 0.00000000",
        'last_claim':        "ALTER TABLE users ADD COLUMN last_claim DATETIME DEFAULT NULL",
        'referral_count':    "ALTER TABLE users ADD COLUMN referral_count INT DEFAULT 0",
        'se_balance':        "ALTER TABLE users ADD COLUMN se_balance DECIMAL(20,8) DEFAULT 0.00000000",
        'usdt_balance':      "ALTER TABLE users ADD COLUMN usdt_balance DECIMAL(20,8) DEFAULT 0.00000000",
        'doge_balance':      "ALTER TABLE users ADD COLUMN doge_balance DECIMAL(20,8) DEFAULT 0.00000000",
    }

    for col, sql in cols.items():
        if not column_exists('users', col):
            safe_alter(f"ADD COLUMN {col}", sql)
        else:
            logger.info(f"  ⏭️  {col} ya existe")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 6 — config: asegurar columna config_key (vs key_name)
# ─────────────────────────────────────────────────────────────

def migrate_config():
    logger.info("\n📋  config — verificar estructura")

    if not table_exists('config'):
        logger.info("  ⚠️  Tabla config no existe")
        return

    # Vieja versión usaba key_name/value, nueva usa config_key/config_value
    if column_exists('config', 'key_name') and not column_exists('config', 'config_key'):
        safe_alter(
            "RENAME key_name → config_key",
            "ALTER TABLE config CHANGE COLUMN key_name config_key VARCHAR(100) NOT NULL"
        )
    if column_exists('config', 'value') and not column_exists('config', 'config_value'):
        safe_alter(
            "RENAME value → config_value",
            "ALTER TABLE config CHANGE COLUMN value config_value TEXT DEFAULT NULL"
        )

    if not column_exists('config', 'updated_at'):
        safe_alter(
            "ADD COLUMN updated_at",
            "ALTER TABLE config ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 7 — Columnas faltantes en otras tablas críticas
# ─────────────────────────────────────────────────────────────

def migrate_withdrawals():
    logger.info("\n📋  withdrawals — verificar columnas")
    if not table_exists('withdrawals'):
        return

    cols = {
        'fee':           "ALTER TABLE withdrawals ADD COLUMN fee DECIMAL(20,8) DEFAULT 0.00000000",
        'tx_hash':       "ALTER TABLE withdrawals ADD COLUMN tx_hash VARCHAR(200) DEFAULT NULL",
        'error_message': "ALTER TABLE withdrawals ADD COLUMN error_message TEXT DEFAULT NULL",
        'processed_at':  "ALTER TABLE withdrawals ADD COLUMN processed_at DATETIME DEFAULT NULL",
        'updated_at':    "ALTER TABLE withdrawals ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        'currency':      "ALTER TABLE withdrawals ADD COLUMN currency VARCHAR(10) DEFAULT 'USDT'",
    }
    for col, sql in cols.items():
        if not column_exists('withdrawals', col):
            safe_alter(f"ADD COLUMN {col}", sql)
        else:
            logger.info(f"  ⏭️  {col} ya existe")


def migrate_referrals():
    logger.info("\n📋  referrals — verificar columnas")
    if not table_exists('referrals'):
        return

    cols = {
        'referred_username':   "ALTER TABLE referrals ADD COLUMN referred_username VARCHAR(100) DEFAULT NULL",
        'referred_first_name': "ALTER TABLE referrals ADD COLUMN referred_first_name VARCHAR(100) DEFAULT 'Usuario'",
        'validated':           "ALTER TABLE referrals ADD COLUMN validated TINYINT(1) DEFAULT 0",
        'bonus_paid':          "ALTER TABLE referrals ADD COLUMN bonus_paid DECIMAL(10,4) DEFAULT 0.0000",
        'validated_at':        "ALTER TABLE referrals ADD COLUMN validated_at DATETIME DEFAULT NULL",
    }
    for col, sql in cols.items():
        if not column_exists('referrals', col):
            safe_alter(f"ADD COLUMN {col}", sql)
        else:
            logger.info(f"  ⏭️  {col} ya existe")


# ─────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 8 — stats: renombrar columnas antiguas
# La tabla vieja podía usar 'key'/'value', la nueva usa 'stat_key'/'stat_value'
# ─────────────────────────────────────────────────────────────

def migrate_stats():
    logger.info("\n📋  stats — verificar estructura de columnas")

    if not table_exists('stats'):
        logger.info("  ⚠️  Tabla stats no existe, se creará luego")
        return

    # Renombrar 'key' → 'stat_key' si aplica
    if column_exists('stats', 'key') and not column_exists('stats', 'stat_key'):
        safe_alter(
            "RENAME key → stat_key",
            "ALTER TABLE stats CHANGE COLUMN `key` stat_key VARCHAR(100) NOT NULL"
        )
    elif not column_exists('stats', 'stat_key'):
        safe_alter(
            "ADD COLUMN stat_key",
            "ALTER TABLE stats ADD COLUMN stat_key VARCHAR(100) NOT NULL DEFAULT ''"
        )
    else:
        logger.info("  ⏭️  stat_key ya existe")

    # Renombrar 'value' → 'stat_value' si aplica
    if column_exists('stats', 'value') and not column_exists('stats', 'stat_value'):
        safe_alter(
            "RENAME value → stat_value",
            "ALTER TABLE stats CHANGE COLUMN `value` stat_value BIGINT DEFAULT 0"
        )
    elif column_exists('stats', 'stat_value'):
        logger.info("  ⏭️  stat_value ya existe")
    else:
        safe_alter(
            "ADD COLUMN stat_value",
            "ALTER TABLE stats ADD COLUMN stat_value BIGINT DEFAULT 0"
        )

    # Renombrar 'name' → 'stat_key' (otra variante posible)
    if column_exists('stats', 'name') and not column_exists('stats', 'stat_key'):
        safe_alter(
            "RENAME name → stat_key",
            "ALTER TABLE stats CHANGE COLUMN `name` stat_key VARCHAR(100) NOT NULL"
        )

    # Agregar updated_at si falta
    if not column_exists('stats', 'updated_at'):
        safe_alter(
            "ADD COLUMN updated_at",
            "ALTER TABLE stats ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
    else:
        logger.info("  ⏭️  updated_at ya existe")

    # Asegurar índice único en stat_key
    try:
        execute_query("ALTER TABLE stats ADD UNIQUE KEY unique_stat_key (stat_key)")
        logger.info("  ✅ UNIQUE KEY en stat_key creado")
    except Exception as e:
        if '1061' in str(e) or 'Duplicate key' in str(e):
            logger.info("  ⏭️  UNIQUE KEY ya existe")


# ─────────────────────────────────────────────────────────────
# MIGRACIÓN 9 — config: renombrar columnas antiguas
# ─────────────────────────────────────────────────────────────

def migrate_config_columns():
    logger.info("\n📋  config — verificar estructura de columnas")

    if not table_exists('config'):
        logger.info("  ⚠️  Tabla config no existe")
        return

    # Renombrar 'key_name' → 'config_key'
    if column_exists('config', 'key_name') and not column_exists('config', 'config_key'):
        safe_alter(
            "RENAME key_name → config_key",
            "ALTER TABLE config CHANGE COLUMN key_name config_key VARCHAR(100) NOT NULL"
        )
    elif column_exists('config', 'key') and not column_exists('config', 'config_key'):
        safe_alter(
            "RENAME key → config_key",
            "ALTER TABLE config CHANGE COLUMN `key` config_key VARCHAR(100) NOT NULL"
        )
    else:
        logger.info("  ⏭️  config_key ya existe (o no hay columna antigua)")

    # Renombrar 'value' → 'config_value'
    if column_exists('config', 'value') and not column_exists('config', 'config_value'):
        safe_alter(
            "RENAME value → config_value",
            "ALTER TABLE config CHANGE COLUMN `value` config_value TEXT DEFAULT NULL"
        )
    else:
        logger.info("  ⏭️  config_value ya existe (o no hay columna 'value')")

    # Agregar updated_at si falta
    if not column_exists('config', 'updated_at'):
        safe_alter(
            "ADD COLUMN updated_at",
            "ALTER TABLE config ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
    else:
        logger.info("  ⏭️  updated_at ya existe")




def run_migrations():
    logger.info("=" * 55)
    logger.info("🔧  MIGRACIONES DE BASE DE DATOS RAILWAY")
    logger.info("=" * 55)

    if not test_connection():
        logger.error("❌ Sin conexión a la base de datos")
        return False

    # Ejecutar todas las migraciones en orden
    migrate_stats()           # ← primero: fix stat_key/stat_value
    migrate_config_columns()  # ← segundo: fix config_key/config_value
    migrate_user_ips()
    migrate_user_device_history()
    migrate_activa_columns()
    migrate_tasks()
    migrate_users()
    migrate_config()
    migrate_withdrawals()
    migrate_referrals()

    logger.info("\n" + "=" * 55)
    logger.info("✅  MIGRACIONES COMPLETADAS")
    logger.info("=" * 55)
    return True



if __name__ == "__main__":
    run_migrations()
