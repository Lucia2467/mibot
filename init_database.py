"""
init_database.py - Inicializa las tablas de la base de datos
Ejecutar este script una vez para crear todas las tablas necesarias
"""

from db import execute_query, get_cursor, test_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_tables():
    """Crea todas las tablas necesarias si no existen"""
    
    logger.info("🔄 Verificando conexión a base de datos...")
    if not test_connection():
        logger.error("❌ No se puede conectar a la base de datos")
        return False
    
    logger.info("✅ Conexión exitosa. Creando tablas...")
    
    tables = [
        # USERS TABLE
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL UNIQUE,
            username VARCHAR(100) DEFAULT NULL,
            first_name VARCHAR(100) DEFAULT 'Usuario',
            se_balance DECIMAL(20, 8) DEFAULT 0.00000000,
            usdt_balance DECIMAL(20, 8) DEFAULT 0.00000000,
            doge_balance DECIMAL(20, 8) DEFAULT 0.00000000,
            mining_power DECIMAL(10, 4) DEFAULT 1.0000,
            mining_level INT DEFAULT 1,
            total_mined DECIMAL(20, 8) DEFAULT 0.00000000,
            last_claim DATETIME DEFAULT NULL,
            referral_count INT DEFAULT 0,
            referred_by VARCHAR(50) DEFAULT NULL,
            pending_referrer VARCHAR(50) DEFAULT NULL,
            referral_validated TINYINT(1) DEFAULT 0,
            wallet_address VARCHAR(100) DEFAULT NULL,
            wallet_linked_at DATETIME DEFAULT NULL,
            banned TINYINT(1) DEFAULT 0,
            ban_reason VARCHAR(255) DEFAULT NULL,
            last_ip VARCHAR(50) DEFAULT NULL,
            completed_tasks JSON DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            last_interaction DATETIME DEFAULT NULL,
            INDEX idx_user_id (user_id),
            INDEX idx_username (username),
            INDEX idx_banned (banned)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # REFERRALS TABLE
        """
        CREATE TABLE IF NOT EXISTS referrals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            referrer_id VARCHAR(50) NOT NULL,
            referred_id VARCHAR(50) NOT NULL,
            referred_username VARCHAR(100) DEFAULT NULL,
            referred_first_name VARCHAR(100) DEFAULT 'Usuario',
            validated TINYINT(1) DEFAULT 0,
            bonus_paid DECIMAL(10, 4) DEFAULT 0.0000,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            validated_at DATETIME DEFAULT NULL,
            UNIQUE KEY unique_referral (referrer_id, referred_id),
            INDEX idx_referrer_id (referrer_id),
            INDEX idx_referred_id (referred_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # TASKS TABLE
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task_id VARCHAR(50) NOT NULL UNIQUE,
            title VARCHAR(200) NOT NULL,
            description TEXT DEFAULT NULL,
            reward DECIMAL(10, 4) DEFAULT 0.0000,
            url VARCHAR(500) DEFAULT NULL,
            task_type VARCHAR(50) DEFAULT 'link',
            active TINYINT(1) DEFAULT 1,
            max_completions INT DEFAULT NULL,
            current_completions INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_task_id (task_id),
            INDEX idx_active (active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # WITHDRAWALS TABLE
        """
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            withdrawal_id VARCHAR(100) NOT NULL UNIQUE,
            user_id VARCHAR(50) NOT NULL,
            currency VARCHAR(10) NOT NULL DEFAULT 'USDT',
            amount DECIMAL(20, 8) NOT NULL,
            fee DECIMAL(20, 8) DEFAULT 0.00000000,
            wallet_address VARCHAR(100) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            tx_hash VARCHAR(100) DEFAULT NULL,
            error_message TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME DEFAULT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # PROMO CODES TABLE
        """
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(50) NOT NULL UNIQUE,
            reward DECIMAL(10, 4) NOT NULL DEFAULT 0.0000,
            currency VARCHAR(10) DEFAULT 'SE',
            max_uses INT DEFAULT 100,
            current_uses INT DEFAULT 0,
            active TINYINT(1) DEFAULT 1,
            expires_at DATETIME DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_code (code),
            INDEX idx_active (active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # PROMO REDEMPTIONS TABLE
        """
        CREATE TABLE IF NOT EXISTS promo_redemptions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            code VARCHAR(50) NOT NULL,
            reward DECIMAL(10, 4) NOT NULL,
            currency VARCHAR(10) DEFAULT 'SE',
            redeemed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_redemption (user_id, code),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # CONFIG TABLE
        """
        CREATE TABLE IF NOT EXISTS config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value TEXT DEFAULT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_config_key (config_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # STATS TABLE
        """
        CREATE TABLE IF NOT EXISTS stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            stat_key VARCHAR(100) NOT NULL UNIQUE,
            stat_value BIGINT DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_stat_key (stat_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # USER IPS TABLE
        """
        CREATE TABLE IF NOT EXISTS user_ips (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            ip_address VARCHAR(50) NOT NULL,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            times_seen INT DEFAULT 1,
            UNIQUE KEY unique_user_ip (user_id, ip_address),
            INDEX idx_ip_address (ip_address)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # IP BANS TABLE
        """
        CREATE TABLE IF NOT EXISTS ip_bans (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ip_address VARCHAR(50) NOT NULL UNIQUE,
            reason VARCHAR(255) DEFAULT NULL,
            banned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_ip_address (ip_address)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # BALANCE HISTORY TABLE
        """
        CREATE TABLE IF NOT EXISTS balance_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            action VARCHAR(100) NOT NULL,
            currency VARCHAR(10) DEFAULT 'SE',
            amount DECIMAL(20, 8) NOT NULL,
            balance_before DECIMAL(20, 8) DEFAULT 0.00000000,
            balance_after DECIMAL(20, 8) DEFAULT 0.00000000,
            description TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # ADMIN SESSIONS TABLE
        """
        CREATE TABLE IF NOT EXISTS admin_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            admin_id VARCHAR(50) NOT NULL,
            session_token VARCHAR(255) NOT NULL,
            ip_address VARCHAR(50) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            INDEX idx_session_token (session_token)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    ]
    
    # Crear cada tabla
    for i, table_sql in enumerate(tables, 1):
        try:
            execute_query(table_sql)
            logger.info(f"✅ Tabla {i}/{len(tables)} creada/verificada")
        except Exception as e:
            logger.error(f"❌ Error en tabla {i}: {e}")
    
    # Insertar configuración por defecto
    logger.info("📝 Insertando configuración por defecto...")
    default_config = [
        ('global_mining_power', '1.0'),
        ('base_mining_rate', '1.0'),
        ('referral_bonus', '1.0'),
        ('referral_commission', '0.05'),
        ('min_withdrawal_usdt', '0.5'),
        ('min_withdrawal_doge', '0.3'),
        ('min_withdrawal_se', '100'),
        ('withdrawal_mode', 'manual'),
        ('se_to_usdt_rate', '0.01'),
        ('se_to_doge_rate', '0.06'),
        ('auto_ban_duplicate_ip', 'false'),
        ('show_promo_fab', 'true'),
        ('admin_password', 'admin123'),
    ]
    
    for key, value in default_config:
        try:
            execute_query("""
                INSERT INTO config (config_key, config_value) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE config_key = config_key
            """, (key, value))
        except Exception as e:
            pass  # Ignorar si ya existe
    
    # Insertar stats por defecto
    default_stats = [
        ('total_starts', 0),
        ('total_claims', 0),
        ('total_tasks_completed', 0),
        ('total_withdrawals', 0),
    ]
    
    for key, value in default_stats:
        try:
            execute_query("""
                INSERT INTO stats (stat_key, stat_value) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE stat_key = stat_key
            """, (key, value))
        except Exception as e:
            pass
    
    logger.info("✅ Base de datos inicializada correctamente")
    return True


def verify_tables():
    """Verifica que todas las tablas existan"""
    required_tables = [
        'users', 'referrals', 'tasks', 'withdrawals', 
        'promo_codes', 'promo_redemptions', 'config', 
        'stats', 'user_ips', 'ip_bans', 'balance_history'
    ]
    
    try:
        with get_cursor() as cursor:
            cursor.execute("SHOW TABLES")
            existing = [row[list(row.keys())[0]] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
            
            missing = [t for t in required_tables if t not in existing]
            
            if missing:
                logger.warning(f"⚠️ Tablas faltantes: {missing}")
                return False
            
            logger.info(f"✅ Todas las tablas verificadas: {len(existing)} tablas")
            return True
    except Exception as e:
        logger.error(f"❌ Error verificando tablas: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("SALLY-E Database Initialization")
    print("=" * 50)
    
    # Verificar tablas existentes
    if verify_tables():
        print("\n✅ La base de datos ya está configurada correctamente")
    else:
        print("\n🔄 Inicializando base de datos...")
        if init_tables():
            print("\n✅ Base de datos inicializada correctamente")
        else:
            print("\n❌ Error inicializando base de datos")
