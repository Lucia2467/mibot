"""
ton_payments_system.py — Sistema TON para ARCADE PXC
Wrapper limpio sobre ton_wallet.py (tonutils + ToncenterClient)

Usa la tabla estándar 'withdrawals' — sin tablas propias.
"""

import os
import re
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Env vars ──────────────────────────────────────────────────────────────────
TON_WALLET_MNEMONIC  = os.environ.get('TON_WALLET_MNEMONIC', '')
TON_API_KEY          = os.environ.get('TON_API_KEY', '')
TON_WALLET_ADDRESS   = os.environ.get('TON_WALLET_ADDRESS', '')
TONCENTER_API_URL    = 'https://toncenter.com/api/v2'
TONSCAN_URL          = 'https://tonscan.org'


def is_ton_configured() -> bool:
    """True si están definidos mnemonic y API key."""
    return bool(TON_WALLET_MNEMONIC and TON_API_KEY)


def validate_ton_address(address: str):
    """
    Valida dirección TON.
    Returns (True, tipo) o (False, motivo_error).
    """
    if not address:
        return False, "Dirección requerida"

    address = address.strip()

    friendly_prefixes = ('EQ', 'UQ', 'Ef', 'Uf', 'kQ', 'kf', '0Q', '0f')
    if address.startswith(friendly_prefixes):
        if len(address) == 48 and re.match(r'^[EUku0][QfF][A-Za-z0-9_-]{46}$', address):
            return True, "user_friendly"
        return False, "Dirección user-friendly inválida (debe tener 48 caracteres)"

    if ':' in address:
        parts = address.split(':')
        if len(parts) == 2:
            try:
                wc = int(parts[0])
                if wc in (0, -1) and len(parts[1]) == 64 and re.match(r'^[a-fA-F0-9]{64}$', parts[1]):
                    return True, "raw"
            except ValueError:
                pass
        return False, "Formato raw inválido (workchain:hex64)"

    return False, "Formato de dirección TON inválido"


def get_system_wallet_info() -> dict:
    """Retorna info de la wallet del sistema (balance, estado, config)."""
    if not TON_WALLET_ADDRESS:
        return {'configured': False, 'error': 'TON_WALLET_ADDRESS no configurado'}
    if not TON_API_KEY:
        return {'configured': False, 'error': 'TON_API_KEY no configurado'}
    if not TON_WALLET_MNEMONIC:
        return {'configured': False, 'error': 'TON_WALLET_MNEMONIC no configurado'}

    try:
        import requests
        resp = requests.get(
            f'{TONCENTER_API_URL}/getAddressBalance',
            params={'address': TON_WALLET_ADDRESS},
            headers={'X-API-Key': TON_API_KEY},
            timeout=10
        )
        data = resp.json()
        if data.get('ok'):
            balance = int(data.get('result', 0)) / 1_000_000_000
            return {
                'configured': True,
                'address': TON_WALLET_ADDRESS,
                'balance': balance,
                'can_process': balance >= 0.05,
                'has_mnemonic': True,
                'network': 'mainnet',
                'tonscan_url': f'{TONSCAN_URL}/address/{TON_WALLET_ADDRESS}',
            }
        return {
            'configured': True,
            'address': TON_WALLET_ADDRESS,
            'balance': 0,
            'error': data.get('error', 'Error al consultar balance'),
        }
    except Exception as e:
        logger.exception(f'get_system_wallet_info error: {e}')
        return {'configured': True, 'address': TON_WALLET_ADDRESS, 'balance': 0, 'error': str(e)}


def send_ton_payment(to_address: str, amount: float, memo: str = ''):
    """
    Envía TON usando ton_wallet.send_ton.
    Returns (success: bool, tx_hash: str|None, error: str|None)
    """
    if not is_ton_configured():
        return False, None, 'TON no configurado (falta MNEMONIC o API_KEY)'

    from ton_wallet import send_ton
    return send_ton(
        mnemonic=TON_WALLET_MNEMONIC,
        to_addr=to_address,
        ton_amount=amount,
        memo=memo,
        api_key=TON_API_KEY,
        bot_wallet_address=TON_WALLET_ADDRESS,
    )


def process_ton_withdrawal_auto(withdrawal_id: str):
    """
    Procesa un retiro TON de la tabla 'withdrawals' de forma automática.
    Returns (success: bool, message: str)
    """
    from database import get_withdrawal, update_withdrawal, update_balance

    withdrawal = get_withdrawal(withdrawal_id)
    if not withdrawal:
        return False, 'Retiro no encontrado'

    if withdrawal['status'] != 'pending':
        return False, f"Estado inválido para procesar: {withdrawal['status']}"

    address = withdrawal['wallet_address']
    is_valid, err = validate_ton_address(address)
    if not is_valid:
        update_withdrawal(withdrawal_id, status='failed', error_message=f'Dirección inválida: {err}')
        update_balance(withdrawal['user_id'], 'ton', float(withdrawal['amount']), 'add',
                       f'TON Retiro fallido (dirección inválida): {withdrawal["amount"]} TON')
        return False, f'Dirección TON inválida: {err}'

    update_withdrawal(withdrawal_id, status='processing')

    memo = f'ARCADE PXC Withdrawal {withdrawal_id}'
    success, tx_hash, error = send_ton_payment(
        to_address=address,
        amount=float(withdrawal['amount']),
        memo=memo,
    )

    if success:
        update_withdrawal(
            withdrawal_id,
            status='completed',
            tx_hash=tx_hash,
            processed_at=datetime.now(),
        )
        logger.info(f'TON withdrawal {withdrawal_id} completed. TX: {tx_hash}')
        return True, f'TON enviado. TX: {tx_hash}'
    else:
        update_withdrawal(withdrawal_id, status='failed', error_message=error)
        update_balance(withdrawal['user_id'], 'ton', float(withdrawal['amount']), 'add',
                       f'TON Retiro fallido: {withdrawal["amount"]} TON')
        logger.error(f'TON withdrawal {withdrawal_id} failed: {error}')
        return False, f'Error al enviar TON: {error}'


def get_tonscan_tx_url(tx_hash: str) -> str:
    return f'{TONSCAN_URL}/tx/{tx_hash}'


def get_tonscan_addr_url(address: str) -> str:
    return f'{TONSCAN_URL}/address/{address}'
