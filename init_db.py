from db import execute_query


def init_database():
    print("Inicializando base de datos...")

    # ================= USERS =================
    execute_query("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT UNIQUE,
        username VARCHAR(255),
        first_name VARCHAR(255),
        last_name VARCHAR(255),
        referrer BIGINT NULL,
        pending_referrer BIGINT NULL,
        balance DECIMAL(18,8) DEFAULT 0,
        banned BOOLEAN DEFAULT FALSE,
        ban_reason TEXT NULL,
        ban_date TIMESTAMP NULL,
        last_ip VARCHAR(100) NULL,
        first_seen TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Forzar columnas faltantes
    user_columns = [
        "first_name VARCHAR(255)",
        "last_name VARCHAR(255)",
        "referrer BIGINT NULL",
        "pending_referrer BIGINT NULL",
        "banned BOOLEAN DEFAULT FALSE",
        "ban_reason TEXT NULL",
        "ban_date TIMESTAMP NULL",
        "last_ip VARCHAR(100) NULL",
        "first_seen TIMESTAMP NULL"
    ]

    for column in user_columns:
        try:
            execute_query(f"ALTER TABLE users ADD COLUMN {column}")
        except Exception:
            pass

    # ================= CONFIG =================
    execute_query("""
    CREATE TABLE IF NOT EXISTS config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        config_key VARCHAR(255) UNIQUE,
        config_value TEXT
    )
    """)

    try:
        execute_query("ALTER TABLE config ADD COLUMN config_key VARCHAR(255)")
    except:
        pass

    try:
        execute_query("ALTER TABLE config ADD COLUMN config_value TEXT")
    except:
        pass

    # ================= STATS =================
    execute_query("""
    CREATE TABLE IF NOT EXISTS stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT,
        clicks INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ================= USER IPS =================
    execute_query("""
    CREATE TABLE IF NOT EXISTS user_ips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT,
        ip_address VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ================= PROMO CODES =================
    execute_query("""
    CREATE TABLE IF NOT EXISTS promo_codes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(100) UNIQUE,
        reward DECIMAL(18,8) DEFAULT 0,
        max_uses INT DEFAULT 1,
        uses INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    print("Base de datos COMPLETAMENTE lista.")


if __name__ == "__main__":
    init_database()
