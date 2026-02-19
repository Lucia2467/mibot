"""
deposit_system.py - Sistema de depósitos DOGE BEP20 para SALLY-E Bot / DOGE PIXEL
Genera direcciones únicas por usuario y monitorea depósitos entrantes
"""

import os
import uuid
import hashlib
import requests
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List

from db import execute_query, get_cursor
from database import get_user, update_balance, row_to_dict, rows_to_list

# ============================================
# CONFIGURACIÓN
# ============================================
logger = logging.getLogger(__name__)

# DOGE Token Contract Address on BSC (BEP20)
DOGE_BEP20_CONTRACT = "0xba2ae424d960c26247dd6c32edc70b295c744c43"

# BSCScan API
BSCSCAN_API_URL = "https://api.bscscan.com/api"
BSCSCAN_API_KEY = os.environ.get('BSCSCAN_API_KEY', '')

# Configuración de confirmaciones
REQUIRED_CONFIRMATIONS = 12

# Intentar importar web3 para generación de direcciones HD
try:
    from web3 import Web3
    from eth_account import Account
    Account.enable_unaudited_hdwallet_features()
    HD_WALLET_AVAILABLE = True
    logger.info("✅ HD Wallet features available")
except ImportError:
    HD_WALLET_AVAILABLE = False
    logger.warning("⚠️ HD Wallet not available - using single address mode")


# ============================================
# FUNCIONES DE BASE DE DATOS
# ============================================

