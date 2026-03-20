"""
withdrawal_notifications.py - Sistema de Notificaciones de Retiros
ARCADE PXC - PARTE 1/2

TODAS las notificaciones se envían en el idioma del usuario.
Cada idioma tiene su propio banner.
INCLUYE BOTONES para Bot y Canal Oficial
"""

import os
import requests
from datetime import datetime

# ============== DATABASE IMPORT ==============
try:
    from database import get_user, get_withdrawal
    print("[withdrawal_notifications] ✅ Database functions imported")
except ImportError as e:
    print(f"[withdrawal_notifications] ⚠️ Database import failed: {e}")
    def get_user(user_id):
        return None
    def get_withdrawal(withdrawal_id):
        return None

# ============== CONFIGURATION ==============

def get_pending_channel():
    return os.environ.get('WITHDRAWALS_PENDING_CHANNEL', '')

def get_success_channel():
    return os.environ.get('WITHDRAWALS_SUCCESS_CHANNEL', '')

def get_bot_token():
    return os.environ.get('BOT_TOKEN', '')

# Currency configuration
CURRENCY_CONFIG = {
    'DOGE': {'network': 'BEP-20', 'explorer': 'https://bscscan.com/tx/'},
    'TON': {'network': 'TON Network', 'explorer': 'https://tonscan.org/tx/'},
    'USDT': {'network': 'BEP-20', 'explorer': 'https://bscscan.com/tx/'},
    'PXC': {'network': 'Internal', 'explorer': None}
}

# ============== BANNER CONFIGURATION BY LANGUAGE ==============

BANNER_URLS = {
    'en': 'https://i.postimg.cc/280qTLtp/file-000000008ea0720eb15afae27fc94a2d.png',  # English banner
    'es': 'https://i.postimg.cc/8PKfprNS/file-00000000fbc0720e85c69f7767c3b428.png',  # Spanish banner
    'pt': 'https://i.postimg.cc/280qTLtp/file-000000008ea0720eb15afae27fc94a2d.png',  # Portuguese banner
    'ru': 'https://i.postimg.cc/wMvzBMQs/file-00000000b97071f584aaa9caf2b3a37c.png',  # Russian banner
    'ar': 'https://i.postimg.cc/26HpgmN1/file-00000000521871f5893de34756d20df8.png'   # Arabic banner
}

def get_banner_url(lang='es'):
    """Get banner URL for specific language"""
    return BANNER_URLS.get(lang, BANNER_URLS['es'])

# ============== TRANSLATIONS - ALL 5 LANGUAGES ==============

