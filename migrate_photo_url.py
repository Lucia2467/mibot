"""
migrate_photo_url.py - Migración para agregar columna photo_url
================================================================
Ejecutar una vez para agregar soporte de foto de perfil en Telegram Web Login.

Uso: python migrate_photo_url.py
"""

import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import execute_query, get_cursor

def check_column_exists(table, column):
    """Verifica si una columna existe en una tabla"""
    try:
        with get_cursor() as cursor:
            cursor.execute(f"""
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = %s
                AND COLUMN_NAME = %s
            """, (table, column))
            result = cursor.fetchone()
            return result.get('count', 0) > 0 if isinstance(result, dict) else result[0] > 0
    except Exception as e:
        print(f"Error verificando columna: {e}")
        return False

def add_photo_url_column():
    """Agrega la columna photo_url a la tabla users si no existe"""
    
    print("=" * 60)
    print("MIGRACIÓN: Agregar columna photo_url")
    print("=" * 60)
    
    # Verificar si la columna ya existe
    if check_column_exists('users', 'photo_url'):
        print("✅ La columna 'photo_url' ya existe en la tabla 'users'")
        return True
    
    print("📝 Agregando columna 'photo_url'...")
    
    try:
        execute_query("""
            ALTER TABLE users
            ADD COLUMN photo_url VARCHAR(512) DEFAULT NULL
            AFTER first_name
        """)
        print("✅ Columna 'photo_url' agregada exitosamente")
        return True
    except Exception as e:
        print(f"❌ Error agregando columna: {e}")
        return False

def add_web_login_fields():
    """Agrega campos adicionales para tracking de login web"""
    
    fields_to_add = [
        ('last_web_login', 'DATETIME DEFAULT NULL', 'Último login desde web'),
        ('login_method', "VARCHAR(50) DEFAULT 'miniapp'", 'Método de login (miniapp/web)'),
    ]
    
    for field_name, field_type, description in fields_to_add:
        if check_column_exists('users', field_name):
            print(f"✅ Columna '{field_name}' ya existe ({description})")
            continue
        
        print(f"📝 Agregando columna '{field_name}' ({description})...")
        
        try:
            execute_query(f"""
                ALTER TABLE users
                ADD COLUMN {field_name} {field_type}
            """)
            print(f"✅ Columna '{field_name}' agregada")
        except Exception as e:
            print(f"⚠️ Error agregando '{field_name}': {e}")

def main():
    """Ejecuta todas las migraciones"""
    
    print("\n🚀 Iniciando migraciones para Telegram Web Login...\n")
    
    # Migración principal: photo_url
    add_photo_url_column()
    
    # Migraciones opcionales: tracking
    print("\n📊 Campos opcionales de tracking...")
    add_web_login_fields()
    
    print("\n" + "=" * 60)
    print("✅ Migraciones completadas")
    print("=" * 60)
    print("\nAhora puedes usar el Login con Telegram Web.")
    print("Rutas disponibles:")
    print("  - /web-login         : Página de login")
    print("  - /api/telegram-web-auth : API de autenticación")
    print("  - /web-logout        : Cerrar sesión web")

if __name__ == '__main__':
    main()
