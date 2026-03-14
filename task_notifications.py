"""
task_notifications.py
Notificaciones del bot para tareas de comunidad:
  1. Broadcast al publicar tarea nueva (con plazas disponibles).
  2. Notificación individual al completar y verificar una tarea.
"""

import os
import time
import threading
import requests

# ═══════════════════════════════════════════════════════════════════
#  TEXTOS POR IDIOMA — NUEVA TAREA
# ═══════════════════════════════════════════════════════════════════
NEW_TASK_MESSAGES = {
    'es': (
        "📢 <b>¡Nueva tarea publicada!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n"
        "{desc_line}"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>Recompensa:</b> <code>+{reward} S-E</code>\n"
        "🎯 <b>Plazas disponibles:</b> <code>{spots}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ ¡Date prisa! Las plazas son limitadas.\n"
        "👉 <b>Tasks → Community</b> para completarla 🚀"
    ),
    'en': (
        "📢 <b>New task published!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n"
        "{desc_line}"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>Reward:</b> <code>+{reward} S-E</code>\n"
        "🎯 <b>Available spots:</b> <code>{spots}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ Hurry! Spots are limited.\n"
        "👉 <b>Tasks → Community</b> to complete it 🚀"
    ),
    'pt': (
        "📢 <b>Nova tarefa publicada!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n"
        "{desc_line}"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>Recompensa:</b> <code>+{reward} S-E</code>\n"
        "🎯 <b>Vagas disponíveis:</b> <code>{spots}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ Corra! As vagas são limitadas.\n"
        "👉 <b>Tasks → Community</b> para completar 🚀"
    ),
    'ru': (
        "📢 <b>Новое задание опубликовано!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n"
        "{desc_line}"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>Награда:</b> <code>+{reward} S-E</code>\n"
        "🎯 <b>Доступных мест:</b> <code>{spots}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ Торопись! Мест ограничено.\n"
        "👉 <b>Tasks → Community</b> для выполнения 🚀"
    ),
    'ar': (
        "📢 <b>تم نشر مهمة جديدة!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n"
        "{desc_line}"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>المكافأة:</b> <code>+{reward} S-E</code>\n"
        "🎯 <b>الأماكن المتاحة:</b> <code>{spots}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ أسرع! الأماكن محدودة.\n"
        "👉 <b>Tasks → Community</b> لإتمامها 🚀"
    ),
}

# ═══════════════════════════════════════════════════════════════════
#  TEXTOS POR IDIOMA — TAREA COMPLETADA
# ═══════════════════════════════════════════════════════════════════
COMPLETION_MESSAGES = {
    'es': (
        "✅ <b>¡Tarea completada y verificada!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>Recompensa acreditada:</b> <code>+{reward} S-E</code>\n"
        "💼 <b>Saldo actual:</b> <code>{balance:.4f} S-E</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎉 ¡Sigue completando tareas para ganar más! 🚀"
    ),
    'en': (
        "✅ <b>Task completed and verified!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>Reward credited:</b> <code>+{reward} S-E</code>\n"
        "💼 <b>Current balance:</b> <code>{balance:.4f} S-E</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎉 Keep completing tasks to earn more! 🚀"
    ),
    'pt': (
        "✅ <b>Tarefa concluída e verificada!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>Recompensa creditada:</b> <code>+{reward} S-E</code>\n"
        "💼 <b>Saldo atual:</b> <code>{balance:.4f} S-E</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎉 Continue completando tarefas para ganhar mais! 🚀"
    ),
    'ru': (
        "✅ <b>Задание выполнено и подтверждено!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>Зачислена награда:</b> <code>+{reward} S-E</code>\n"
        "💼 <b>Текущий баланс:</b> <code>{balance:.4f} S-E</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎉 Продолжай выполнять задания и зарабатывай больше! 🚀"
    ),
    'ar': (
        "✅ <b>تمت المهمة والتحقق منها!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>{title}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💰 <b>المكافأة المضافة:</b> <code>+{reward} S-E</code>\n"
        "💼 <b>الرصيد الحالي:</b> <code>{balance:.4f} S-E</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎉 واصل إتمام المهام لكسب المزيد! 🚀"
    ),
}

SUPPORTED_LANGS = set(NEW_TASK_MESSAGES.keys())
FALLBACK_LANG   = 'es'
DESC_LINE       = "📝 {desc}\n\n"


# ═══════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════

