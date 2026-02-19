"""
ton_deposit_system.py - Sistema de depósitos TON para SALLY-E Bot
Verifica transacciones en la blockchain TON antes de acreditar saldo.
"""

import os
import time
import hashlib
import logging
import requests
from datetime import datetime
from decimal import Decimal
from db import execute_query, get_cursor

# Configuración de logging
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN TON
# ============================================

# Wallet receptora de depósitos (configurable via .env)
DEPOSIT_WALLET_ADDRESS = os.environ.get('TON_DEPOSIT_WALLET', os.environ.get('TON_WALLET_ADDRESS', ''))

# API de TON
TON_API_URL = os.environ.get('TON_API_URL', 'https://toncenter.com/api/v2')
TON_API_KEY = os.environ.get('TON_API_KEY', '')

# Mínimo depósito (en TON)
MIN_DEPOSIT_TON = float(os.environ.get('MIN_DEPOSIT_TON', '0.1'))

# Confirmaciones requeridas (para seguridad)
REQUIRED_CONFIRMATIONS = 1

# ============================================
# INICIALIZACIÓN DE TABLA
# ============================================

def init_deposits_table():
    """Crea la tabla de depósitos si no existe"""
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS ton_deposits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                deposit_id VARCHAR(100) NOT NULL UNIQUE,
                user_id VARCHAR(50) NOT NULL,
                wallet_origin VARCHAR(100) NOT NULL,
                wallet_destination VARCHAR(100) NOT NULL,
                tx_hash VARCHAR(100) UNIQUE,
                lt BIGINT DEFAULT NULL,
                amount DECIMAL(20, 9) NOT NULL,
                status ENUM('pending', 'confirming', 'confirmed', 'failed', 'expired') DEFAULT 'pending',
                error_message TEXT DEFAULT NULL,
                credited_at DATETIME DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_tx_hash (tx_hash),
                INDEX idx_status (status),
                INDEX idx_wallet_origin (wallet_origin)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("✅ Tabla ton_deposits creada/verificada")
        return True
    except Exception as e:
        logger.error(f"❌ Error creando tabla ton_deposits: {e}")
        return False

# Inicializar tabla al importar
init_deposits_table()

# ============================================
# FUNCIONES DE UTILIDAD
# ============================================

def generate_deposit_id(user_id):
    """Genera un ID único para el depósito"""
    timestamp = int(time.time() * 1000)
    data = f"{user_id}:{timestamp}:{os.urandom(8).hex()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]

def nano_to_ton(nano_amount):
    """Convierte nanoTON a TON"""
    return Decimal(str(nano_amount)) / Decimal('1000000000')

def ton_to_nano(ton_amount):
    """Convierte TON a nanoTON"""
    return int(Decimal(str(ton_amount)) * Decimal('1000000000'))

def normalize_ton_address(address):
    """Normaliza dirección TON a formato user-friendly"""
    if not address:
        return None
    address = address.strip()
    # Ya está en formato user-friendly
    if address.startswith(('EQ', 'UQ', 'Ef', 'Uf', 'kQ', 'kf', '0Q', '0f')):
        return address
    return address

# ============================================
# API TON CENTER
# ============================================

def get_ton_headers():
    """Obtiene headers para API de TON"""
    headers = {'Content-Type': 'application/json'}
    if TON_API_KEY:
        headers['X-API-Key'] = TON_API_KEY
    return headers

