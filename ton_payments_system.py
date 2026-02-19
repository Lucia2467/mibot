"""
ton_payments_system.py - Complete TON Payment System for SALLY-E / DOGE PIXEL
Handles automatic and manual TON payments with full admin control

Features:
- TON wallet integration via TonCenter API
- Automatic and manual payment processing
- Complete audit trail
- Admin panel control
- Security measures (address validation, duplicate prevention, etc.)
"""

import os
import re
import json
import uuid
import hashlib
import time
import base64
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

# ============================================
# CONFIGURATION
# ============================================

# TON API Configuration
TON_API_KEY = os.environ.get('TON_API_KEY', '')
TON_WALLET_ADDRESS = os.environ.get('TON_WALLET_ADDRESS', '')
TON_WALLET_MNEMONIC = os.environ.get('TON_WALLET_MNEMONIC', '')
TON_TESTNET = os.environ.get('TON_TESTNET', 'false').lower() == 'true'

# API URLs
TON_MAINNET_API = 'https://toncenter.com/api/v2'
TON_TESTNET_API = 'https://testnet.toncenter.com/api/v2'
TON_API_URL = TON_TESTNET_API if TON_TESTNET else TON_MAINNET_API

# TonScan URLs
TONSCAN_MAINNET = 'https://tonscan.org'
TONSCAN_TESTNET = 'https://testnet.tonscan.org'
TONSCAN_URL = TONSCAN_TESTNET if TON_TESTNET else TONSCAN_MAINNET

# Default settings
DEFAULT_MIN_WITHDRAWAL = 0.1
DEFAULT_MAX_WITHDRAWAL = 100.0
DEFAULT_FEE = 0.01
DEFAULT_CONFIRMATIONS = 1

# Payment statuses
class PaymentStatus:
    PENDING = 'pending'
    APPROVED = 'approved'
    PROCESSING = 'processing'
    SENT = 'sent'
    CONFIRMED = 'confirmed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

# ============================================
# DATABASE IMPORTS (lazy loading)
# ============================================

def get_db_connection():
    """Get database connection - lazy import"""
    from db import get_cursor, execute_query
    return get_cursor, execute_query

def get_database_functions():
    """Get database helper functions"""
    from database import row_to_dict, rows_to_list, decimal_to_float
    return row_to_dict, rows_to_list, decimal_to_float

# ============================================
# ADDRESS VALIDATION
# ============================================

def validate_ton_address(address: str) -> Tuple[bool, str]:
    """
    Validate TON address format
    
    Supports:
    - User-friendly format: EQ.../UQ.../Ef.../Uf.../kQ.../kf.../0Q.../0f... (48 chars)
    - Raw format: workchain:hex (e.g., 0:abc...def)
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message or address_type)
    """
    if not address:
        return False, "Address is required"
    
    address = address.strip()
    
    # Check user-friendly format (base64url encoded)
    friendly_prefixes = ('EQ', 'UQ', 'Ef', 'Uf', 'kQ', 'kf', '0Q', '0f')
    if address.startswith(friendly_prefixes):
        if len(address) == 48:
            # Validate base64url characters
            pattern = r'^[EUku0][QfF][A-Za-z0-9_-]{46}$'
            if re.match(pattern, address):
                return True, "user_friendly"
        return False, "Invalid user-friendly address format (must be 48 characters)"
    
    # Check raw format (workchain:hex)
    if ':' in address:
        parts = address.split(':')
        if len(parts) == 2:
            try:
                workchain = int(parts[0])
                if workchain in [0, -1]:
                    if len(parts[1]) == 64:
                        if re.match(r'^[a-fA-F0-9]{64}$', parts[1]):
                            return True, "raw"
            except ValueError:
                pass
        return False, "Invalid raw address format"
    
    return False, "Invalid TON address format"

def normalize_ton_address(address: str) -> Optional[str]:
    """
    Normalize TON address to a standard format
    Returns None if address is invalid
    """
    is_valid, _ = validate_ton_address(address)
    if not is_valid:
        return None
    return address.strip()

# ============================================
# TON API CLIENT
# ============================================

