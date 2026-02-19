"""
ton_payment_routes.py - Flask routes for TON Payment System
Admin panel and API endpoints for SALLY-E / DOGE PIXEL
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from datetime import datetime

# Create blueprint
ton_bp = Blueprint('ton_payments', __name__)

# ============================================
# DECORATORS
# ============================================

def admin_required(f):
    """Decorator for admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            if request.is_json:
                return jsonify({'success': False, 'error': 'Unauthorized'}), 401
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# ADMIN PANEL ROUTES
# ============================================

@ton_bp.route('/admin/ton-payments')
@admin_required
def admin_ton_payments():
    """Main admin TON payments page"""
    from ton_payments_system import (
        get_system_wallet_info, get_all_ton_config, get_ton_payment_stats,
        get_ton_payments_by_status, PaymentStatus
    )
    
    # Get wallet info
    wallet_info = get_system_wallet_info()
    
    # Get configuration
    config = get_all_ton_config()
    
    # Get stats
    stats = get_ton_payment_stats(30)
    
    # Get payments by status
    pending = get_ton_payments_by_status(PaymentStatus.PENDING)
    processing = get_ton_payments_by_status(PaymentStatus.PROCESSING)
    sent = get_ton_payments_by_status(PaymentStatus.SENT)
    confirmed = get_ton_payments_by_status(PaymentStatus.CONFIRMED)
    failed = get_ton_payments_by_status(PaymentStatus.FAILED)
    
    return render_template('admin_ton_payments.html',
        wallet_info=wallet_info,
        config=config,
        stats=stats,
        pending=pending,
        processing=processing,
        sent=sent,
        confirmed=confirmed,
        failed=failed
    )

# ============================================
# API ENDPOINTS
# ============================================