def init_deposit_tables():
    """Crea las tablas necesarias para el sistema de depósitos"""
    
    tables = [
        # Tabla de direcciones de depósito por usuario
        """
        CREATE TABLE IF NOT EXISTS user_deposit_addresses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL UNIQUE,
            deposit_address VARCHAR(100) NOT NULL UNIQUE,
            derivation_index INT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_deposit_address (deposit_address)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # Tabla de depósitos
        """
        CREATE TABLE IF NOT EXISTS deposits (
            id INT AUTO_INCREMENT PRIMARY KEY,
            deposit_id VARCHAR(100) NOT NULL UNIQUE,
            user_id VARCHAR(50) NOT NULL,
            currency VARCHAR(10) NOT NULL DEFAULT 'DOGE',
            network VARCHAR(20) NOT NULL DEFAULT 'BEP20',
            amount DECIMAL(20, 8) NOT NULL,
            deposit_address VARCHAR(100) NOT NULL,
            tx_hash VARCHAR(100) NOT NULL UNIQUE,
            confirmations INT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            credited TINYINT(1) DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            confirmed_at DATETIME DEFAULT NULL,
            credited_at DATETIME DEFAULT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_status (status),
            INDEX idx_tx_hash (tx_hash),
            INDEX idx_deposit_address (deposit_address)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # Tabla de configuración del sistema de depósitos
        """
        CREATE TABLE IF NOT EXISTS deposit_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value TEXT DEFAULT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_config_key (config_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    ]
    
    for table_sql in tables:
        try:
            execute_query(table_sql)
        except Exception as e:
            logger.error(f"Error creating deposit table: {e}")
    
    # Inicializar configuración por defecto
    default_config = [
        ('last_derivation_index', '0'),
        ('min_deposit_doge', '1'),
        ('required_confirmations', str(REQUIRED_CONFIRMATIONS)),
        ('deposits_enabled', 'true'),
    ]
    
    for key, value in default_config:
        try:
            execute_query("""
                INSERT INTO deposit_config (config_key, config_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE config_key = config_key
            """, (key, value))
        except Exception:
            pass
    
    logger.info("✅ Deposit tables initialized")
    return True


def get_deposit_config(key: str, default: str = '') -> str:
    """Obtiene un valor de configuración de depósitos"""
    try:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT config_value FROM deposit_config WHERE config_key = %s",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    return row.get('config_value', default)
                return row[0] if row[0] else default
            return default
    except Exception as e:
        logger.error(f"Error getting deposit config {key}: {e}")
        return default


def set_deposit_config(key: str, value: str) -> bool:
    """Establece un valor de configuración de depósitos"""
    try:
        execute_query("""
            INSERT INTO deposit_config (config_key, config_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
        """, (key, value))
        return True
    except Exception as e:
        logger.error(f"Error setting deposit config {key}: {e}")
        return False


def get_next_derivation_index() -> int:
    """Obtiene y incrementa el índice de derivación"""
    try:
        current = int(get_deposit_config('last_derivation_index', '0'))
        next_index = current + 1
        set_deposit_config('last_derivation_index', str(next_index))
        return next_index
    except Exception as e:
        logger.error(f"Error getting derivation index: {e}")
        return 1


# ============================================
# GENERACIÓN DE DIRECCIONES HD
# ============================================

def get_or_create_master_seed() -> str:
    """Obtiene o crea el master seed para derivación de direcciones"""
    
    # Primero intentar obtener de variable de entorno
    env_seed = os.environ.get('DEPOSIT_MASTER_SEED', '')
    if env_seed:
        return env_seed
    
    # Luego intentar obtener de la base de datos
    stored_seed = get_deposit_config('master_seed', '')
    if stored_seed:
        return stored_seed
    
    # Si no existe y HD wallet está disponible, generar uno nuevo
    if HD_WALLET_AVAILABLE:
        try:
            from mnemonic import Mnemonic
            mnemo = Mnemonic("english")
            new_mnemonic = mnemo.generate(strength=256)
            set_deposit_config('master_seed', new_mnemonic)
            logger.warning("⚠️ New master seed generated. BACKUP THIS IMMEDIATELY!")
            return new_mnemonic
        except ImportError:
            pass
    
    # Fallback: generar seed determinístico basado en SECRET_KEY
    secret = os.environ.get('SECRET_KEY', 'default_secret_key_change_me')
    fallback_seed = hashlib.sha256(f"DEPOSIT_SEED_{secret}".encode()).hexdigest()
    set_deposit_config('master_seed', fallback_seed)
    logger.warning("⚠️ Using fallback deterministic seed")
    return fallback_seed


def derive_address_from_seed(seed_phrase: str, index: int) -> Optional[str]:
    """
    Deriva una dirección BSC a partir de un seed e índice
    
    Returns:
        address string o None si hay error
    """
    if not HD_WALLET_AVAILABLE:
        return None
    
    try:
        # Si el seed parece ser un mnemonic (tiene espacios)
        if ' ' in seed_phrase:
            derivation_path = f"m/44'/60'/0'/0/{index}"
            account = Account.from_mnemonic(seed_phrase, account_path=derivation_path)
            return account.address
        else:
            # Es un hash, usar como base para generar clave privada
            combined = f"{seed_phrase}_{index}"
            private_key = hashlib.sha256(combined.encode()).hexdigest()
            account = Account.from_key(private_key)
            return account.address
    except Exception as e:
        logger.error(f"Error deriving address at index {index}: {e}")
        return None


def generate_user_deposit_address(user_id: str) -> Optional[Dict]:
    """
    Genera o recupera la dirección de depósito para un usuario
    
    Returns:
        Dict con address y otra info, o None si hay error
    """
    user_id = str(user_id)
    
    try:
        # Verificar si el usuario ya tiene una dirección
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT deposit_address, derivation_index, created_at
                FROM user_deposit_addresses
                WHERE user_id = %s
            """, (user_id,))
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, dict):
                    return {
                        'address': row['deposit_address'],
                        'index': row['derivation_index'],
                        'created_at': row['created_at'],
                        'is_new': False
                    }
                return {
                    'address': row[0],
                    'index': row[1],
                    'created_at': row[2],
                    'is_new': False
                }
        
        # No tiene dirección, generar una nueva
        if HD_WALLET_AVAILABLE:
            master_seed = get_or_create_master_seed()
            derivation_index = get_next_derivation_index()
            address = derive_address_from_seed(master_seed, derivation_index)
            
            if address:
                execute_query("""
                    INSERT INTO user_deposit_addresses (user_id, deposit_address, derivation_index)
                    VALUES (%s, %s, %s)
                """, (user_id, address, derivation_index))
                
                logger.info(f"✅ Generated deposit address for user {user_id}: {address}")
                
                return {
                    'address': address,
                    'index': derivation_index,
                    'created_at': datetime.now(),
                    'is_new': True
                }
        
        # Fallback: usar dirección maestra del admin
        admin_address = os.environ.get('ADMIN_ADDRESS', '')
        if admin_address:
            # En modo fallback, todos usan la misma dirección
            # El admin debe verificar manualmente
            execute_query("""
                INSERT INTO user_deposit_addresses (user_id, deposit_address, derivation_index)
                VALUES (%s, %s, %s)
            """, (user_id, admin_address, 0))
            
            logger.warning(f"⚠️ Using admin address for user {user_id} (manual verification required)")
            
            return {
                'address': admin_address,
                'index': 0,
                'created_at': datetime.now(),
                'is_new': True,
                'manual_mode': True
            }
        
        logger.error("No HD wallet and no admin address configured!")
        return None
        
    except Exception as e:
        logger.error(f"Error generating deposit address for user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_user_deposit_address(user_id: str) -> Optional[str]:
    """Obtiene la dirección de depósito de un usuario (sin crear)"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT deposit_address FROM user_deposit_addresses WHERE user_id = %s
            """, (str(user_id),))
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    return row.get('deposit_address')
                return row[0]
            return None
    except Exception as e:
        logger.error(f"Error getting deposit address: {e}")
        return None


def get_user_by_deposit_address(address: str) -> Optional[str]:
    """Obtiene el user_id asociado a una dirección de depósito"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT user_id FROM user_deposit_addresses WHERE LOWER(deposit_address) = LOWER(%s)
            """, (address,))
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    return row.get('user_id')
                return row[0]
            return None
    except Exception as e:
        logger.error(f"Error getting user by deposit address: {e}")
        return None


# ============================================
# MONITOREO DE DEPÓSITOS
# ============================================

def get_doge_token_transfers(address: str, start_block: int = 0) -> List[Dict]:
    """
    Obtiene las transferencias de DOGE BEP20 a una dirección usando BSCScan API
    """
    try:
        params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': DOGE_BEP20_CONTRACT,
            'address': address,
            'startblock': start_block,
            'endblock': 99999999,
            'sort': 'desc',
        }
        
        if BSCSCAN_API_KEY:
            params['apikey'] = BSCSCAN_API_KEY
        
        response = requests.get(BSCSCAN_API_URL, params=params, timeout=30)
        data = response.json()
        
        if data.get('status') == '1' and data.get('result'):
            return [
                tx for tx in data['result']
                if tx.get('to', '').lower() == address.lower()
            ]
        
        return []
        
    except Exception as e:
        logger.error(f"Error fetching DOGE transfers for {address}: {e}")
        return []