class TonApiClient:
    """Client for interacting with TonCenter API"""
    
    def __init__(self, api_key: str = None, api_url: str = None):
        self.api_key = api_key or TON_API_KEY
        self.api_url = api_url or TON_API_URL
        self._requests = None
    
    @property
    def requests(self):
        if self._requests is None:
            import requests
            self._requests = requests
        return self._requests
    
    def _make_request(self, method: str, endpoint: str, params: dict = None, json_data: dict = None) -> dict:
        """Make API request with error handling"""
        headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        url = f"{self.api_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.requests.get(url, headers=headers, params=params, timeout=30)
            else:
                response = self.requests.post(url, headers=headers, json=json_data, timeout=60)
            
            data = response.json()
            return data
        except Exception as e:
            return {'ok': False, 'error': str(e)}
    
    def get_address_balance(self, address: str) -> Tuple[bool, float]:
        """
        Get balance of a TON address
        
        Returns:
            Tuple[bool, float]: (success, balance_in_ton)
        """
        data = self._make_request('GET', 'getAddressBalance', {'address': address})
        
        if data.get('ok'):
            balance_nano = int(data.get('result', 0))
            return True, balance_nano / 1e9
        
        return False, 0.0
    
    def get_address_info(self, address: str) -> dict:
        """Get detailed information about an address"""
        data = self._make_request('GET', 'getAddressInformation', {'address': address})
        
        if data.get('ok'):
            result = data.get('result', {})
            return {
                'success': True,
                'balance': int(result.get('balance', 0)) / 1e9,
                'state': result.get('state', 'unknown'),
                'code': result.get('code'),
                'data': result.get('data'),
                'last_tx_lt': result.get('last_transaction_id', {}).get('lt'),
                'last_tx_hash': result.get('last_transaction_id', {}).get('hash')
            }
        
        return {'success': False, 'error': data.get('error', 'Unknown error')}
    
    def get_transactions(self, address: str, limit: int = 10, lt: str = None, hash: str = None) -> List[dict]:
        """Get transactions for an address"""
        params = {'address': address, 'limit': limit}
        if lt:
            params['lt'] = lt
        if hash:
            params['hash'] = hash
        
        data = self._make_request('GET', 'getTransactions', params)
        
        if data.get('ok'):
            return data.get('result', [])
        
        return []
    
    def get_transaction_by_hash(self, tx_hash: str) -> Optional[dict]:
        """Get transaction details by hash"""
        # First get transactions from our wallet
        transactions = self.get_transactions(TON_WALLET_ADDRESS, limit=100)
        
        for tx in transactions:
            tx_id = tx.get('transaction_id', {})
            if tx_id.get('hash') == tx_hash:
                return {
                    'found': True,
                    'hash': tx_hash,
                    'lt': tx_id.get('lt'),
                    'fee': int(tx.get('fee', 0)) / 1e9,
                    'utime': tx.get('utime'),
                    'in_msg': tx.get('in_msg'),
                    'out_msgs': tx.get('out_msgs', [])
                }
        
        return {'found': False}
    
    def send_boc(self, boc: str) -> Tuple[bool, str]:
        """
        Send a signed transaction (BOC) to the network
        
        Returns:
            Tuple[bool, str]: (success, tx_hash or error)
        """
        data = self._make_request('POST', 'sendBoc', json_data={'boc': boc})
        
        if data.get('ok'):
            result = data.get('result', {})
            tx_hash = result.get('hash', '')
            return True, tx_hash
        
        return False, data.get('error', 'Failed to send transaction')
    
    def estimate_fee(self, from_address: str, to_address: str, amount: float) -> float:
        """Estimate transaction fee"""
        # TON network fees are typically around 0.01-0.05 TON
        return 0.01

# Global API client instance
_api_client = None

def get_api_client() -> TonApiClient:
    """Get or create API client singleton"""
    global _api_client
    if _api_client is None:
        _api_client = TonApiClient()
    return _api_client

# ============================================
# WALLET OPERATIONS
# ============================================

def get_system_wallet_balance() -> Tuple[bool, float]:
    """Get balance of the system TON wallet"""
    if not TON_WALLET_ADDRESS:
        return False, 0.0
    
    client = get_api_client()
    return client.get_address_balance(TON_WALLET_ADDRESS)

