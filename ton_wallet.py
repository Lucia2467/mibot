"""
ton_wallet.py — tonutils con ToncenterClient
"""
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

TON_TO_NANO = 1_000_000_000


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

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError
            return loop.run_until_complete(
                _send(words, to_addr, float(ton_amount), memo, api_key)
            )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    _send(words, to_addr, float(ton_amount), memo, api_key)
                )
            finally:
                loop.close()

    except Exception as e:
        logger.exception(f'send_ton error: {e}')
        return False, None, str(e)


def _extract_hash(tx) -> str:
    """Extrae hash hex limpio de 64 chars del resultado de tonutils."""
    # Intentar atributos directos primero
    for attr in ('hash', 'cell_hash', 'tx_hash', 'body_hash'):
        val = getattr(tx, attr, None)
        if val is not None:
            if isinstance(val, bytes):
                return val.hex()
            s = str(val).strip()
            if re.match(r'^[0-9a-fA-F]{64}$', s):
                return s

    # Intentar método hash()
    try:
        h = tx.hash()
        if isinstance(h, bytes):
            return h.hex()
        s = str(h).strip()
        if re.match(r'^[0-9a-fA-F]{64}$', s):
            return s
    except Exception:
        pass

    # Buscar patrón hex de 64 chars dentro del string del objeto
    s = str(tx)
    matches = re.findall(r'[0-9a-fA-F]{64}', s)
    if matches:
        return matches[0]

    # Último recurso: truncar
    return s[:190]


async def _send(words, to_addr, ton_amount, memo, api_key):
    from tonutils.contracts.wallet import WalletV5R1

    amount_nano = int(round(ton_amount * TON_TO_NANO))

    # Try each known API variant in order of newest → oldest
    client = None
    # 1) tonutils >= some version: tonutils.client (no 's'), is_testnet kwarg
    try:
        from tonutils.client import ToncenterClient as _TC
        client = _TC(api_key=api_key, is_testnet=False)
    except (ImportError, TypeError):
        pass

    # 2) tonutils.client with ToncenterV2Client name
    if client is None:
        try:
            from tonutils.client import ToncenterV2Client as _TC2
            client = _TC2(api_key=api_key, is_testnet=False)
        except (ImportError, TypeError):
            pass

    # 3) tonutils.clients (with 's'): pass base_url explicitly (avoids network arg)
    if client is None:
        try:
            from tonutils.clients import ToncenterClient as _TC3
            client = _TC3(
                base_url='https://toncenter.com/api/v2/',
                api_key=api_key
            )
        except (ImportError, TypeError):
            pass

    # 4) tonutils.clients with is_testnet kwarg (older)
    if client is None:
        from tonutils.clients import ToncenterClient as _TC4
        client = _TC4(api_key=api_key, is_testnet=False)

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