def get_current_block_number() -> int:
    """Obtiene el número de bloque actual de BSC"""
    try:
        params = {
            'module': 'proxy',
            'action': 'eth_blockNumber',
        }
        if BSCSCAN_API_KEY:
            params['apikey'] = BSCSCAN_API_KEY
        
        response = requests.get(BSCSCAN_API_URL, params=params, timeout=10)
        data = response.json()
        
        if data.get('result'):
            return int(data['result'], 16)
        return 0
    except Exception as e:
        logger.error(f"Error getting current block: {e}")
        return 0


def process_deposit_transaction(tx: Dict) -> Optional[str]:
    """
    Procesa una transacción de depósito individual
    
    Returns:
        deposit_id si se creó/actualizó, None si ya existe o hay error
    """
    try:
        tx_hash = tx.get('hash', '')
        to_address = tx.get('to', '')
        value_raw = tx.get('value', '0')
        block_number = int(tx.get('blockNumber', 0))
        
        # DOGE tiene 8 decimales
        decimals = int(tx.get('tokenDecimal', 8))
        amount = Decimal(value_raw) / Decimal(10 ** decimals)
        
        # Obtener el usuario asociado a esta dirección
        user_id = get_user_by_deposit_address(to_address)
        if not user_id:
            logger.warning(f"No user found for deposit address: {to_address}")
            return None
        
        # Verificar si ya existe este depósito
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT deposit_id, status, credited FROM deposits WHERE tx_hash = %s
            """, (tx_hash,))
            existing = cursor.fetchone()
        
        current_block = get_current_block_number()
        confirmations = max(0, current_block - block_number) if current_block > 0 else 0
        required_confirmations = int(get_deposit_config('required_confirmations', str(REQUIRED_CONFIRMATIONS)))
        
        if existing:
            existing_dict = row_to_dict(None, existing) if not isinstance(existing, dict) else existing
            deposit_id = existing_dict.get('deposit_id')
            status = existing_dict.get('status')
            credited = existing_dict.get('credited', 0)
            
            execute_query("""
                UPDATE deposits SET confirmations = %s, updated_at = NOW()
                WHERE tx_hash = %s
            """, (confirmations, tx_hash))
            
            if confirmations >= required_confirmations and not credited and status == 'pending':
                return credit_deposit(deposit_id)
            
            return None
        
        # Crear nuevo registro de depósito
        deposit_id = f"dep_{uuid.uuid4().hex[:12]}"
        status = 'confirmed' if confirmations >= required_confirmations else 'pending'
        
        execute_query("""
            INSERT INTO deposits (
                deposit_id, user_id, currency, network, amount,
                deposit_address, tx_hash, confirmations, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            deposit_id, user_id, 'DOGE', 'BEP20', float(amount),
            to_address, tx_hash, confirmations, status
        ))
        
        logger.info(f"✅ New deposit recorded: {deposit_id} - {amount} DOGE for user {user_id}")
        
        if confirmations >= required_confirmations:
            return credit_deposit(deposit_id)
        
        return deposit_id
        
    except Exception as e:
        logger.error(f"Error processing deposit transaction: {e}")
        import traceback
        traceback.print_exc()
        return None


