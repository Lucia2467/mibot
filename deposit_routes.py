"""
deposit_routes.py - Rutas API para el sistema de depósitos DOGE BEP20
"""

from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)

# Crear blueprint
deposit_bp = Blueprint('deposits', __name__)

# Importar sistema de depósitos
try:
    from deposit_system import (
        generate_user_deposit_address,
        get_user_deposit_address,
        get_user_deposits,
        get_deposit,
        get_user_deposit_stats,
        format_deposit_for_display,
        scan_all_deposit_addresses,
        update_pending_deposits,
        get_deposit_config,
        get_pending_deposits
    )
    from database import get_user
    DEPOSIT_SYSTEM_AVAILABLE = True
    logger.info("✅ Deposit system loaded for routes")
except ImportError as e:
    DEPOSIT_SYSTEM_AVAILABLE = False
    logger.warning(f"⚠️ Deposit system not available: {e}")


def register_deposit_routes(app):
    """Registra las rutas de depósito en la aplicación Flask"""
    
    @app.route('/api/deposit/address', methods=['GET', 'POST'])
    def api_get_deposit_address():
        """
        Obtiene o genera la dirección de depósito única del usuario
        GET/POST ?user_id=xxx
        """
        if not DEPOSIT_SYSTEM_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Deposit system not available'
            }), 503
        
        # Obtener user_id
        user_id = request.args.get('user_id') or (request.json.get('user_id') if request.is_json else None)
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID required'
            }), 400
        
        # Verificar que el usuario existe
        user = get_user(user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Verificar si los depósitos están habilitados
        deposits_enabled = get_deposit_config('deposits_enabled', 'true').lower() == 'true'
        if not deposits_enabled:
            return jsonify({
                'success': False,
                'error': 'Deposits are currently disabled'
            }), 503
        
        # Generar o recuperar información de depósito
        deposit_info = generate_user_deposit_address(user_id)
        
        if not deposit_info:
            return jsonify({
                'success': False,
                'error': 'Failed to generate deposit address'
            }), 500
        
        # Obtener configuración
        min_deposit = float(get_deposit_config('min_deposit_doge', '1'))
        required_confirmations = int(get_deposit_config('required_confirmations', '12'))
        
        return jsonify({
            'success': True,
            'data': {
                'address': deposit_info['address'],
                'currency': 'DOGE',
                'network': 'BEP20',
                'network_name': 'Binance Smart Chain (BSC)',
                'min_deposit': min_deposit,
                'required_confirmations': required_confirmations,
                'is_new': deposit_info.get('is_new', False),
                'warning': 'Only send DOGE (BEP20) to this address. Other tokens will be lost.',
                'contract': '0xba2ae424d960c26247dd6c32edc70b295c744c43'
            }
        })
    
    
    @app.route('/api/deposit/history', methods=['GET'])
    def api_get_deposit_history():
        """
        Obtiene el historial de depósitos del usuario
        GET ?user_id=xxx&limit=20
        """
        if not DEPOSIT_SYSTEM_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Deposit system not available'
            }), 503
        
        user_id = request.args.get('user_id')
        limit = min(int(request.args.get('limit', 20)), 100)
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID required'
            }), 400
        
        deposits = get_user_deposits(user_id, limit)
        formatted_deposits = [format_deposit_for_display(d) for d in deposits]
        
        return jsonify({
            'success': True,
            'data': {
                'deposits': formatted_deposits,
                'count': len(formatted_deposits)
            }
        })
    
    
    @app.route('/api/deposit/status/<deposit_id>', methods=['GET'])
    def api_get_deposit_status(deposit_id):
        """
        Obtiene el estado de un depósito específico
        GET /api/deposit/status/{deposit_id}
        """
        if not DEPOSIT_SYSTEM_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Deposit system not available'
            }), 503
        
        deposit = get_deposit(deposit_id)
        
        if not deposit:
            return jsonify({
                'success': False,
                'error': 'Deposit not found'
            }), 404
        
        formatted = format_deposit_for_display(deposit)
        
        return jsonify({
            'success': True,
            'data': formatted
        })
    
    
    @app.route('/api/deposit/stats', methods=['GET'])
    def api_get_deposit_stats():
        """
        Obtiene estadísticas de depósitos del usuario
        GET ?user_id=xxx
        """
        if not DEPOSIT_SYSTEM_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Deposit system not available'
            }), 503
        
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID required'
            }), 400
        
        stats = get_user_deposit_stats(user_id)
        
        return jsonify({
            'success': True,
            'data': stats
        })
    
    
    @app.route('/api/deposit/check', methods=['POST'])
    def api_check_deposits():
        """
        Fuerza una verificación de depósitos para un usuario específico
        POST { user_id: xxx }
        
        Nota: Este endpoint también es llamado automáticamente por un job periódico
        """
        if not DEPOSIT_SYSTEM_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Deposit system not available'
            }), 503
        
        # Ejecutar escaneo
        try:
            processed = scan_all_deposit_addresses()
            credited = update_pending_deposits()
            
            return jsonify({
                'success': True,
                'data': {
                    'new_deposits_found': processed,
                    'deposits_credited': credited
                }
            })
        except Exception as e:
            logger.error(f"Error checking deposits: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    
    @app.route('/api/deposit/refresh', methods=['POST'])
    def api_refresh_deposits():
        """
        Refresca los depósitos pendientes y verifica nuevos depósitos
        POST { user_id: xxx }
        """
        if not DEPOSIT_SYSTEM_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Deposit system not available'
            }), 503
        
        user_id = request.json.get('user_id') if request.is_json else request.args.get('user_id')
        
        try:
            # Escanear direcciones
            scan_all_deposit_addresses()
            update_pending_deposits()
            
            # Obtener datos actualizados del usuario
            if user_id:
                deposits = get_user_deposits(user_id, 10)
                stats = get_user_deposit_stats(user_id)
                
                return jsonify({
                    'success': True,
                    'data': {
                        'deposits': [format_deposit_for_display(d) for d in deposits],
                        'stats': stats
                    }
                })
            
            return jsonify({'success': True})
            
        except Exception as e:
            logger.error(f"Error refreshing deposits: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    
    # ============================================
    # RUTAS DE ADMIN
    # ============================================
    
    @app.route('/api/admin/deposits/pending', methods=['GET'])
    def api_admin_pending_deposits():
        """Obtiene todos los depósitos pendientes (admin)"""
        if not DEPOSIT_SYSTEM_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Deposit system not available'
            }), 503
        
        # Aquí deberías agregar verificación de admin
        # Por ahora solo retornamos los datos
        
        pending = get_pending_deposits()
        formatted = [format_deposit_for_display(d) for d in pending]
        
        return jsonify({
            'success': True,
            'data': {
                'deposits': formatted,
                'count': len(formatted)
            }
        })
    
    
    @app.route('/api/admin/deposits/scan', methods=['POST'])
    def api_admin_scan_deposits():
        """Fuerza un escaneo completo de depósitos (admin)"""
        if not DEPOSIT_SYSTEM_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Deposit system not available'
            }), 503
        
        try:
            processed = scan_all_deposit_addresses()
            credited = update_pending_deposits()
            
            return jsonify({
                'success': True,
                'message': f'Scan complete. Found {processed} new deposits, credited {credited}.'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    
    logger.info("✅ Deposit routes registered")
    return True
