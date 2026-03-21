"""
wsgi.py — Entrypoint para Gunicorn
Arranca el bot de Telegram en un hilo daemon y expone la app Flask.
Gunicorn lo llama con: gunicorn wsgi:app
"""
import os
import logging
import threading
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# 1. Migraciones (solo la primera vez, el resto es instantáneo)
try:
    from migrate_railway import run_migrations
    run_migrations()
except Exception as e:
    logger.error(f"Migration error: {e}")

try:
    from migrate_arcade import run_arcade_migration
    run_arcade_migration()
except Exception:
    pass

# 2. Bot de Telegram en hilo daemon
try:
    from web import _start_bot_thread
    threading.Thread(target=_start_bot_thread, daemon=True, name="TelegramBot").start()
    logger.info("🤖 Bot thread started")
except Exception as e:
    logger.error(f"Bot thread error: {e}")

# 3. Exponer la app Flask para Gunicorn
from web import app