def credit_deposit(deposit_id: str) -> Optional[str]:
    """
    Acredita un depósito al balance del usuario
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM deposits WHERE deposit_id = %s", (deposit_id,))
            deposit = cursor.fetchone()
        
        if not deposit:
            logger.error(f"Deposit not found: {deposit_id}")
            return None
        
        deposit = row_to_dict(None, deposit) if not isinstance(deposit, dict) else deposit
        
        if deposit.get('credited'):
            logger.warning(f"Deposit already credited: {deposit_id}")
            return None
        
        user_id = deposit.get('user_id')
        amount = float(deposit.get('amount', 0))
        currency = deposit.get('currency', 'DOGE').lower()
        
        update_balance(user_id, currency, amount, 'add', f'Deposit {deposit_id}')
        
        execute_query("""
            UPDATE deposits 
            SET credited = 1, status = 'confirmed', credited_at = NOW(), confirmed_at = NOW()
            WHERE deposit_id = %s
        """, (deposit_id,))
        
        logger.info(f"✅ Deposit credited: {deposit_id} - {amount} {currency.upper()} to user {user_id}")
        
        return deposit_id
        
    except Exception as e:
        logger.error(f"Error crediting deposit {deposit_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def scan_all_deposit_addresses():
    """
    Escanea todas las direcciones de depósito en busca de nuevas transacciones
    """
    try:
        if get_deposit_config('deposits_enabled', 'true').lower() != 'true':
            logger.info("Deposits are disabled, skipping scan")
            return 0
        
        with get_cursor() as cursor:
            cursor.execute("SELECT DISTINCT deposit_address FROM user_deposit_addresses")
            addresses = cursor.fetchall()
        
        if not addresses:
            return 0
        
        processed_count = 0
        
        for row in addresses:
            if isinstance(row, dict):
                address = row.get('deposit_address')
            else:
                address = row[0]
            
            transfers = get_doge_token_transfers(address)
            
            for tx in transfers:
                result = process_deposit_transaction(tx)
                if result:
                    processed_count += 1
        
        if processed_count > 0:
            logger.info(f"✅ Processed {processed_count} new deposits")
        
        return processed_count
        
    except Exception as e:
        logger.error(f"Error scanning deposit addresses: {e}")
        import traceback
        traceback.print_exc()
        return 0


def update_pending_deposits():
    """
    Actualiza las confirmaciones de depósitos pendientes
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT deposit_id, tx_hash, confirmations
                FROM deposits
                WHERE status = 'pending' AND credited = 0
            """)
            pending = cursor.fetchall()
        
        if not pending:
            return 0
        
        current_block = get_current_block_number()
        if current_block == 0:
            return 0
        
        required_confirmations = int(get_deposit_config('required_confirmations', str(REQUIRED_CONFIRMATIONS)))
        credited_count = 0
        
        for row in pending:
            if isinstance(row, dict):
                deposit_id = row.get('deposit_id')
                tx_hash = row.get('tx_hash')
            else:
                deposit_id = row[0]
                tx_hash = row[1]
            
            try:
                params = {
                    'module': 'proxy',
                    'action': 'eth_getTransactionReceipt',
                    'txhash': tx_hash,
                }
                if BSCSCAN_API_KEY:
                    params['apikey'] = BSCSCAN_API_KEY
                
                response = requests.get(BSCSCAN_API_URL, params=params, timeout=10)
                data = response.json()
                
                if data.get('result'):
                    block_number = int(data['result'].get('blockNumber', '0'), 16)
                    confirmations = current_block - block_number
                    
                    execute_query("""
                        UPDATE deposits SET confirmations = %s WHERE deposit_id = %s
                    """, (confirmations, deposit_id))
                    
                    if confirmations >= required_confirmations:
                        if credit_deposit(deposit_id):
                            credited_count += 1
                            
            except Exception as e:
                logger.error(f"Error checking tx {tx_hash}: {e}")
                continue
        
        if credited_count > 0:
            logger.info(f"✅ Credited {credited_count} pending deposits")
        
        return credited_count
        
    except Exception as e:
        logger.error(f"Error updating pending deposits: {e}")
        return 0


# ============================================
# FUNCIONES DE CONSULTA
# ============================================

def get_deposit(deposit_id: str) -> Optional[Dict]:
    """Obtiene un depósito por su ID"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM deposits WHERE deposit_id = %s", (deposit_id,))
            row = cursor.fetchone()
            return row_to_dict(cursor, row) if row else None
    except Exception as e:
        logger.error(f"Error getting deposit: {e}")
        return None


