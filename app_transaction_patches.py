"""
app_transaction_patches.py - Parches para integrar el sistema de transacciones
SALLY-E / DOGE PIXEL

Este archivo contiene el código que debe integrarse en app.py para:
1. Usar el nuevo sistema unificado de transacciones
2. Enviar notificaciones de retiros a Telegram
3. Soportar todas las monedas (DOGE, TON, USDT, SE)

INSTRUCCIONES DE INTEGRACIÓN:
=============================

1. Agregar imports al inicio de app.py:
   from transactions_system import get_user_unified_transactions, format_transaction_for_api, CURRENCIES, get_translations
   from withdrawal_notifications import on_withdrawal_created, on_withdrawal_completed, on_withdrawal_rejected

2. Reemplazar la función api_transactions() con new_api_transactions()

3. Agregar llamadas a notificaciones en los lugares indicados
"""

# ============== NUEVO ENDPOINT DE TRANSACCIONES ==============

def new_api_transactions():
    """
    Nuevo endpoint unificado de transacciones
    Soporta: DOGE, TON, USDT, SE
    Incluye: balance_history, withdrawals, ton_payments
    
    Reemplaza: @app.route('/api/transactions')
    """
    from flask import request, jsonify
    from transactions_system import get_user_unified_transactions, format_transaction_for_api, CURRENCIES
    
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    # Parámetros opcionales
    currency = request.args.get('currency')  # DOGE, TON, USDT, SE o None
    tx_type = request.args.get('type')  # withdrawal, mining, referral, etc.
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    lang = request.args.get('lang', 'en')  # Idioma para traducciones
    
    try:
        # Obtener transacciones unificadas
        transactions = get_user_unified_transactions(
            user_id=user_id,
            currency=currency.upper() if currency else None,
            tx_type=tx_type,
            limit=limit,
            offset=offset
        )
        
        # Formatear para API
        formatted = [format_transaction_for_api(tx, lang) for tx in transactions]
        
        # Calcular estadísticas
        stats = {
            'total_received': 0,
            'total_sent': 0,
            'by_currency': {}
        }
        
        for tx in transactions:
            currency_code = tx.get('currency', 'SE')
            amount = float(tx.get('amount', 0))
            
            if currency_code not in stats['by_currency']:
                stats['by_currency'][currency_code] = {'received': 0, 'sent': 0}
            
            if tx.get('tx_type') == 'withdrawal':
                stats['total_sent'] += amount
                stats['by_currency'][currency_code]['sent'] += amount
            else:
                stats['total_received'] += amount
                stats['by_currency'][currency_code]['received'] += amount
        
        return jsonify({
            'success': True,
            'transactions': formatted,
            'count': len(formatted),
            'stats': stats,
            'currencies': list(CURRENCIES.keys())
        })
        
    except Exception as e:
        import logging
        logging.error(f"[api_transactions_unified] Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Error al obtener transacciones',
            'transactions': []
        }), 500


# ============== INTEGRACIÓN DE NOTIFICACIONES ==============

"""
INSTRUCCIONES PARA NOTIFICACIONES:

1. Al CREAR un retiro (después de insertar en la base de datos):
   
   from withdrawal_notifications import on_withdrawal_created
   
   # Después de crear el retiro en la base de datos
   on_withdrawal_created(
       withdrawal_id=withdrawal_id,
       user_id=user_id,
       currency=currency,  # 'DOGE', 'TON', 'USDT'
       amount=amount,
       wallet_address=wallet_address
   )

2. Al APROBAR un retiro (después de procesar el pago):
   
   from withdrawal_notifications import on_withdrawal_completed
   
   # Después de aprobar y obtener el tx_hash
   on_withdrawal_completed(
       withdrawal_id=withdrawal_id,
       user_id=user_id,
       currency=currency,
       amount=amount,
       wallet_address=wallet_address,
       tx_hash=tx_hash
   )

3. Al RECHAZAR un retiro:
   
   from withdrawal_notifications import on_withdrawal_rejected
   
   # Después de rechazar el retiro
   on_withdrawal_rejected(
       withdrawal_id=withdrawal_id,
       user_id=user_id,
       currency=currency,
       amount=amount,
       reason=reason  # Opcional
   )
"""


# ============== EJEMPLO DE INTEGRACIÓN EN RUTA DE RETIRO ==============

