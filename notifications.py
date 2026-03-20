"""
notifications.py - Notificaciones privadas ARCADE PXC
Usa requests (síncrono) — compatible con Flask/Gunicorn sin asyncio.
Detecta idioma automáticamente por language_code de Telegram.
"""

import os, json, logging
import requests as _req

logger = logging.getLogger(__name__)

BOT_TOKEN    = os.environ.get('BOT_TOKEN', '')
WEBAPP_URL   = os.environ.get('WEBAPP_URL', '')
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'ArcadePXCBot')
_BOT_TITLE   = os.environ.get('BOT_TITLE', 'ARCADE PXC')

# ──────────────────────────────────────────────────────────
# DETECCIÓN DE IDIOMA
# ──────────────────────────────────────────────────────────
_LANG_MAP = {
    'es':'es','es-419':'es','es-ar':'es','es-bo':'es','es-cl':'es','es-co':'es',
    'es-cr':'es','es-cu':'es','es-do':'es','es-ec':'es','es-sv':'es','es-gt':'es',
    'es-hn':'es','es-mx':'es','es-ni':'es','es-pa':'es','es-py':'es','es-pe':'es',
    'es-pr':'es','es-uy':'es','es-ve':'es',
    'pt':'pt','pt-br':'pt','pt-pt':'pt',
    'ru':'ru','ru-ru':'ru',
    'ar':'ar','ar-ae':'ar','ar-sa':'ar','ar-eg':'ar',
    'en':'en','en-us':'en','en-gb':'en','en-au':'en',
}

def detect_lang(language_code):
    if not language_code: return 'es'
    lc = str(language_code).lower().strip()
    return _LANG_MAP.get(lc) or _LANG_MAP.get(lc[:2]) or 'en'

