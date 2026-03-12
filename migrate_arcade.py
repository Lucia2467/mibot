"""
migrate_arcade.py - Crea la tabla arcade_sessions para el sistema de juegos externos
Ejecutar una sola vez o incluir en migrate_railway.py
"""

import logging
logger = logging.getLogger(__name__)

def run_arcade_migration():
    try:
        from db import execute_query
        execute_query("""
            CREATE TABLE IF NOT EXISTS arcade_sessions (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                game_id VARCHAR(64) NOT NULL DEFAULT 'unknown',
                minutes_played INT NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_arcade_user_date (user_id, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        logger.info("✅ [Arcade] Tabla arcade_sessions lista.")
    except Exception as e:
        logger.error(f"❌ [Arcade] Error creando tabla arcade_sessions: {e}")

if __name__ == '__main__':
    run_arcade_migration()
