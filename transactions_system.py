"""
transactions_system.py - Sistema Unificado de Transacciones
SALLY-E / DOGE PIXEL - Soporte para DOGE, TON, USDT y futuras monedas

Características:
- Historial unificado de todas las monedas
- Soporte multiidioma (EN, ES, PT, RU, AR)
- Registro consistente de depósitos y retiros
- Integración con sistema de notificaciones
"""

import json
from datetime import datetime
from decimal import Decimal
from db import execute_query, get_cursor

# ============== CONFIGURACIÓN DE MONEDAS ==============
CURRENCIES = {
    'SE': {
        'name': 'SALLY-E',
        'symbol': 'SE',
        'decimals': 4,
        'color': '#00F5FF',
        'icon': '⚡',
        'network': 'Internal',
        'explorer': None
    },
    'DOGE': {
        'name': 'Dogecoin',
        'symbol': 'DOGE',
        'decimals': 8,
        'color': '#C9A635',
        'icon': '🐕',
        'network': 'BEP-20',
        'explorer': 'https://bscscan.com/tx/'
    },
    'TON': {
        'name': 'Toncoin',
        'symbol': 'TON',
        'decimals': 9,
        'color': '#0098EA',
        'icon': '💎',
        'network': 'TON',
        'explorer': 'https://tonscan.org/tx/'
    },
    'USDT': {
        'name': 'Tether USD',
        'symbol': 'USDT',
        'decimals': 6,
        'color': '#26A17B',
        'icon': '💵',
        'network': 'BEP-20',
        'explorer': 'https://bscscan.com/tx/'
    }
}

