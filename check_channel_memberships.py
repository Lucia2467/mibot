#!/usr/bin/env python3
"""
check_channel_memberships.py - Script para verificar membresías de canales

Este script debe ejecutarse periódicamente (recomendado: cada hora) para:
1. Verificar si los usuarios siguen siendo miembros de los canales
2. Aplicar penalizaciones si abandonaron antes del tiempo requerido
3. Enviar notificaciones de penalización

CONFIGURACIÓN DE CRON (PythonAnywhere):
En la consola de PythonAnywhere, agregar una tarea programada:
    python3 /home/tu_usuario/mibot/check_channel_memberships.py

EJECUCIÓN MANUAL:
    python3 check_channel_memberships.py
"""

import os
import sys
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Añadir el directorio de la aplicación al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Ejecutar verificación de membresías"""
    logger.info("=" * 50)
    logger.info(f"[CRON] Iniciando verificación de membresías - {datetime.now()}")
    
    try:
        from promoted_tasks_system import check_channel_memberships, send_penalty_notification
        from db import get_cursor
        
        # Ejecutar verificación
        penalties_count = check_channel_memberships()
        
        logger.info(f"[CRON] Verificación completada. Penalizaciones aplicadas: {penalties_count}")
        
        # Enviar notificaciones pendientes
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT user_id, channel_username, penalty_amount 
                    FROM channel_penalties 
                    WHERE notified = 0
                """)
                pending = cursor.fetchall()
                
                for row in pending:
                    row_dict = dict(row) if hasattr(row, 'keys') else {}
                    user_id = row_dict.get('user_id', row[0])
                    channel = row_dict.get('channel_username', row[1])
                    amount = float(row_dict.get('penalty_amount', row[2]))
                    
                    if send_penalty_notification(user_id, channel, amount):
                        logger.info(f"[CRON] Notificación enviada a {user_id}")
                    else:
                        logger.warning(f"[CRON] No se pudo enviar notificación a {user_id}")
                        
        except Exception as e:
            logger.error(f"[CRON] Error enviando notificaciones: {e}")
            
        logger.info(f"[CRON] Proceso completado - {datetime.now()}")
        return True
        
    except ImportError as e:
        logger.error(f"[CRON] Error de importación: {e}")
        logger.error("[CRON] Asegúrate de que promoted_tasks_system.py esté en el directorio correcto")
        return False
        
    except Exception as e:
        logger.error(f"[CRON] Error inesperado: {e}")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
