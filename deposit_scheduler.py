"""
deposit_scheduler.py - Scheduler de background para escaneo automático de depósitos DOGE BEP20
Se ejecuta cada 5 minutos en un hilo separado.
"""

import threading
import time
import logging

logger = logging.getLogger(__name__)

_scheduler_thread = None
_running = False
SCAN_INTERVAL_SECONDS = 300  # 5 minutos


def _scan_loop():
    """Loop principal del scheduler de depósitos."""
    global _running
    logger.info("✅ Deposit scheduler started (interval: %ds)", SCAN_INTERVAL_SECONDS)

    while _running:
        try:
            from deposit_system import scan_all_deposit_addresses, update_pending_deposits
            new_found = scan_all_deposit_addresses()
            credited = update_pending_deposits()
            if new_found or credited:
                logger.info(
                    "🔍 Deposit scan: %d nuevos encontrados, %d acreditados",
                    new_found, credited
                )
        except Exception as e:
            logger.error("❌ Error en deposit scan loop: %s", e)

        # Esperar en fragmentos para poder detener limpiamente
        for _ in range(SCAN_INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)

    logger.info("🛑 Deposit scheduler stopped")


def start_deposit_scheduler():
    """Inicia el scheduler en un hilo daemon."""
    global _scheduler_thread, _running

    if _scheduler_thread and _scheduler_thread.is_alive():
        logger.warning("⚠️ Deposit scheduler already running")
        return

    _running = True
    _scheduler_thread = threading.Thread(
        target=_scan_loop,
        name="deposit-scanner",
        daemon=True
    )
    _scheduler_thread.start()
    logger.info("✅ Deposit scheduler thread launched")


def stop_deposit_scheduler():
    """Detiene el scheduler."""
    global _running
    _running = False
    logger.info("🛑 Deposit scheduler stop requested")