def get_system_wallet_info() -> dict:
    """Get comprehensive system wallet information"""
    if not TON_WALLET_ADDRESS:
        return {
            'configured': False,
            'error': 'TON wallet address not configured'
        }
    
    if not TON_API_KEY:
        return {
            'configured': False,
            'error': 'TON API key not configured'
        }
    
    client = get_api_client()
    info = client.get_address_info(TON_WALLET_ADDRESS)
    
    if info.get('success'):
        balance = info.get('balance', 0)
        return {
            'configured': True,
            'address': TON_WALLET_ADDRESS,
            'balance': balance,
            'state': info.get('state'),
            'network': 'testnet' if TON_TESTNET else 'mainnet',
            'can_process': balance >= 0.1,  # Minimum for processing
            'has_mnemonic': bool(TON_WALLET_MNEMONIC),
            'api_url': TON_API_URL
        }
    
    return {
        'configured': True,
        'address': TON_WALLET_ADDRESS,
        'balance': 0,
        'error': info.get('error', 'Failed to fetch wallet info'),
        'network': 'testnet' if TON_TESTNET else 'mainnet'
    }

def is_ton_configured() -> bool:
    """Check if TON payments are properly configured"""
    return bool(TON_API_KEY and TON_WALLET_ADDRESS)

def can_process_payments() -> Tuple[bool, str]:
    """Check if system can process TON payments"""
    if not TON_API_KEY:
        return False, "TON API key not configured"
    
    if not TON_WALLET_ADDRESS:
        return False, "TON wallet address not configured"
    
    if not TON_WALLET_MNEMONIC:
        return False, "TON wallet mnemonic not configured (manual processing only)"
    
    success, balance = get_system_wallet_balance()
    if not success:
        return False, "Failed to fetch wallet balance"
    
    if balance < 0.1:
        return False, f"Insufficient wallet balance: {balance:.4f} TON"
    
    return True, f"Ready to process. Balance: {balance:.4f} TON"

# ============================================
# PAYMENT CONFIGURATION
# ============================================

def get_ton_config(key: str, default: Any = None) -> Any:
    """Get TON payment configuration value"""
    get_cursor, execute_query = get_db_connection()
    
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT config_value, config_type 
                FROM ton_payment_config 
                WHERE config_key = %s
            """, (key,))
            row = cursor.fetchone()
            
            if row:
                value = row['config_value'] if isinstance(row, dict) else row[0]
                config_type = row['config_type'] if isinstance(row, dict) else row[1]
                
                if config_type == 'number':
                    return float(value) if '.' in str(value) else int(value)
                elif config_type == 'boolean':
                    return value.lower() in ('true', '1', 'yes')
                elif config_type == 'json':
                    return json.loads(value)
                return value
            
            return default
    except Exception as e:
        print(f"Error getting TON config {key}: {e}")
        return default

def set_ton_config(key: str, value: Any, updated_by: str = 'system') -> bool:
    """Set TON payment configuration value"""
    get_cursor, execute_query = get_db_connection()
    
    try:
        # Determine type
        if isinstance(value, bool):
            config_type = 'boolean'
            str_value = 'true' if value else 'false'
        elif isinstance(value, (int, float)):
            config_type = 'number'
            str_value = str(value)
        elif isinstance(value, (dict, list)):
            config_type = 'json'
            str_value = json.dumps(value)
        else:
            config_type = 'string'
            str_value = str(value)
        
        execute_query("""
            INSERT INTO ton_payment_config (config_key, config_value, config_type, updated_by)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                config_value = VALUES(config_value),
                config_type = VALUES(config_type),
                updated_by = VALUES(updated_by)
        """, (key, str_value, config_type, updated_by))
        
        return True
    except Exception as e:
        print(f"Error setting TON config {key}: {e}")
        return False

def get_all_ton_config() -> dict:
    """Get all TON payment configuration"""
    get_cursor, execute_query = get_db_connection()
    
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM ton_payment_config ORDER BY config_key")
            rows = cursor.fetchall()
            
            config = {}
            for row in rows:
                if isinstance(row, dict):
                    key = row['config_key']
                    value = row['config_value']
                    config_type = row['config_type']
                else:
                    key, value, config_type = row[1], row[2], row[3]
                
                if config_type == 'number':
                    config[key] = float(value) if '.' in str(value) else int(value)
                elif config_type == 'boolean':
                    config[key] = value.lower() in ('true', '1', 'yes')
                elif config_type == 'json':
                    config[key] = json.loads(value)
                else:
                    config[key] = value
            
            return config
    except Exception as e:
        print(f"Error getting all TON config: {e}")
        return {}

# ============================================
# PAYMENT OPERATIONS
# ============================================

def create_ton_payment(
    user_id: str,
    amount: float,
    to_address: str,
    withdrawal_id: str = None,
    payment_type: str = 'manual',
    memo: str = None,
    created_by: str = 'system'
) -> Tuple[bool, str]:
    """
    Create a new TON payment record
    
    Returns:
        Tuple[bool, str]: (success, payment_id or error_message)
    """
    get_cursor, execute_query = get_db_connection()
    
    # Validate address
    is_valid, error = validate_ton_address(to_address)
    if not is_valid:
        return False, f"Invalid TON address: {error}"
    
    # Get fee
    fee = get_ton_config('ton_withdrawal_fee', DEFAULT_FEE)
    fee_type = get_ton_config('ton_withdrawal_fee_type', 'fixed')
    
    if fee_type == 'percentage':
        actual_fee = amount * (fee / 100)
    else:
        actual_fee = fee
    
    net_amount = amount - actual_fee
    
    if net_amount <= 0:
        return False, "Amount after fees is zero or negative"
    
    # Generate payment ID
    payment_id = f"ton_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    try:
        execute_query("""
            INSERT INTO ton_payments (
                payment_id, withdrawal_id, user_id, amount, fee, net_amount,
                from_address, to_address, status, payment_type, memo, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            payment_id, withdrawal_id, str(user_id), amount, actual_fee, net_amount,
            TON_WALLET_ADDRESS, to_address, PaymentStatus.PENDING, payment_type,
            memo, created_by
        ))
        
        # Log creation
        log_payment_action(payment_id, 'created', None, PaymentStatus.PENDING,
                          'system', created_by, f"Payment created: {amount} TON to {to_address}")
        
        return True, payment_id
    except Exception as e:
        return False, f"Failed to create payment: {str(e)}"