# ============== TRADUCCIONES ==============
TRANSLATIONS = {
    'status': {
        'pending': {
            'en': 'Pending',
            'es': 'Pendiente',
            'pt': 'Pendente',
            'ru': 'В ожидании',
            'ar': 'قيد الانتظار'
        },
        'processing': {
            'en': 'Processing',
            'es': 'Procesando',
            'pt': 'Processando',
            'ru': 'Обработка',
            'ar': 'جاري المعالجة'
        },
        'completed': {
            'en': 'Completed',
            'es': 'Completado',
            'pt': 'Concluído',
            'ru': 'Завершено',
            'ar': 'مكتمل'
        },
        'confirmed': {
            'en': 'Confirmed',
            'es': 'Confirmado',
            'pt': 'Confirmado',
            'ru': 'Подтверждено',
            'ar': 'مؤكد'
        },
        'failed': {
            'en': 'Failed',
            'es': 'Fallido',
            'pt': 'Falhou',
            'ru': 'Ошибка',
            'ar': 'فشل'
        },
        'rejected': {
            'en': 'Rejected',
            'es': 'Rechazado',
            'pt': 'Rejeitado',
            'ru': 'Отклонено',
            'ar': 'مرفوض'
        },
        'cancelled': {
            'en': 'Cancelled',
            'es': 'Cancelado',
            'pt': 'Cancelado',
            'ru': 'Отменено',
            'ar': 'ملغى'
        }
    },
    'type': {
        'withdrawal': {
            'en': 'Withdrawal',
            'es': 'Retiro',
            'pt': 'Saque',
            'ru': 'Вывод',
            'ar': 'سحب'
        },
        'deposit': {
            'en': 'Deposit',
            'es': 'Depósito',
            'pt': 'Depósito',
            'ru': 'Депозит',
            'ar': 'إيداع'
        },
        'mining': {
            'en': 'Mining',
            'es': 'Minería',
            'pt': 'Mineração',
            'ru': 'Майнинг',
            'ar': 'تعدين'
        },
        'referral': {
            'en': 'Referral',
            'es': 'Referido',
            'pt': 'Indicação',
            'ru': 'Реферал',
            'ar': 'إحالة'
        },
        'commission': {
            'en': 'Referral Commission',
            'es': 'Comisión Referido',
            'pt': 'Comissão Indicação',
            'ru': 'Реферальная комиссия',
            'ar': 'عمولة الإحالة'
        },
        'invitation': {
            'en': 'Invitation Bonus',
            'es': 'Bono Invitación',
            'pt': 'Bônus Convite',
            'ru': 'Бонус за приглашение',
            'ar': 'مكافأة الدعوة'
        },
        'task': {
            'en': 'Task',
            'es': 'Tarea',
            'pt': 'Tarefa',
            'ru': 'Задание',
            'ar': 'مهمة'
        },
        'promo': {
            'en': 'Promo Code',
            'es': 'Código Promo',
            'pt': 'Código Promo',
            'ru': 'Промокод',
            'ar': 'رمز ترويجي'
        },
        'swap': {
            'en': 'Swap',
            'es': 'Intercambio',
            'pt': 'Troca',
            'ru': 'Обмен',
            'ar': 'تبديل'
        },
        'upgrade': {
            'en': 'Upgrade',
            'es': 'Mejora',
            'pt': 'Melhoria',
            'ru': 'Улучшение',
            'ar': 'ترقية'
        },
        'game': {
            'en': 'Game',
            'es': 'Juego',
            'pt': 'Jogo',
            'ru': 'Игра',
            'ar': 'لعبة'
        },
        'bonus': {
            'en': 'Bonus',
            'es': 'Bono',
            'pt': 'Bônus',
            'ru': 'Бонус',
            'ar': 'مكافأة'
        },
        'ad_reward': {
            'en': 'Ad Reward',
            'es': 'Recompensa Anuncio',
            'pt': 'Recompensa Anúncio',
            'ru': 'Награда за рекламу',
            'ar': 'مكافأة إعلان'
        },
        'penalty': {
            'en': 'Penalty',
            'es': 'Penalidad',
            'pt': 'Penalidade',
            'ru': 'Штраф',
            'ar': 'غرامة'
        },
        'refund': {
            'en': 'Refund',
            'es': 'Reembolso',
            'pt': 'Reembolso',
            'ru': 'Возврат',
            'ar': 'استرداد'
        },
        'mining_machine': {
            'en': 'Mining Machine',
            'es': 'Máquina Minería',
            'pt': 'Máquina Mineração',
            'ru': 'Майнинг машина',
            'ar': 'آلة التعدين'
        },
        'other': {
            'en': 'Other',
            'es': 'Otro',
            'pt': 'Outro',
            'ru': 'Другое',
            'ar': 'أخرى'
        }
    },
    'labels': {
        'transaction_history': {
            'en': 'Transaction History',
            'es': 'Historial de Transacciones',
            'pt': 'Histórico de Transações',
            'ru': 'История транзакций',
            'ar': 'سجل المعاملات'
        },
        'all_currencies': {
            'en': 'All Currencies',
            'es': 'Todas las Monedas',
            'pt': 'Todas as Moedas',
            'ru': 'Все валюты',
            'ar': 'جميع العملات'
        },
        'all_types': {
            'en': 'All Types',
            'es': 'Todos los Tipos',
            'pt': 'Todos os Tipos',
            'ru': 'Все типы',
            'ar': 'جميع الأنواع'
        },
        'no_transactions': {
            'en': 'No transactions found',
            'es': 'No se encontraron transacciones',
            'pt': 'Nenhuma transação encontrada',
            'ru': 'Транзакции не найдены',
            'ar': 'لم يتم العثور على معاملات'
        },
        'amount': {
            'en': 'Amount',
            'es': 'Monto',
            'pt': 'Valor',
            'ru': 'Сумма',
            'ar': 'المبلغ'
        },
        'date': {
            'en': 'Date',
            'es': 'Fecha',
            'pt': 'Data',
            'ru': 'Дата',
            'ar': 'التاريخ'
        },
        'status': {
            'en': 'Status',
            'es': 'Estado',
            'pt': 'Status',
            'ru': 'Статус',
            'ar': 'الحالة'
        },
        'type': {
            'en': 'Type',
            'es': 'Tipo',
            'pt': 'Tipo',
            'ru': 'Тип',
            'ar': 'النوع'
        },
        'currency': {
            'en': 'Currency',
            'es': 'Moneda',
            'pt': 'Moeda',
            'ru': 'Валюта',
            'ar': 'العملة'
        },
        'tx_hash': {
            'en': 'Transaction Hash',
            'es': 'Hash de Transacción',
            'pt': 'Hash da Transação',
            'ru': 'Хэш транзакции',
            'ar': 'تجزئة المعاملة'
        },
        'wallet': {
            'en': 'Wallet',
            'es': 'Billetera',
            'pt': 'Carteira',
            'ru': 'Кошелек',
            'ar': 'المحفظة'
        },
        'view_explorer': {
            'en': 'View in Explorer',
            'es': 'Ver en Explorador',
            'pt': 'Ver no Explorador',
            'ru': 'Смотреть в обозревателе',
            'ar': 'عرض في المستكشف'
        },
        'export_csv': {
            'en': 'Export CSV',
            'es': 'Exportar CSV',
            'pt': 'Exportar CSV',
            'ru': 'Экспорт CSV',
            'ar': 'تصدير CSV'
        }
    }
}

