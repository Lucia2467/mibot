"""
wallet.py - Sistema de retiros para SALLY-E Bot / DOGE PIXEL
Maneja solicitudes de retiro, validación y procesamiento
Soporta: USDT (BEP20), DOGE (BEP20), TON (TON Network)
"""

import re
from datetime import datetime
from database import (
    get_user, update_user, update_balance,
    create_withdrawal, get_withdrawal, get_user_withdrawals,
    update_withdrawal, get_config
)

# Minimum withdrawal amounts
MIN_WITHDRAWALS = {
    'USDT': 0.5,
    'DOGE': 0.3,
    'TON': 0.1
}

# Network fees (0 = free)
NETWORK_FEES = {
    'USDT': 0,
    'DOGE': 0,
    'TON': 0.01
}

def validate_bep20_address(address):
    """Valida formato de dirección BEP20/ERC20"""
    if not address:
        return False
    # Must start with 0x and have 40 hex characters after
    pattern = r'^0x[a-fA-F0-9]{40}$'
    return bool(re.match(pattern, address))

def validate_ton_address(address):
    """
    Valida formato de dirección TON
    
    Soporta:
    - User-friendly: EQ.../UQ.../Ef.../Uf.../kQ.../kf.../0Q.../0f... (48 chars)
    - Raw: workchain:hex (e.g., 0:abc...def or -1:abc...def)
    """
    if not address:
        return False
    
    address = address.strip()
    
    # User-friendly format (base64url encoded, 48 chars)
    friendly_prefixes = ('EQ', 'UQ', 'Ef', 'Uf', 'kQ', 'kf', '0Q', '0f')
    if address.startswith(friendly_prefixes) and len(address) == 48:
        # Basic base64url validation
        pattern = r'^[EUku0][QfF][A-Za-z0-9_-]{46}$'
        return bool(re.match(pattern, address))
    
    # Raw format: workchain:hex (64 hex chars)
    if ':' in address:
        parts = address.split(':')
        if len(parts) == 2:
            workchain, hex_part = parts
            if workchain in ['0', '-1'] and len(hex_part) == 64:
                return bool(re.match(r'^[a-fA-F0-9]{64}$', hex_part))
    
    return False

def get_min_withdrawal(currency):
    """Obtiene el mínimo de retiro para una moneda"""
    currency = currency.upper()
    config_key = f'min_withdrawal_{currency.lower()}'
    return float(get_config(config_key, MIN_WITHDRAWALS.get(currency, 0.5)))

def get_network_fee(currency):
    """Obtiene la comisión de red para una moneda"""
    currency = currency.upper()
    config_key = f'network_fee_{currency.lower()}'
    return float(get_config(config_key, NETWORK_FEES.get(currency, 0)))