def verify_transaction_on_blockchain(tx_hash, expected_destination, expected_amount, wallet_origin=None):
    """
    Verifica una transacción en la blockchain TON.
    
    Args:
        tx_hash: Hash de la transacción
        expected_destination: Dirección de destino esperada (nuestra wallet)
        expected_amount: Monto esperado en TON
        wallet_origin: Dirección de origen (opcional, para verificación adicional)
    
    Returns:
        dict: {verified: bool, message: str, actual_amount: float, confirmations: int}
    """
    try:
        if not tx_hash:
            return {'verified': False, 'message': 'Hash de transacción requerido'}
        
        # Buscar transacción por hash usando getTransactions
        url = f"{TON_API_URL}/getTransactions"
        
        # Primero, obtener información de la wallet destino
        params = {
            'address': expected_destination,
            'limit': 100,  # Buscar en las últimas 100 transacciones
            'archival': True
        }
        
        response = requests.get(url, params=params, headers=get_ton_headers(), timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Error API TON: {response.status_code} - {response.text}")
            return {'verified': False, 'message': f'Error API: {response.status_code}'}
        
        data = response.json()
        
        if not data.get('ok'):
            return {'verified': False, 'message': data.get('error', 'Error desconocido')}
        
        transactions = data.get('result', [])
        
        # Buscar la transacción específica
        for tx in transactions:
            # Obtener hash de la transacción
            tx_id = tx.get('transaction_id', {})
            current_hash = tx_id.get('hash', '')
            
            # Comparar hashes (pueden estar en diferentes formatos)
            if current_hash == tx_hash or tx_hash in current_hash:
                # Verificar que es una transacción entrante
                in_msg = tx.get('in_msg', {})
                
                if not in_msg:
                    continue
                
                # Obtener monto
                value = int(in_msg.get('value', 0))
                actual_amount = float(nano_to_ton(value))
                
                # Obtener origen
                source = in_msg.get('source', '')
                
                # Verificar origen si se especificó
                if wallet_origin and source:
                    if normalize_ton_address(source) != normalize_ton_address(wallet_origin):
                        return {
                            'verified': False, 
                            'message': 'Origen de transacción no coincide',
                            'actual_amount': actual_amount
                        }
                
                # Verificar monto (con tolerancia del 1% por comisiones)
                tolerance = float(expected_amount) * 0.01
                if actual_amount < (float(expected_amount) - tolerance):
                    return {
                        'verified': False,
                        'message': f'Monto incorrecto. Esperado: {expected_amount} TON, Recibido: {actual_amount} TON',
                        'actual_amount': actual_amount
                    }
                
                # Transacción verificada
                return {
                    'verified': True,
                    'message': 'Transacción verificada correctamente',
                    'actual_amount': actual_amount,
                    'confirmations': REQUIRED_CONFIRMATIONS,
                    'source': source,
                    'lt': tx_id.get('lt')
                }
        
        return {'verified': False, 'message': 'Transacción no encontrada en blockchain'}
        
    except requests.exceptions.Timeout:
        return {'verified': False, 'message': 'Timeout conectando a TON API'}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de conexión TON API: {e}")
        return {'verified': False, 'message': f'Error de conexión: {str(e)}'}
    except Exception as e:
        logger.error(f"Error verificando transacción: {e}")
        return {'verified': False, 'message': f'Error interno: {str(e)}'}

def check_incoming_transactions(wallet_address, since_lt=None, limit=50):
    """
    Obtiene transacciones entrantes recientes a una wallet.
    
    Args:
        wallet_address: Dirección de la wallet
        since_lt: Logical time desde el cual buscar
        limit: Límite de transacciones
    
    Returns:
        list: Lista de transacciones entrantes
    """
    try:
        url = f"{TON_API_URL}/getTransactions"
        params = {
            'address': wallet_address,
            'limit': limit,
            'archival': True
        }
        
        if since_lt:
            params['lt'] = since_lt
        
        response = requests.get(url, params=params, headers=get_ton_headers(), timeout=30)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        
        if not data.get('ok'):
            return []
        
        transactions = data.get('result', [])
        incoming = []
        
        for tx in transactions:
            in_msg = tx.get('in_msg', {})
            if in_msg and in_msg.get('value', 0) > 0:
                tx_id = tx.get('transaction_id', {})
                incoming.append({
                    'hash': tx_id.get('hash'),
                    'lt': tx_id.get('lt'),
                    'source': in_msg.get('source'),
                    'value': float(nano_to_ton(int(in_msg.get('value', 0)))),
                    'message': in_msg.get('message', ''),
                    'timestamp': tx.get('utime', 0)
                })
        
        return incoming
        
    except Exception as e:
        logger.error(f"Error obteniendo transacciones: {e}")
        return []

# ============================================
# OPERACIONES DE DEPÓSITO
# ============================================

def create_deposit_intent(user_id, amount, wallet_origin):
    """
    Crea una intención de depósito (estado: pending).
    El usuario debe enviar la transacción y luego confirmar.
    
    Args:
        user_id: ID del usuario
        amount: Monto en TON
        wallet_origin: Wallet desde donde enviará
    
    Returns:
        dict: {success: bool, deposit_id: str, wallet_destination: str, ...}
    """
    try:
        # Validar monto mínimo
        amount = float(amount)
        if amount < MIN_DEPOSIT_TON:
            return {
                'success': False, 
                'error': f'Monto mínimo: {MIN_DEPOSIT_TON} TON'
            }
        
        # Validar wallet origen
        if not wallet_origin:
            return {'success': False, 'error': 'Wallet de origen requerida'}
        
        # Verificar que tenemos wallet de destino configurada
        if not DEPOSIT_WALLET_ADDRESS:
            return {'success': False, 'error': 'Sistema de depósitos no configurado'}
        
        # Generar ID único
        deposit_id = generate_deposit_id(user_id)
        
        # Crear registro de depósito pendiente
        execute_query("""
            INSERT INTO ton_deposits 
            (deposit_id, user_id, wallet_origin, wallet_destination, amount, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """, (deposit_id, str(user_id), wallet_origin, DEPOSIT_WALLET_ADDRESS, amount))
        
        logger.info(f"✅ Depósito creado: {deposit_id} - {amount} TON de {wallet_origin}")
        
        return {
            'success': True,
            'deposit_id': deposit_id,
            'wallet_destination': DEPOSIT_WALLET_ADDRESS,
            'amount': amount,
            'status': 'pending',
            'message': f'Envía {amount} TON a la wallet indicada'
        }
        
    except Exception as e:
        logger.error(f"Error creando depósito: {e}")
        return {'success': False, 'error': str(e)}

def confirm_deposit(deposit_id, tx_hash, user_id=None):
    """
    Confirma un depósito verificando la transacción en blockchain.
    
    Args:
        deposit_id: ID del depósito
        tx_hash: Hash de la transacción TON
        user_id: ID del usuario (para verificación adicional)
    
    Returns:
        dict: {success: bool, message: str, amount_credited: float}
    """
    try:
        # Obtener depósito
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM ton_deposits WHERE deposit_id = %s
            """, (deposit_id,))
            deposit = cursor.fetchone()
        
        if not deposit:
            return {'success': False, 'error': 'Depósito no encontrado'}
        
        # Verificar usuario
        if user_id and str(deposit['user_id']) != str(user_id):
            return {'success': False, 'error': 'Depósito no pertenece a este usuario'}
        
        # Verificar estado
        if deposit['status'] == 'confirmed':
            return {'success': False, 'error': 'Este depósito ya fue confirmado'}
        
        if deposit['status'] not in ['pending', 'confirming']:
            return {'success': False, 'error': f'Estado inválido: {deposit["status"]}'}
        
        # Verificar que el hash no fue usado antes
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id FROM ton_deposits 
                WHERE tx_hash = %s AND status = 'confirmed' AND id != %s
            """, (tx_hash, deposit['id']))
            existing = cursor.fetchone()
        
        if existing:
            return {'success': False, 'error': 'Esta transacción ya fue utilizada'}
        
        # Actualizar estado a "confirming"
        execute_query("""
            UPDATE ton_deposits 
            SET status = 'confirming', tx_hash = %s, updated_at = NOW()
            WHERE deposit_id = %s
        """, (tx_hash, deposit_id))
        
        # Verificar transacción en blockchain
        verification = verify_transaction_on_blockchain(
            tx_hash=tx_hash,
            expected_destination=deposit['wallet_destination'],
            expected_amount=float(deposit['amount']),
            wallet_origin=deposit['wallet_origin']
        )
        
        if not verification.get('verified'):
            # Transacción no verificada
            execute_query("""
                UPDATE ton_deposits 
                SET status = 'pending', 
                    error_message = %s,
                    updated_at = NOW()
                WHERE deposit_id = %s
            """, (verification.get('message', 'Error de verificación'), deposit_id))
            
            return {
                'success': False, 
                'error': verification.get('message', 'No se pudo verificar la transacción')
            }
        
        # ¡Transacción verificada! Acreditar saldo
        actual_amount = verification.get('actual_amount', float(deposit['amount']))
        
        # Acreditar TON al usuario
        success = credit_ton_balance(deposit['user_id'], actual_amount, deposit_id)
        
        if not success:
            execute_query("""
                UPDATE ton_deposits 
                SET status = 'failed', 
                    error_message = 'Error acreditando saldo',
                    updated_at = NOW()
                WHERE deposit_id = %s
            """, (deposit_id,))
            return {'success': False, 'error': 'Error acreditando saldo'}
        
        # Actualizar depósito como confirmado
        execute_query("""
            UPDATE ton_deposits 
            SET status = 'confirmed',
                amount = %s,
                lt = %s,
                credited_at = NOW(),
                updated_at = NOW()
            WHERE deposit_id = %s
        """, (actual_amount, verification.get('lt'), deposit_id))
        
        logger.info(f"✅ Depósito confirmado: {deposit_id} - {actual_amount} TON")
        
        return {
            'success': True,
            'message': 'Depósito confirmado y acreditado',
            'amount_credited': actual_amount,
            'tx_hash': tx_hash
        }
        
    except Exception as e:
        logger.error(f"Error confirmando depósito: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

def credit_ton_balance(user_id, amount, deposit_id):
    """
    Acredita TON al balance del usuario.
    SOLO se llama desde el backend después de verificación.
    
    Args:
        user_id: ID del usuario
        amount: Monto en TON
        deposit_id: ID del depósito (para registro)
    
    Returns:
        bool: True si se acreditó correctamente
    """
    try:
        from database import get_user, update_balance
        
        user = get_user(user_id)
        if not user:
            logger.error(f"Usuario no encontrado: {user_id}")
            return False
        
        # Obtener balance actual
        current_balance = float(user.get('ton_balance', 0))
        new_balance = current_balance + float(amount)
        
        # Actualizar balance
        update_balance(user_id, 'ton', amount, 'add', f'TON Deposit: {amount} TON')
        
        # Registrar en historial
        try:
            execute_query("""
                INSERT INTO balance_history 
                (user_id, action, currency, amount, balance_before, balance_after, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                str(user_id), 
                'deposit', 
                'TON', 
                amount, 
                current_balance, 
                new_balance,
                f'TON Deposit - ID: {deposit_id}'
            ))
        except Exception as e:
            logger.warning(f"No se pudo registrar historial: {e}")
        
        logger.info(f"✅ Balance acreditado: {user_id} +{amount} TON (nuevo: {new_balance})")
        return True
        
    except Exception as e:
        logger.error(f"Error acreditando balance: {e}")
        return False

# ============================================
# CONSULTAS
# ============================================

def get_deposit(deposit_id):
    """Obtiene un depósito por ID"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM ton_deposits WHERE deposit_id = %s
            """, (deposit_id,))
            row = cursor.fetchone()
            if row:
                return dict(row) if hasattr(row, 'keys') else row
        return None
    except Exception as e:
        logger.error(f"Error obteniendo depósito: {e}")
        return None

def get_user_deposits(user_id, status=None, limit=50):
    """Obtiene depósitos de un usuario"""
    try:
        with get_cursor() as cursor:
            if status:
                cursor.execute("""
                    SELECT * FROM ton_deposits 
                    WHERE user_id = %s AND status = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (str(user_id), status, limit))
            else:
                cursor.execute("""
                    SELECT * FROM ton_deposits 
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (str(user_id), limit))
            
            rows = cursor.fetchall()
            return [dict(row) if hasattr(row, 'keys') else row for row in rows]
    except Exception as e:
        logger.error(f"Error obteniendo depósitos: {e}")
        return []

def get_pending_deposits():
    """Obtiene todos los depósitos pendientes"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM ton_deposits 
                WHERE status IN ('pending', 'confirming')
                ORDER BY created_at ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) if hasattr(row, 'keys') else row for row in rows]
    except Exception as e:
        logger.error(f"Error obteniendo depósitos pendientes: {e}")
        return []

