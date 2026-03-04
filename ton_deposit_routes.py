"""
ton_deposit_routes.py  –  Rutas Flask para depósitos TON
=========================================================
Endpoints:
  GET  /api/ton/deposit/address        → devuelve wallet + memo + deposit_id
  GET  /api/ton/deposit/status/<id>    → polling (escanea blockchain en cada llamada)
  GET  /api/ton/deposit/history        → historial del usuario
  POST /admin/ton/deposit/approve      → aprobación manual (admin)
  POST /admin/ton/deposit/reject       → rechazo manual (admin)
"""

import os
import logging
from flask import Blueprint, request, jsonify, session
from functools import wraps

from ton_deposits import (
    get_or_create_user_memo,
    create_pending_deposit,
    get_deposit,
    get_user_deposits,
    get_pending_deposits,
    credit_deposit,
    _scan_and_credit,
    _cfg,
)
from database import get_user

logger = logging.getLogger(__name__)

ton_deposit_bp = Blueprint("ton_deposit", __name__)


# ── Decoradores ────────────────────────────────────────────────────────────────

def _get_user_id():
    from flask import request
    return (
        request.args.get("user_id")
        or (request.get_json(silent=True) or {}).get("user_id")
        or request.form.get("user_id")
    )


def require_user(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = _get_user_id()
        if not user_id:
            return jsonify({"success": False, "error": "user_id requerido"}), 400
        user = get_user(user_id)
        if not user:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        return f(user, *args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"success": False, "error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return wrapper


# ── Rutas de usuario ───────────────────────────────────────────────────────────

@ton_deposit_bp.route("/api/ton/deposit/address")
@require_user
def api_ton_deposit_address(user):
    """
    Devuelve la dirección de depósito del bot y el memo único del usuario.
    Crea (o reutiliza) un registro pending en ton_deposits.
    """
    # BUG FIX: usar _cfg() porque get_config() devuelve int, no string
    if _cfg("ton_deposits_enabled", "1") != "1":
        return jsonify({"success": False, "error": "Depósitos TON deshabilitados"}), 503

    ton_wallet = _cfg("ton_wallet_address", "") or os.getenv("TON_WALLET_ADDRESS", "")
    if not ton_wallet or not ton_wallet.startswith(("EQ", "UQ", "kQ", "0Q", "Ef", "Uf")):
        return jsonify({"success": False, "error": "Wallet TON no configurada en admin config"}), 503

    user_id  = str(user["user_id"])
    memo     = get_or_create_user_memo(user_id)
    ton_min  = float(_cfg("ton_min_deposit", "0.1") or "0.1")

    # Reutilizar pending existente si lo hay
    existing = None
    try:
        from db import get_cursor
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT deposit_id FROM ton_deposits
                WHERE user_id=%s AND status='pending'
                ORDER BY created_at DESC LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                existing = row["deposit_id"] if isinstance(row, dict) else row[0]
    except Exception:
        pass

    deposit_id = existing or create_pending_deposit(user_id, memo)

    return jsonify({
        "success":         True,
        "deposit_address": ton_wallet,
        "memo":            memo,
        "deposit_id":      deposit_id,
        "min_deposit":     ton_min,
        "network":         "TON Mainnet",
    })


@ton_deposit_bp.route("/api/ton/deposit/status/<deposit_id>")
@require_user
def api_ton_deposit_status(user, deposit_id):
    """
    Polling: el frontend llama esto cada 8 s.
    En cada llamada se escanea Toncenter buscando el pago del usuario.
    """
    user_id = str(user["user_id"])

    dep = get_deposit(deposit_id)
    if not dep or str(dep.get("user_id", "")) != user_id:
        return jsonify({"status": "not_found"})

    # Si sigue pending → escanear blockchain
    if dep["status"] == "pending":
        _scan_and_credit(user_id, deposit_id)
        dep = get_deposit(deposit_id)   # re-leer tras posible actualización

    return jsonify({
        "success":    True,
        "status":     dep["status"] if dep else "not_found",
        "ton_amount": float(dep.get("ton_amount") or 0) if dep else 0,
    })


@ton_deposit_bp.route("/api/ton/deposit/history")
@require_user
def api_ton_deposit_history(user):
    """Historial de depósitos del usuario."""
    deposits = get_user_deposits(str(user["user_id"]), limit=20)
    result = []
    for d in deposits:
        result.append({
            "deposit_id":  d.get("deposit_id"),
            "ton_amount":  float(d.get("ton_amount") or 0),
            "status":      d.get("status"),
            "tx_hash":     d.get("ton_tx_hash"),
            "created_at":  str(d["created_at"]) if d.get("created_at") else None,
            "credited_at": str(d["credited_at"]) if d.get("credited_at") else None,
        })
    return jsonify({"success": True, "deposits": result})


# ── Rutas de admin ─────────────────────────────────────────────────────────────

@ton_deposit_bp.route("/admin/ton/deposit/approve", methods=["POST"])
@require_admin
def admin_approve_deposit():
    """Aprobar depósito manualmente."""
    data       = request.get_json(silent=True) or request.form
    deposit_id = data.get("deposit_id")
    tx_hash    = data.get("tx_hash", "manual")
    ton_amount = float(data.get("ton_amount", 0))

    if not deposit_id:
        return jsonify({"success": False, "error": "deposit_id requerido"}), 400

    dep = get_deposit(deposit_id)
    if not dep:
        return jsonify({"success": False, "error": "Depósito no encontrado"}), 404

    if dep["status"] == "credited":
        return jsonify({"success": False, "error": "Ya acreditado"}), 400

    amount = ton_amount or float(dep.get("ton_amount") or 0)
    if amount <= 0:
        return jsonify({"success": False, "error": "Monto inválido"}), 400

    ok = credit_deposit(deposit_id, amount, tx_hash, "admin_manual")
    return jsonify({"success": ok})


@ton_deposit_bp.route("/admin/ton/deposit/reject", methods=["POST"])
@require_admin
def admin_reject_deposit():
    """Rechazar depósito."""
    data       = request.get_json(silent=True) or request.form
    deposit_id = data.get("deposit_id")
    note       = data.get("note", "")

    if not deposit_id:
        return jsonify({"success": False, "error": "deposit_id requerido"}), 400

    from db import execute_query
    execute_query(
        "UPDATE ton_deposits SET status='failed', admin_note=%s WHERE deposit_id=%s",
        (note, deposit_id)
    )
    return jsonify({"success": True})


@ton_deposit_bp.route("/admin/ton/deposits")
@require_admin
def admin_ton_deposits():
    """Lista todos los depósitos pendientes para el panel admin."""
    pending = get_pending_deposits()
    return jsonify({"success": True, "deposits": [
        {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in (d.items() if isinstance(d, dict) else {}.items())}
        for d in pending
    ]})


# ── Registro del blueprint ─────────────────────────────────────────────────────

def register_ton_deposit_routes(app):
    app.register_blueprint(ton_deposit_bp)
    logger.info("✅ TON deposit routes registered")
