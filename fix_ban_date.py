"""
Ejecuta esto UNA SOLA VEZ para agregar la columna ban_date a tu base de datos.
Puedes correrlo desde Railway console o agregarlo al inicio de app.py
"""
from database import execute_query

columns_to_add = [
    "ban_date TIMESTAMP NULL",
    "ban_reason TEXT NULL", 
    "ban_type VARCHAR(50) NULL",
    "ban_expires TIMESTAMP NULL",
]

for col in columns_to_add:
    col_name = col.split()[0]
    try:
        execute_query(f"ALTER TABLE users ADD COLUMN {col}")
        print(f"✅ Columna '{col_name}' agregada")
    except Exception as e:
        if "Duplicate column" in str(e) or "1060" in str(e):
            print(f"ℹ️ Columna '{col_name}' ya existe")
        else:
            print(f"❌ Error en '{col_name}': {e}")

print("Listo.")