# ──────────────────────────────────────────────────────────
# TEXTOS
# ──────────────────────────────────────────────────────────
_TEXTS = {

'welcome':{
  'es':(
    "👋 <b>Hola {name}</b> 🌎🪙\n"
    "Bienvenido/a a <b>{bot_title}</b>\n\n"
    "🚀 <b>Un bot de recompensas donde tu tiempo y acciones\n"
    "se convierten en criptomoneda real</b>\n\n"
    "🎉 <b>Completa tareas</b> y gana PXC al instante\n"
    "👥 <b>Invita amigos</b> y cobra por cada referido\n"
    "⛏️ <b>Minería automática</b> — acumula PXC mientras duermes\n"
    "🎮 <b>Juegos</b> — Mines, Ruleta y Arcade\n"
    "🏆 <b>Ranking</b> — compite y escala posiciones\n"
    "💸 <b>Retiro instantáneo</b> en <b>USDT · DOGE · TON</b>\n\n"
    "⬇️ <b>Empieza a ganar ahora</b>"
  ),
  'en':(
    "👋 <b>Hello {name}</b> 🌎🪙\n"
    "Welcome to <b>{bot_title}</b>\n\n"
    "🚀 <b>A rewards bot where your time and actions\n"
    "turn into real cryptocurrency</b>\n\n"
    "🎉 <b>Complete tasks</b> and earn PXC instantly\n"
    "👥 <b>Invite friends</b> and earn for every referral\n"
    "⛏️ <b>Auto-mining</b> — accumulate PXC while you sleep\n"
    "🎮 <b>Games</b> — Mines, Roulette and Arcade\n"
    "🏆 <b>Ranking</b> — compete and climb the leaderboard\n"
    "💸 <b>Instant withdrawal</b> in <b>USDT · DOGE · TON</b>\n\n"
    "⬇️ <b>Start earning now</b>"
  ),
  'pt':(
    "👋 <b>Olá {name}</b> 🌎🪙\n"
    "Bem-vindo(a) ao <b>{bot_title}</b>\n\n"
    "🚀 <b>Um bot de recompensas onde seu tempo e ações\n"
    "se transformam em criptomoeda real</b>\n\n"
    "🎉 <b>Complete tarefas</b> e ganhe PXC na hora\n"
    "👥 <b>Convide amigos</b> e ganhe por cada indicação\n"
    "⛏️ <b>Mineração automática</b> — acumule PXC enquanto dorme\n"
    "🎮 <b>Jogos</b> — Mines, Roleta e Arcade\n"
    "🏆 <b>Ranking</b> — compita e suba no placar\n"
    "💸 <b>Saque instantâneo</b> em <b>USDT · DOGE · TON</b>\n\n"
    "⬇️ <b>Comece a ganhar agora</b>"
  ),
  'ru':(
    "👋 <b>Привет, {name}</b> 🌎🪙\n"
    "Добро пожаловать в <b>{bot_title}</b>\n\n"
    "🚀 <b>Бот вознаграждений, где твоё время и действия\n"
    "превращаются в настоящую криптовалюту</b>\n\n"
    "🎉 <b>Выполняй задания</b> и сразу получай PXC\n"
    "👥 <b>Приглашай друзей</b> и зарабатывай за каждого реферала\n"
    "⛏️ <b>Автоматический майнинг</b> — накапливай PXC пока спишь\n"
    "🎮 <b>Игры</b> — Mines, Рулетка и Аркада\n"
    "🏆 <b>Рейтинг</b> — соревнуйся и поднимайся в таблице\n"
    "💸 <b>Мгновенный вывод</b> в <b>USDT · DOGE · TON</b>\n\n"
    "⬇️ <b>Начни зарабатывать прямо сейчас</b>"
  ),
  'ar':(
    "👋 <b>مرحباً {name}</b> 🌎🪙\n"
    "أهلاً بك في <b>{bot_title}</b>\n\n"
    "🚀 <b>بوت مكافآت يحوّل وقتك وأفعالك\n"
    "إلى عملة مشفرة حقيقية</b>\n\n"
    "🎉 <b>أكمل المهام</b> واكسب PXC فوراً\n"
    "👥 <b>ادعُ أصدقاءك</b> واكسب عن كل إحالة\n"
    "⛏️ <b>التعدين التلقائي</b> — اجمع PXC أثناء نومك\n"
    "🎮 <b>الألعاب</b> — Mines والروليت والأركيد\n"
    "🏆 <b>الترتيب</b> — تنافس وتصدّر القائمة\n"
    "💸 <b>سحب فوري</b> بـ <b>USDT · DOGE · TON</b>\n\n"
    "⬇️ <b>ابدأ الكسب الآن</b>"
  ),
},

'referral_validated':{
  'es':(
    "🎉 <b>¡Recompensa recibida!</b>\n\n"
    "👤 <b>Referido:</b> {referred_name}\n"
    "💎 <b>PXC ganados:</b> +{reward} PXC\n"
    "👥 <b>Total referidos validados:</b> {total_refs}\n\n"
    "Tu amigo acaba de completar su primera tarea. ¡Sigue invitando y sigue ganando! 🚀"
  ),
  'en':(
    "🎉 <b>Reward Received!</b>\n\n"
    "👤 <b>Referral:</b> {referred_name}\n"
    "💎 <b>PXC earned:</b> +{reward} PXC\n"
    "👥 <b>Total validated referrals:</b> {total_refs}\n\n"
    "Your friend just completed their first task. Keep inviting and keep earning! 🚀"
  ),
  'pt':(
    "🎉 <b>Recompensa Recebida!</b>\n\n"
    "👤 <b>Indicado:</b> {referred_name}\n"
    "💎 <b>PXC ganhos:</b> +{reward} PXC\n"
    "👥 <b>Total de indicados validados:</b> {total_refs}\n\n"
    "Seu amigo acabou de completar a primeira tarefa. Continue convidando e ganhando! 🚀"
  ),
  'ru':(
    "🎉 <b>Награда получена!</b>\n\n"
    "👤 <b>Реферал:</b> {referred_name}\n"
    "💎 <b>PXC заработано:</b> +{reward} PXC\n"
    "👥 <b>Всего подтверждённых рефералов:</b> {total_refs}\n\n"
    "Ваш друг только что выполнил первое задание. Продолжайте приглашать и зарабатывать! 🚀"
  ),
  'ar':(
    "🎉 <b>تم استلام المكافأة!</b>\n\n"
    "👤 <b>المُحال:</b> {referred_name}\n"
    "💎 <b>PXC المكتسبة:</b> +{reward} PXC\n"
    "👥 <b>إجمالي الإحالات المؤكدة:</b> {total_refs}\n\n"
    "أكمل صديقك أول مهمة للتو. استمر في الدعوة والكسب! 🚀"
  ),
},

'referral_fraud_skip':{
  'es':(
    "⚠️ <b>Tu referido se ha unido — pero no recibiste recompensa</b>\n\n"
    "👤 <b>Referido:</b> {referred_name}\n\n"
    "Tu referido se registró correctamente bajo tu enlace, sin embargo "
    "<b>la recompensa no fue acreditada</b> porque se detectó actividad anormal entre las cuentas.\n\n"
    "✅ <b>Tu cuenta no tiene ninguna restricción por ahora.</b>\n\n"
    "⛔ Por favor, deja de intentar ganar recompensas con cuentas propias o vinculadas. "
    "Si este comportamiento continúa, tu cuenta podría ser restringida permanentemente."
  ),
  'en':(
    "⚠️ <b>Your referral joined — but no reward was credited</b>\n\n"
    "👤 <b>Referral:</b> {referred_name}\n\n"
    "Your referral registered under your link, however "
    "<b>the reward was not credited</b> because abnormal activity "
    "was detected between the accounts.\n\n"
    "✅ <b>Your account has no restrictions at this time.</b>\n\n"
    "⛔ Please stop attempting to earn rewards using your own or linked accounts. "
    "If this continues, your account may be permanently restricted."
  ),
  'pt':(
    "⚠️ <b>Seu indicado entrou — mas nenhuma recompensa foi creditada</b>\n\n"
    "👤 <b>Indicado:</b> {referred_name}\n\n"
    "Seu indicado se registrou pelo seu link, porém "
    "<b>a recompensa não foi creditada</b> pois foi detectada "
    "atividade anormal entre as contas.\n\n"
    "✅ <b>Sua conta não tem nenhuma restrição no momento.</b>\n\n"
    "⛔ Por favor, pare de tentar ganhar recompensas com suas próprias contas. "
    "Se isso continuar, sua conta poderá ser permanentemente restrita."
  ),
  'ru':(
    "⚠️ <b>Ваш реферал вступил — но награда не была начислена</b>\n\n"
    "👤 <b>Реферал:</b> {referred_name}\n\n"
    "Ваш реферал зарегистрировался по вашей ссылке, однако "
    "<b>награда не была начислена</b>, так как обнаружена "
    "аномальная активность между аккаунтами.\n\n"
    "✅ <b>Ваш аккаунт пока не имеет ограничений.</b>\n\n"
    "⛔ Пожалуйста, прекратите попытки получить награды через собственные аккаунты. "
    "Если это продолжится, ваш аккаунт может быть навсегда ограничен."
  ),
  'ar':(
    "⚠️ <b>انضم المُحال — لكن لم تُضَف أي مكافأة</b>\n\n"
    "👤 <b>المُحال:</b> {referred_name}\n\n"
    "سجّل المُحال عبر رابطك، إلا أن "
    "<b>المكافأة لم تُضَف</b> لأنه تم رصد نشاط غير طبيعي بين الحسابين.\n\n"
    "✅ <b>حسابك لا يواجه أي قيود في الوقت الحالي.</b>\n\n"
    "⛔ يرجى التوقف عن محاولة كسب المكافآت باستخدام حساباتك الخاصة. "
    "إذا استمر هذا، قد يُقيَّد حسابك بشكل دائم."
  ),
},

'generic_reply':{
  'es':(
    "⛏️ <b>{name}, tu minero sigue trabajando.</b>\n\n"
    "🟢 Activo · PXC acumulándose en tiempo real\n\n"
    "Revisa tus ganancias, completa tareas o invita amigos\n"
    "directamente desde la app. 👇"
  ),
  'en':(
    "⛏️ <b>{name}, your miner is still running.</b>\n\n"
    "🟢 Active · PXC accumulating in real time\n\n"
    "Check your earnings, complete tasks or invite friends\n"
    "directly from the app. 👇"
  ),
  'pt':(
    "⛏️ <b>{name}, seu minerador continua rodando.</b>\n\n"
    "🟢 Ativo · PXC acumulando em tempo real\n\n"
    "Veja seus ganhos, complete tarefas ou convide amigos\n"
    "direto pelo app. 👇"
  ),
  'ru':(
    "⛏️ <b>{name}, ваш майнер продолжает работать.</b>\n\n"
    "🟢 Активен · PXC накапливаются в реальном времени\n\n"
    "Проверьте доходы, выполняйте задания или приглашайте друзей\n"
    "прямо из приложения. 👇"
  ),
  'ar':(
    "⛏️ <b>{name}، عمّالك لا يزال يعمل.</b>\n\n"
    "🟢 نشط · PXC تتراكم في الوقت الفعلي\n\n"
    "تحقق من أرباحك، أكمل المهام أو ادعُ أصدقاء\n"
    "مباشرةً من التطبيق. 👇"
  ),
},

}

