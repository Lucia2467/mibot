"""
ton_payment_routes.py — Rutas Flask para pagos TON — SALLY-E Bot
Panel admin y API endpoints. Usa tabla estándar 'withdrawals'.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from datetime import datetime

ton_bp = Blueprint('ton_payments', __name__)


# ── Decorador admin ───────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            if request.is_json:
                return jsonify({'success': False, 'error': 'Unauthorized'}), 401
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_ton_withdrawals(status=None, limit=200):
    from db import get_cursor
    with get_cursor() as cursor:
        if status:
            cursor.execute("""
                SELECT w.*, u.username, u.first_name
                FROM withdrawals w
                LEFT JOIN users u ON w.user_id = u.user_id
                WHERE w.currency = 'TON' AND w.status = %s
                ORDER BY w.created_at DESC LIMIT %s
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT w.*, u.username, u.first_name
                FROM withdrawals w
                LEFT JOIN users u ON w.user_id = u.user_id
                WHERE w.currency = 'TON'
                ORDER BY w.created_at DESC LIMIT %s
            """, (limit,))
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        result = []
        for row in rows:
            item = dict(zip(cols, row)) if not isinstance(row, dict) else row
            # Serialise datetimes
            for k, v in item.items():
                if hasattr(v, 'isoformat'):
                    item[k] = v.isoformat()
            result.append(item)
        return result


def _get_ton_stats():
    from db import get_cursor
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN status='pending'    THEN 1 ELSE 0 END) AS pending,
                  SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS processing,
                  SUM(CASE WHEN status='completed'  THEN 1 ELSE 0 END) AS completed,
                  SUM(CASE WHEN status='failed'     THEN 1 ELSE 0 END) AS failed,
                  SUM(CASE WHEN status='completed'  THEN amount ELSE 0 END) AS total_sent
                FROM withdrawals WHERE currency='TON'
            """)
            row = cursor.fetchone()
            if row:
                cols = [d[0] for d in cursor.description]
                d = dict(zip(cols, row)) if not isinstance(row, dict) else row
                return {k: (float(v) if v is not None else 0) for k, v in d.items()}
    except Exception as e:
        pass
    return {'total': 0, 'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0, 'total_sent': 0}


# ── Panel admin ───────────────────────────────────────────────────────────────

@ton_bp.route('/admin/ton-payments')
@admin_required
def admin_ton_payments():
    from ton_payments_system import get_system_wallet_info

    wallet_info = get_system_wallet_info()
    stats       = _get_ton_stats()
    pending     = _get_ton_withdrawals('pending')
    processing  = _get_ton_withdrawals('processing')
    completed   = _get_ton_withdrawals('completed')
    failed      = _get_ton_withdrawals('failed')

    return render_template('admin_ton_payments.html',
        wallet_info=wallet_info,
        stats=stats,
        pending=pending,
        processing=processing,
        completed=completed,
        failed=failed,
    )


# ── API endpoints ─────────────────────────────────────────────────────────────

@ton_bp.route('/api/admin/ton/wallet-info')
@admin_required
def api_wallet_info():
    from ton_payments_system import get_system_wallet_info
    try:
        return jsonify({'success': True, 'wallet': get_system_wallet_info()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@ton_bp.route('/api/admin/ton/process/<withdrawal_id>', methods=['POST'])
@admin_required
def api_process_withdrawal(withdrawal_id):
    """Procesa (envía) un retiro TON manualmente."""
    from ton_payments_system import process_ton_withdrawal_auto
    try:
        success, message = process_ton_withdrawal_auto(withdrawal_id)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@ton_bp.route('/api/admin/ton/reject/<withdrawal_id>', methods=['POST'])
@admin_required
def api_reject_withdrawal(withdrawal_id):
    """Rechaza un retiro TON y devuelve el balance al usuario."""
    from database import get_withdrawal, update_withdrawal, update_balance
    try:
        data   = request.get_json() or {}
        reason = data.get('reason', 'Rechazado por admin')

        w = get_withdrawal(withdrawal_id)
        if not w:
            return jsonify({'success': False, 'error': 'Retiro no encontrado'})
        if w['status'] not in ('pending', 'processing'):
            return jsonify({'success': False, 'error': f"No se puede rechazar en estado: {w['status']}"})

        update_withdrawal(withdrawal_id,
                          status='rejected',
                          error_message=reason,
                          processed_at=datetime.now())
        update_balance(w['user_id'], 'ton', float(w['amount']), 'add',
                       f'TON Retiro rechazado: {w["amount"]} TON — {reason}')
        return jsonify({'success': True, 'message': 'Retiro rechazado y balance devuelto'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@ton_bp.route('/api/admin/ton/process-all', methods=['POST'])
@admin_required
def api_process_all():
    """Procesa todos los retiros TON pendientes."""
    from ton_payments_system import process_ton_withdrawal_auto
    try:
        pending = _get_ton_withdrawals('pending')
        results = {'processed': 0, 'success': 0, 'failed': 0, 'details': []}

        for w in pending:
            results['processed'] += 1
            ok, msg = process_ton_withdrawal_auto(w['withdrawal_id'])
            if ok:
                results['success'] += 1
            else:
                results['failed'] += 1
            results['details'].append({
                'withdrawal_id': w['withdrawal_id'],
                'success': ok,
                'message': msg,
            })

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@ton_bp.route('/api/admin/ton/stats')
@admin_required
def api_stats():
    try:
        return jsonify({'success': True, 'stats': _get_ton_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── Endpoint usuario: validar dirección ───────────────────────────────────────

@ton_bp.route('/api/ton/validate-address', methods=['POST'])
def api_validate_address():
    from ton_payments_system import validate_ton_address
    try:
        data    = request.get_json() or {}
        address = data.get('address', '')
        valid, result = validate_ton_address(address)
        return jsonify({'valid': valid, 'type': result if valid else None,
                        'error': result if not valid else None})
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})


# ── Registro ──────────────────────────────────────────────────────────────────

def register_ton_routes(app):
    app.register_blueprint(ton_bp)
    print("✅ TON Payment routes registradas")
