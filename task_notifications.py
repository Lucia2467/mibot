"""
task_notifications.py
Notificaciones del bot para tareas de comunidad.
"""

import os
import time
import threading
import requests

# ═══════════════════════════════════════════════════════════════════
#  TEXTOS — NUEVA TAREA
# ═══════════════════════════════════════════════════════════════════
NEW_TASK_MESSAGES = {
    'es': (
        "🆕 <b>¡Nueva tarea disponible!</b>\n\n"
        "📋 <b>Tarea:</b> {title}\n"
        "{desc_line}"
        "👥 <b>Espacios:</b> {spots}\n"
        "💰 <b>Recompensa:</b> +{reward} S-E\n\n"
        "¡Completa la tarea para ganar recompensas! 🚀\n\n"
        "👉 <b>Tasks → Community</b>"
    ),
    'en': (
        "🆕 <b>New task available!</b>\n\n"
        "📋 <b>Task:</b> {title}\n"
        "{desc_line}"
        "👥 <b>Spots:</b> {spots}\n"
        "💰 <b>Reward:</b> +{reward} S-E\n\n"
        "Complete the task to earn rewards! 🚀\n\n"
        "👉 <b>Tasks → Community</b>"
    ),
    'pt': (
        "🆕 <b>Nova tarefa disponível!</b>\n\n"
        "📋 <b>Tarefa:</b> {title}\n"
        "{desc_line}"
        "👥 <b>Vagas:</b> {spots}\n"
        "💰 <b>Recompensa:</b> +{reward} S-E\n\n"
        "Complete a tarefa para ganhar recompensas! 🚀\n\n"
        "👉 <b>Tasks → Community</b>"
    ),
    'ru': (
        "🆕 <b>Новое задание доступно!</b>\n\n"
        "📋 <b>Задание:</b> {title}\n"
        "{desc_line}"
        "👥 <b>Мест:</b> {spots}\n"
        "💰 <b>Награда:</b> +{reward} S-E\n\n"
        "Выполни задание и получи награду! 🚀\n\n"
        "👉 <b>Tasks → Community</b>"
    ),
    'ar': (
        "🆕 <b>مهمة جديدة متاحة!</b>\n\n"
        "📋 <b>المهمة:</b> {title}\n"
        "{desc_line}"
        "👥 <b>الأماكن:</b> {spots}\n"
        "💰 <b>المكافأة:</b> +{reward} S-E\n\n"
        "أتمم المهمة لكسب المكافآت! 🚀\n\n"
        "👉 <b>Tasks → Community</b>"
    ),
}

DESC_LINE = {
    'es': "📝 <b>Descripción:</b> {desc}\n",
    'en': "📝 <b>Description:</b> {desc}\n",
    'pt': "📝 <b>Descrição:</b> {desc}\n",
    'ru': "📝 <b>Описание:</b> {desc}\n",
    'ar': "📝 <b>الوصف:</b> {desc}\n",
}

# ═══════════════════════════════════════════════════════════════════
#  TEXTOS — TAREA COMPLETADA
# ═══════════════════════════════════════════════════════════════════
COMPLETION_MESSAGES = {
    'es': (
        "🎉 <b>¡Tarea completada!</b>\n\n"
        "✅ <b>Tarea:</b> {title}\n"
        "💰 <b>Recompensa:</b> +{reward} S-E\n"
        "💼 <b>Saldo actual:</b> {balance:.4f} S-E\n\n"
        "¡Sigue completando tareas para más recompensas! 🚀"
    ),
    'en': (
        "🎉 <b>Task completed!</b>\n\n"
        "✅ <b>Task:</b> {title}\n"
        "💰 <b>Reward:</b> +{reward} S-E\n"
        "💼 <b>Current balance:</b> {balance:.4f} S-E\n\n"
        "Keep completing tasks for more rewards! 🚀"
    ),
    'pt': (
        "🎉 <b>Tarefa concluída!</b>\n\n"
        "✅ <b>Tarefa:</b> {title}\n"
        "💰 <b>Recompensa:</b> +{reward} S-E\n"
        "💼 <b>Saldo atual:</b> {balance:.4f} S-E\n\n"
        "Continue completando tarefas para mais recompensas! 🚀"
    ),
    'ru': (
        "🎉 <b>Задание выполнено!</b>\n\n"
        "✅ <b>Задание:</b> {title}\n"
        "💰 <b>Награда:</b> +{reward} S-E\n"
        "💼 <b>Баланс:</b> {balance:.4f} S-E\n\n"
        "Продолжай выполнять задания для большего заработка! 🚀"
    ),
    'ar': (
        "🎉 <b>تمت المهمة!</b>\n\n"
        "✅ <b>المهمة:</b> {title}\n"
        "💰 <b>المكافأة:</b> +{reward} S-E\n"
        "💼 <b>الرصيد الحالي:</b> {balance:.4f} S-E\n\n"
        "واصل إتمام المهام للمزيد من المكافآت! 🚀"
    ),
}

