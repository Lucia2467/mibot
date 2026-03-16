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

FALLBACK = 'es'


MESSAGES.update({
    'invalid_package': {
        'es': 'Paquete no válido',
        'en': 'Invalid package',
        'pt': 'Pacote inválido',
        'ru': 'Неверный пакет',
        'ar': 'الباقة غير صالحة',
    },
    'user_not_found': {
        'es': 'Usuario no encontrado',
        'en': 'User not found',
        'pt': 'Usuário não encontrado',
        'ru': 'Пользователь не найден',
        'ar': 'المستخدم غير موجود',
    },
    'insufficient_balance_detail': {
        'es': 'Balance insuficiente. Necesitas {price} PXC, tienes {balance:.4f} PXC',
        'en': 'Insufficient balance. You need {price} PXC, you have {balance:.4f} PXC',
        'pt': 'Saldo insuficiente. Você precisa de {price} PXC, você tem {balance:.4f} PXC',
        'ru': 'Недостаточно средств. Нужно {price} PXC, у вас {balance:.4f} PXC',
        'ar': 'رصيد غير كافٍ. تحتاج {price} PXC، لديك {balance:.4f} PXC',
    },
    'payment_error': {
        'es': 'Error al procesar el pago',
        'en': 'Payment processing error',
        'pt': 'Erro ao processar o pagamento',
        'ru': 'Ошибка обработки платежа',
        'ar': 'خطأ في معالجة الدفع',
    },
    'task_created': {
        'es': '¡Tarea creada con éxito!',
        'en': 'Task created successfully!',
        'pt': 'Tarefa criada com sucesso!',
        'ru': 'Задание успешно создано!',
        'ar': 'تم إنشاء المهمة بنجاح!',
    },
    'title_too_short': {
        'es': 'El título es muy corto',
        'en': 'Title is too short',
        'pt': 'O título é muito curto',
        'ru': 'Заголовок слишком короткий',
        'ar': 'العنوان قصير جداً',
    },
    'invalid_url': {
        'es': 'URL inválida',
        'en': 'Invalid URL',
        'pt': 'URL inválida',
        'ru': 'Неверный URL',
        'ar': 'رابط غير صالح',
    },
    'select_package': {
        'es': 'Selecciona un paquete',
        'en': 'Please select a package',
        'pt': 'Selecione um pacote',
        'ru': 'Выберите пакет',
        'ar': 'الرجاء اختيار باقة',
    },
    'channel_required': {
        'es': 'Proporciona el @username del canal y agrega @SallyEDogeBot como admin',
        'en': 'Provide the channel @username and add @SallyEDogeBot as admin',
        'pt': 'Forneça o @username do canal e adicione @SallyEDogeBot como admin',
        'ru': 'Укажите @username канала и добавьте @SallyEDogeBot как администратора',
        'ar': 'أدخل @username للقناة وأضف @SallyEDogeBot كمشرف',
    },
    'params_missing': {
        'es': 'Parámetros faltantes',
        'en': 'Missing parameters',
        'pt': 'Parâmetros ausentes',
        'ru': 'Отсутствуют параметры',
        'ar': 'معاملات مفقودة',
    },
})


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


def get_lang_from_request(user_id=None, request=None):
    """Get language from user_id DB or request args fallback."""
    if user_id:
        return get_user_lang(user_id)
    if request:
        return str(request.args.get('lang', 'en'))[:2]
    return FALLBACK
