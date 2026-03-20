"""
start.py — Arranca la app web (Flask) y el bot de Telegram juntos
==================================================================
Railway solo permite un comando de inicio, este archivo corre los dos:
  - Flask (web.py) en un hilo separado
  - Bot de Telegram (main.py) en el hilo principal con asyncio

Uso:
    python start.py
"""

import os
import sys
import logging
import threading
import asyncio
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# EJECUTAR MIGRACIONES PRIMERO (una sola vez, antes de todo)
# ─────────────────────────────────────────────────────────────
def run_migrations_once():
    try:
        from migrate_railway import run_migrations
        logger.info("🔧 Ejecutando migraciones de base de datos...")
        run_migrations()
        logger.info("✅ Migraciones completadas")
    except Exception as e:
        logger.error(f"⚠️ Error en migraciones: {e}")

    try:
        from migrate_arcade import run_arcade_migration
        run_arcade_migration()
    except Exception as e:
        logger.error(f"⚠️ Error en migración arcade: {e}")


# ─────────────────────────────────────────────────────────────
# BOT DE TELEGRAM — hilo daemon controlado desde aquí
# ─────────────────────────────────────────────────────────────
def run_bot_thread():
    """Arranca el bot de Telegram en un hilo daemon separado."""
    try:
        from web import _start_bot_thread
        bot_thread = threading.Thread(target=_start_bot_thread, daemon=True, name="TelegramBot")
        bot_thread.start()
        logger.info("🤖 Hilo del bot de Telegram iniciado")
    except Exception as e:
        logger.error(f"❌ Error arrancando bot: {e}")


# ─────────────────────────────────────────────────────────────
# FLASK — hilo principal
# ─────────────────────────────────────────────────────────────
def run_flask():
    try:
        logger.info("🌐 Iniciando Flask...")
        from web import app
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ Error en Flask: {e}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 ARCADE PXC — Iniciando sistema")
    logger.info("=" * 50)

    # 1. Migraciones
    run_migrations_once()

    # 2. Bot en hilo daemon (UNA sola instancia, controlada aquí)
    run_bot_thread()

    # 3. Flask en el hilo principal (bloquea hasta que el proceso muere)
    run_flask()