def example_withdrawal_creation():
    """
    Ejemplo de cómo integrar notificaciones en la creación de retiros
    NO usar directamente - es solo referencia
    """
    from flask import request, jsonify
    from withdrawal_notifications import on_withdrawal_created
    
    user_id = request.args.get('user_id')
    currency = request.form.get('currency', 'DOGE')
    amount = float(request.form.get('amount', 0))
    wallet_address = request.form.get('wallet_address', '')
    
    # ... validaciones ...
    
    # Crear retiro en base de datos
    # withdrawal_id = create_withdrawal(user_id, currency, amount, wallet_address)
    
    # NUEVO: Enviar notificación a canal de Telegram
    # on_withdrawal_created(withdrawal_id, user_id, currency, amount, wallet_address)
    
    pass


# ============== FUNCIONES HELPER ==============

def notify_new_withdrawal(withdrawal_id, user_id, currency, amount, wallet_address):
    """
    Helper para notificar nuevo retiro
    Llamar después de crear retiro en la base de datos
    """
    try:
        from withdrawal_notifications import on_withdrawal_created
        on_withdrawal_created(
            withdrawal_id=withdrawal_id,
            user_id=user_id,
            currency=currency,
            amount=amount,
            wallet_address=wallet_address
        )
    except Exception as e:
        import logging
        logging.error(f"[notify_new_withdrawal] Error sending notification: {e}")


def notify_completed_withdrawal(withdrawal_id, user_id, currency, amount, wallet_address, tx_hash):
    """
    Helper para notificar retiro completado
    Llamar después de aprobar el retiro
    """
    try:
        from withdrawal_notifications import on_withdrawal_completed
        on_withdrawal_completed(
            withdrawal_id=withdrawal_id,
            user_id=user_id,
            currency=currency,
            amount=amount,
            wallet_address=wallet_address,
            tx_hash=tx_hash
        )
    except Exception as e:
        import logging
        logging.error(f"[notify_completed_withdrawal] Error sending notification: {e}")


def notify_rejected_withdrawal(withdrawal_id, user_id, currency, amount, reason=''):
    """
    Helper para notificar retiro rechazado
    Llamar después de rechazar el retiro
    """
    try:
        from withdrawal_notifications import on_withdrawal_rejected
        on_withdrawal_rejected(
            withdrawal_id=withdrawal_id,
            user_id=user_id,
            currency=currency,
            amount=amount,
            reason=reason
        )
    except Exception as e:
        import logging
        logging.error(f"[notify_rejected_withdrawal] Error sending notification: {e}")


# ============== CÓDIGO PARA COPIAR A app.py ==============

PATCH_IMPORTS = """
# === TRANSACTIONS SYSTEM IMPORTS ===
from transactions_system import get_user_unified_transactions, format_transaction_for_api, CURRENCIES, get_translations
from withdrawal_notifications import on_withdrawal_created, on_withdrawal_completed, on_withdrawal_rejected
"""

PATCH_API_TRANSACTIONS = """
@app.route('/api/transactions')
def api_transactions():
    \"\"\"Get unified user transactions history - supports all currencies\"\"\"
    user_id = request.args.get('user_id') or get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400
    
    # Parámetros opcionales
    currency = request.args.get('currency')
    tx_type = request.args.get('type')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    lang = request.args.get('lang', 'en')
    
    try:
        # Obtener transacciones unificadas
        transactions = get_user_unified_transactions(
            user_id=user_id,
            currency=currency.upper() if currency else None,
            tx_type=tx_type,
            limit=limit,
            offset=offset
        )
        
        # Formatear para API
        formatted = [format_transaction_for_api(tx, lang) for tx in transactions]
        
        # Calcular estadísticas
        stats = {
            'total_received': 0,
            'total_sent': 0,
            'by_currency': {}
        }
        
        for tx in transactions:
            curr = tx.get('currency', 'SE')
            amount = float(tx.get('amount', 0))
            
            if curr not in stats['by_currency']:
                stats['by_currency'][curr] = {'received': 0, 'sent': 0}
            
            if tx.get('tx_type') == 'withdrawal':
                stats['total_sent'] += amount
                stats['by_currency'][curr]['sent'] += amount
            else:
                stats['total_received'] += amount
                stats['by_currency'][curr]['received'] += amount
        
        return jsonify({
            'success': True,
            'transactions': formatted,
            'count': len(formatted),
            'stats': stats,
            'currencies': list(CURRENCIES.keys())
        })
        
    except Exception as e:
        logger.error(f"[api_transactions] Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Error al obtener transacciones',
            'transactions': []
        }), 500
"""

if __name__ == "__main__":
    print("=" * 60)
    print("PARCHES PARA app.py")
    print("=" * 60)
    print("\n1. Agregar estos imports al inicio de app.py:")
    print(PATCH_IMPORTS)
    print("\n2. Reemplazar la función api_transactions() con:")
    print(PATCH_API_TRANSACTIONS)
    print("\n3. Agregar notificaciones en las rutas de retiros")
    print("=" * 60)
