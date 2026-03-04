"""
ton_deposits.py  –  Sistema de depósitos TON para SALLY-E
==========================================================

Flujo completo:
  1. Usuario abre modal → GET /api/ton/deposit/address
     → Devuelve wallet del bot + memo único del usuario (TONU<user_id_8dig>)
     → Crea registro pending en ton_deposits
  2. Usuario envía TON con su memo a la wallet del bot
  3. Frontend hace polling cada 8 s → GET /api/ton/deposit/status/<deposit_id>
     → En CADA poll el backend llama _scan_and_credit()
     → _scan_and_credit consulta Toncenter, busca tx con el memo, acredita ton_balance
  4. Cuando status == 'credited' → frontend muestra éxito
"""

import os
import uuid
import logging
import requests

from db import execute_query, get_cursor
from database import get_user, update_balance, get_config

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _memo_for(user_id) -> str:
    """Memo único y estable por usuario. Ej: user_id=123456789 → 'TONU23456789'"""
    digits = "".join(c for c in str(user_id) if c.isdigit())
    return "TONU" + digits[-8:].zfill(8) if digits else "TONU00000001"


# ── Inicialización de tabla ────────────────────────────────────────────────────

def init_ton_deposits_table():
    """Crea la tabla ton_deposits y agrega columnas necesarias. Se ejecuta al iniciar la app."""
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
                INDEX idx_user_id  (user_id),
                INDEX idx_status   (status),
                INDEX idx_tx_hash  (ton_tx_hash),
                INDEX idx_memo     (memo)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception as e:
        logger.warning(f"ton_deposits table: {e}")

    # Columna memo en users
    try:
        execute_query("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS ton_deposit_memo VARCHAR(50) DEFAULT NULL
        """)
    except Exception:
        pass

    # Config por defecto (solo inserta si no existen)
    default_config = [
        ('ton_wallet_address',   ''),
        ('ton_min_deposit',      '0.1'),
        ('ton_deposits_enabled', '1'),
        ('toncenter_api_key',    ''),
    ]
    for key, value in default_config:
        try:
            execute_query(
                "INSERT IGNORE INTO config (config_key, config_value) VALUES (%s, %s)",
                (key, value)
            )
        except Exception:
            pass

    logger.info("✅ ton_deposits initialized")


# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_or_create_user_memo(user_id) -> str:
    """
    Devuelve el memo único del usuario (lo crea y persiste si no existe).
    El memo identifica al usuario en la blockchain.
    """
    user_id = str(user_id)
    try:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT ton_deposit_memo FROM users WHERE user_id = %s", (user_id,)
            )
            row = cursor.fetchone()
            if row:
                memo = row["ton_deposit_memo"] if isinstance(row, dict) else row[0]
                if memo:
                    return memo
    except Exception:
        pass

    memo = _memo_for(user_id)
    try:
        execute_query(
            "UPDATE users SET ton_deposit_memo = %s WHERE user_id = %s",
            (memo, user_id)
        )
    except Exception as e:
        logger.warning(f"Could not save memo for user {user_id}: {e}")
    return memo


def create_pending_deposit(user_id, memo) -> str:
    """Crea un registro pending. Devuelve deposit_id."""
    deposit_id = "TOND-" + uuid.uuid4().hex[:8].upper()
    execute_query("""
        INSERT INTO ton_deposits (deposit_id, user_id, memo, status)
        VALUES (%s, %s, %s, 'pending')
    """, (deposit_id, str(user_id), memo))
    return deposit_id


def get_deposit(deposit_id: str):
    """Devuelve el registro de un depósito."""
    try:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM ton_deposits WHERE deposit_id = %s", (deposit_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row and hasattr(row, "keys") else (
                {"id": row[0], "deposit_id": row[1], "user_id": row[2],
                 "ton_amount": row[3], "ton_wallet_from": row[4],
                 "ton_tx_hash": row[5], "memo": row[6], "status": row[7]} if row else None
            )
    except Exception as e:
        logger.error(f"get_deposit error: {e}")
        return None


def get_user_deposits(user_id, limit=20):
    """Historial de depósitos de un usuario."""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT deposit_id, ton_amount, ton_tx_hash, status, created_at, credited_at
                FROM ton_deposits
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (str(user_id), limit))
            rows = cursor.fetchall()
            return [dict(r) if hasattr(r, "keys") else r for r in rows]
    except Exception:
        return []


def get_pending_deposits():
    """Todos los depósitos pendientes (para panel admin)."""
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
    """
    Acredita ton_balance al usuario y marca el depósito como 'credited'.
    Llama a update_balance de database.py (currency='ton').
    """
    dep = get_deposit(deposit_id)
    if not dep:
        logger.error(f"credit_deposit: deposit {deposit_id} not found")
        return False

    if dep["status"] == "credited":
        logger.warning(f"credit_deposit: {deposit_id} already credited")
        return False

    user_id = dep["user_id"]

    # Acreditar usando update_balance de SALLY-E (currency='ton', operation='add')
    ok = update_balance(
        user_id, "ton", ton_amount, "add",
        f"TON Deposit {deposit_id} | tx:{tx_hash[:16] if tx_hash else 'N/A'}"
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

    logger.info(f"✅ TON deposit credited: {ton_amount} TON → user {user_id} (deposit {deposit_id})")
    return True


# ── Scanner de blockchain ──────────────────────────────────────────────────────

def _scan_and_credit(user_id, deposit_id):
    """
    Consulta Toncenter buscando transacciones entrantes a la wallet del bot
    cuyo comment/message coincida con el memo del usuario.
    Si la encuentra, acredita ton_balance automáticamente.
    Llamado en cada poll del frontend (GET /api/ton/deposit/status/<id>).
    """
    try:
        receiver  = get_config("ton_wallet_address", "")
        api_key   = get_config("toncenter_api_key", "") or os.getenv("TONCENTER_API_KEY", "")
        ton_min   = float(get_config("ton_min_deposit", "0.1"))

        if not receiver or not receiver.startswith(("EQ", "UQ", "kQ", "0Q")):
            logger.warning("ton_wallet_address no configurada o inválida")
            return

        memo = get_or_create_user_memo(user_id)

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
            logger.warning(f"Toncenter error: {data.get('error')}")
            return

        for tx in data.get("result", []):
            in_msg  = tx.get("in_msg", {})
            comment = str(in_msg.get("message", "") or "").strip()
            value_nano = int(in_msg.get("value", "0") or 0)
            tx_hash    = tx.get("transaction_id", {}).get("hash", "")

            # El comment del usuario debe coincidir con su memo
            if memo not in comment:
                continue

            ton_amount = value_nano / 1_000_000_000
            if ton_amount < ton_min * 0.95:   # 5% tolerancia
                continue

            # Verificar que esta tx no fue procesada antes
            with get_cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM ton_deposits WHERE ton_tx_hash = %s", (tx_hash,)
                )
                if cursor.fetchone():
                    continue   # ya procesada

            sender = str(in_msg.get("source", ""))
            credit_deposit(deposit_id, ton_amount, tx_hash, sender)
            return   # solo procesar una tx por polling

    except Exception as e:
        logger.error(f"_scan_and_credit error: {e}")


# ── Auto-inicialización ────────────────────────────────────────────────────────
try:
    init_ton_deposits_table()
except Exception as _e:
    logger.warning(f"ton_deposits init: {_e}")
