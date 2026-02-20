from db import execute_query


def init_database():
    print("Inicializando base de datos...")

    # ===== USERS =====
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
        last_ip VARCHAR(100) NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Agregar columnas faltantes si la tabla ya existía
    columns = [
        "first_name VARCHAR(255)",
        "last_name VARCHAR(255)",
        "referrer BIGINT NULL",
        "pending_referrer BIGINT NULL",
        "banned BOOLEAN DEFAULT FALSE",
        "ban_reason TEXT NULL",
        "last_ip VARCHAR(100) NULL"
    ]

    for column in columns:
        try:
            execute_query(f"ALTER TABLE users ADD COLUMN {column}")
        except:
            pass

    # ===== CONFIG =====
    execute_query("""
    CREATE TABLE IF NOT EXISTS config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        key_name VARCHAR(255) UNIQUE,
        config_value TEXT
    )
    """)

    # ===== STATS =====
    execute_query("""
    CREATE TABLE IF NOT EXISTS stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT,
        clicks INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ===== USER IPS =====
    execute_query("""
    CREATE TABLE IF NOT EXISTS user_ips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT,
        ip_address VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    print("Base de datos verificada correctamente.")


if __name__ == "__main__":
    init_database()