@ton_bp.route('/api/admin/ton/wallet-info')
@admin_required
def api_wallet_info():
    """Get system wallet information"""
    from ton_payments_system import get_system_wallet_info
    
    try:
        wallet_info = get_system_wallet_info()
        return jsonify({
            'success': True,
            'wallet': wallet_info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/config', methods=['GET', 'POST'])
@admin_required
def api_config():
    """Get or set single configuration value"""
    from ton_payments_system import get_ton_config, set_ton_config
    
    if request.method == 'GET':
        from ton_payments_system import get_all_ton_config
        config = get_all_ton_config()
        return jsonify({'success': True, 'config': config})
    
    try:
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')
        
        if not key:
            return jsonify({'success': False, 'error': 'Key is required'})
        
        admin_id = session.get('admin_id', 'unknown')
        success = set_ton_config(key, value, admin_id)
        
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/config/bulk', methods=['POST'])
@admin_required
def api_config_bulk():
    """Set multiple configuration values"""
    from ton_payments_system import set_ton_config
    
    try:
        data = request.get_json()
        admin_id = session.get('admin_id', 'unknown')
        
        for key, value in data.items():
            # Convert string numbers to actual numbers
            if isinstance(value, str):
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass
            
            set_ton_config(key, value, admin_id)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/payments')
@admin_required
def api_get_payments():
    """Get all TON payments with filtering"""
    from ton_payments_system import get_all_ton_payments
    
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        status = request.args.get('status')
        user_id = request.args.get('user_id')
        payment_type = request.args.get('payment_type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        payments, total = get_all_ton_payments(
            limit=limit,
            offset=offset,
            status=status,
            user_id=user_id,
            payment_type=payment_type,
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert datetime objects to strings
        for p in payments:
            for key in ['created_at', 'sent_at', 'confirmed_at', 'approved_at', 'last_retry_at', 'updated_at']:
                if p.get(key) and hasattr(p[key], 'isoformat'):
                    p[key] = p[key].isoformat()
        
        return jsonify({
            'success': True,
            'payments': payments,
            'total': total
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/payment/<payment_id>')
@admin_required
def api_get_payment(payment_id):
    """Get single payment details with logs"""
    from ton_payments_system import get_ton_payment, get_payment_logs
    
    try:
        payment = get_ton_payment(payment_id)
        if not payment:
            return jsonify({'success': False, 'error': 'Payment not found'})
        
        logs = get_payment_logs(payment_id)
        
        # Convert datetime objects
        for key in ['created_at', 'sent_at', 'confirmed_at', 'approved_at', 'last_retry_at', 'updated_at']:
            if payment.get(key) and hasattr(payment[key], 'isoformat'):
                payment[key] = payment[key].isoformat()
        
        for log in logs:
            if log.get('created_at') and hasattr(log['created_at'], 'isoformat'):
                log['created_at'] = log['created_at'].isoformat()
        
        return jsonify({
            'success': True,
            'payment': payment,
            'logs': logs
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/process/<payment_id>', methods=['POST'])
@admin_required
def api_process_payment(payment_id):
    """Process a single TON payment"""
    from ton_payments_system import process_ton_payment
    
    try:
        admin_id = session.get('admin_id', 'unknown')
        success, message = process_ton_payment(payment_id, admin_id)
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/approve/<payment_id>', methods=['POST'])
@admin_required
def api_approve_payment(payment_id):
    """Approve a pending payment"""
    from ton_payments_system import approve_ton_payment
    
    try:
        admin_id = session.get('admin_id', 'unknown')
        success, message = approve_ton_payment(payment_id, admin_id)
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/reject/<payment_id>', methods=['POST'])
@admin_required
def api_reject_payment(payment_id):
    """Reject a payment"""
    from ton_payments_system import reject_ton_payment
    
    try:
        data = request.get_json() or {}
        reason = data.get('reason', '')
        admin_id = session.get('admin_id', 'unknown')
        
        success, message = reject_ton_payment(payment_id, admin_id, reason)
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/retry/<payment_id>', methods=['POST'])
@admin_required
def api_retry_payment(payment_id):
    """Retry a failed payment"""
    from ton_payments_system import retry_ton_payment
    
    try:
        admin_id = session.get('admin_id', 'unknown')
        success, message = retry_ton_payment(payment_id, admin_id)
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/cancel/<payment_id>', methods=['POST'])
@admin_required
def api_cancel_payment(payment_id):
    """Cancel a payment"""
    from ton_payments_system import cancel_ton_payment
    
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'Cancelled by admin')
        admin_id = session.get('admin_id', 'unknown')
        
        success, message = cancel_ton_payment(payment_id, admin_id, reason)
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/process-all', methods=['POST'])
@admin_required
def api_process_all_pending():
    """Process all pending TON payments"""
    from ton_payments_system import get_ton_payments_by_status, process_ton_payment, PaymentStatus
    
    try:
        admin_id = session.get('admin_id', 'unknown')
        pending = get_ton_payments_by_status(PaymentStatus.PENDING)
        
        results = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'details': []
        }
        
        for payment in pending:
            results['processed'] += 1
            success, message = process_ton_payment(payment['payment_id'], admin_id)
            
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append({
                'payment_id': payment['payment_id'],
                'success': success,
                'message': message
            })
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/admin/ton/stats')
@admin_required
def api_get_stats():
    """Get TON payment statistics"""
    from ton_payments_system import get_ton_payment_stats
    
    try:
        days = request.args.get('days', 30, type=int)
        stats = get_ton_payment_stats(days)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# USER API ENDPOINTS
# ============================================

@ton_bp.route('/api/ton/validate-address', methods=['POST'])
def api_validate_address():
    """Validate a TON address"""
    from ton_payments_system import validate_ton_address
    
    try:
        data = request.get_json()
        address = data.get('address', '')
        
        is_valid, result = validate_ton_address(address)
        
        return jsonify({
            'valid': is_valid,
            'type': result if is_valid else None,
            'error': result if not is_valid else None
        })
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})

@ton_bp.route('/api/ton/withdraw', methods=['POST'])
def api_ton_withdraw():
    """Create a TON withdrawal request"""
    from ton_payments_system import (
        validate_ton_address, create_ton_payment, get_ton_config, 
        process_ton_payment
    )
    from database import get_user, update_balance
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = float(data.get('amount', 0))
        to_address = data.get('address', '')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'})
        
        # Validate address
        is_valid, error = validate_ton_address(to_address)
        if not is_valid:
            return jsonify({'success': False, 'error': f'Invalid address: {error}'})
        
        # Get user
        user = get_user(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'})
        
        if user.get('banned'):
            return jsonify({'success': False, 'error': 'Account is banned'})
        
        if user.get('withdrawal_blocked'):
            return jsonify({'success': False, 'error': user.get('withdrawal_block_reason', 'Withdrawals blocked')})
        
        # Check minimum
        min_withdrawal = get_ton_config('ton_min_withdrawal', 0.1)
        if amount < min_withdrawal:
            return jsonify({'success': False, 'error': f'Minimum withdrawal: {min_withdrawal} TON'})
        
        # Check maximum
        max_withdrawal = get_ton_config('ton_max_withdrawal', 100)
        if amount > max_withdrawal:
            return jsonify({'success': False, 'error': f'Maximum withdrawal: {max_withdrawal} TON'})
        
        # Check balance
        ton_balance = float(user.get('ton_balance', 0))
        if amount > ton_balance:
            return jsonify({'success': False, 'error': f'Insufficient balance. Have: {ton_balance:.4f} TON'})
        
        # Check maintenance mode
        if get_ton_config('ton_maintenance_mode', False):
            return jsonify({'success': False, 'error': 'TON withdrawals are temporarily disabled'})
        
        # Deduct balance first
        update_balance(user_id, 'ton', amount, 'subtract', f'TON Withdrawal: {amount} TON to {to_address[:10]}...')
        
        # Create payment
        auto_pay = get_ton_config('ton_auto_pay_enabled', False)
        payment_type = 'automatic' if auto_pay else 'manual'
        
        success, result = create_ton_payment(
            user_id=user_id,
            amount=amount,
            to_address=to_address,
            payment_type=payment_type,
            memo=f"DOGE PIXEL Withdrawal"
        )
        
        if not success:
            # Refund on failure
            update_balance(user_id, 'ton', amount, 'add', f'TON Withdrawal refund: {amount} TON')
            return jsonify({'success': False, 'error': result})
        
        payment_id = result
        
        # Auto-process if enabled
        if auto_pay:
            process_success, message = process_ton_payment(payment_id)
            if process_success:
                return jsonify({
                    'success': True,
                    'payment_id': payment_id,
                    'status': 'processing',
                    'message': 'Payment is being processed automatically'
                })
        
        return jsonify({
            'success': True,
            'payment_id': payment_id,
            'status': 'pending',
            'message': 'Withdrawal request submitted'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/ton/link-wallet', methods=['POST'])
def api_link_ton_wallet():
    """Link a TON wallet address to user account"""
    from ton_payments_system import validate_ton_address
    from database import get_user, update_user
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        address = data.get('address', '').strip()
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'})
        
        # Validate address
        is_valid, error = validate_ton_address(address)
        if not is_valid:
            return jsonify({'success': False, 'error': f'Invalid address: {error}'})
        
        # Get user
        user = get_user(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'})
        
        # Update user
        update_user(user_id, ton_wallet_address=address, ton_wallet_linked_at=datetime.now())
        
        return jsonify({
            'success': True,
            'message': 'TON wallet linked successfully',
            'address': address
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/ton/history/<user_id>')
def api_ton_history(user_id):
    """Get user's TON payment history"""
    from ton_payments_system import get_user_ton_payments
    
    try:
        limit = request.args.get('limit', 20, type=int)
        payments = get_user_ton_payments(user_id, limit)
        
        # Convert datetime objects
        for p in payments:
            for key in ['created_at', 'sent_at', 'confirmed_at']:
                if p.get(key) and hasattr(p[key], 'isoformat'):
                    p[key] = p[key].isoformat()
        
        return jsonify({
            'success': True,
            'payments': payments
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@ton_bp.route('/api/ton/status/<payment_id>')
def api_payment_status(payment_id):
    """Get payment status"""
    from ton_payments_system import get_ton_payment, get_tonscan_link
    
    try:
        payment = get_ton_payment(payment_id)
        if not payment:
            return jsonify({'success': False, 'error': 'Payment not found'})
        
        result = {
            'success': True,
            'status': payment['status'],
            'amount': float(payment['amount']),
            'net_amount': float(payment['net_amount']),
            'to_address': payment['to_address']
        }
        
        if payment.get('tx_hash'):
            result['tx_hash'] = payment['tx_hash']
            result['tonscan_url'] = get_tonscan_link(payment['tx_hash'], is_tx=True)
        
        if payment.get('error_message'):
            result['error'] = payment['error_message']
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# HELPER FUNCTION TO REGISTER BLUEPRINT
# ============================================

def register_ton_routes(app):
    """Register TON payment routes with the Flask app"""
    app.register_blueprint(ton_bp)
    print("✅ TON Payment routes registered")
