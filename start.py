"""
start.py — Arranca la app web (Gunicorn + Flask) y el bot de Telegram
======================================================================
Railway solo permite un comando de inicio, este archivo corre los dos:
  - Gunicorn (producción) sirviendo web.py — reemplaza Flask dev server
  - Bot de Telegram en hilo daemon del mismo proceso

Uso:
    python start.py
"""

import os
import sys
import logging
import threading
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# MIGRACIONES (una sola vez, antes de todo)
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
# BOT DE TELEGRAM — hilo daemon
# ─────────────────────────────────────────────────────────────
def run_bot_thread():
    try:
        from web import _start_bot_thread
        bot_thread = threading.Thread(target=_start_bot_thread, daemon=True, name="TelegramBot")
        bot_thread.start()
        logger.info("🤖 Hilo del bot de Telegram iniciado")
    except Exception as e:
        logger.error(f"❌ Error arrancando bot: {e}")


# ─────────────────────────────────────────────────────────────
# GUNICORN — servidor de producción
# ─────────────────────────────────────────────────────────────
def run_gunicorn():
    """
    Arranca Gunicorn programáticamente.
    Equivalente a: gunicorn --config gunicorn.conf.py web:app
    Pero corriendo en el mismo proceso, para que el bot thread siga vivo.
    """
    try:
        from gunicorn.app.base import BaseApplication

        class StandaloneApp(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        from web import app as flask_app

        port = int(os.environ.get("PORT", 5000))

        options = {
            "bind":               f"0.0.0.0:{port}",
            "workers":            1,          # 1 solo worker → bot no se duplica
            "worker_class":       "gthread",  # threads reales
            "threads":            8,          # 8 requests en paralelo
            "timeout":            60,
            "graceful_timeout":   30,
            "keepalive":          5,
            "preload_app":        True,
            "max_requests":       1000,
            "max_requests_jitter":100,
            "accesslog":          "-",
            "errorlog":           "-",
            "loglevel":           "warning",
        }

        logger.info(f"🌐 Iniciando Gunicorn en puerto {port} (1 worker, 8 threads)...")
        StandaloneApp(flask_app, options).run()

    except ImportError:
        # Fallback: si gunicorn no está instalado, usar Flask dev server
        logger.warning("⚠️ Gunicorn no disponible, usando Flask dev server como fallback")
        from web import app
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)

    except Exception as e:
        logger.error(f"❌ Error en Gunicorn: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 ARCADE PXC — Iniciando sistema")
    logger.info("=" * 50)

    # 1. Migraciones
    run_migrations_once()

    # 2. Bot en hilo daemon
    run_bot_thread()

    # 3. Gunicorn en hilo principal (bloquea hasta que el proceso muere)
    run_gunicorn()
