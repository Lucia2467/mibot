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
# FLASK — corre en un hilo daemon
# ─────────────────────────────────────────────────────────────
def run_flask():
    try:
        logger.info("🌐 Iniciando servidor Flask...")
        from web import app
        port = int(os.environ.get("PORT", 5000))
        # use_reloader=False es obligatorio dentro de un hilo
        app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ Error en Flask: {e}")


# ─────────────────────────────────────────────────────────────
# TELEGRAM BOT — corre en el hilo principal con asyncio
# ─────────────────────────────────────────────────────────────
async def run_bot():
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN no configurado. El bot no arrancará.")
        return

    try:
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
        from telegram.ext import (
            Application, CommandHandler, CallbackQueryHandler, ContextTypes
        )

        # Importar todos los handlers desde main.py
        from main import (
            start_command, help_command, stats_command, broadcast_command,
            verify_channel_callback, my_referrals_callback,
            share_referral_callback, start_callback,
            broadcast_confirm_callback, broadcast_cancel_callback,
            error_handler
        )

        logger.info("🤖 Iniciando bot de Telegram...")

        application = Application.builder().token(BOT_TOKEN).build()

        # Comandos
        application.add_handler(CommandHandler("start",     start_command))
        application.add_handler(CommandHandler("help",      help_command))
        application.add_handler(CommandHandler("stats",     stats_command))
        application.add_handler(CommandHandler("broadcast", broadcast_command))

        # Callbacks
        application.add_handler(CallbackQueryHandler(verify_channel_callback,    pattern="^verify_channel$"))
        application.add_handler(CallbackQueryHandler(my_referrals_callback,      pattern="^my_referrals$"))
        application.add_handler(CallbackQueryHandler(share_referral_callback,    pattern="^share_referral$"))
        application.add_handler(CallbackQueryHandler(start_callback,             pattern="^start$"))
        application.add_handler(CallbackQueryHandler(broadcast_confirm_callback, pattern="^broadcast_confirm$"))
        application.add_handler(CallbackQueryHandler(broadcast_cancel_callback,  pattern="^broadcast_cancel$"))

        application.add_error_handler(error_handler)

        logger.info("✅ Bot de Telegram listo")

        # Arrancar en modo polling
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        # Mantener corriendo hasta señal de parada
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            logger.info("🛑 Deteniendo bot...")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

    except ImportError as e:
        logger.error(f"❌ Error importando módulos del bot: {e}")
    except Exception as e:
        logger.error(f"❌ Error en el bot de Telegram: {e}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 SALLY-E — Iniciando sistema completo")
    logger.info("=" * 50)

    # 1. Migraciones (antes de todo)
    run_migrations_once()

    # 2. Flask en hilo separado (daemon=True para que muera si el principal muere)
    flask_thread = threading.Thread(target=run_flask, daemon=True, name="Flask")
    flask_thread.start()
    logger.info("🌐 Flask arrancado en hilo secundario")

    # 3. Bot de Telegram en el hilo principal
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Sistema detenido por el usuario")