def get_ton_payment(payment_id: str) -> Optional[dict]:
    """Get TON payment by ID"""
    get_cursor, execute_query = get_db_connection()
    row_to_dict, _, decimal_to_float = get_database_functions()
    
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM ton_payments WHERE payment_id = %s", (payment_id,))
            row = cursor.fetchone()
            if row:
                return row_to_dict(cursor, row)
            return None
    except Exception as e:
        print(f"Error getting TON payment: {e}")
        return None

def get_ton_payments_by_status(status: str, limit: int = 100) -> List[dict]:
    """Get TON payments by status"""
    get_cursor, execute_query = get_db_connection()
    _, rows_to_list, _ = get_database_functions()
    
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM ton_payments 
                WHERE status = %s 
                ORDER BY created_at DESC
                LIMIT %s
            """, (status, limit))
            return rows_to_list(cursor, cursor.fetchall())
    except Exception as e:
        print(f"Error getting TON payments by status: {e}")
        return []

def get_user_ton_payments(user_id: str, limit: int = 50) -> List[dict]:
    """Get TON payments for a user"""
    get_cursor, execute_query = get_db_connection()
    _, rows_to_list, _ = get_database_functions()
    
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM ton_payments 
                WHERE user_id = %s 
                ORDER BY created_at DESC
                LIMIT %s
            """, (str(user_id), limit))
            return rows_to_list(cursor, cursor.fetchall())
    except Exception as e:
        print(f"Error getting user TON payments: {e}")
        return []

def update_ton_payment(payment_id: str, **kwargs) -> bool:
    """Update TON payment fields"""
    get_cursor, execute_query = get_db_connection()
    
    if not kwargs:
        return False
    
    set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [payment_id]
    
    try:
        execute_query(f"""
            UPDATE ton_payments SET {set_clause}
            WHERE payment_id = %s
        """, values)
        return True
    except Exception as e:
        print(f"Error updating TON payment: {e}")
        return False

def log_payment_action(
    payment_id: str,
    action: str,
    old_status: str,
    new_status: str,
    actor_type: str,
    actor_id: str,
    details: str = None,
    ip_address: str = None
) -> bool:
    """Log a payment action for audit trail"""
    get_cursor, execute_query = get_db_connection()
    
    try:
        execute_query("""
            INSERT INTO ton_payment_logs (
                payment_id, action, old_status, new_status,
                actor_type, actor_id, details, ip_address
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (payment_id, action, old_status, new_status, actor_type, actor_id, details, ip_address))
        return True
    except Exception as e:
        print(f"Error logging payment action: {e}")
        return False

def get_payment_logs(payment_id: str) -> List[dict]:
    """Get all logs for a payment"""
    get_cursor, execute_query = get_db_connection()
    _, rows_to_list, _ = get_database_functions()
    
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM ton_payment_logs 
                WHERE payment_id = %s 
                ORDER BY created_at ASC
            """, (payment_id,))
            return rows_to_list(cursor, cursor.fetchall())
    except Exception as e:
        print(f"Error getting payment logs: {e}")
        return []