def cancel_deposit(deposit_id, user_id=None):
    """Cancela un depósito pendiente"""
    try:
        deposit = get_deposit(deposit_id)
        
        if not deposit:
            return {'success': False, 'error': 'Depósito no encontrado'}
        
        if user_id and str(deposit['user_id']) != str(user_id):
            return {'success': False, 'error': 'No autorizado'}
        
        if deposit['status'] not in ['pending']:
            return {'success': False, 'error': 'Solo se pueden cancelar depósitos pendientes'}
        
        execute_query("""
            UPDATE ton_deposits 
            SET status = 'expired', updated_at = NOW()
            WHERE deposit_id = %s
        """, (deposit_id,))
        
        return {'success': True, 'message': 'Depósito cancelado'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_deposit_stats(user_id=None):
    """Obtiene estadísticas de depósitos"""
    try:
        with get_cursor() as cursor:
            if user_id:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_deposits,
                        SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_deposits,
                        SUM(CASE WHEN status = 'confirmed' THEN amount ELSE 0 END) as total_deposited
                    FROM ton_deposits
                    WHERE user_id = %s
                """, (str(user_id),))
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_deposits,
                        SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_deposits,
                        SUM(CASE WHEN status = 'confirmed' THEN amount ELSE 0 END) as total_deposited
                    FROM ton_deposits
                """)
            
            row = cursor.fetchone()
            if row:
                return {
                    'total_deposits': int(row['total_deposits'] or 0),
                    'confirmed_deposits': int(row['confirmed_deposits'] or 0),
                    'total_deposited': float(row['total_deposited'] or 0)
                }
        return {'total_deposits': 0, 'confirmed_deposits': 0, 'total_deposited': 0}
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return {'total_deposits': 0, 'confirmed_deposits': 0, 'total_deposited': 0}

# ============================================
# INFORMACIÓN DEL SISTEMA
# ============================================

def get_deposit_config():
    """Obtiene configuración de depósitos"""
    return {
        'deposit_wallet': DEPOSIT_WALLET_ADDRESS,
        'min_deposit': MIN_DEPOSIT_TON,
        'enabled': bool(DEPOSIT_WALLET_ADDRESS),
        'network': 'mainnet' if 'mainnet' in TON_API_URL.lower() or 'toncenter' in TON_API_URL.lower() else 'testnet'
    }
