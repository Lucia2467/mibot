"""
ton_deposit_routes.py - Rutas API para depósitos TON
Se registra en app.py
"""

from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

# Blueprint para rutas de depósito
ton_deposit_bp = Blueprint('ton_deposit', __name__)

# ============================================
# API ENDPOINTS
# ============================================

@ton_deposit_bp.route('/api/ton/deposit/config', methods=['GET'])
def get_deposit_config_endpoint():
    """Obtiene configuración de depósitos"""
    try:
        from ton_deposit_system import get_deposit_config
        config = get_deposit_config()
        return jsonify({
            'success': True,
            **config
        })
    except Exception as e:
        logger.error(f"Error en config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ton_deposit_bp.route('/api/ton/deposit/create', methods=['POST'])
def create_deposit_endpoint():
    """
    Crea una intención de depósito.
    
    Body JSON:
    {
        "user_id": "123456",
        "amount": 1.5,
        "wallet_origin": "EQ..."
    }
    """
    try:
        from ton_deposit_system import create_deposit_intent
        
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Datos requeridos'}), 400
        
        user_id = data.get('user_id') or request.args.get('user_id')
        amount = data.get('amount')
        wallet_origin = data.get('wallet_origin')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id requerido'}), 400
        
        if not amount:
            return jsonify({'success': False, 'error': 'amount requerido'}), 400
        
        if not wallet_origin:
            return jsonify({'success': False, 'error': 'wallet_origin requerido'}), 400
        
        result = create_deposit_intent(user_id, amount, wallet_origin)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error creando depósito: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ton_deposit_bp.route('/api/ton/deposit/confirm', methods=['POST'])
def confirm_deposit_endpoint():
    """
    Confirma un depósito con hash de transacción.
    Verifica en blockchain antes de acreditar.
    
    Body JSON:
    {
        "deposit_id": "abc123...",
        "tx_hash": "xyz789...",
        "user_id": "123456"  (opcional, para verificación)
    }
    """
    try:
        from ton_deposit_system import confirm_deposit
        
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Datos requeridos'}), 400
        
        deposit_id = data.get('deposit_id')
        tx_hash = data.get('tx_hash')
        user_id = data.get('user_id') or request.args.get('user_id')
        
        if not deposit_id:
            return jsonify({'success': False, 'error': 'deposit_id requerido'}), 400
        
        if not tx_hash:
            return jsonify({'success': False, 'error': 'tx_hash requerido'}), 400
        
        result = confirm_deposit(deposit_id, tx_hash, user_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error confirmando depósito: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ton_deposit_bp.route('/api/ton/deposit/status/<deposit_id>', methods=['GET'])
def get_deposit_status_endpoint(deposit_id):
    """Obtiene estado de un depósito"""
    try:
        from ton_deposit_system import get_deposit
        
        user_id = request.args.get('user_id')
        deposit = get_deposit(deposit_id)
        
        if not deposit:
            return jsonify({'success': False, 'error': 'Depósito no encontrado'}), 404
        
        # Verificar pertenencia si se proporciona user_id
        if user_id and str(deposit['user_id']) != str(user_id):
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        return jsonify({
            'success': True,
            'deposit': {
                'deposit_id': deposit['deposit_id'],
                'amount': float(deposit['amount']),
                'status': deposit['status'],
                'wallet_destination': deposit['wallet_destination'],
                'tx_hash': deposit.get('tx_hash'),
                'created_at': str(deposit['created_at']) if deposit.get('created_at') else None,
                'credited_at': str(deposit['credited_at']) if deposit.get('credited_at') else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estado: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ton_deposit_bp.route('/api/ton/deposit/history', methods=['GET'])
def get_deposit_history_endpoint():
    """Obtiene historial de depósitos del usuario"""
    try:
        from ton_deposit_system import get_user_deposits
        
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id requerido'}), 400
        
        status = request.args.get('status')  # opcional: pending, confirmed, failed
        limit = int(request.args.get('limit', 20))
        
        deposits = get_user_deposits(user_id, status=status, limit=limit)
        
        # Formatear para respuesta
        formatted = []
        for d in deposits:
            formatted.append({
                'deposit_id': d['deposit_id'],
                'amount': float(d['amount']),
                'status': d['status'],
                'tx_hash': d.get('tx_hash'),
                'created_at': str(d['created_at']) if d.get('created_at') else None,
                'credited_at': str(d['credited_at']) if d.get('credited_at') else None
            })
        
        return jsonify({
            'success': True,
            'deposits': formatted,
            'count': len(formatted)
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ton_deposit_bp.route('/api/ton/deposit/cancel', methods=['POST'])
def cancel_deposit_endpoint():
    """Cancela un depósito pendiente"""
    try:
        from ton_deposit_system import cancel_deposit
        
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Datos requeridos'}), 400
        
        deposit_id = data.get('deposit_id')
        user_id = data.get('user_id') or request.args.get('user_id')
        
        if not deposit_id:
            return jsonify({'success': False, 'error': 'deposit_id requerido'}), 400
        
        result = cancel_deposit(deposit_id, user_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error cancelando depósito: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@ton_deposit_bp.route('/api/ton/deposit/stats', methods=['GET'])
def get_deposit_stats_endpoint():
    """Obtiene estadísticas de depósitos"""
    try:
        from ton_deposit_system import get_deposit_stats
        
        user_id = request.args.get('user_id')
        
        stats = get_deposit_stats(user_id)
        
        return jsonify({
            'success': True,
            **stats
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def register_deposit_routes(app):
    """Registra las rutas de depósito en la aplicación Flask"""
    app.register_blueprint(ton_deposit_bp)
    logger.info("✅ Rutas de depósito TON registradas")