def create_withdrawal_request(user_id, currency, amount, wallet_address=None):
    """
    Crea una solicitud de retiro
    
    Soporta: USDT, DOGE (BEP20) y TON (TON Network)
    
    Returns:
        tuple: (success: bool, result: withdrawal_id or error_message)
    """
    # Validate currency
    currency = currency.upper()
    if currency not in ['USDT', 'DOGE', 'TON']:
        return False, "Moneda no soportada. Use USDT, DOGE o TON."
    
    # Get user
    user = get_user(user_id)
    if not user:
        return False, "Usuario no encontrado"
    
    if user.get('banned'):
        return False, "Usuario baneado"
    
    # Check if withdrawal is blocked
    if user.get('withdrawal_blocked'):
        reason = user.get('withdrawal_block_reason', 'Retiros bloqueados')
        return False, reason
    
    # Get wallet address based on currency
    if currency == 'TON':
        # TON uses ton_wallet_address
        if not wallet_address:
            wallet_address = user.get('ton_wallet_address')
        
        if not wallet_address:
            return False, "Debe vincular una dirección TON primero"
        
        if not validate_ton_address(wallet_address):
            return False, "Formato de dirección TON inválido"
    else:
        # USDT/DOGE use BEP20 wallet_address
        if not wallet_address:
            wallet_address = user.get('wallet_address')
        
        if not wallet_address:
            return False, "Debe vincular una dirección de wallet BEP20 primero"
        
        if not validate_bep20_address(wallet_address):
            return False, "Formato de dirección BEP20 inválido (debe ser 0x...)"
    
    # Validate amount
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return False, "Cantidad inválida"
    
    if amount <= 0:
        return False, "La cantidad debe ser mayor a 0"
    
    # Check minimum
    min_amount = get_min_withdrawal(currency)
    if amount < min_amount:
        return False, f"Mínimo de retiro: {min_amount} {currency}"
    
    # Check balance
    balance_key = f'{currency.lower()}_balance'
    user_balance = float(user.get(balance_key, 0))
    
    # Check for negative balance (debt) in any currency - block withdrawals
    se_balance = float(user.get('se_balance', 0) or 0)
    doge_balance = float(user.get('doge_balance', 0) or 0)
    usdt_balance = float(user.get('usdt_balance', 0) or 0)
    ton_balance = float(user.get('ton_balance', 0) or 0)
    
    if se_balance < 0 or doge_balance < 0 or usdt_balance < 0 or ton_balance < 0:
        debt_info = []
        if se_balance < 0:
            debt_info.append(f"S-E: {se_balance:.4f}")
        if doge_balance < 0:
            debt_info.append(f"DOGE: {doge_balance:.4f}")
        if usdt_balance < 0:
            debt_info.append(f"USDT: {usdt_balance:.4f}")
        if ton_balance < 0:
            debt_info.append(f"TON: {ton_balance:.4f}")
        return False, f"⚠️ Tienes deuda pendiente que debes pagar antes de retirar. Saldo negativo: {', '.join(debt_info)}"
    
    if amount > user_balance:
        return False, f"Balance insuficiente. Tienes: {user_balance:.4f} {currency}"
    
    # Calculate fee
    fee = get_network_fee(currency)
    final_amount = amount - fee
    
    if final_amount <= 0:
        return False, "La cantidad después de comisiones es 0 o negativa"
    
    # Deduct balance first
    update_balance(user_id, currency.lower(), amount, 'subtract', f'Withdrawal: {amount} {currency} to {wallet_address[:10]}...')
    
    # Create withdrawal record
    withdrawal_id = create_withdrawal(user_id, currency, amount, wallet_address)
    
    if not withdrawal_id:
        # Refund if creation failed
        update_balance(user_id, currency.lower(), amount, 'add', f'Withdrawal refund: {amount} {currency}')
        return False, "Error al crear la solicitud de retiro"
    
    # Check withdrawal mode
    mode = get_config('withdrawal_mode', 'manual')
    
    if mode == 'automatic':
        # Try automatic processing based on currency
        if currency == 'TON':
            # Use TON payment system for TON
            try:
                from ton_payments_system import process_ton_payment
                # Note: TON uses its own payment table, not withdrawals table
                # This is handled separately in ton_payment_routes.py
                pass
            except ImportError:
                pass
        else:
            # Use auto_pay for BEP20 tokens
            try:
                from auto_pay import process_withdrawal
                success, message = process_withdrawal(withdrawal_id)
                if not success:
                    # Auto-pay failed, stays as pending for manual review
                    pass
            except ImportError:
                pass  # Auto-pay not available, manual mode
    
    return True, withdrawal_id

def link_wallet_address(user_id, wallet_address, wallet_type='bep20'):
    """
    Vincula una dirección de wallet a un usuario
    
    Args:
        user_id: ID del usuario
        wallet_address: Dirección de la wallet
        wallet_type: 'bep20' o 'ton'
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not wallet_address:
        return False, "Dirección requerida"
    
    wallet_address = wallet_address.strip()
    
    user = get_user(user_id)
    if not user:
        return False, "Usuario no encontrado"
    
    if wallet_type == 'ton':
        # Validate TON address
        if not validate_ton_address(wallet_address):
            return False, "Formato de dirección TON inválido. Use EQ.../UQ... (48 caracteres)"
        
        update_user(user_id, 
                   ton_wallet_address=wallet_address,
                   ton_wallet_linked_at=datetime.now())
        
        return True, "Dirección TON vinculada correctamente"
    
    else:  # BEP20
        if not validate_bep20_address(wallet_address):
            return False, "Formato inválido. Use dirección BEP20 (0x + 40 caracteres hex)"
        
        update_user(user_id, wallet_address=wallet_address)
        
        return True, "Dirección BEP20 vinculada correctamente"

def approve_withdrawal(withdrawal_id, tx_hash=None):
    """
    Aprueba un retiro (admin)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    withdrawal = get_withdrawal(withdrawal_id)
    
    if not withdrawal:
        return False, "Retiro no encontrado"
    
    if withdrawal['status'] != 'pending':
        return False, f"El retiro ya está en estado: {withdrawal['status']}"
    
    # Update to completed
    update_withdrawal(withdrawal_id, 
                     status='completed',
                     tx_hash=tx_hash,
                     processed_at=datetime.now())
    
    return True, "Retiro aprobado"

