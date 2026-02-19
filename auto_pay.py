"""
auto_pay.py - Procesador automático de pagos para SALLY-E Bot
Procesa retiros automáticamente usando payments.py para BEP20 y ton_payments.py para TON
"""

from datetime import datetime
from database import (
    get_withdrawal, update_withdrawal, update_balance,
    get_pending_withdrawals, get_config
)

# Try to import payments modules
try:
    from payments import send_crypto, validate_address as validate_bep20, get_wallet_info as get_bep20_wallet_info
    BEP20_PAYMENTS_AVAILABLE = True
except ImportError:
    BEP20_PAYMENTS_AVAILABLE = False
    print("Warning: payments.py not available - BEP20 auto_pay will use manual mode")

try:
    from ton_payments import send_ton, validate_address as validate_ton, get_wallet_info as get_ton_wallet_info, is_ton_configured
    TON_PAYMENTS_AVAILABLE = True
except ImportError:
    TON_PAYMENTS_AVAILABLE = False
    print("Warning: ton_payments.py not available - TON auto_pay will use manual mode")

def process_withdrawal(withdrawal_id):
    """
    Procesa un retiro individual
    
    Returns:
        tuple: (success: bool, message: str)
    """
    withdrawal = get_withdrawal(withdrawal_id)
    
    if not withdrawal:
        return False, "Retiro no encontrado"
    
    if withdrawal['status'] != 'pending':
        return False, f"Estado inválido: {withdrawal['status']}"
    
    currency = withdrawal['currency'].upper()
    
    # Determinar qué sistema de pago usar
    if currency == 'TON':
        return process_ton_withdrawal(withdrawal)
    else:
        return process_bep20_withdrawal(withdrawal)

def process_bep20_withdrawal(withdrawal):
    """Procesa un retiro BEP20 (USDT/DOGE)"""
    if not BEP20_PAYMENTS_AVAILABLE:
        return False, "Sistema de pagos BEP20 no disponible - requiere aprobación manual"
    
    withdrawal_id = withdrawal['withdrawal_id']
    
    # Validate wallet address
    if not validate_bep20(withdrawal['wallet_address']):
        update_withdrawal(withdrawal_id, 
                         status='failed',
                         error_message='Dirección de wallet BEP20 inválida')
        # Return balance
        update_balance(withdrawal['user_id'],
                      withdrawal['currency'].lower(),
                      withdrawal['amount'],
                      'add',
                      f'Withdrawal failed refund: {withdrawal["amount"]} {withdrawal["currency"]}')
        return False, "Dirección de wallet BEP20 inválida"
    
    # Mark as processing
    update_withdrawal(withdrawal_id, status='processing')
    
    try:
        # Attempt to send crypto
        success, result = send_crypto(
            to_address=withdrawal['wallet_address'],
            amount=float(withdrawal['amount']),
            currency=withdrawal['currency']
        )
        
        if success:
            # Update to completed with tx hash
            update_withdrawal(withdrawal_id,
                            status='completed',
                            tx_hash=result,
                            processed_at=datetime.now())
            return True, f"Pago enviado. TX: {result}"
        else:
            # Payment failed
            update_withdrawal(withdrawal_id,
                            status='failed',
                            error_message=result)
            # Return balance to user
            update_balance(withdrawal['user_id'],
                          withdrawal['currency'].lower(),
                          withdrawal['amount'],
                          'add',
                          f'Withdrawal failed refund: {withdrawal["amount"]} {withdrawal["currency"]}')
            return False, f"Error en el pago: {result}"
            
    except Exception as e:
        # Handle unexpected errors
        error_msg = str(e)
        update_withdrawal(withdrawal_id,
                         status='failed',
                         error_message=error_msg)
        # Return balance
        update_balance(withdrawal['user_id'],
                      withdrawal['currency'].lower(),
                      withdrawal['amount'],
                      'add',
                      f'Withdrawal error refund: {withdrawal["amount"]} {withdrawal["currency"]}')
        return False, f"Error inesperado: {error_msg}"

