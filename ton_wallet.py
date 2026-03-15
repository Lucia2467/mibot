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
    """Create ToncenterClient — tries every known API variant."""
    # Try tonutils.client (2.x, no 's') — ToncenterV2Client
    try:
        from tonutils.client import ToncenterV2Client
        logger.info("[ton] Using ToncenterV2Client from tonutils.client")
        return ToncenterV2Client(api_key=api_key, is_testnet=False)
    except ImportError:
        logger.info("[ton] ToncenterV2Client not found")
    except Exception as e:
        logger.warning(f"[ton] ToncenterV2Client failed: {e}")

    # Try tonutils.client — ToncenterV3Client
    try:
        from tonutils.client import ToncenterV3Client
        logger.info("[ton] Using ToncenterV3Client from tonutils.client")
        return ToncenterV3Client(api_key=api_key, is_testnet=False)
    except ImportError:
        logger.info("[ton] ToncenterV3Client not found")
    except Exception as e:
        logger.warning(f"[ton] ToncenterV3Client failed: {e}")

    # Try tonutils.client — ToncenterClient (new path)
    try:
        from tonutils.client import ToncenterClient
        logger.info("[ton] Using ToncenterClient from tonutils.client")
        return ToncenterClient(api_key=api_key, is_testnet=False)
    except ImportError:
        logger.info("[ton] tonutils.client.ToncenterClient not found")
    except TypeError:
        # needs network as positional arg
        try:
            from tonutils.client import ToncenterClient
            return ToncenterClient('https://toncenter.com/api/v2/', api_key=api_key)
        except Exception as e:
            logger.warning(f"[ton] tonutils.client.ToncenterClient with URL failed: {e}")

    # Last resort: tonutils.clients (old path, 's') — pass URL as network
    try:
        from tonutils.clients import ToncenterClient
        logger.info("[ton] Using ToncenterClient from tonutils.clients with URL")
        return ToncenterClient('https://toncenter.com/api/v2/', api_key=api_key)
    except Exception as e:
        logger.error(f"[ton] All client variants failed. Last error: {e}")
        # Log what IS available
        try:
            import tonutils.client as tc
            logger.error(f"[ton] tonutils.client has: {dir(tc)}")
        except Exception:
            pass
        try:
            import tonutils.clients as tcs
            logger.error(f"[ton] tonutils.clients has: {dir(tcs)}")
        except Exception:
            pass
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
