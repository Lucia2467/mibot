"""
deposit_scheduler.py - Scheduler de background para escaneo automático de depósitos.
Escanea DOGE BEP20 y TON cada 2 minutos en un hilo daemon.
"""

import threading
import time
import logging

logger = logging.getLogger(__name__)

_scheduler_thread = None
_running = False
SCAN_INTERVAL_SECONDS = 120  # 2 minutos


def _scan_loop():
    global _running
    logger.info("✅ Deposit scheduler started (interval: %ds)", SCAN_INTERVAL_SECONDS)

    while _running:
        # ── TON auto-scan ──
        try:
            from ton_deposit_system import scan_pending_ton_deposits
            credited_ton = scan_pending_ton_deposits()
            if credited_ton:
                logger.info("🔍 TON scan: %d depósito(s) acreditado(s)", credited_ton)
        except Exception as e:
            logger.error("❌ Error en TON scan loop: %s", e)

        # ── DOGE BEP20 auto-scan ──
        try:
            from deposit_system import scan_all_deposit_addresses, update_pending_deposits
            new_found = scan_all_deposit_addresses()
            credited_doge = update_pending_deposits()
            if new_found or credited_doge:
                logger.info("🔍 DOGE scan: %d nuevos, %d acreditados", new_found, credited_doge)
        except Exception as e:
            logger.error("❌ Error en DOGE scan loop: %s", e)

        # Esperar en fragmentos pequeños para poder detener limpiamente
        for _ in range(SCAN_INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)

    logger.info("🛑 Deposit scheduler stopped")


def start_deposit_scheduler():
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
    global _running
    _running = False
