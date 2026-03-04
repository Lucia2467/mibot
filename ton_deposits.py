"""
ton_deposits.py  –  Sistema de depósitos TON para SALLY-E
==========================================================
Flujo:
  1. GET /api/ton/deposit/address  → wallet del bot + memo único (TONU12345678)
  2. Usuario envía TON con memo como comment
  3. Polling cada 8s → _scan_and_credit() busca la tx en Toncenter y acredita
"""

import os
import uuid
import logging
import requests

from db import execute_query, get_cursor
from database import get_user, update_balance

logger = logging.getLogger(__name__)


# ── helpers de config ──────────────────────────────────────────────────────────

def _cfg(key, default=""):
    """Lee config seguro — siempre devuelve string, nunca lanza excepción.
    NOTA: get_config() de SALLY-E convierte automáticamente a int/float,
    por eso usamos esta función que siempre devuelve string."""
    try:
        from database import get_config
        val = get_config(key, default)
        if val is None or val is False:
            return str(default)
        return str(val)
    except Exception:
        return str(default)


# ── memo único por usuario ─────────────────────────────────────────────────────

def _memo_for(user_id) -> str:
    digits = "".join(c for c in str(user_id) if c.isdigit())
    return "TONU" + digits[-8:].zfill(8) if digits else "TONU00000001"


# ── inicialización de tabla ────────────────────────────────────────────────────