# ============================================
# TRANSACTION PROCESSING
# ============================================

def send_ton_transaction(
    to_address: str,
    amount: float,
    memo: str = None
) -> Tuple[bool, str]:
    """
    Send TON to an address
    
    This function attempts to send TON using:
    1. External payment service (if configured)
    2. Direct SDK signing (if mnemonic available)
    3. Returns error if neither available
    
    Returns:
        Tuple[bool, str]: (success, tx_hash or error)
    """
    if not is_ton_configured():
        return False, "TON not configured"
    
    # Validate address
    is_valid, error = validate_ton_address(to_address)
    if not is_valid:
        return False, f"Invalid address: {error}"
    
    # Check balance
    success, balance = get_system_wallet_balance()
    if not success:
        return False, "Failed to check wallet balance"
    
    total_needed = amount + 0.05  # Amount + estimated fees
    if balance < total_needed:
        return False, f"Insufficient balance. Have: {balance:.4f}, Need: {total_needed:.4f}"
    
    import requests
    
    # Method 1: External payment service
    external_api = os.environ.get('TON_PAYMENT_SERVICE_URL', '')
    external_key = os.environ.get('TON_PAYMENT_SERVICE_KEY', '')
    
    if external_api and external_key:
        try:
            payload = {
                'to_address': to_address,
                'amount': amount,
                'memo': memo or '',
                'api_key': external_key
            }
            
            response = requests.post(
                f"{external_api}/send",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=60
            )
            
            data = response.json()
            
            if data.get('success'):
                return True, data.get('tx_hash', f"ext_{int(time.time())}")
            
            # Don't fail yet, try SDK method
            print(f"External service failed: {data.get('error')}")
        except Exception as e:
            print(f"External service error: {e}")
    
    # Method 2: Direct SDK signing
    if TON_WALLET_MNEMONIC:
        try:
            from tonsdk.contract.wallet import Wallets, WalletVersionEnum
            from tonsdk.utils import to_nano
            
            mnemonic = TON_WALLET_MNEMONIC.split()
            
            if len(mnemonic) != 24:
                return False, "Invalid mnemonic (must be 24 words)"
            
            # Create wallet from mnemonic
            mnemonics, pub_k, priv_k, wallet = Wallets.from_mnemonics(
                mnemonic,
                WalletVersionEnum.v4r2,
                0  # workchain
            )
            
            # Get current seqno
            client = get_api_client()
            
            # Get seqno using runGetMethod
            seqno_data = client._make_request('GET', 'runGetMethod', {
                'address': TON_WALLET_ADDRESS,
                'method': 'seqno',
                'stack': '[]'
            })
            
            seqno = 0
            if seqno_data.get('ok'):
                stack = seqno_data.get('result', {}).get('stack', [[]])
                if stack and len(stack) > 0:
                    seqno_val = stack[0]
                    if isinstance(seqno_val, list) and len(seqno_val) > 1:
                        seqno = int(seqno_val[1], 16)
                    elif isinstance(seqno_val, (int, str)):
                        seqno = int(seqno_val)
            
            # Create transfer
            transfer = wallet.create_transfer_message(
                to_addr=to_address,
                amount=to_nano(amount, 'ton'),
                seqno=seqno,
                payload=memo or ''
            )
            
            # Send BOC
            boc = base64.b64encode(transfer['message'].to_boc()).decode()
            success, result = client.send_boc(boc)
            
            if success:
                return True, result or f"sdk_{int(time.time())}_{seqno}"
            else:
                return False, result
                
        except ImportError:
            return False, "TON SDK not installed. Install with: pip install tonsdk"
        except Exception as e:
            return False, f"SDK error: {str(e)}"
    
    return False, "No payment method available (configure mnemonic or external service)"

