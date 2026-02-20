from db import execute_query


def init_database():
    print("Creando tablas...")

    execute_query("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT UNIQUE,
        username VARCHAR(255),
        first_name VARCHAR(255),
        last_name VARCHAR(255),
        referrer BIGINT NULL,
        pending_referrer BIGINT NULL,
        banned BOOLEAN DEFAULT FALSE,
        balance DECIMAL(18,8) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 🔥 Si la tabla ya existía sin estas columnas
    columns_to_add = [
        "first_name VARCHAR(255)",
        "last_name VARCHAR(255)",
        "referrer BIGINT NULL",
        "pending_referrer BIGINT NULL",
        "banned BOOLEAN DEFAULT FALSE"
    ]

    for column in columns_to_add:
        try:
            execute_query(f"ALTER TABLE users ADD COLUMN {column}")
        except:
            pass

    execute_query("""
    CREATE TABLE IF NOT EXISTS config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        key_name VARCHAR(255) UNIQUE,
        value TEXT
    )
    """)

    execute_query("""
    CREATE TABLE IF NOT EXISTS stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT,
        clicks INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    print("Tablas verificadas correctamente.")


if __name__ == "__main__":
    init_database()