TRANSLATIONS = {
    'en': {
        'new_withdrawal': 'NEW WITHDRAWAL REQUEST',
        'withdrawal_approved': 'WITHDRAWAL APPROVED',
        'withdrawal_rejected': 'WITHDRAWAL REJECTED',
        'user': 'User',
        'user_id': 'User ID',
        'amount': 'Amount',
        'network': 'Network',
        'wallet': 'Wallet',
        'status': 'Status',
        'pending': 'Pending',
        'completed': 'Completed',
        'rejected': 'Rejected',
        'date': 'Date',
        'tx_hash': 'TX Hash',
        'reason': 'Reason',
        'view_explorer': 'View in Explorer',
        'requires_approval': 'Requires manual approval',
        'processed_success': 'Withdrawal processed successfully',
        'balance_refunded': 'Balance has been refunded to your account',
        'thanks': 'Thank you for using ARCADE PXC!',
        'withdrawal_id': 'Withdrawal ID',
        'btn_bot': '🤖 Go to Bot',
        'btn_channel': '📢 Official Channel'
    },
    'es': {
        'new_withdrawal': 'NUEVA SOLICITUD DE RETIRO',
        'withdrawal_approved': 'RETIRO APROBADO',
        'withdrawal_rejected': 'RETIRO RECHAZADO',
        'user': 'Usuario',
        'user_id': 'ID Usuario',
        'amount': 'Monto',
        'network': 'Red',
        'wallet': 'Billetera',
        'status': 'Estado',
        'pending': 'Pendiente',
        'completed': 'Completado',
        'rejected': 'Rechazado',
        'date': 'Fecha',
        'tx_hash': 'Hash TX',
        'reason': 'Razón',
        'view_explorer': 'Ver en Explorador',
        'requires_approval': 'Requiere aprobación manual',
        'processed_success': 'Retiro procesado exitosamente',
        'balance_refunded': 'El saldo ha sido devuelto a tu cuenta',
        'thanks': '¡Gracias por usar ARCADE PXC!',
        'withdrawal_id': 'ID Retiro',
        'btn_bot': '🤖 Ir al Bot',
        'btn_channel': '📢 Canal Oficial'
    },
    'pt': {
        'new_withdrawal': 'NOVA SOLICITAÇÃO DE SAQUE',
        'withdrawal_approved': 'SAQUE APROVADO',
        'withdrawal_rejected': 'SAQUE REJEITADO',
        'user': 'Usuário',
        'user_id': 'ID Usuário',
        'amount': 'Valor',
        'network': 'Rede',
        'wallet': 'Carteira',
        'status': 'Status',
        'pending': 'Pendente',
        'completed': 'Concluído',
        'rejected': 'Rejeitado',
        'date': 'Data',
        'tx_hash': 'Hash TX',
        'reason': 'Motivo',
        'view_explorer': 'Ver no Explorador',
        'requires_approval': 'Requer aprovação manual',
        'processed_success': 'Saque processado com sucesso',
        'balance_refunded': 'O saldo foi devolvido à sua conta',
        'thanks': 'Obrigado por usar o ARCADE PXC!',
        'withdrawal_id': 'ID Saque',
        'btn_bot': '🤖 Ir ao Bot',
        'btn_channel': '📢 Canal Oficial'
    },
    'ru': {
        'new_withdrawal': 'НОВЫЙ ЗАПРОС НА ВЫВОД',
        'withdrawal_approved': 'ВЫВОД ОДОБРЕН',
        'withdrawal_rejected': 'ВЫВОД ОТКЛОНЕН',
        'user': 'Пользователь',
        'user_id': 'ID Пользователя',
        'amount': 'Сумма',
        'network': 'Сеть',
        'wallet': 'Кошелек',
        'status': 'Статус',
        'pending': 'В ожидании',
        'completed': 'Завершено',
        'rejected': 'Отклонено',
        'date': 'Дата',
        'tx_hash': 'Хеш TX',
        'reason': 'Причина',
        'view_explorer': 'Посмотреть в Explorer',
        'requires_approval': 'Требуется ручное подтверждение',
        'processed_success': 'Вывод успешно обработан',
        'balance_refunded': 'Баланс был возвращен на ваш счет',
        'thanks': 'Спасибо за использование ARCADE PXC!',
        'withdrawal_id': 'ID Вывода',
        'btn_bot': '🤖 Перейти к боту',
        'btn_channel': '📢 Официальный канал'
    },
    'ar': {
        'new_withdrawal': 'طلب سحب جديد',
        'withdrawal_approved': 'تم الموافقة على السحب',
        'withdrawal_rejected': 'تم رفض السحب',
        'user': 'المستخدم',
        'user_id': 'معرف المستخدم',
        'amount': 'المبلغ',
        'network': 'الشبكة',
        'wallet': 'المحفظة',
        'status': 'الحالة',
        'pending': 'قيد الانتظار',
        'completed': 'مكتمل',
        'rejected': 'مرفوض',
        'date': 'التاريخ',
        'tx_hash': 'هاش المعاملة',
        'reason': 'السبب',
        'view_explorer': 'عرض في المستكشف',
        'requires_approval': 'يتطلب موافقة يدوية',
        'processed_success': 'تمت معالجة السحب بنجاح',
        'balance_refunded': 'تم إعادة الرصيد إلى حسابك',
        'thanks': 'شكرا لاستخدامك ARCADE PXC!',
        'withdrawal_id': 'معرف السحب',
        'btn_bot': '🤖 اذهب إلى البوت',
        'btn_channel': '📢 القناة الرسمية'
    }
}

def txt(key, lang='es'):
    """Get translated text"""
    if lang not in TRANSLATIONS:
        lang = 'es'
    return TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS['es'].get(key, key))

def get_user_language(user_id):
    """
    Get user's language from database.
    Returns 'es' as default if not found.
    """
    try:
        user = get_user(user_id)
        if user:
            lang = user.get('language_code')
            if lang:
                # Handle codes like 'en-US' -> 'en'
                lang = lang[:2].lower()
                if lang in TRANSLATIONS:
                    print(f"[get_user_language] User {user_id} language: {lang}")
                    return lang
        print(f"[get_user_language] User {user_id} no language found, using 'es'")
        return 'es'
    except Exception as e:
        print(f"[get_user_language] Error getting language for {user_id}: {e}")
        return 'es'