def process_ton_withdrawal(withdrawal):
    """Procesa un retiro TON"""
    if not TON_PAYMENTS_AVAILABLE or not is_ton_configured():
        return False, "Sistema de pagos TON no disponible - requiere aprobación manual"
    
    withdrawal_id = withdrawal['withdrawal_id']
    
    # Validate wallet address
    if not validate_ton(withdrawal['wallet_address']):
        update_withdrawal(withdrawal_id, 
                         status='failed',
                         error_message='Dirección TON inválida')
        # Return balance
        update_balance(withdrawal['user_id'],
                      'ton',
                      withdrawal['amount'],
                      'add',
                      f'TON Withdrawal failed refund: {withdrawal["amount"]} TON')
        return False, "Dirección TON inválida"
    
    # Mark as processing
    update_withdrawal(withdrawal_id, status='processing')
    
    try:
        # Attempt to send TON
        memo = f"SALLY-E Withdrawal {withdrawal_id}"
        success, result = send_ton(
            to_address=withdrawal['wallet_address'],
            amount=float(withdrawal['amount']),
            memo=memo
        )
        
        if success:
            # Update to completed with tx hash
            update_withdrawal(withdrawal_id,
                            status='completed',
                            tx_hash=result,
                            processed_at=datetime.now())
            return True, f"TON enviado. TX: {result}"
        else:
            # Payment failed
            update_withdrawal(withdrawal_id,
                            status='failed',
                            error_message=result)
            # Return balance to user
            update_balance(withdrawal['user_id'],
                          'ton',
                          withdrawal['amount'],
                          'add',
                          f'TON Withdrawal failed refund: {withdrawal["amount"]} TON')
            return False, f"Error en el pago TON: {result}"
            
    except Exception as e:
        # Handle unexpected errors
        error_msg = str(e)
        update_withdrawal(withdrawal_id,
                         status='failed',
                         error_message=error_msg)
        # Return balance
        update_balance(withdrawal['user_id'],
                      'ton',
                      withdrawal['amount'],
                      'add',
                      f'TON Withdrawal error refund: {withdrawal["amount"]} TON')
        return False, f"Error inesperado: {error_msg}"

def process_all_pending():
    """
    Procesa todos los retiros pendientes
    
    Returns:
        dict: Results summary
    """
    # Check if automatic mode is enabled
    mode = get_config('withdrawal_mode', 'manual')
    if mode != 'auto':
        return {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'error': 'Modo automático desactivado'
        }
    
    pending = get_pending_withdrawals()
    results = {
        'processed': 0,
        'success': 0,
        'failed': 0,
        'details': []
    }
    
    for withdrawal in pending:
        results['processed'] += 1
        success, message = process_withdrawal(withdrawal['withdrawal_id'])
        
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
        
        results['details'].append({
            'withdrawal_id': withdrawal['withdrawal_id'],
            'currency': withdrawal['currency'],
            'success': success,
            'message': message
        })
    
    return results

def check_wallet_status():
    """
    Verifica el estado de las wallets del sistema
    
    Returns:
        dict: Wallet status info
    """
    status = {
        'bep20': {
            'available': False,
            'error': 'No disponible'
        },
        'ton': {
            'available': False,
            'error': 'No disponible'
        }
    }
    
    # Check BEP20 wallet
    if BEP20_PAYMENTS_AVAILABLE:
        try:
            info = get_bep20_wallet_info()
            status['bep20'] = {
                'available': True,
                'address': info.get('address'),
                'bnb_balance': info.get('bnb_balance', 0),
                'usdt_balance': info.get('usdt_balance', 0),
                'doge_balance': info.get('doge_balance', 0),
                'can_process': info.get('bnb_balance', 0) > 0.001
            }
        except Exception as e:
            status['bep20'] = {
                'available': False,
                'error': str(e)
            }
    
    # Check TON wallet
    if TON_PAYMENTS_AVAILABLE and is_ton_configured():
        try:
            info = get_ton_wallet_info()
            status['ton'] = {
                'available': info.get('configured', False),
                'address': info.get('address'),
                'ton_balance': info.get('balance', 0),
                'network': info.get('network', 'mainnet'),
                'can_process': info.get('can_process', False)
            }
        except Exception as e:
            status['ton'] = {
                'available': False,
                'error': str(e)
            }
    
    return status

def estimate_gas_cost(currency):
    """
    Estima el costo de gas para una transacción
    
    Returns:
        float: Estimated gas cost
    """
    currency = currency.upper()
    
    if currency == 'TON':
        # TON network fee is typically ~0.01 TON
        return 0.01
    else:
        # BEP20 token transfers typically cost around 0.0005 BNB
        return 0.0005