def get_translation(category, key, lang='es'):
    """Obtiene una traducción por categoría, clave e idioma"""
    if lang not in ['en', 'es', 'pt', 'ru', 'ar']:
        lang = 'es'
    
    try:
        return TRANSLATIONS.get(category, {}).get(key, {}).get(lang, key)
    except:
        return key

def get_all_translations(lang='es'):
    """Obtiene todas las traducciones para un idioma"""
    if lang not in ['en', 'es', 'pt', 'ru', 'ar']:
        lang = 'es'
    
    result = {}
    for category, items in TRANSLATIONS.items():
        result[category] = {}
        for key, translations in items.items():
            result[category][key] = translations.get(lang, key)
    
    return result

# ============== FUNCIONES DE TRANSACCIONES ==============

def get_user_unified_transactions(user_id, currency=None, tx_type=None, limit=50, offset=0):
    """
    Obtiene todas las transacciones de un usuario de forma unificada
    Combina: balance_history, withdrawals, ton_payments
    
    Args:
        user_id: ID del usuario
        currency: Filtrar por moneda (DOGE, TON, USDT, SE) o None para todas
        tx_type: Filtrar por tipo (withdrawal, deposit, mining, etc.) o None para todos
        limit: Número máximo de resultados
        offset: Desplazamiento para paginación
    
    Returns:
        list: Lista de transacciones unificadas
    """
    user_id = str(user_id)
    transactions = []
    
    try:
        with get_cursor() as cursor:
            # 1. Obtener de balance_history (SE y otras monedas internas)
            cursor.execute("""
                SELECT 
                    id,
                    user_id,
                    currency,
                    amount,
                    action as tx_type,
                    description,
                    balance_before,
                    balance_after,
                    created_at,
                    NULL as tx_hash,
                    NULL as wallet_address,
                    'completed' as status,
                    'balance_history' as source
                FROM balance_history
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 200
            """, (user_id,))
            
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    tx = dict(row)
                else:
                    tx = {
                        'id': row[0],
                        'user_id': row[1],
                        'currency': row[2],
                        'amount': row[3],
                        'tx_type': row[4],
                        'description': row[5],
                        'balance_before': row[6],
                        'balance_after': row[7],
                        'created_at': row[8],
                        'tx_hash': row[9],
                        'wallet_address': row[10],
                        'status': row[11],
                        'source': row[12]
                    }
                
                # Normalizar tipo de transacción
                tx['tx_type'] = normalize_transaction_type(tx.get('tx_type'), tx.get('description'))
                tx['currency'] = (tx.get('currency') or 'SE').upper()
                transactions.append(tx)
            
            # 2. Obtener de withdrawals (DOGE, USDT, TON)
            cursor.execute("""
                SELECT 
                    withdrawal_id as id,
                    user_id,
                    currency,
                    amount,
                    'withdrawal' as tx_type,
                    CONCAT('Retiro a ', COALESCE(wallet_address, '')) as description,
                    NULL as balance_before,
                    NULL as balance_after,
                    created_at,
                    tx_hash,
                    wallet_address,
                    status,
                    'withdrawals' as source
                FROM withdrawals
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 100
            """, (user_id,))
            
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    tx = dict(row)
                else:
                    tx = {
                        'id': row[0],
                        'user_id': row[1],
                        'currency': row[2],
                        'amount': row[3],
                        'tx_type': row[4],
                        'description': row[5],
                        'balance_before': row[6],
                        'balance_after': row[7],
                        'created_at': row[8],
                        'tx_hash': row[9],
                        'wallet_address': row[10],
                        'status': row[11],
                        'source': row[12]
                    }
                tx['currency'] = (tx.get('currency') or 'DOGE').upper()
                transactions.append(tx)
            
            # 3. Obtener de ton_payments (TON específicamente)
            try:
                cursor.execute("""
                    SELECT 
                        id,
                        user_id,
                        'TON' as currency,
                        amount,
                        payment_type as tx_type,
                        CONCAT('TON ', payment_type) as description,
                        NULL as balance_before,
                        NULL as balance_after,
                        created_at,
                        tx_hash,
                        wallet_address,
                        status,
                        'ton_payments' as source
                    FROM ton_payments
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 100
                """, (user_id,))
                
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        tx = dict(row)
                    else:
                        tx = {
                            'id': row[0],
                            'user_id': row[1],
                            'currency': row[2],
                            'amount': row[3],
                            'tx_type': row[4],
                            'description': row[5],
                            'balance_before': row[6],
                            'balance_after': row[7],
                            'created_at': row[8],
                            'tx_hash': row[9],
                            'wallet_address': row[10],
                            'status': row[11],
                            'source': row[12]
                        }
                    tx['currency'] = 'TON'
                    transactions.append(tx)
            except Exception as e:
                print(f"[transactions] Tabla ton_payments no disponible: {e}")
        
        # Filtrar por moneda si se especifica
        if currency:
            currency = currency.upper()
            transactions = [tx for tx in transactions if tx.get('currency', '').upper() == currency]
        
        # Filtrar por tipo si se especifica
        if tx_type:
            tx_type = tx_type.lower()
            transactions = [tx for tx in transactions if tx.get('tx_type', '').lower() == tx_type]
        
        # Ordenar por fecha descendente
        transactions.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=True)
        
        # Eliminar duplicados basados en source + id
        seen = set()
        unique_transactions = []
        for tx in transactions:
            key = f"{tx.get('source')}_{tx.get('id')}"
            if key not in seen:
                seen.add(key)
                unique_transactions.append(tx)
        
        # Aplicar paginación
        return unique_transactions[offset:offset + limit]
        
    except Exception as e:
        print(f"[get_user_unified_transactions] Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def normalize_transaction_type(action, description=None):
    """
    Normaliza el tipo de transacción basado en action y description
    
    Args:
        action: La acción original (add, subtract, withdrawal, etc.)
        description: La descripción de la transacción
    
    Returns:
        str: Tipo normalizado de transacción
    """
    action = (action or '').lower().strip()
    desc = (description or '').lower().strip()
    
    # Debug
    # print(f"[normalize] action='{action}', desc='{desc}'")
    
    # Combinar para búsqueda
    combined = f"{action} {desc}"
    
    # 1. RETIROS - detectar primero
    if any(x in combined for x in ['withdrawal', 'withdraw', 'retiro']):
        return 'withdrawal'
    
    # 2. DEPÓSITOS
    if any(x in combined for x in ['deposit', 'depósito', 'deposito', 'ton deposit', 'doge deposit']):
        return 'deposit'
    
    # 3. SWAP/INTERCAMBIO
    if any(x in combined for x in ['swap:', 'swap ', 'intercambio', 'exchange', 'received']):
        if 'swap' in combined:
            return 'swap'
    
    # 4. JUEGOS (ruleta, minas, etc.)
    if any(x in combined for x in ['roulette', 'ruleta', 'mines game', 'mines ', 'game win', 'game bet', 'spin', 'casino', 'dice']):
        return 'game'
    
    # 5. MINERÍA
    if any(x in combined for x in ['mining', 'minería', 'mineria', 'mining claim', 'mined']):
        return 'mining'
    
    # 6. TAREAS
    if any(x in combined for x in ['task:', 'task ', 'tarea', 'task completed', 'ad watched in task']):
        return 'task'
    
    # 7. COMISIONES DE REFERIDOS
    if any(x in combined for x in ['referral bonus', 'referral commission', 'comisión referido', 'comision referido']):
        return 'commission'
    
    # 8. REFERIDOS GENÉRICOS
    if any(x in combined for x in ['referral', 'referido', 'invited']):
        return 'referral'
    
    # 9. CÓDIGOS PROMO
    if any(x in combined for x in ['promo code', 'promo:', 'promoción', 'promocion']):
        return 'promo'
    
    # 10. MEJORAS
    if any(x in combined for x in ['upgrade', 'mejora', 'level up']):
        return 'upgrade'
    
    # 11. BONOS
    if any(x in combined for x in ['bonus', 'bono']):
        return 'bonus'
    
    # 12. RECOMPENSAS DE ANUNCIOS
    if any(x in combined for x in ['ad reward', 'ad watched', 'anuncio', 'telega', 'reward video', 'watch ads', 'task center ad', 'monetag', 'adsgram']):
        return 'ad_reward'
    
    # 13. PENALIDADES
    if any(x in combined for x in ['penalty', 'penalidad', 'left @']):
        return 'penalty'
    
    # 14. REEMBOLSOS
    if any(x in combined for x in ['refund', 'reembolso', 'rejected refund', 'failed refund']):
        return 'refund'
    
    # 15. MÁQUINAS DE MINERÍA
    if any(x in combined for x in ['machine', 'máquina', 'maquina', 'mining machine']):
        return 'mining_machine'
    
    # FALLBACK: Basado en action si no hay descripción útil
    if not desc or desc == action:
        if action == 'add':
            return 'deposit'
        elif action == 'subtract':
            return 'withdrawal'
    
    # Si tiene acción pero no detectamos tipo específico
    if action == 'add':
        return 'bonus'  # Ingresos sin categoría
    elif action == 'subtract':
        return 'withdrawal'  # Egresos sin categoría
    
    return 'other'

def format_transaction_for_display(tx, lang='es'):
    """
    Formatea una transacción para mostrar en la UI
    
    Args:
        tx: Diccionario de transacción
        lang: Código de idioma (en, es, pt, ru, ar)
    
    Returns:
        dict: Transacción formateada con traducciones
    """
    if not tx:
        return None
    
    currency = (tx.get('currency') or 'SE').upper()
    currency_config = CURRENCIES.get(currency, CURRENCIES['SE'])
    
    tx_type = tx.get('tx_type', 'other')
    status = tx.get('status', 'completed')
    
    # Formatear fecha
    created_at = tx.get('created_at')
    if created_at:
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                pass
        
        if isinstance(created_at, datetime):
            date_formatted = format_date_for_lang(created_at, lang)
            time_formatted = created_at.strftime('%H:%M')
        else:
            date_formatted = str(created_at)
            time_formatted = ''
    else:
        date_formatted = '-'
        time_formatted = ''
    
    # Formatear monto
    amount = float(tx.get('amount', 0))
    decimals = currency_config['decimals']
    amount_formatted = f"{amount:.{min(decimals, 8)}f}"
    
    # Determinar signo del monto
    is_negative = tx_type in ['withdrawal', 'subtract', 'upgrade', 'game'] or 'subtract' in str(tx.get('tx_type', '')).lower()
    amount_display = f"-{amount_formatted}" if is_negative else f"+{amount_formatted}"
    
    # Construir URL del explorador
    explorer_url = None
    tx_hash = tx.get('tx_hash')
    if tx_hash and currency_config.get('explorer'):
        explorer_url = currency_config['explorer'] + tx_hash
    
    # Acortar dirección de wallet
    wallet = tx.get('wallet_address', '')
    wallet_short = f"{wallet[:6]}...{wallet[-4:]}" if wallet and len(wallet) > 12 else wallet
    
    return {
        **tx,
        'currency': currency,
        'currency_name': currency_config['name'],
        'currency_color': currency_config['color'],
        'currency_icon': currency_config['icon'],
        'currency_network': currency_config['network'],
        'tx_type': tx_type,
        'tx_type_label': get_translation('type', tx_type, lang),
        'status': status,
        'status_label': get_translation('status', status, lang),
        'status_color': get_status_color(status),
        'amount': amount,
        'amount_formatted': amount_formatted,
        'amount_display': amount_display,
        'is_negative': is_negative,
        'date_formatted': date_formatted,
        'time_formatted': time_formatted,
        'tx_hash': tx_hash,
        'tx_hash_short': f"{tx_hash[:8]}...{tx_hash[-6:]}" if tx_hash and len(tx_hash) > 16 else tx_hash,
        'explorer_url': explorer_url,
        'wallet_address': wallet,
        'wallet_short': wallet_short
    }


def format_transaction_for_api(tx, lang='en'):
    """
    Formatea una transacción para la respuesta de la API
    Optimizado para el frontend historial_new.html
    
    Args:
        tx: Diccionario de transacción
        lang: Código de idioma (en, es, pt, ru, ar)
    
    Returns:
        dict: Transacción en formato para API
    """
    if not tx:
        return None
    
    currency = (tx.get('currency') or 'SE').upper()
    currency_config = CURRENCIES.get(currency, CURRENCIES['SE'])
    
    tx_type = tx.get('tx_type', 'mining')
    status = tx.get('status', 'completed')
    
    # Formatear timestamp
    created_at = tx.get('created_at')
    timestamp = None
    if created_at:
        if isinstance(created_at, datetime):
            timestamp = created_at.isoformat()
        elif isinstance(created_at, str):
            timestamp = created_at
    
    # Monto
    amount = float(tx.get('amount', 0))
    
    return {
        'id': tx.get('id'),
        'type': tx_type,
        'currency': currency,
        'amount': amount,
        'status': status,
        'description': tx.get('description', ''),
        'timestamp': timestamp,
        'tx_hash': tx.get('tx_hash'),
        'wallet_address': tx.get('wallet_address'),
        'network': currency_config.get('network', 'Internal'),
        'explorer': currency_config.get('explorer')
    }


def get_status_color(status):
    """Obtiene el color CSS para un estado"""
    colors = {
        'pending': '#FFA500',      # Naranja
        'processing': '#3498DB',   # Azul
        'completed': '#27AE60',    # Verde
        'confirmed': '#27AE60',    # Verde
        'failed': '#E74C3C',       # Rojo
        'rejected': '#95A5A6',     # Gris
        'cancelled': '#7F8C8D'     # Gris oscuro
    }
    return colors.get(status, '#95A5A6')

def format_date_for_lang(dt, lang='es'):
    """Formatea una fecha según el idioma"""
    if not dt:
        return '-'
    
    months = {
        'es': ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'],
        'en': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        'pt': ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'],
        'ru': ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
        'ar': ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
    }
    
    month_names = months.get(lang, months['es'])
    month = month_names[dt.month - 1]
    
    if lang == 'es':
        return f"{dt.day} de {month}, {dt.year}"
    elif lang == 'ar':
        return f"{dt.day} {month} {dt.year}"
    else:
        return f"{month} {dt.day}, {dt.year}"

def get_transaction_stats(user_id):
    """
    Obtiene estadísticas de transacciones de un usuario
    
    Returns:
        dict: Estadísticas por moneda y tipo
    """
    transactions = get_user_unified_transactions(user_id, limit=1000)
    
    stats = {
        'total_count': len(transactions),
        'by_currency': {},
        'by_type': {},
        'by_status': {}
    }
    
    for tx in transactions:
        currency = tx.get('currency', 'SE')
        tx_type = tx.get('tx_type', 'other')
        status = tx.get('status', 'completed')
        amount = float(tx.get('amount', 0))
        
        # Por moneda
        if currency not in stats['by_currency']:
            stats['by_currency'][currency] = {'count': 0, 'total': 0}
        stats['by_currency'][currency]['count'] += 1
        stats['by_currency'][currency]['total'] += amount
        
        # Por tipo
        if tx_type not in stats['by_type']:
            stats['by_type'][tx_type] = 0
        stats['by_type'][tx_type] += 1
        
        # Por estado
        if status not in stats['by_status']:
            stats['by_status'][status] = 0
        stats['by_status'][status] += 1
    
    return stats

def export_transactions_csv(user_id, lang='es'):
    """
    Exporta transacciones a formato CSV
    
    Returns:
        str: Contenido CSV
    """
    transactions = get_user_unified_transactions(user_id, limit=1000)
    
    # Cabeceras
    headers = [
        get_translation('labels', 'date', lang),
        get_translation('labels', 'type', lang),
        get_translation('labels', 'currency', lang),
        get_translation('labels', 'amount', lang),
        get_translation('labels', 'status', lang),
        get_translation('labels', 'tx_hash', lang),
        get_translation('labels', 'wallet', lang)
    ]
    
    lines = [','.join(headers)]
    
    for tx in transactions:
        formatted = format_transaction_for_display(tx, lang)
        row = [
            formatted.get('date_formatted', ''),
            formatted.get('tx_type_label', ''),
            formatted.get('currency', ''),
            formatted.get('amount_display', ''),
            formatted.get('status_label', ''),
            formatted.get('tx_hash', '') or '',
            formatted.get('wallet_address', '') or ''
        ]
        # Escapar comas en valores
        row = [f'"{v}"' if ',' in str(v) else str(v) for v in row]
        lines.append(','.join(row))
    
    return '\n'.join(lines)

# ============== REGISTRO DE TRANSACCIONES ==============

def log_transaction(user_id, currency, amount, tx_type, description=None, 
                   status='completed', tx_hash=None, wallet_address=None,
                   balance_before=None, balance_after=None):
    """
    Registra una transacción en el historial unificado
    
    Esta función se usa para registrar transacciones que no pasan
    por el sistema de balance_history normal (ej: TON payments)
    """
    try:
        # Para mantener compatibilidad, usamos balance_history
        # pero con campos adicionales cuando están disponibles
        from database import log_balance_change
        
        # Determinar acción basada en tipo
        action = 'add' if tx_type in ['deposit', 'mining', 'referral', 'task', 'promo', 'bonus', 'ad_reward'] else 'subtract'
        
        # Crear descripción si no existe
        if not description:
            description = f"{tx_type}: {amount} {currency}"
        
        log_balance_change(
            user_id=user_id,
            currency=currency.upper(),
            amount=amount,
            action=action,
            description=description,
            balance_before=balance_before,
            balance_after=balance_after
        )
        
        print(f"[log_transaction] ✅ Registrado: {user_id} {tx_type} {amount} {currency}")
        return True
        
    except Exception as e:
        print(f"[log_transaction] ❌ Error: {e}")
        return False