def get_deposit_by_tx_hash(tx_hash: str) -> Optional[Dict]:
    """Obtiene un depósito por su hash de transacción"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM deposits WHERE tx_hash = %s", (tx_hash,))
            row = cursor.fetchone()
            return row_to_dict(cursor, row) if row else None
    except Exception as e:
        logger.error(f"Error getting deposit by tx_hash: {e}")
        return None


def get_user_deposits(user_id: str, limit: int = 20) -> List[Dict]:
    """Obtiene los depósitos de un usuario"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM deposits
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (str(user_id), limit))
            return rows_to_list(cursor, cursor.fetchall())
    except Exception as e:
        logger.error(f"Error getting user deposits: {e}")
        return []


def get_pending_deposits() -> List[Dict]:
    """Obtiene todos los depósitos pendientes"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM deposits
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
            return rows_to_list(cursor, cursor.fetchall())
    except Exception as e:
        logger.error(f"Error getting pending deposits: {e}")
        return []


def get_user_deposit_stats(user_id: str) -> Dict:
    """Obtiene estadísticas de depósitos de un usuario"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_deposits,
                    COALESCE(SUM(CASE WHEN status = 'confirmed' AND credited = 1 THEN amount ELSE 0 END), 0) as total_deposited,
                    COALESCE(SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END), 0) as pending_amount,
                    COALESCE(SUM(CASE WHEN status = 'confirmed' AND credited = 1 THEN 1 ELSE 0 END), 0) as confirmed_count,
                    COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) as pending_count
                FROM deposits
                WHERE user_id = %s
            """, (str(user_id),))
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, dict):
                    return {
                        'total_deposits': int(row.get('total_deposits', 0) or 0),
                        'total_deposited': float(row.get('total_deposited', 0) or 0),
                        'pending_amount': float(row.get('pending_amount', 0) or 0),
                        'confirmed_count': int(row.get('confirmed_count', 0) or 0),
                        'pending_count': int(row.get('pending_count', 0) or 0)
                    }
                return {
                    'total_deposits': int(row[0] or 0),
                    'total_deposited': float(row[1] or 0),
                    'pending_amount': float(row[2] or 0),
                    'confirmed_count': int(row[3] or 0),
                    'pending_count': int(row[4] or 0)
                }
            
            return {
                'total_deposits': 0,
                'total_deposited': 0,
                'pending_amount': 0,
                'confirmed_count': 0,
                'pending_count': 0
            }
    except Exception as e:
        logger.error(f"Error getting deposit stats: {e}")
        return {
            'total_deposits': 0,
            'total_deposited': 0,
            'pending_amount': 0,
            'confirmed_count': 0,
            'pending_count': 0
        }


def format_deposit_for_display(deposit: Dict) -> Dict:
    """Formatea un depósito para mostrar en la UI"""
    if not deposit:
        return None
    
    status_labels = {
        'pending': '⏳ Pending',
        'confirmed': '✅ Confirmed',
        'failed': '❌ Failed'
    }
    
    status_colors = {
        'pending': 'warning',
        'confirmed': 'success',
        'failed': 'danger'
    }
    
    return {
        **deposit,
        'status_label': status_labels.get(deposit.get('status', ''), deposit.get('status', '')),
        'status_color': status_colors.get(deposit.get('status', ''), 'secondary'),
        'amount_formatted': f"{float(deposit.get('amount', 0)):.8f}",
        'tx_hash_short': f"{deposit['tx_hash'][:10]}...{deposit['tx_hash'][-6:]}" if deposit.get('tx_hash') else 'N/A',
        'address_short': f"{deposit['deposit_address'][:8]}...{deposit['deposit_address'][-6:]}" if deposit.get('deposit_address') else 'N/A',
        'bscscan_url': f"https://bscscan.com/tx/{deposit['tx_hash']}" if deposit.get('tx_hash') else None
    }


# ============================================
# INICIALIZACIÓN
# ============================================

def initialize_deposit_system():
    """Inicializa el sistema de depósitos"""
    try:
        init_deposit_tables()
        logger.info("✅ Deposit system initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error initializing deposit system: {e}")
        return False


# Auto-inicializar al importar
try:
    initialize_deposit_system()
except Exception as e:
    logger.warning(f"Could not auto-initialize deposit system: {e}")
