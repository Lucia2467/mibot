"""
payments.py - Integración blockchain para SALLY-E Bot
Maneja transacciones de tokens BEP20 en BSC (Binance Smart Chain)
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()

# Configuration
BSC_RPC = os.environ.get('BSC_RPC', 'https://bsc-dataseed.binance.org/')
ADMIN_ADDRESS = os.environ.get('ADMIN_ADDRESS', '')
ADMIN_PRIVATE_KEY = os.environ.get('ADMIN_PRIVATE_KEY', '')

# Token contracts on BSC (BEP20)
CONTRACTS = {
    'USDT': '0x55d398326f99059fF775485246999027B3197955',  # BSC-USD (USDT)
    'DOGE': '0xbA2aE424d960c26247Dd6c32edC70B295c744C43',  # Binance-Peg Dogecoin
}

# Token decimals
DECIMALS = {
    'USDT': 18,
    'DOGE': 8,
}

# ERC20 ABI (minimal for transfers)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

# Lazy Web3 initialization
_web3 = None

def get_web3():
    """Get or create Web3 instance"""
    global _web3
    if _web3 is None:
        try:
            from web3 import Web3
            _web3 = Web3(Web3.HTTPProvider(BSC_RPC))
            if not _web3.is_connected():
                raise Exception("Could not connect to BSC")
        except ImportError:
            raise Exception("web3 library not installed. Run: pip install web3")
    return _web3

def validate_address(address):
    """
    Valida formato de dirección BEP20/ERC20
    
    Returns:
        bool: True if valid
    """
    if not address:
        return False
    pattern = r'^0x[a-fA-F0-9]{40}$'
    return bool(re.match(pattern, address))

def get_token_contract(currency):
    """
    Obtiene el contrato del token
    
    Returns:
        Contract instance
    """
    currency = currency.upper()
    if currency not in CONTRACTS:
        raise ValueError(f"Unsupported currency: {currency}")
    
    w3 = get_web3()
    contract_address = w3.to_checksum_address(CONTRACTS[currency])
    return w3.eth.contract(address=contract_address, abi=ERC20_ABI)

def get_token_balance(address, currency):
    """
    Obtiene el balance de un token para una dirección
    
    Returns:
        float: Token balance
    """
    w3 = get_web3()
    contract = get_token_contract(currency)
    
    checksum_address = w3.to_checksum_address(address)
    balance_wei = contract.functions.balanceOf(checksum_address).call()
    
    decimals = DECIMALS.get(currency.upper(), 18)
    return balance_wei / (10 ** decimals)

def get_bnb_balance(address):
    """
    Obtiene el balance de BNB (para gas)
    
    Returns:
        float: BNB balance
    """
    w3 = get_web3()
    checksum_address = w3.to_checksum_address(address)
    balance_wei = w3.eth.get_balance(checksum_address)
    return w3.from_wei(balance_wei, 'ether')

def send_crypto(to_address, amount, currency):
    """
    Envía tokens BEP20
    
    Args:
        to_address: Recipient address
        amount: Amount to send
        currency: Token symbol (USDT, DOGE)
    
    Returns:
        tuple: (success: bool, tx_hash or error_message)
    """
    if not ADMIN_ADDRESS or not ADMIN_PRIVATE_KEY:
        return False, "Admin wallet not configured"
    
    if not validate_address(to_address):
        return False, "Invalid recipient address"
    
    currency = currency.upper()
    if currency not in CONTRACTS:
        return False, f"Unsupported currency: {currency}"
    
    try:
        w3 = get_web3()
        
        # Check BNB balance for gas
        bnb_balance = get_bnb_balance(ADMIN_ADDRESS)
        if bnb_balance < 0.001:
            return False, "Insufficient BNB for gas fees"
        
        # Check token balance
        token_balance = get_token_balance(ADMIN_ADDRESS, currency)
        if token_balance < amount:
            return False, f"Insufficient {currency} balance. Have: {token_balance}"
        
        # Get contract
        contract = get_token_contract(currency)
        
        # Convert amount to wei
        decimals = DECIMALS.get(currency, 18)
        amount_wei = int(amount * (10 ** decimals))
        
        # Prepare addresses
        from_address = w3.to_checksum_address(ADMIN_ADDRESS)
        to_address_checksum = w3.to_checksum_address(to_address)
        
        # Get nonce
        nonce = w3.eth.get_transaction_count(from_address)
        
        # Estimate gas
        try:
            gas_estimate = contract.functions.transfer(
                to_address_checksum, amount_wei
            ).estimate_gas({'from': from_address})
            gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
        except:
            gas_limit = 100000  # Default for token transfers
        
        # Get gas price
        gas_price = w3.eth.gas_price
        
        # Build transaction
        tx = contract.functions.transfer(
            to_address_checksum,
            amount_wei
        ).build_transaction({
            'from': from_address,
            'nonce': nonce,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'chainId': 56  # BSC mainnet
        })
        
        # Sign transaction
        private_key = ADMIN_PRIVATE_KEY
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        
        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        
        # Wait for confirmation (with timeout)
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt['status'] == 1:
                return True, tx_hash_hex
            else:
                return False, f"Transaction failed. Hash: {tx_hash_hex}"
        except Exception as e:
            # Transaction sent but not confirmed yet
            return True, tx_hash_hex
        
    except Exception as e:
        return False, str(e)

def get_wallet_info():
    """
    Obtiene información de la wallet del sistema
    
    Returns:
        dict: Wallet info including balances
    """
    if not ADMIN_ADDRESS:
        return {
            'configured': False,
            'error': 'Admin wallet not configured'
        }
    
    try:
        info = {
            'configured': True,
            'address': ADMIN_ADDRESS,
            'bnb_balance': get_bnb_balance(ADMIN_ADDRESS),
        }
        
        # Get token balances
        for currency in CONTRACTS.keys():
            try:
                balance = get_token_balance(ADMIN_ADDRESS, currency)
                info[f'{currency.lower()}_balance'] = balance
            except:
                info[f'{currency.lower()}_balance'] = 0
        
        return info
        
    except Exception as e:
        return {
            'configured': True,
            'address': ADMIN_ADDRESS,
            'error': str(e)
        }

def get_transaction_status(tx_hash):
    """
    Obtiene el estado de una transacción
    
    Returns:
        dict: Transaction status
    """
    try:
        w3 = get_web3()
        
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        
        if receipt is None:
            return {'status': 'pending', 'confirmed': False}
        
        return {
            'status': 'confirmed' if receipt['status'] == 1 else 'failed',
            'confirmed': True,
            'block_number': receipt['blockNumber'],
            'gas_used': receipt['gasUsed']
        }
        
    except Exception as e:
        return {'status': 'unknown', 'error': str(e)}

def get_bscscan_link(tx_hash):
    """
    Genera link a BscScan para una transacción
    
    Returns:
        str: BscScan URL
    """
    return f"https://bscscan.com/tx/{tx_hash}"

# CLI for testing
if __name__ == '__main__':
    import sys
    
    print("SALLY-E Payment System")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'info':
            print("Getting wallet info...")
            info = get_wallet_info()
            for key, value in info.items():
                print(f"  {key}: {value}")
        
        elif command == 'balance':
            if len(sys.argv) > 2:
                address = sys.argv[2]
                print(f"Getting balances for {address}...")
                print(f"  BNB: {get_bnb_balance(address)}")
                for currency in CONTRACTS.keys():
                    print(f"  {currency}: {get_token_balance(address, currency)}")
            else:
                print("Usage: python payments.py balance <address>")
        
        elif command == 'send':
            if len(sys.argv) >= 5:
                to_address = sys.argv[2]
                amount = float(sys.argv[3])
                currency = sys.argv[4].upper()
                
                print(f"Sending {amount} {currency} to {to_address}...")
                success, result = send_crypto(to_address, amount, currency)
                print(f"  Success: {success}")
                print(f"  Result: {result}")
                if success:
                    print(f"  BscScan: {get_bscscan_link(result)}")
            else:
                print("Usage: python payments.py send <to_address> <amount> <currency>")
        
        elif command == 'validate':
            if len(sys.argv) > 2:
                address = sys.argv[2]
                valid = validate_address(address)
                print(f"Address {address} is {'valid' if valid else 'invalid'}")
            else:
                print("Usage: python payments.py validate <address>")
        
        else:
            print(f"Unknown command: {command}")
    else:
        print("Commands:")
        print("  info                        - Show wallet info")
        print("  balance <address>           - Get address balances")
        print("  send <to> <amount> <token>  - Send tokens")
        print("  validate <address>          - Validate address format")