def init_ton_deposits_table():
    """Crea tabla + columnas + config por defecto. Se ejecuta al importar."""

    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS ton_deposits (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                deposit_id      VARCHAR(100)  NOT NULL UNIQUE,
                user_id         VARCHAR(50)   NOT NULL,
                ton_amount      DECIMAL(20,9) NOT NULL DEFAULT 0,
                ton_wallet_from VARCHAR(100)  NOT NULL DEFAULT '',
                ton_tx_hash     VARCHAR(200)  DEFAULT NULL,
                memo            VARCHAR(50)   DEFAULT NULL,
                status          ENUM('pending','credited','failed') DEFAULT 'pending',
                admin_note      TEXT          DEFAULT NULL,
                created_at      DATETIME      DEFAULT CURRENT_TIMESTAMP,
                credited_at     DATETIME      DEFAULT NULL,
                INDEX idx_user_id (user_id),
                INDEX idx_status  (status),
                INDEX idx_tx_hash (ton_tx_hash),
                INDEX idx_memo    (memo)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception as e:
        logger.warning(f"ton_deposits CREATE TABLE: {e}")

    # NO usamos ALTER TABLE porque Railway MySQL no soporta IF NOT EXISTS en ALTER
    # El memo se calcula deterministicamente desde user_id, no necesita columna extra

    for key, val in [
        ("ton_wallet_address",   ""),
        ("ton_min_deposit",      "0.1"),
        ("ton_deposits_enabled", "1"),
        ("toncenter_api_key",    ""),
    ]:
        try:
            execute_query(
                "INSERT IGNORE INTO config (config_key, config_value) VALUES (%s, %s)",
                (key, val)
            )
        except Exception:
            pass

    logger.info("✅ ton_deposits initialized")


# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_or_create_user_memo(user_id) -> str:
    """
    Calcula el memo único del usuario de forma determinista desde su user_id.
    No requiere columna extra en la tabla users.
    Ej: user_id=5515244003 → 'TONU44003' → 'TONU44003' (últimos 8 dígitos con padding)
    """
    return _memo_for(str(user_id))


def create_pending_deposit(user_id, memo) -> str:
    deposit_id = "TOND-" + uuid.uuid4().hex[:8].upper()
    execute_query("""
        INSERT INTO ton_deposits (deposit_id, user_id, memo, status)
        VALUES (%s, %s, %s, 'pending')
    """, (deposit_id, str(user_id), memo))
    return deposit_id


def get_deposit(deposit_id: str):
    try:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM ton_deposits WHERE deposit_id = %s", (deposit_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row) if hasattr(row, "keys") else row
    except Exception as e:
        logger.error(f"get_deposit: {e}")
    return None


def get_user_deposits(user_id, limit=20):
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT deposit_id, ton_amount, ton_tx_hash, status, created_at, credited_at
                FROM ton_deposits WHERE user_id = %s
                ORDER BY created_at DESC LIMIT %s
            """, (str(user_id), limit))
            rows = cursor.fetchall()
            return [dict(r) if hasattr(r, "keys") else r for r in rows]
    except Exception:
        return []


def get_pending_deposits():
    try:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM ton_deposits WHERE status='pending' ORDER BY created_at ASC"
            )
            rows = cursor.fetchall()
            return [dict(r) if hasattr(r, "keys") else r for r in rows]
    except Exception:
        return []


def credit_deposit(deposit_id: str, ton_amount: float, tx_hash: str, sender: str) -> bool:
    dep = get_deposit(deposit_id)
    if not dep:
        logger.error(f"credit_deposit: {deposit_id} not found")
        return False
    if dep.get("status") == "credited":
        logger.warning(f"credit_deposit: {deposit_id} already credited")
        return False

    user_id = str(dep["user_id"])
    ok = update_balance(
        user_id, "ton", ton_amount, "add",
        f"TON Deposit {deposit_id} | tx:{(tx_hash or '')[:16]}"
    )
    if not ok:
        logger.error(f"credit_deposit: update_balance failed for {user_id}")
        return False

    execute_query("""
        UPDATE ton_deposits
        SET status='credited', ton_amount=%s, ton_tx_hash=%s,
            ton_wallet_from=%s, credited_at=NOW()
        WHERE deposit_id=%s
    """, (ton_amount, tx_hash, sender, deposit_id))

    logger.info(f"✅ TON credited: {ton_amount} TON → user {user_id} (dep {deposit_id})")
    return True


# ── scanner de blockchain ──────────────────────────────────────────────────────

def _scan_and_credit(user_id, deposit_id):
    """
    Llama a Toncenter, busca tx entrante cuyo comment == memo del usuario,
    y si la encuentra acredita ton_balance.
    """
    try:
        receiver = _cfg("ton_wallet_address", "")
        api_key  = _cfg("toncenter_api_key", "") or os.getenv("TONCENTER_API_KEY", "")
        ton_min  = float(_cfg("ton_min_deposit", "0.1") or "0.1")

        # Fallback a variable de entorno si config está vacía
        if not receiver:
            receiver = os.getenv("TON_WALLET_ADDRESS", "")

        if not receiver:
            logger.error("TON: ton_wallet_address no configurada")
            return

        if not receiver.startswith(("EQ", "UQ", "kQ", "0Q", "Ef", "Uf")):
            logger.error(f"TON: dirección inválida: '{receiver}'")
            return

        memo = get_or_create_user_memo(user_id)
        logger.info(f"TON scan: memo='{memo}' wallet={receiver[:12]}…")

        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key

        resp = requests.get(
            "https://toncenter.com/api/v2/getTransactions",
            params={"address": receiver, "limit": 50},
            headers=headers,
            timeout=10
        )
        data = resp.json()

        if not data.get("ok"):
            logger.warning(f"Toncenter error: {data.get('error')} status={resp.status_code}")
            return

        txs = data.get("result", [])
        logger.info(f"TON scan: {len(txs)} txs de Toncenter")

        for tx in txs:
            in_msg     = tx.get("in_msg", {})
            comment    = str(in_msg.get("message", "") or "").strip()
            value_nano = int(in_msg.get("value", "0") or 0)
            tx_hash    = tx.get("transaction_id", {}).get("hash", "")

            if not comment or memo not in comment:
                continue

            ton_amount = value_nano / 1_000_000_000
            logger.info(f"TON match! tx={tx_hash[:12]} amount={ton_amount} comment='{comment}'")

            if ton_amount < ton_min * 0.95:
                logger.warning(f"TON: monto {ton_amount} < min {ton_min}")
                continue

            with get_cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM ton_deposits WHERE ton_tx_hash = %s", (tx_hash,)
                )
                if cursor.fetchone():
                    logger.info(f"TON: tx {tx_hash[:12]} ya procesada")
                    continue

            sender = str(in_msg.get("source", ""))
            credit_deposit(deposit_id, ton_amount, tx_hash, sender)
            return

        logger.info(f"TON scan: sin match para memo '{memo}'")

    except Exception as e:
        logger.error(f"_scan_and_credit error: {e}", exc_info=True)


# ── auto-init ──────────────────────────────────────────────────────────────────
try:
    init_ton_deposits_table()
except Exception as _e:
    logger.warning(f"ton_deposits init: {_e}")