def process_ton_payment(payment_id: str, admin_id: str = None) -> Tuple[bool, str]:
    """
    Process a TON payment
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    payment = get_ton_payment(payment_id)
    
    if not payment:
        return False, "Payment not found"
    
    if payment['status'] not in [PaymentStatus.PENDING, PaymentStatus.APPROVED]:
        return False, f"Invalid payment status: {payment['status']}"
    
    # Update to processing
    old_status = payment['status']
    update_ton_payment(payment_id, status=PaymentStatus.PROCESSING)
    log_payment_action(payment_id, 'processing_started', old_status, PaymentStatus.PROCESSING,
                      'admin' if admin_id else 'system', admin_id or 'system')
    
    # Attempt to send
    memo = payment.get('memo') or f"DOGE PIXEL Payment {payment_id}"
    success, result = send_ton_transaction(
        payment['to_address'],
        float(payment['net_amount']),
        memo
    )
    
    if success:
        # Update to sent
        update_ton_payment(
            payment_id,
            status=PaymentStatus.SENT,
            tx_hash=result,
            sent_at=datetime.now()
        )
        log_payment_action(payment_id, 'sent', PaymentStatus.PROCESSING, PaymentStatus.SENT,
                          'system', 'blockchain', f"TX: {result}")
        
        # Also update the withdrawal if linked
        if payment.get('withdrawal_id'):
            from database import update_withdrawal
            update_withdrawal(
                payment['withdrawal_id'],
                status='completed',
                tx_hash=result,
                processed_at=datetime.now()
            )
        
        return True, f"Payment sent. TX: {result}"
    else:
        # Update retry count
        retry_count = (payment.get('retry_count') or 0) + 1
        max_retries = get_ton_config('ton_retry_max_attempts', 3)
        
        if retry_count >= max_retries:
            update_ton_payment(
                payment_id,
                status=PaymentStatus.FAILED,
                error_message=result,
                retry_count=retry_count,
                last_retry_at=datetime.now()
            )
            log_payment_action(payment_id, 'failed', PaymentStatus.PROCESSING, PaymentStatus.FAILED,
                              'system', 'blockchain', f"Max retries reached. Error: {result}")
            
            # Refund user balance if needed
            _refund_user_balance(payment)
            
            return False, f"Payment failed after {retry_count} attempts: {result}"
        else:
            update_ton_payment(
                payment_id,
                status=PaymentStatus.PENDING,
                error_message=result,
                retry_count=retry_count,
                last_retry_at=datetime.now()
            )
            log_payment_action(payment_id, 'retry_scheduled', PaymentStatus.PROCESSING, PaymentStatus.PENDING,
                              'system', 'system', f"Retry {retry_count}/{max_retries}. Error: {result}")
            
            return False, f"Payment failed, retry scheduled ({retry_count}/{max_retries}): {result}"

def _refund_user_balance(payment: dict) -> bool:
    """Refund user's TON balance for failed payment"""
    try:
        from database import update_balance
        update_balance(payment['user_id'], 'ton', float(payment['amount']), 'add', f'TON payment refund: {payment["amount"]} TON')
        log_payment_action(payment['payment_id'], 'balance_refunded', None, None,
                          'system', 'system', f"Refunded {payment['amount']} TON")
        return True
    except Exception as e:
        print(f"Error refunding balance: {e}")
        return False

def approve_ton_payment(payment_id: str, admin_id: str) -> Tuple[bool, str]:
    """Approve a pending TON payment for processing"""
    payment = get_ton_payment(payment_id)
    
    if not payment:
        return False, "Payment not found"
    
    if payment['status'] != PaymentStatus.PENDING:
        return False, f"Invalid status: {payment['status']}"
    
    update_ton_payment(
        payment_id,
        status=PaymentStatus.APPROVED,
        approved_by=admin_id,
        approved_at=datetime.now()
    )
    
    log_payment_action(payment_id, 'approved', PaymentStatus.PENDING, PaymentStatus.APPROVED,
                      'admin', admin_id, 'Payment approved for processing')
    
    # Check if auto-processing is enabled
    auto_process = get_ton_config('ton_auto_pay_enabled', False)
    if auto_process:
        return process_ton_payment(payment_id, admin_id)
    
    return True, "Payment approved"

def reject_ton_payment(payment_id: str, admin_id: str, reason: str = None) -> Tuple[bool, str]:
    """Reject a TON payment and refund user"""
    payment = get_ton_payment(payment_id)
    
    if not payment:
        return False, "Payment not found"
    
    if payment['status'] not in [PaymentStatus.PENDING, PaymentStatus.APPROVED]:
        return False, f"Cannot reject payment in status: {payment['status']}"
    
    old_status = payment['status']
    
    update_ton_payment(
        payment_id,
        status=PaymentStatus.CANCELLED,
        error_message=reason or 'Rejected by admin'
    )
    
    log_payment_action(payment_id, 'rejected', old_status, PaymentStatus.CANCELLED,
                      'admin', admin_id, reason or 'Rejected by admin')
    
    # Refund user
    _refund_user_balance(payment)
    
    # Update linked withdrawal
    if payment.get('withdrawal_id'):
        from database import update_withdrawal
        update_withdrawal(
            payment['withdrawal_id'],
            status='rejected',
            error_message=reason or 'Rejected by admin',
            processed_at=datetime.now()
        )
    
    return True, "Payment rejected and balance refunded"

