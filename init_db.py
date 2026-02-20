from db import execute_query


def init_database():
    print("Creando tablas...")

    # ===== TABLA USERS =====
    execute_query("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT UNIQUE,
        username VARCHAR(255),
        first_name VARCHAR(255),
        last_name VARCHAR(255),
        balance DECIMAL(18,8) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 🔥 Si la tabla ya existía sin estas columnas
    try:
        execute_query("ALTER TABLE users ADD COLUMN first_name VARCHAR(255)")
    except:
        pass

    try:
        execute_query("ALTER TABLE users ADD COLUMN last_name VARCHAR(255)")
    except:
        pass

    # ===== TABLA CONFIG =====
    execute_query("""
    CREATE TABLE IF NOT EXISTS config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        key_name VARCHAR(255) UNIQUE,
        value TEXT
    )
    """)

    # ===== TABLA STATS =====
    execute_query("""
    CREATE TABLE IF NOT EXISTS stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT,
        clicks INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    print("Tablas creadas correctamente.")


if __name__ == "__main__":
    init_database()