def can_process_withdrawal(withdrawal_id):
    """
    Verifica si un retiro puede ser procesado automáticamente
    
    Returns:
        tuple: (can_process: bool, reason: str or None)
    """
    withdrawal = get_withdrawal(withdrawal_id)
    if not withdrawal:
        return False, "Retiro no encontrado"
    
    if withdrawal['status'] != 'pending':
        return False, f"Estado inválido: {withdrawal['status']}"
    
    currency = withdrawal['currency'].upper()
    
    # Check appropriate wallet based on currency
    if currency == 'TON':
        if not TON_PAYMENTS_AVAILABLE or not is_ton_configured():
            return False, "Sistema de pagos TON no disponible"
        
        status = check_wallet_status()
        ton_status = status.get('ton', {})
        
        if not ton_status.get('available'):
            return False, ton_status.get('error', 'TON wallet no disponible')
        
        if not ton_status.get('can_process'):
            return False, "Balance TON insuficiente"
        
        if float(withdrawal['amount']) > ton_status.get('ton_balance', 0):
            return False, "Balance TON insuficiente para este retiro"
    
    else:  # BEP20 (USDT/DOGE)
        if not BEP20_PAYMENTS_AVAILABLE:
            return False, "Sistema de pagos BEP20 no disponible"
        
        status = check_wallet_status()
        bep20_status = status.get('bep20', {})
        
        if not bep20_status.get('available'):
            return False, bep20_status.get('error', 'BEP20 wallet no disponible')
        
        if not bep20_status.get('can_process'):
            return False, "Balance de BNB insuficiente para gas"
        
        # Check token balance
        balance_key = f"{currency.lower()}_balance"
        wallet_balance = bep20_status.get(balance_key, 0)
        
        if float(withdrawal['amount']) > wallet_balance:
            return False, f"Balance insuficiente de {currency} en wallet del sistema"
    
    return True, None

def is_auto_mode():
    """
    Verifica si el modo automático está activado
    
    Returns:
        bool: True if auto mode is enabled
    """
    mode = get_config('withdrawal_mode', 'manual')
    return mode == 'auto'

def process_withdrawal_if_auto(withdrawal_id):
    """
    Procesa un retiro automáticamente si el modo automático está activado.
    Esta función se llama inmediatamente después de crear un retiro.
    
    Args:
        withdrawal_id: ID del retiro a procesar
    
    Returns:
        tuple: (processed: bool, success: bool, message: str)
               processed=False significa que se dejó en modo manual
    """
    # Verificar si el modo automático está activado
    if not is_auto_mode():
        return False, False, "Modo manual - pendiente de aprobación"
    
    # Verificar si se puede procesar
    can_process, reason = can_process_withdrawal(withdrawal_id)
    if not can_process:
        return True, False, f"Auto-pago no disponible: {reason}"
    
    # Intentar procesar
    success, message = process_withdrawal(withdrawal_id)
    return True, success, message

def get_auto_pay_status():
    """
    Obtiene el estado del sistema de pagos automáticos
    
    Returns:
        dict: Status info
    """
    mode = get_config('withdrawal_mode', 'manual')
    wallet_status = check_wallet_status()
    
    return {
        'mode': mode,
        'auto_enabled': mode == 'auto',
        'bep20_ready': wallet_status.get('bep20', {}).get('can_process', False),
        'ton_ready': wallet_status.get('ton', {}).get('can_process', False),
        'bep20_status': wallet_status.get('bep20', {}),
        'ton_status': wallet_status.get('ton', {})
    }

# CLI for testing
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'status':
            print("Checking wallet status...")
            status = check_wallet_status()
            print("\nBEP20 Wallet:")
            for key, value in status.get('bep20', {}).items():
                print(f"  {key}: {value}")
            print("\nTON Wallet:")
            for key, value in status.get('ton', {}).items():
                print(f"  {key}: {value}")
        
        elif command == 'process':
            if len(sys.argv) > 2:
                withdrawal_id = sys.argv[2]
                print(f"Processing withdrawal {withdrawal_id}...")
                success, message = process_withdrawal(withdrawal_id)
                print(f"  Success: {success}")
                print(f"  Message: {message}")
            else:
                print("Processing all pending withdrawals...")
                results = process_all_pending()
                print(f"  Processed: {results['processed']}")
                print(f"  Success: {results['success']}")
                print(f"  Failed: {results['failed']}")
        
        elif command == 'check':
            if len(sys.argv) > 2:
                withdrawal_id = sys.argv[2]
                can, reason = can_process_withdrawal(withdrawal_id)
                print(f"Can process: {can}")
                if reason:
                    print(f"Reason: {reason}")
            else:
                print("Usage: python auto_pay.py check <withdrawal_id>")
        
        else:
            print(f"Unknown command: {command}")
            print("Usage: python auto_pay.py [status|process [withdrawal_id]|check <withdrawal_id>]")
    else:
        print("SALLY-E Auto Payment Processor")
        print("Usage: python auto_pay.py [status|process [withdrawal_id]|check <withdrawal_id>]")