def cancel_ton_payment(payment_id: str, admin_id: str = None, reason: str = None) -> Tuple[bool, str]:
    """Cancel a pending TON payment"""
    return reject_ton_payment(payment_id, admin_id or 'system', reason or 'Cancelled')

def retry_ton_payment(payment_id: str, admin_id: str = None) -> Tuple[bool, str]:
    """Retry a failed TON payment"""
    payment = get_ton_payment(payment_id)
    
    if not payment:
        return False, "Payment not found"
    
    if payment['status'] != PaymentStatus.FAILED:
        return False, f"Can only retry failed payments, current status: {payment['status']}"
    
    # Reset to pending
    update_ton_payment(
        payment_id,
        status=PaymentStatus.PENDING,
        retry_count=0,
        error_message=None
    )
    
    log_payment_action(payment_id, 'retry_requested', PaymentStatus.FAILED, PaymentStatus.PENDING,
                      'admin' if admin_id else 'system', admin_id or 'system', 'Manual retry requested')
    
    # Process immediately
    return process_ton_payment(payment_id, admin_id)

# ============================================
# TRANSACTION VERIFICATION
# ============================================

def verify_ton_transaction(tx_hash: str) -> dict:
    """
    Verify a TON transaction on the blockchain
    
    Returns:
        dict: Transaction verification result
    """
    client = get_api_client()
    tx = client.get_transaction_by_hash(tx_hash)
    
    return tx

def check_pending_confirmations() -> List[dict]:
    """Check and update pending transaction confirmations"""
    sent_payments = get_ton_payments_by_status(PaymentStatus.SENT, limit=50)
    results = []
    
    confirmations_required = get_ton_config('ton_confirmations_required', DEFAULT_CONFIRMATIONS)
    
    for payment in sent_payments:
        if not payment.get('tx_hash'):
            continue
        
        tx_info = verify_ton_transaction(payment['tx_hash'])
        
        if tx_info.get('found'):
            # Transaction confirmed on blockchain
            update_ton_payment(
                payment['payment_id'],
                status=PaymentStatus.CONFIRMED,
                confirmations=1,
                confirmed_at=datetime.now()
            )
            
            log_payment_action(payment['payment_id'], 'confirmed', PaymentStatus.SENT, PaymentStatus.CONFIRMED,
                              'blockchain', 'network', f"Transaction confirmed: {payment['tx_hash']}")
            
            results.append({
                'payment_id': payment['payment_id'],
                'status': 'confirmed',
                'tx_hash': payment['tx_hash']
            })
        else:
            # Check if too old (more than 1 hour)
            sent_at = payment.get('sent_at')
            if sent_at:
                if isinstance(sent_at, str):
                    sent_at = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
                
                if datetime.now() - sent_at > timedelta(hours=1):
                    # Mark as potentially failed
                    results.append({
                        'payment_id': payment['payment_id'],
                        'status': 'unconfirmed',
                        'message': 'Transaction not found after 1 hour'
                    })
    
    return results

# ============================================
# STATISTICS AND REPORTING
# ============================================