def escape_html(text):
    """Escape HTML special characters"""
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def truncate_wallet(wallet_address, start_chars=10, end_chars=6):
    """
    Truncate wallet address for display
    Example: 0x4e6FAC5144a345Cac1bb819d2f0964......
    """
    if not wallet_address:
        return ''

    wallet_str = str(wallet_address)

    # If address is short, return as is
    if len(wallet_str) <= (start_chars + end_chars + 6):
        return wallet_str

    # Truncate: start + "......" + end
    return f"{wallet_str[:start_chars]}......{wallet_str[-end_chars:]}"

# ============== INLINE KEYBOARD BUTTONS ==============

def get_inline_keyboard(lang='es'):
    """
    Create inline keyboard with Bot and Channel buttons in user's language
    """
    return {
        "inline_keyboard": [
            [
                {
                    "text": txt('btn_bot', lang),
                    "url": "https://t.me/ArcadePXCBot"
                },
                {
                    "text": txt('btn_channel', lang),
                    "url": "https://t.me/ArcadePXC_Community"
                }
            ]
        ]
    }

# ============== TELEGRAM API WITH PHOTO AND BUTTONS ==============

def send_telegram_photo(chat_id, photo_url, caption, parse_mode='HTML', reply_markup=None):
    """Send photo with caption and optional buttons to Telegram"""
    bot_token = get_bot_token()

    if not bot_token:
        print("[send_telegram_photo] ❌ BOT_TOKEN not configured")
        return False

    if not chat_id:
        print("[send_telegram_photo] ❌ chat_id is empty")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {
            'chat_id': chat_id,
            'photo': photo_url,
            'caption': caption,
            'parse_mode': parse_mode
        }
        
        # Add buttons if provided
        if reply_markup:
            payload['reply_markup'] = reply_markup

        response = requests.post(url, json=payload, timeout=15)
        result = response.json()

        if result.get('ok'):
            print(f"[send_telegram_photo] ✅ Photo sent to {chat_id}")
            return True
        else:
            print(f"[send_telegram_photo] ❌ API Error: {result.get('description')}")
            return False

    except Exception as e:
        print(f"[send_telegram_photo] ❌ Error: {e}")
        return False

def send_telegram_message(chat_id, message, parse_mode='HTML', reply_markup=None):
    """Send message to Telegram chat/channel (fallback without photo)"""
    bot_token = get_bot_token()

    if not bot_token:
        print("[send_telegram_message] ❌ BOT_TOKEN not configured")
        return False

    if not chat_id:
        print("[send_telegram_message] ❌ chat_id is empty")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        # Add buttons if provided
        if reply_markup:
            payload['reply_markup'] = reply_markup

        response = requests.post(url, json=payload, timeout=10)
        result = response.json()

        if result.get('ok'):
            print(f"[send_telegram_message] ✅ Sent to {chat_id}")
            return True
        else:
            print(f"[send_telegram_message] ❌ API Error: {result.get('description')}")
            return False

    except Exception as e:
        print(f"[send_telegram_message] ❌ Error: {e}")
        return False

# ============== NOTIFICATION FUNCTIONS WITH BANNERS AND BUTTONS ==============

def on_withdrawal_created(withdrawal_id, user_id, currency, amount, wallet_address):
    """
    Called when a new withdrawal is created.
    Sends notification to pending channel with banner and buttons IN USER'S LANGUAGE.
    """
    channel = get_pending_channel()
    if not channel:
        print("[on_withdrawal_created] ⚠️ WITHDRAWALS_PENDING_CHANNEL not set")
        return False

    # Get user info and LANGUAGE
    user = get_user(user_id)
    user_name = 'User'
    lang = get_user_language(user_id)  # GET USER'S LANGUAGE

    if user:
        user_name = user.get('first_name') or user.get('username') or f"ID: {user_id}"

    # Currency info
    currency = currency.upper()
    curr_info = CURRENCY_CONFIG.get(currency, CURRENCY_CONFIG['DOGE'])

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Get banner for this language
    banner_url = get_banner_url(lang)

    # Truncate wallet address for display
    wallet_display = truncate_wallet(wallet_address)

    # Caption in USER'S LANGUAGE
    caption = f"""<b>🔔 {txt('new_withdrawal', lang)}</b>

<b>💰 {currency}</b> • {curr_info['network']}
<b>👤 {txt('user', lang)}:</b> {escape_html(user_name)} (<code>{user_id}</code>)
<b>💵 {txt('amount', lang)}:</b> <code>{float(amount):.8f}</code> {currency}
<b>📍 {txt('wallet', lang)}:</b> <code>{wallet_display}</code>
<b>🆔 {txt('withdrawal_id', lang)}:</b> <code>{withdrawal_id}</code>
<b>📅 {txt('date', lang)}:</b> {now}
<b>⏳ {txt('status', lang)}:</b> {txt('pending', lang)}

⚙️ {txt('requires_approval', lang)}"""

    # Get inline keyboard with buttons ONLY FOR CHANNEL
    keyboard = get_inline_keyboard(lang)

    # User caption (simpler, without admin info)
    user_caption = f"""<b>⏳ {txt('new_withdrawal', lang)}</b>

<b>💰 {currency}</b>
<b>💵 {txt('amount', lang)}:</b> <code>{float(amount):.8f}</code> {currency}
<b>📍 {txt('wallet', lang)}:</b> <code>{wallet_display}</code>
<b>🆔 {txt('withdrawal_id', lang)}:</b> <code>{withdrawal_id}</code>
<b>📅 {txt('date', lang)}:</b> {now}
<b>⏳ {txt('status', lang)}:</b> {txt('pending', lang)}

⚙️ {txt('requires_approval', lang)}"""

    print(f"[on_withdrawal_created] Sending notification to CHANNEL and USER in language: {lang}")

    # Send to channel WITH buttons
    result_channel = send_telegram_photo(channel, banner_url, caption, reply_markup=keyboard)

    # Send to user WITHOUT buttons
    send_telegram_photo(user_id, banner_url, user_caption)

    return result_channel


