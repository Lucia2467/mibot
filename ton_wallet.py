"""
ton_wallet.py — tonutils con ToncenterV2Client (tonutils 2.x)
"""
import asyncio
import logging
import re
import threading

logger = logging.getLogger(__name__)

TON_TO_NANO = 1_000_000_000

# Thread-local storage for event loops
_local = threading.local()


def _get_loop():
    """Get or create an event loop for the current thread."""
    loop = getattr(_local, 'loop', None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _local.loop = loop
    return loop


def send_ton(mnemonic, to_addr, ton_amount, memo='', api_key='',
             bot_wallet_address=''):
    try:
        if isinstance(mnemonic, str):
            words = mnemonic.strip().split()
        else:
            words = list(mnemonic)

        if len(words) != 24:
            return False, None, f'Mnemonic necesita 24 palabras (tiene {len(words)})'

        if not api_key:
            return False, None, 'TONCENTER_API_KEY no configurada'

        loop = _get_loop()
        try:
            return loop.run_until_complete(
                _send(words, to_addr, float(ton_amount), memo, api_key)
            )
        except Exception:
            # If loop had issues, create a fresh one
            loop = asyncio.new_event_loop()
            _local.loop = loop
            return loop.run_until_complete(
                _send(words, to_addr, float(ton_amount), memo, api_key)
            )

    except Exception as e:
        logger.exception(f'send_ton error: {e}')
        return False, None, str(e)


def _extract_hash(tx) -> str:
    """Extrae hash hex limpio de 64 chars del resultado de tonutils."""
    for attr in ('hash', 'cell_hash', 'tx_hash', 'body_hash'):
        val = getattr(tx, attr, None)
        if val is not None:
            if isinstance(val, bytes):
                return val.hex()
            s = str(val).strip()
            if re.match(r'^[0-9a-fA-F]{64}$', s):
                return s

    try:
        h = tx.hash()
        if isinstance(h, bytes):
            return h.hex()
        s = str(h).strip()
        if re.match(r'^[0-9a-fA-F]{64}$', s):
            return s
    except Exception:
        pass

    s = str(tx)
    matches = re.findall(r'[0-9a-fA-F]{64}', s)
    if matches:
        return matches[0]

    return s[:190]


def _make_client(api_key):
    """Create ToncenterClient para tonutils 2.x (NetworkGlobalID enum)."""
    # tonutils 2.x: ToncenterClient(NetworkGlobalID, api_key=...)
    try:
        from tonutils.clients import ToncenterClient
        from tonutils.types import NetworkGlobalID
        logger.info("[ton] Using ToncenterClient (tonutils 2.x) with MAINNET")
        return ToncenterClient(NetworkGlobalID.MAINNET, api_key=api_key)
    except ImportError:
        logger.warning("[ton] tonutils.clients no disponible")
    except Exception as e:
        logger.error(f"[ton] ToncenterClient (2.x) failed: {e}")
        raise


async def _send(words, to_addr, ton_amount, memo, api_key):
    from tonutils.contracts.wallet import WalletV5R1

    amount_nano = int(round(ton_amount * TON_TO_NANO))
    client = _make_client(api_key)

    async with client:
        result = WalletV5R1.from_mnemonic(client, words)
        if asyncio.iscoroutine(result):
            result = await result
        wallet = result[0] if isinstance(result, (tuple, list)) else result

        logger.info(f'Enviando {ton_amount} TON ({amount_nano} nanotons) -> {to_addr}')
        tx = await wallet.transfer(
            destination=to_addr,
            amount=amount_nano,
            body=memo if memo else None
        )

        tx_hash = _extract_hash(tx)
        logger.info(f'SUCCESS tx_hash={tx_hash}')
        return True, tx_hash, None