def get_ton_payment_stats(days: int = 30) -> dict:
    """Get TON payment statistics"""
    get_cursor, execute_query = get_db_connection()
    
    try:
        with get_cursor() as cursor:
            # Overall stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_payments,
                    SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_payments,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_payments,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_payments,
                    SUM(CASE WHEN status = 'confirmed' THEN amount ELSE 0 END) as total_amount,
                    SUM(CASE WHEN status = 'confirmed' THEN fee ELSE 0 END) as total_fees,
                    COUNT(DISTINCT user_id) as unique_users
                FROM ton_payments
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            
            row = cursor.fetchone()
            stats = {
                'total_payments': row['total_payments'] if isinstance(row, dict) else row[0],
                'confirmed_payments': row['confirmed_payments'] if isinstance(row, dict) else row[1],
                'failed_payments': row['failed_payments'] if isinstance(row, dict) else row[2],
                'pending_payments': row['pending_payments'] if isinstance(row, dict) else row[3],
                'total_amount': float(row['total_amount'] or 0) if isinstance(row, dict) else float(row[4] or 0),
                'total_fees': float(row['total_fees'] or 0) if isinstance(row, dict) else float(row[5] or 0),
                'unique_users': row['unique_users'] if isinstance(row, dict) else row[6],
                'period_days': days
            }
            
            # Daily breakdown
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count,
                    SUM(CASE WHEN status = 'confirmed' THEN amount ELSE 0 END) as amount
                FROM ton_payments
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """, (days,))
            
            stats['daily_breakdown'] = []
            for row in cursor.fetchall():
                stats['daily_breakdown'].append({
                    'date': str(row['date'] if isinstance(row, dict) else row[0]),
                    'count': row['count'] if isinstance(row, dict) else row[1],
                    'amount': float(row['amount'] or 0) if isinstance(row, dict) else float(row[2] or 0)
                })
            
            return stats
    except Exception as e:
        print(f"Error getting TON stats: {e}")
        return {}

def get_all_ton_payments(
    limit: int = 100,
    offset: int = 0,
    status: str = None,
    user_id: str = None,
    payment_type: str = None,
    start_date: str = None,
    end_date: str = None
) -> Tuple[List[dict], int]:
    """
    Get all TON payments with filtering and pagination
    
    Returns:
        Tuple[List[dict], int]: (payments, total_count)
    """
    get_cursor, execute_query = get_db_connection()
    _, rows_to_list, _ = get_database_functions()
    
    # Build WHERE clause
    conditions = []
    params = []
    
    if status:
        conditions.append("status = %s")
        params.append(status)
    
    if user_id:
        conditions.append("user_id = %s")
        params.append(str(user_id))
    
    if payment_type:
        conditions.append("payment_type = %s")
        params.append(payment_type)
    
    if start_date:
        conditions.append("created_at >= %s")
        params.append(start_date)
    
    if end_date:
        conditions.append("created_at <= %s")
        params.append(end_date)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    try:
        with get_cursor() as cursor:
            # Get total count
            cursor.execute(f"SELECT COUNT(*) as cnt FROM ton_payments WHERE {where_clause}", params)
            count_row = cursor.fetchone()
            total = count_row['cnt'] if isinstance(count_row, dict) else count_row[0]
            
            # Get payments
            cursor.execute(f"""
                SELECT tp.*, u.username, u.first_name
                FROM ton_payments tp
                LEFT JOIN users u ON tp.user_id = u.user_id
                WHERE {where_clause}
                ORDER BY tp.created_at DESC
                LIMIT %s OFFSET %s
            """, params + [limit, offset])
            
            payments = rows_to_list(cursor, cursor.fetchall())
            
            return payments, total
    except Exception as e:
        print(f"Error getting all TON payments: {e}")
        return [], 0

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_tonscan_link(hash_or_address: str, is_tx: bool = False) -> str:
    """Generate TonScan link"""
    if is_tx:
        return f"{TONSCAN_URL}/tx/{hash_or_address}"
    return f"{TONSCAN_URL}/address/{hash_or_address}"

def format_ton_amount(amount: float) -> str:
    """Format TON amount for display"""
    return f"{amount:.9f}".rstrip('0').rstrip('.')

# ============================================
# CLI TESTING
# ============================================

if __name__ == '__main__':
    import sys
    
    print("TON Payment System - CLI")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("Commands:")
        print("  wallet              - Show wallet info")
        print("  balance <address>   - Get address balance")
        print("  validate <address>  - Validate address")
        print("  config              - Show all config")
        print("  stats               - Show payment stats")
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command == 'wallet':
        info = get_system_wallet_info()
        print(json.dumps(info, indent=2))
    
    elif command == 'balance':
        address = sys.argv[2] if len(sys.argv) > 2 else TON_WALLET_ADDRESS
        success, balance = get_api_client().get_address_balance(address)
        print(f"Balance: {balance:.9f} TON" if success else f"Error: {balance}")
    
    elif command == 'validate':
        if len(sys.argv) > 2:
            valid, msg = validate_ton_address(sys.argv[2])
            print(f"Valid: {valid}, Type: {msg}")
        else:
            print("Usage: validate <address>")
    
    elif command == 'config':
        config = get_all_ton_config()
        print(json.dumps(config, indent=2))
    
    elif command == 'stats':
        stats = get_ton_payment_stats()
        print(json.dumps(stats, indent=2, default=str))
    
    else:
        print(f"Unknown command: {command}")