def _get_lang(user):
    """
    Lee el idioma del usuario desde la DB.
    La columna puede ser 'language_code' (guardada por update_user)
    o 'language' (guardada por el endpoint directo de SQL).
    Toma la primera que tenga valor.
    """
    raw = (
        user.get('language_code') or
        user.get('language') or
        FALLBACK_LANG
    )
    lang = str(raw).lower()[:2]
    return lang if lang in SUPPORTED_LANGS else FALLBACK_LANG


def _get_token():
    token = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN', '')
    return token.strip()


def _send(bot_token, chat_id, text):
    """Envía mensaje HTML. Retorna True si OK."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={'chat_id': str(chat_id), 'text': text, 'parse_mode': 'HTML'},
            timeout=10,
        )
        result = resp.json()
        if not result.get('ok'):
            err = result.get('description', '')
            # Silenciar errores de usuario bloqueó el bot
            if 'blocked' not in err.lower() and 'forbidden' not in err.lower():
                print(f"[task_notifications] ⚠️ API error para {chat_id}: {err}")
        return resp.status_code == 200 and result.get('ok', False)
    except Exception as e:
        print(f"[task_notifications] ❌ Send error {chat_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════
#  1. BROADCAST — nueva tarea publicada
# ═══════════════════════════════════════════════════════════════════

def _broadcast_worker(task_id, title, description, reward, spots):
    bot_token = _get_token()
    if not bot_token:
        print("[task_notifications] ❌ BOT_TOKEN no configurado — broadcast cancelado")
        return

    try:
        from database import get_all_users_no_limit
        users = get_all_users_no_limit()
    except Exception as e:
        print(f"[task_notifications] ❌ Error obteniendo usuarios: {e}")
        return

    # Pre-construir mensajes por idioma para no recalcular en cada usuario
    msg_cache = {}
    for lang, tmpl in NEW_TASK_MESSAGES.items():
        desc_line = DESC_LINE.format(desc=description) if description else ''
        msg_cache[lang] = tmpl.format(
            title=title,
            desc_line=desc_line,
            reward=reward,
            spots=spots,
        )

    ok = fail = skipped = 0
    total = len(users)
    print(f"[task_notifications] 📢 Broadcast '{title}' ({spots} plazas) → {total} usuarios")

    for user in users:
        if user.get('banned'):
            skipped += 1
            continue

        uid  = user.get('user_id', '')
        if not uid:
            skipped += 1
            continue

        lang = _get_lang(user)
        sent = _send(bot_token, uid, msg_cache[lang])
        if sent:
            ok += 1
        else:
            fail += 1

        time.sleep(0.04)  # ~25 msg/s, bajo el límite de Telegram (30/s)

    print(
        f"[task_notifications] ✅ Broadcast completado — "
        f"OK: {ok} | Fallidos: {fail} | Omitidos: {skipped} | Total: {total}"
    )


def notify_new_task(task_id, title, description, reward, spots):
    """Lanza el broadcast en un hilo daemon para no bloquear la respuesta HTTP."""
    bot_token = _get_token()
    if not bot_token:
        print("[task_notifications] ❌ BOT_TOKEN no configurado — no se puede notificar")
        return

    t = threading.Thread(
        target=_broadcast_worker,
        args=(task_id, title, description, reward, spots),
        daemon=True,
    )
    t.start()
    print(f"[task_notifications] 🚀 Broadcast iniciado en background para tarea {task_id}")


# ═══════════════════════════════════════════════════════════════════
#  2. NOTIFICACIÓN INDIVIDUAL — tarea completada y verificada
# ═══════════════════════════════════════════════════════════════════

def notify_task_completed(user_id, title, reward):
    """
    Notifica al usuario que completó una tarea.
    Obtiene su idioma y saldo actualizado desde la DB.
    Se ejecuta en un hilo daemon para no bloquear.
    """
    bot_token = _get_token()
    if not bot_token:
        return

    def _worker():
        try:
            from database import get_user
            user = get_user(user_id)
            if not user:
                print(f"[task_notifications] ⚠️ Usuario {user_id} no encontrado para notificación")
                return

            lang    = _get_lang(user)
            balance = float(user.get('se_balance', 0) or 0)
            tmpl    = COMPLETION_MESSAGES.get(lang, COMPLETION_MESSAGES[FALLBACK_LANG])
            text    = tmpl.format(title=title, reward=reward, balance=balance)

            ok = _send(bot_token, str(user_id), text)
            if ok:
                print(f"[task_notifications] ✅ Notificación completado → {user_id} [{lang}]")
            else:
                print(f"[task_notifications] ⚠️ No se pudo notificar a {user_id}")
        except Exception as e:
            print(f"[task_notifications] ❌ Error notificando completado a {user_id}: {e}")

    threading.Thread(target=_worker, daemon=True).start()