# ──────────────────────────────────────────────────────────
# ENVÍO VÍA BOT API (síncrono, solo requests)
# ──────────────────────────────────────────────────────────

def _api(method, payload):
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN no configurado")
        return None
    try:
        r = _req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json=payload, timeout=10
        )
        data = r.json()
        if not data.get('ok'):
            logger.warning(f"Telegram [{method}] -> {data}")
        return data
    except Exception as e:
        logger.error(f"Error en Telegram API {method}: {e}")
        return None


def _get_open_btn(lang):
    labels = {
        'es': f'🚀 Abrir {_BOT_TITLE}',
        'en': f'🚀 Open {_BOT_TITLE}',
        'pt': f'🚀 Abrir {_BOT_TITLE}',
        'ru': f'🚀 Открыть {_BOT_TITLE}',
        'ar': f'🚀 فتح {_BOT_TITLE}',
    }
    return labels.get(lang, f'🚀 Open {_BOT_TITLE}')


def _keyboard(user_id, lang):
    if not WEBAPP_URL:
        return None
    url = f"{WEBAPP_URL.rstrip('/')}?user_id={user_id}"
    return {"inline_keyboard":[[{"text": _get_open_btn(lang), "web_app":{"url": url}}]]}


def _send(chat_id, notif_type, lang, user_id=None, **kwargs):
    texts = _TEXTS.get(notif_type, {})
    tmpl  = texts.get(lang) or texts.get('es') or texts.get('en', '')
    kwargs.setdefault('bot_title', _BOT_TITLE)
    try:
        text = tmpl.format(**kwargs)
    except KeyError as e:
        logger.warning(f"Clave faltante {e} en notif '{notif_type}'")
        text = tmpl
    uid = user_id or chat_id
    kb = _keyboard(uid, lang)
    payload = {
        "chat_id": int(chat_id),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if kb:
        payload["reply_markup"] = json.dumps(kb)
    _api("sendMessage", payload)

# ──────────────────────────────────────────────────────────
# API PÚBLICA
# ──────────────────────────────────────────────────────────

def notify_welcome(user_id, first_name, language_code=None):
    _send(user_id, 'welcome', detect_lang(language_code), user_id=user_id, name=first_name)

def notify_referral_validated(referrer_id, referred_name, reward, total_refs=0, language_code=None):
    _send(referrer_id, 'referral_validated', detect_lang(language_code), user_id=referrer_id,
          referred_name=referred_name, reward=reward, total_refs=total_refs)

def notify_referral_fraud_skip(referrer_id, referred_name, language_code=None):
    """Notifica al referidor que se unió el referido pero no hubo recompensa por IP compartida."""
    _send(referrer_id, 'referral_fraud_skip', detect_lang(language_code), user_id=referrer_id,
          referred_name=referred_name)

def notify_generic(user_id, first_name, language_code=None):
    _send(user_id, 'generic_reply', detect_lang(language_code), user_id=user_id, name=first_name)