SUPPORTED_LANGS = set(NEW_TASK_MESSAGES.keys())
FALLBACK_LANG   = 'es'


# ═══════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════

def _get_lang(user):
    raw = (
        user.get('language_code') or
        user.get('language') or
        FALLBACK_LANG
    )
    lang = str(raw).lower()[:2]
    return lang if lang in SUPPORTED_LANGS else FALLBACK_LANG


def _get_token():
    return (os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN', '')).strip()


def _send(bot_token, chat_id, text):
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={'chat_id': str(chat_id), 'text': text, 'parse_mode': 'HTML'},
            timeout=10,
        )
        result = resp.json()
        if not result.get('ok'):
            err = result.get('description', '')
            if 'blocked' not in err.lower() and 'forbidden' not in err.lower():
                print(f"[task_notifications] ⚠️ API error {chat_id}: {err}")
        return result.get('ok', False)
    except Exception as e:
        print(f"[task_notifications] ❌ Send error {chat_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════
#  1. BROADCAST — nueva tarea
# ═══════════════════════════════════════════════════════════════════

def _broadcast_worker(task_id, title, description, reward, spots):
    bot_token = _get_token()
    if not bot_token:
        print("[task_notifications] ❌ BOT_TOKEN no configurado")
        return

    try:
        from database import get_all_users_no_limit
        users = get_all_users_no_limit()
    except Exception as e:
        print(f"[task_notifications] ❌ Error obteniendo usuarios: {e}")
        return

    # Pre-construir un mensaje por idioma
    msg_cache = {}
    for lang, tmpl in NEW_TASK_MESSAGES.items():
        desc_line = DESC_LINE[lang].format(desc=description) if description else ''
        msg_cache[lang] = tmpl.format(
            title=title,
            desc_line=desc_line,
            reward=reward,
            spots=spots,
        )

    ok = fail = 0
    print(f"[task_notifications] 📢 Broadcast '{title}' ({spots} espacios) → {len(users)} usuarios")

    for user in users:
        if user.get('banned'):
            continue
        uid = user.get('user_id', '')
        if not uid:
            continue
        lang = _get_lang(user)
        sent = _send(bot_token, uid, msg_cache[lang])
        ok   += sent
        fail += not sent
        time.sleep(0.04)

    print(f"[task_notifications] ✅ Broadcast listo — OK: {ok} | Fallos: {fail}")


def notify_new_task(task_id, title, description, reward, spots):
    bot_token = _get_token()
    if not bot_token:
        print("[task_notifications] ❌ BOT_TOKEN no configurado")
        return
    threading.Thread(
        target=_broadcast_worker,
        args=(task_id, title, description, reward, spots),
        daemon=True,
    ).start()
    print(f"[task_notifications] 🚀 Broadcast iniciado para tarea {task_id}")


# ═══════════════════════════════════════════════════════════════════
#  2. NOTIFICACIÓN INDIVIDUAL — tarea completada
# ═══════════════════════════════════════════════════════════════════

def notify_task_completed(user_id, title, reward):
    bot_token = _get_token()
    if not bot_token:
        return

    def _worker():
        try:
            from database import get_user
            user    = get_user(user_id)
            if not user:
                return
            lang    = _get_lang(user)
            balance = float(user.get('se_balance', 0) or 0)
            text    = COMPLETION_MESSAGES.get(lang, COMPLETION_MESSAGES[FALLBACK_LANG]).format(
                title=title, reward=reward, balance=balance
            )
            ok = _send(bot_token, str(user_id), text)
            print(f"[task_notifications] {'✅' if ok else '⚠️'} Completado → {user_id} [{lang}]")
        except Exception as e:
            print(f"[task_notifications] ❌ Error completado {user_id}: {e}")

    threading.Thread(target=_worker, daemon=True).start()