def reject_withdrawal(withdrawal_id, reason=None):
    """
    Rechaza un retiro y devuelve el balance (admin)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    withdrawal = get_withdrawal(withdrawal_id)
    
    if not withdrawal:
        return False, "Retiro no encontrado"
    
    if withdrawal['status'] != 'pending':
        return False, f"El retiro ya está en estado: {withdrawal['status']}"
    
    # Return balance to user
    update_balance(withdrawal['user_id'], 
                  withdrawal['currency'].lower(),
                  withdrawal['amount'],
                  'add',
                  f'Withdrawal rejected refund: {withdrawal["amount"]} {withdrawal["currency"]}')
    
    # Update status
    update_withdrawal(withdrawal_id,
                     status='rejected',
                     error_message=reason or 'Rejected by admin',
                     processed_at=datetime.now())
    
    return True, "Retiro rechazado y balance devuelto"

def get_withdrawal_stats(user_id):
    """
    Obtiene estadísticas de retiros de un usuario
    
    Returns:
        dict: Statistics including totals and counts
    """
    withdrawals = get_user_withdrawals(user_id)
    
    stats = {
        'total_usdt': 0,
        'total_doge': 0,
        'total_ton': 0,
        'pending_count': 0,
        'completed_count': 0,
        'rejected_count': 0,
        'total_withdrawn': 0
    }
    
    for w in withdrawals:
        if w['status'] == 'completed':
            if w['currency'] == 'USDT':
                stats['total_usdt'] += float(w['amount'])
            elif w['currency'] == 'DOGE':
                stats['total_doge'] += float(w['amount'])
            elif w['currency'] == 'TON':
                stats['total_ton'] += float(w['amount'])
            stats['completed_count'] += 1
            stats['total_withdrawn'] += float(w['amount'])
        elif w['status'] == 'pending':
            stats['pending_count'] += 1
        elif w['status'] == 'rejected':
            stats['rejected_count'] += 1
    
    return stats

def format_withdrawal_for_display(withdrawal):
    """
    Formatea un retiro para mostrar en la UI
    
    Returns:
        dict: Formatted withdrawal data
    """
    if not withdrawal:
        return None
    
    status_labels = {
        'pending': '⏳ Pendiente',
        'processing': '⚙️ Procesando',
        'completed': '✅ Completado',
        'failed': '❌ Fallido',
        'rejected': '🚫 Rechazado'
    }
    
    status_colors = {
        'pending': 'warning',
        'processing': 'info',
        'completed': 'success',
        'failed': 'danger',
        'rejected': 'secondary'
    }
    
    # Currency colors
    currency_colors = {
        'USDT': '#26A17B',
        'DOGE': '#C9A635',
        'TON': '#0098EA'
    }
    
    return {
        **withdrawal,
        'status_label': status_labels.get(withdrawal['status'], withdrawal['status']),
        'status_color': status_colors.get(withdrawal['status'], 'secondary'),
        'currency_color': currency_colors.get(withdrawal['currency'], '#ffffff'),
        'amount_formatted': f"{withdrawal['amount']:.6f}",
        'address_short': f"{withdrawal['wallet_address'][:6]}...{withdrawal['wallet_address'][-4:]}" if withdrawal.get('wallet_address') else 'N/A'
    }

def get_pending_amount(user_id, currency=None):
    """
    Obtiene el monto total pendiente de retiro
    
    Returns:
        float: Total pending amount
    """
    withdrawals = get_user_withdrawals(user_id)
    
    total = 0
    for w in withdrawals:
        if w['status'] in ['pending', 'processing']:
            if currency is None or w['currency'].upper() == currency.upper():
                total += float(w['amount'])
    
    return total

def can_withdraw(user_id, currency, amount):
    """
    Verifica si un usuario puede hacer un retiro
    
    Returns:
        tuple: (can_withdraw: bool, reason: str or None)
    """
    user = get_user(user_id)
    if not user:
        return False, "Usuario no encontrado"
    
    if user.get('banned'):
        return False, "Usuario baneado"
    
    if user.get('withdrawal_blocked'):
        return False, user.get('withdrawal_block_reason', 'Retiros bloqueados')
    
    currency = currency.upper()
    balance_key = f'{currency.lower()}_balance'
    balance = float(user.get(balance_key, 0))
    
    if float(amount) > balance:
        return False, "Balance insuficiente"
    
    min_amount = get_min_withdrawal(currency)
    if float(amount) < min_amount:
        return False, f"Mínimo: {min_amount} {currency}"
    
    # Check wallet address based on currency
    if currency == 'TON':
        if not user.get('ton_wallet_address'):
            return False, "Sin dirección TON vinculada"
    else:
        if not user.get('wallet_address'):
            return False, "Sin dirección BEP20 vinculada"
    
    return True, None

def get_user_wallet_info(user_id):
    """
    Obtiene información de las wallets vinculadas del usuario
    
    Returns:
        dict: Wallet information
    """
    user = get_user(user_id)
    if not user:
        return None
    
    return {
        'bep20_address': user.get('wallet_address'),
        'bep20_linked': bool(user.get('wallet_address')),
        'ton_address': user.get('ton_wallet_address'),
        'ton_linked': bool(user.get('ton_wallet_address')),
        'ton_linked_at': user.get('ton_wallet_linked_at')
    }
