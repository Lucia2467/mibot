"""
migrate_ton_deposit.py - Migración para añadir columnas de depósito TON
Ejecutar una vez para añadir las columnas necesarias a la base de datos existente.
"""

from db import execute_query, get_cursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Ejecuta las migraciones necesarias para el sistema de depósitos TON"""
    
    migrations = [
        # Add ton_balance column to users if not exists
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS ton_balance DECIMAL(20, 9) DEFAULT 0.000000000
        """,
        
        # Add ton_wallet_address if not exists
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS ton_wallet_address VARCHAR(100) DEFAULT NULL
        """,
        
        # Add ton_wallet_linked_at if not exists
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS ton_wallet_linked_at DATETIME DEFAULT NULL
        """,
        
        # Add ton_wallet_memo if not exists
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS ton_wallet_memo VARCHAR(120) DEFAULT NULL
        """,
    ]
    
    logger.info("🔄 Ejecutando migraciones para depósitos TON...")
    
    for i, migration in enumerate(migrations, 1):
        try:
            # MySQL doesn't support IF NOT EXISTS for columns directly
            # Try to add and catch error if exists
            execute_query(migration)
            logger.info(f"✅ Migración {i}/{len(migrations)} completada")
        except Exception as e:
            if 'Duplicate column' in str(e) or 'already exists' in str(e).lower():
                logger.info(f"ℹ️ Migración {i}/{len(migrations)} - columna ya existe")
            else:
                logger.warning(f"⚠️ Migración {i}/{len(migrations)}: {e}")
    
    # Verify ton_deposits table exists
    try:
        from ton_deposit_system import init_deposits_table
        init_deposits_table()
        logger.info("✅ Tabla ton_deposits verificada")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo verificar ton_deposits: {e}")
    
    logger.info("✅ Migraciones completadas")
    return True


def verify_migration():
    """Verifica que las columnas existan"""
    try:
        with get_cursor() as cursor:
            cursor.execute("DESCRIBE users")
            columns = [row['Field'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
            
            required = ['ton_balance', 'ton_wallet_address']
            missing = [c for c in required if c not in columns]
            
            if missing:
                logger.warning(f"⚠️ Columnas faltantes: {missing}")
                return False
            
            logger.info("✅ Todas las columnas TON existen")
            return True
    except Exception as e:
        logger.error(f"❌ Error verificando: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("TON Deposit Migration")
    print("=" * 50)
    
    if verify_migration():
        print("\n✅ Las columnas ya existen, no se necesita migración")
    else:
        print("\n🔄 Ejecutando migración...")
        run_migration()
        verify_migration()
