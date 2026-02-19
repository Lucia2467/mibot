"""
mining_machine_routes.py - Rutas Flask para el sistema de máquinas de minería
"""

import logging
from flask import request, jsonify, render_template
from decimal import Decimal

logger = logging.getLogger(__name__)

def register_mining_machine_routes(app, get_user, update_user, get_user_id, 
                                    check_channel_or_redirect, safe_user_dict,
                                    calculate_unclaimed, get_effective_rate, execute_query):
    """Registra todas las rutas del sistema de máquinas de minería"""
    
    # Import mining machine system
    try:
        from mining_machine_system import (
            get_machine_status, can_purchase_machine, purchase_machine,
            claim_machine_earnings, get_machine_config, get_user_machine_history
        )
        MINING_MACHINE_AVAILABLE = True
        logger.info("✅ Mining machine system loaded")
    except ImportError as e:
        MINING_MACHINE_AVAILABLE = False
        logger.warning(f"⚠️ Mining machine system not available: {e}")
        return
    
    # ============================================
    # API ROUTES
    # ============================================
    
    @app.route('/api/mining-machine/status', methods=['GET'])
    def api_mining_machine_status():
        """Obtiene el estado de la máquina de minería del usuario"""
        try:
            user_id = request.args.get('user_id')
            if not user_id:
                return jsonify({'success': False, 'error': 'User ID required'}), 400
            
            user = get_user(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            status = get_machine_status(user_id)
            status['doge_balance'] = float(user.get('doge_balance', 0))
            status['success'] = True
            
            return jsonify(status)
        
        except Exception as e:
            logger.error(f"Error getting machine status: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    @app.route('/api/mining-machine/purchase', methods=['POST'])
    def api_mining_machine_purchase():
        """Compra una máquina de minería"""
        try:
            data = request.get_json() or {}
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'success': False, 'error': 'User ID required'}), 400
            
            user = get_user(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Verificar si está baneado
            if user.get('banned'):
                return jsonify({'success': False, 'error': 'User is banned'}), 403
            
            doge_balance = Decimal(str(user.get('doge_balance', 0)))
            
            # Verificar si puede comprar
            can_buy, reason, message = can_purchase_machine(user_id, doge_balance)
            
            if not can_buy:
                return jsonify({
                    'success': False,
                    'error': reason,
                    'message': message
                }), 400
            
            # Obtener configuración de la máquina
            config = get_machine_config()
            price = Decimal(str(config['price']))
            
            # Deducir balance PRIMERO (atómico con la compra)
            new_balance = doge_balance - price
            
            # Actualizar balance del usuario
            update_user(user_id, doge_balance=float(new_balance))
            
            # Registrar en historial de balance
            try:
                execute_query("""
                    INSERT INTO balance_history 
                    (user_id, action, currency, amount, balance_before, balance_after, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(user_id),
                    'machine_purchase',
                    'DOGE',
                    str(-price),
                    str(doge_balance),
                    str(new_balance),
                    f'Compra de máquina de minería DOGE Miner Pro'
                ))
            except Exception as hist_error:
                logger.warning(f"Could not record balance history: {hist_error}")
            
            # Procesar la compra
            result = purchase_machine(user_id)
            
            if result.get('success'):
                result['new_doge_balance'] = float(new_balance)
                result['message'] = '¡Máquina de minería comprada exitosamente!'
                
                logger.info(f"✅ User {user_id} purchased mining machine for {price} DOGE")
                return jsonify(result)
            else:
                # Si falla la compra, revertir el balance
                update_user(user_id, doge_balance=float(doge_balance))
                return jsonify(result), 500
        
        except Exception as e:
            logger.error(f"Error purchasing machine: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    @app.route('/api/mining-machine/claim', methods=['POST'])
    def api_mining_machine_claim():
        """Reclama las ganancias de la máquina de minería"""
        try:
            data = request.get_json() or {}
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'success': False, 'error': 'User ID required'}), 400
            
            user = get_user(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Verificar si está baneado
            if user.get('banned'):
                return jsonify({'success': False, 'error': 'User is banned'}), 403
            
            # Reclamar ganancias
            result = claim_machine_earnings(user_id)
            
            if result.get('success'):
                amount = Decimal(str(result.get('amount', 0)))
                old_balance = Decimal(str(user.get('doge_balance', 0)))
                new_balance = old_balance + amount
                
                # Actualizar balance
                update_user(user_id, doge_balance=float(new_balance))
                
                # Registrar en historial
                try:
                    execute_query("""
                        INSERT INTO balance_history 
                        (user_id, action, currency, amount, balance_before, balance_after, description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(user_id),
                        'machine_claim',
                        'DOGE',
                        str(amount),
                        str(old_balance),
                        str(new_balance),
                        f'Ganancias de máquina de minería'
                    ))
                except Exception as hist_error:
                    logger.warning(f"Could not record balance history: {hist_error}")
                
                result['new_doge_balance'] = float(new_balance)
                
                logger.info(f"✅ User {user_id} claimed {amount} DOGE from mining machine")
                return jsonify(result)
            else:
                return jsonify(result), 400
        
        except Exception as e:
            logger.error(f"Error claiming machine earnings: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    @app.route('/api/mining-machine/config', methods=['GET'])
    def api_mining_machine_config():
        """Obtiene la configuración de las máquinas de minería"""
        try:
            config = get_machine_config()
            return jsonify({
                'success': True,
                'config': config
            })
        except Exception as e:
            logger.error(f"Error getting machine config: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    @app.route('/api/mining-machine/history', methods=['GET'])
    def api_mining_machine_history():
        """Obtiene el historial de máquinas del usuario"""
        try:
            user_id = request.args.get('user_id')
            if not user_id:
                return jsonify({'success': False, 'error': 'User ID required'}), 400
            
            history = get_user_machine_history(user_id, limit=10)
            
            return jsonify({
                'success': True,
                'history': history
            })
        
        except Exception as e:
            logger.error(f"Error getting machine history: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    logger.info("✅ Mining machine routes registered successfully")