def on_withdrawal_completed(withdrawal_id, user_id, currency, amount, wallet_address, tx_hash=None):
    """
    Called when a withdrawal is approved.
    Sends to channel WITH BUTTONS and to user WITHOUT BUTTONS, BOTH IN USER'S LANGUAGE.
    """
    success_channel = get_success_channel()

    # Get user info and LANGUAGE
    user = get_user(user_id)
    user_name = 'User'
    lang = get_user_language(user_id)  # GET USER'S LANGUAGE

    if user:
        user_name = user.get('first_name') or user.get('username') or f"ID: {user_id}"

    # Currency info
    currency = currency.upper()
    curr_info = CURRENCY_CONFIG.get(currency, CURRENCY_CONFIG['DOGE'])

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Get banner for this language
    banner_url = get_banner_url(lang)

    # Truncate wallet address for display
    wallet_display = truncate_wallet(wallet_address)

    # Explorer link
    explorer_link = ""
    if tx_hash and curr_info.get('explorer'):
        explorer_url = curr_info['explorer'] + tx_hash
        explorer_link = f"\n<b>🔗 {txt('tx_hash', lang)}:</b> <a href='{explorer_url}'>{txt('view_explorer', lang)}</a>"

    # Channel caption - IN USER'S LANGUAGE
    channel_caption = f"""<b>✅ {txt('withdrawal_approved', lang)}</b>

<b>💰 {currency}</b> • {curr_info['network']}
<b>👤 {txt('user', lang)}:</b> {escape_html(user_name)} (<code>{user_id}</code>)
<b>💵 {txt('amount', lang)}:</b> <code>{float(amount):.8f}</code> {currency}
<b>📍 {txt('wallet', lang)}:</b> <code>{wallet_display}</code>
<b>📅 {txt('date', lang)}:</b> {now}
<b>✔️ {txt('status', lang)}:</b> {txt('completed', lang)}{explorer_link}

🎉 {txt('processed_success', lang)}"""

    # User caption - IN USER'S LANGUAGE
    user_caption = f"""<b>✅ {txt('withdrawal_approved', lang)}</b>

<b>💰 {currency}</b>
<b>💵 {txt('amount', lang)}:</b> <code>{float(amount):.8f}</code> {currency}
<b>📍 {txt('wallet', lang)}:</b> <code>{wallet_display}</code>
<b>✔️ {txt('status', lang)}:</b> {txt('completed', lang)}{explorer_link}

🎉 {txt('thanks', lang)}"""

    # Get inline keyboard with buttons ONLY FOR CHANNEL
    keyboard = get_inline_keyboard(lang)

    result_channel = True
    result_user = True

    print(f"[on_withdrawal_completed] Sending notifications in language: {lang}")

    # Send to channel WITH BUTTONS
    if success_channel:
        result_channel = send_telegram_photo(success_channel, banner_url, channel_caption, reply_markup=keyboard)
        print(f"[on_withdrawal_completed] Channel notification sent WITH buttons")
    else:
        print("[on_withdrawal_completed] ⚠️ WITHDRAWALS_SUCCESS_CHANNEL not set")

    # Send to user WITHOUT BUTTONS
    result_user = send_telegram_photo(user_id, banner_url, user_caption)
    print(f"[on_withdrawal_completed] User notification sent WITHOUT buttons")

    return result_channel and result_user


