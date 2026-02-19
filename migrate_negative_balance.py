#!/usr/bin/env python3
"""
migrate_negative_balance.py - Migración para permitir saldos negativos

Este script modifica las columnas de balance para permitir valores negativos.
Esto es necesario para el sistema de penalizaciones/deudas.

EJECUTAR UNA VEZ:
    python3 migrate_negative_balance.py
"""

import os
import sys
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Añadir el directorio de la aplicación al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_migration():
    """Ejecuta la migración para permitir saldos negativos"""
    
    try:
        from db import execute_query, get_cursor
        
        logger.info("=" * 60)
        logger.info("🔄 Iniciando migración para permitir saldos negativos...")
        logger.info("=" * 60)
        
        # Lista de columnas de balance a modificar
        # Usamos DECIMAL SIGNED (sin UNSIGNED) para permitir negativos
        migrations = [
            # Tabla users - columnas de balance
            ("users", "se_balance", "DECIMAL(20, 8) DEFAULT 0.00000000"),
            ("users", "usdt_balance", "DECIMAL(20, 8) DEFAULT 0.00000000"),
            ("users", "doge_balance", "DECIMAL(20, 8) DEFAULT 0.00000000"),
            ("users", "ton_balance", "DECIMAL(20, 8) DEFAULT 0.00000000"),
            ("users", "total_mined", "DECIMAL(20, 8) DEFAULT 0.00000000"),
        ]
        
        success_count = 0
        error_count = 0
        
        for table, column, definition in migrations:
            try:
                # Verificar si la columna existe
                with get_cursor() as cursor:
                    cursor.execute(f"""
                        SELECT COLUMN_NAME, COLUMN_TYPE 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = '{table}' 
                        AND COLUMN_NAME = '{column}'
                    """)
                    result = cursor.fetchone()
                    
                    if result:
                        current_type = result[1] if isinstance(result, tuple) else result.get('COLUMN_TYPE', '')
                        logger.info(f"📋 {table}.{column}: Tipo actual = {current_type}")
                        
                        # Modificar la columna para asegurar que permita negativos
                        # DECIMAL sin UNSIGNED permite negativos por defecto
                        alter_sql = f"ALTER TABLE {table} MODIFY COLUMN {column} {definition}"
                        logger.info(f"   Ejecutando: {alter_sql}")
                        execute_query(alter_sql)
                        logger.info(f"   ✅ {table}.{column} modificado correctamente")
                        success_count += 1
                    else:
                        logger.warning(f"⚠️ Columna {table}.{column} no existe, saltando...")
                        
            except Exception as e:
                logger.error(f"❌ Error modificando {table}.{column}: {e}")
                error_count += 1
        
        logger.info("=" * 60)
        logger.info(f"✅ Migración completada: {success_count} éxitos, {error_count} errores")
        logger.info("=" * 60)
        
        # Verificar que funciona con un test
        logger.info("\n🧪 Verificando que los negativos funcionan...")
        
        with get_cursor() as cursor:
            # Crear usuario de prueba temporal
            cursor.execute("""
                INSERT INTO users (user_id, username, se_balance) 
                VALUES ('_test_negative_balance_', '_test_', 0)
                ON DUPLICATE KEY UPDATE se_balance = 0
            """)
            
            # Intentar poner balance negativo
            cursor.execute("""
                UPDATE users SET se_balance = -10.5 WHERE user_id = '_test_negative_balance_'
            """)
            
            # Verificar
            cursor.execute("""
                SELECT se_balance FROM users WHERE user_id = '_test_negative_balance_'
            """)
            result = cursor.fetchone()
            balance = float(result[0] if isinstance(result, tuple) else result.get('se_balance', 0))
            
            # Limpiar usuario de prueba
            cursor.execute("DELETE FROM users WHERE user_id = '_test_negative_balance_'")
            
            if balance < 0:
                logger.info(f"✅ TEST EXITOSO: Balance negativo guardado correctamente ({balance})")
                return True
            else:
                logger.error(f"❌ TEST FALLIDO: Balance debería ser -10.5, pero es {balance}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error en migración: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_migration()
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 MIGRACIÓN EXITOSA")
        print("Ahora el sistema puede manejar saldos negativos (deudas)")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ MIGRACIÓN FALLÓ")
        print("Revisa los errores arriba")
        print("=" * 60)
    
    sys.exit(0 if success else 1)
