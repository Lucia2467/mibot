"""
init_deposit_tables.py - Inicializa las tablas del sistema de depósitos
Ejecutar una vez antes de usar el sistema de depósitos
"""

import os
import sys

# Asegurar que el directorio está en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import execute_query, get_cursor, test_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_deposit_tables():
    """Crea las tablas necesarias para el sistema de depósitos"""
    
    logger.info("🔄 Verificando conexión a base de datos...")
    if not test_connection():
        logger.error("❌ No se puede conectar a la base de datos")
        return False
    
    logger.info("✅ Conexión exitosa. Creando tablas de depósitos...")
    
    tables = [
        # Tabla de direcciones de depósito por usuario (usa dirección única + memo)
        """
        CREATE TABLE IF NOT EXISTS user_deposit_addresses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL UNIQUE,
            deposit_address VARCHAR(100) NOT NULL,
            deposit_memo VARCHAR(100) NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_deposit_memo (deposit_memo)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # Tabla de depósitos
        """
        CREATE TABLE IF NOT EXISTS deposits (
            id INT AUTO_INCREMENT PRIMARY KEY,
            deposit_id VARCHAR(100) NOT NULL UNIQUE,
            user_id VARCHAR(50) NOT NULL,
            currency VARCHAR(10) NOT NULL DEFAULT 'DOGE',
            network VARCHAR(20) NOT NULL DEFAULT 'BEP20',
            amount DECIMAL(20, 8) NOT NULL,
            deposit_address VARCHAR(100) NOT NULL,
            tx_hash VARCHAR(100) NOT NULL UNIQUE,
            confirmations INT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            credited TINYINT(1) DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            confirmed_at DATETIME DEFAULT NULL,
            credited_at DATETIME DEFAULT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_status (status),
            INDEX idx_tx_hash (tx_hash),
            INDEX idx_deposit_address (deposit_address)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # Tabla de configuración del sistema de depósitos
        """
        CREATE TABLE IF NOT EXISTS deposit_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value TEXT DEFAULT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_config_key (config_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    ]
    
    for i, table_sql in enumerate(tables, 1):
        try:
            execute_query(table_sql)
            logger.info(f"✅ Tabla {i}/{len(tables)} creada/verificada")
        except Exception as e:
            logger.error(f"❌ Error en tabla {i}: {e}")
            return False
    
    # Insertar configuración por defecto
    logger.info("📝 Insertando configuración por defecto...")
    default_config = [
        ('min_deposit_doge', '1'),
        ('required_confirmations', '12'),
        ('deposits_enabled', 'true'),
        ('master_deposit_address', os.environ.get('ADMIN_ADDRESS', '')),
    ]
    
    for key, value in default_config:
        try:
            execute_query("""
                INSERT INTO deposit_config (config_key, config_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE config_key = config_key
            """, (key, value))
        except Exception as e:
            logger.warning(f"⚠️ Config {key}: {e}")
    
    logger.info("✅ Tablas de depósitos inicializadas correctamente")
    return True


def verify_deposit_tables():
    """Verifica que las tablas de depósitos existan"""
    required_tables = ['user_deposit_addresses', 'deposits', 'deposit_config']
    
    try:
        with get_cursor() as cursor:
            cursor.execute("SHOW TABLES")
            existing = [row[list(row.keys())[0]] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
            
            missing = [t for t in required_tables if t not in existing]
            
            if missing:
                logger.warning(f"⚠️ Tablas faltantes: {missing}")
                return False
            
            logger.info(f"✅ Todas las tablas de depósitos verificadas")
            return True
    except Exception as e:
        logger.error(f"❌ Error verificando tablas: {e}")
        return False


def add_bscscan_api_key_to_env():
    """Recuerda al usuario agregar la API key de BSCScan"""
    logger.info("""
╔════════════════════════════════════════════════════════════════════════╗
║                   CONFIGURACIÓN DE DEPÓSITOS                           ║
╠════════════════════════════════════════════════════════════════════════╣
║ Para un mejor funcionamiento del sistema de depósitos, agrega estas    ║
║ variables a tu archivo .env:                                           ║
║                                                                        ║
║   # BSCScan API Key (obtén una en https://bscscan.com/apis)           ║
║   BSCSCAN_API_KEY=tu_api_key_aqui                                     ║
║                                                                        ║
║   # Master seed para direcciones de depósito (OPCIONAL)                ║
║   # Si no lo defines, se generará automáticamente y se guardará       ║
║   # en la base de datos                                                ║
║   # DEPOSIT_MASTER_SEED=tus 24 palabras del mnemonic                  ║
║                                                                        ║
║ IMPORTANTE: El master seed se usa para derivar direcciones de         ║
║ depósito. Si lo cambias, los usuarios perderán sus direcciones        ║
║ anteriores. Guarda una copia de seguridad!                            ║
╚════════════════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    print("=" * 60)
    print("DOGE PIXEL - Deposit System Initialization")
    print("=" * 60)
    
    # Verificar si las tablas ya existen
    if verify_deposit_tables():
        print("\n✅ Las tablas de depósitos ya están configuradas")
    else:
        print("\n🔄 Inicializando tablas de depósitos...")
        if init_deposit_tables():
            print("\n✅ Tablas de depósitos inicializadas correctamente")
        else:
            print("\n❌ Error inicializando tablas de depósitos")
            sys.exit(1)
    
    # Mostrar información de configuración
    add_bscscan_api_key_to_env()