def on_withdrawal_rejected(withdrawal_id, user_id, currency, amount, reason=None):
    """
    Called when a withdrawal is rejected.
    Sends notification to user WITHOUT IMAGE and WITHOUT BUTTONS IN USER'S LANGUAGE.
    """
    # Get user's LANGUAGE
    lang = get_user_language(user_id)

    # Currency info
    currency = currency.upper()

    # Reason text
    reason_text = f"\n<b>📋 {txt('reason', lang)}:</b> {escape_html(reason)}" if reason else ""

    # User message - IN USER'S LANGUAGE (TEXT ONLY, NO IMAGE)
    user_message = f"""<b>❌ {txt('withdrawal_rejected', lang)}</b>

<b>💰 {currency}</b>
<b>💵 {txt('amount', lang)}:</b> <code>{float(amount):.8f}</code> {currency}
<b>🚫 {txt('status', lang)}:</b> {txt('rejected', lang)}{reason_text}

💡 {txt('balance_refunded', lang)}"""

    print(f"[on_withdrawal_rejected] Sending TEXT notification to USER (no image, no buttons) in language: {lang}")
    return send_telegram_message(user_id, user_message)


# ============== UTILITY FUNCTIONS ==============

def notify_admin_withdrawal(withdrawal_id):
    """Send notification about a withdrawal using DB data"""
    withdrawal = get_withdrawal(withdrawal_id)
    if not withdrawal:
        print(f"[notify_admin_withdrawal] ❌ Withdrawal {withdrawal_id} not found")
        return False

    return on_withdrawal_created(
        withdrawal_id=withdrawal_id,
        user_id=withdrawal['user_id'],
        currency=withdrawal['currency'],
        amount=withdrawal['amount'],
        wallet_address=withdrawal['wallet_address']
    )

def notify_completion(withdrawal_id, tx_hash=None):
    """Send completion notification using DB data"""
    withdrawal = get_withdrawal(withdrawal_id)
    if not withdrawal:
        print(f"[notify_completion] ❌ Withdrawal {withdrawal_id} not found")
        return False

    return on_withdrawal_completed(
        withdrawal_id=withdrawal_id,
        user_id=withdrawal['user_id'],
        currency=withdrawal['currency'],
        amount=withdrawal['amount'],
        wallet_address=withdrawal['wallet_address'],
        tx_hash=tx_hash or withdrawal.get('tx_hash')
    )

def notify_rejection(withdrawal_id, reason=None):
    """Send rejection notification using DB data"""
    withdrawal = get_withdrawal(withdrawal_id)
    if not withdrawal:
        print(f"[notify_rejection] ❌ Withdrawal {withdrawal_id} not found")
        return False

    return on_withdrawal_rejected(
        withdrawal_id=withdrawal_id,
        user_id=withdrawal['user_id'],
        currency=withdrawal['currency'],
        amount=withdrawal['amount'],
        reason=reason or withdrawal.get('error_message')
    )


# ============== TEST ==============

def test_notifications():
    """Test configuration"""
    print("=" * 50)
    print("NOTIFICATION SYSTEM TEST WITH BANNERS AND BUTTONS")
    print("=" * 50)

    bot_token = get_bot_token()
    pending = get_pending_channel()
    success = get_success_channel()

    print(f"BOT_TOKEN: {'✅ SET' if bot_token else '❌ NOT SET'}")
    print(f"PENDING_CHANNEL: {pending or '❌ NOT SET'}")
    print(f"SUCCESS_CHANNEL: {success or '❌ NOT SET'}")

    print("\nBanner URLs by language:")
    for lang in ['en', 'es', 'pt', 'ru', 'ar']:
        print(f"  {lang}: {get_banner_url(lang)}")

    print("\nTranslations test:")
    for lang in ['en', 'es', 'pt', 'ru', 'ar']:
        print(f"  {lang}: {txt('withdrawal_approved', lang)}")

    print("\nButton translations test:")
    for lang in ['en', 'es', 'pt', 'ru', 'ar']:
        print(f"  {lang}: Bot='{txt('btn_bot', lang)}' | Channel='{txt('btn_channel', lang)}'")

    if bot_token and pending:
        print("\nSending test photo message with buttons...")
        keyboard = get_inline_keyboard('es')
        result = send_telegram_photo(
            pending,
            get_banner_url('es'),
            "🔧 Test - Notification system with banners and buttons active",
            reply_markup=keyboard
        )
        print(f"Result: {'✅ OK' if result else '❌ FAILED'}")

    print("=" * 50)

if __name__ == "__main__":
    test_notifications()