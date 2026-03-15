"""
i18n_messages.py — Mensajes del servidor traducidos por idioma del usuario.
Uso: from i18n_messages import get_msg, get_user_lang
"""

MESSAGES = {
    'must_join_channel': {
        'es': 'Debes unirte al canal {channel} primero',
        'en': 'You must join {channel} first',
        'pt': 'Você deve entrar no canal {channel} primeiro',
        'ru': 'Вы должны вступить в {channel} сначала',
        'ar': 'يجب عليك الانضمام إلى {channel} أولاً',
    },
    'task_not_found': {
        'es': 'Tarea no encontrada',
        'en': 'Task not found',
        'pt': 'Tarefa não encontrada',
        'ru': 'Задание не найдено',
        'ar': 'المهمة غير موجودة',
    },
    'task_already_completed': {
        'es': 'Ya completaste esta tarea',
        'en': 'You already completed this task',
        'pt': 'Você já completou esta tarefa',
        'ru': 'Вы уже выполнили это задание',
        'ar': 'لقد أكملت هذه المهمة بالفعل',
    },
    'task_not_active': {
        'es': 'Tarea no activa',
        'en': 'Task is not active',
        'pt': 'Tarefa não está ativa',
        'ru': 'Задание неактивно',
        'ar': 'المهمة غير نشطة',
    },
    'task_exhausted': {
        'es': 'Tarea agotada',
        'en': 'Task is full',
        'pt': 'Tarefa esgotada',
        'ru': 'Задание заполнено',
        'ar': 'المهمة ممتلئة',
    },
    'cannot_complete_own_task': {
        'es': 'No puedes completar tu propia tarea',
        'en': 'You cannot complete your own task',
        'pt': 'Você não pode completar sua própria tarefa',
        'ru': 'Нельзя выполнить своё задание',
        'ar': 'لا يمكنك إكمال مهمتك الخاصة',
    },
    'task_completed': {
        'es': '¡Tarea completada! +{reward} PXC',
        'en': 'Task completed! +{reward} PXC',
        'pt': 'Tarefa concluída! +{reward} PXC',
        'ru': 'Задание выполнено! +{reward} PXC',
        'ar': 'تمت المهمة! +{reward} PXC',
    },
    'insufficient_balance': {
        'es': 'Balance insuficiente. Necesitas {price} PXC',
        'en': 'Insufficient balance. You need {price} PXC',
        'pt': 'Saldo insuficiente. Você precisa de {price} PXC',
        'ru': 'Недостаточно средств. Нужно {price} PXC',
        'ar': 'رصيد غير كافٍ. تحتاج {price} PXC',
    },
    'submitted_review': {
        'es': 'Enviado para revisión',
        'en': 'Submitted for review',
        'pt': 'Enviado para revisão',
        'ru': 'Отправлено на проверку',
        'ar': 'تم الإرسال للمراجعة',
    },
}

FALLBACK = 'en'


def get_user_lang(user_id):
    """Get user language from DB."""
    try:
        from database import get_user
        user = get_user(user_id)
        if user:
            lang = str(user.get('language_code') or user.get('language') or FALLBACK).lower()[:2]
            return lang if lang in ('es', 'en', 'pt', 'ru', 'ar') else FALLBACK
    except Exception:
        pass
    return FALLBACK


def get_msg(key, lang='en', **kwargs):
    """Get translated message for key and language."""
    variants = MESSAGES.get(key, {})
    text = variants.get(lang) or variants.get(FALLBACK) or key
    for k, v in kwargs.items():
        text = text.replace('{' + k + '}', str(v))
    return text
