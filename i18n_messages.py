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
        'es': 'Proporciona el @username del canal y agrega @ArcadePXCBot como admin',
        'en': 'Provide the channel @username and add @ArcadePXCBot as admin',
        'pt': 'Forneça o @username do canal e adicione @ArcadePXCBot como admin',
        'ru': 'Укажите @username канала и добавьте @ArcadePXCBot как администратора',
        'ar': 'أدخل @username للقناة وأضف @ArcadePXCBot كمشرف',
    },
    'params_missing': {
        'es': 'Parámetros faltantes',
        'en': 'Missing parameters',
        'pt': 'Parâmetros ausentes',
        'ru': 'Отсутствуют параметры',
        'ar': 'معاملات مفقودة',
    },
    'no_wallet_bep20': {
        'es': 'Debe vincular una dirección de wallet BEP20 primero',
        'en': 'You must link a BEP20 wallet address first',
        'pt': 'Você deve vincular um endereço de carteira BEP20 primeiro',
        'ru': 'Сначала необходимо привязать адрес кошелька BEP20',
        'ar': 'يجب ربط عنوان محفظة BEP20 أولاً',
    },
    'no_wallet_ton': {
        'es': 'Debe vincular una dirección TON primero',
        'en': 'You must link a TON address first',
        'pt': 'Você deve vincular um endereço TON primeiro',
        'ru': 'Сначала необходимо привязать адрес TON',
        'ar': 'يجب ربط عنوان TON أولاً',
    },
    'invalid_ton_address': {
        'es': 'Formato de dirección TON inválido',
        'en': 'Invalid TON address format',
        'pt': 'Formato de endereço TON inválido',
        'ru': 'Неверный формат адреса TON',
        'ar': 'تنسيق عنوان TON غير صالح',
    },
    'invalid_bep20_address': {
        'es': 'Formato de dirección BEP20 inválido (debe ser 0x...)',
        'en': 'Invalid BEP20 address format (must start with 0x...)',
        'pt': 'Formato de endereço BEP20 inválido (deve começar com 0x...)',
        'ru': 'Неверный формат адреса BEP20 (должен начинаться с 0x...)',
        'ar': 'تنسيق عنوان BEP20 غير صالح (يجب أن يبدأ بـ 0x...)',
    },
    'invalid_amount': {
        'es': 'Cantidad inválida',
        'en': 'Invalid amount',
        'pt': 'Valor inválido',
        'ru': 'Неверная сумма',
        'ar': 'المبلغ غير صالح',
    },
    'amount_must_be_positive': {
        'es': 'La cantidad debe ser mayor a 0',
        'en': 'Amount must be greater than 0',
        'pt': 'O valor deve ser maior que 0',
        'ru': 'Сумма должна быть больше 0',
        'ar': 'يجب أن يكون المبلغ أكبر من 0',
    },
    'debt_pending_withdrawal': {
        'es': 'Tienes deuda pendiente que debes pagar antes de retirar. Saldo negativo: {debt}',
        'en': 'You have a pending debt that must be paid before withdrawing. Negative balance: {debt}',
        'pt': 'Você tem uma dívida pendente que deve ser paga antes de sacar. Saldo negativo: {debt}',
        'ru': 'У вас есть задолженность, которую необходимо погасить перед выводом. Отрицательный баланс: {debt}',
        'ar': 'لديك دين معلق يجب سداده قبل السحب. الرصيد السلبي: {debt}',
    },
    'insufficient_balance': {
        'es': 'Balance insuficiente. Tienes: {balance} {currency}',
        'en': 'Insufficient balance. You have: {balance} {currency}',
        'pt': 'Saldo insuficiente. Você tem: {balance} {currency}',
        'ru': 'Недостаточный баланс. У вас: {balance} {currency}',
        'ar': 'رصيد غير كافٍ. لديك: {balance} {currency}',
    },
    'withdrawal_min_amount': {
        'es': 'Mínimo de retiro: {min} {currency}',
        'en': 'Minimum withdrawal: {min} {currency}',
        'pt': 'Retirada mínima: {min} {currency}',
        'ru': 'Минимальный вывод: {min} {currency}',
        'ar': 'الحد الأدنى للسحب: {min} {currency}',
    },
    'account_under_review': {
        'es': 'Tu cuenta está bajo revisión. Contacta soporte.',
        'en': 'Your account is under review. Contact support.',
        'pt': 'Sua conta está em revisão. Entre em contato com o suporte.',
        'ru': 'Ваш аккаунт проверяется. Свяжитесь с поддержкой.',
        'ar': 'حسابك قيد المراجعة. تواصل مع الدعم.',
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
