"""
database.py - Operaciones principales de base de datos para SALLY-E Bot
Usa el pool de conexiones de db.py
FIXED VERSION - Referral validation only after first task completion
"""

import json
from datetime import datetime
from decimal import Decimal
from db import execute_query, execute_many, get_cursor

# ============== UPDATE_USER THROTTLING SYSTEM ==============
# In-memory cache to track when each user's profile was last updated
# Format: { user_id: datetime_of_last_profile_update }
_user_profile_update_cache = {}

# Throttle interval in seconds (5 hours = 5 * 60 * 60 = 18000 seconds)
_PROFILE_UPDATE_THROTTLE_SECONDS = 5 * 60 * 60

# Fields that are THROTTLED (profile-related, only update every 5 hours)
_THROTTLED_FIELDS = {
    'username',
    'first_name',
    'last_name',
    'last_ip',
    'banned',
    'ban_reason',
    'is_admin',
    'photo_url',
}

# language_code is NOT throttled - it should update immediately for notifications

# Fields that are CRITICAL (always update immediately, no throttling)
# These include: se_balance, total_mined, last_claim, completed_tasks, 
# referral_count, referral_validated, pending_referrer, mining_power,
# wallet_address, usdt_balance, doge_balance, and any other field not in _THROTTLED_FIELDS

def _should_allow_profile_update(user_id):
    """
    Check if enough time has passed to allow a profile update for this user.
    Returns True if 5 hours have passed or if user is not in cache.
    """
    user_id_str = str(user_id)
    now = datetime.now()
    
    if user_id_str not in _user_profile_update_cache:
        return True
    
    last_update = _user_profile_update_cache[user_id_str]
    elapsed_seconds = (now - last_update).total_seconds()
    
    return elapsed_seconds >= _PROFILE_UPDATE_THROTTLE_SECONDS

def _mark_profile_updated(user_id):
    """Mark that this user's profile was just updated."""
    _user_profile_update_cache[str(user_id)] = datetime.now()

# ============== HELPER FUNCTIONS ==============

def decimal_to_float(obj):
    """Convierte Decimal a float para compatibilidad JSON"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj

def row_to_dict(cursor, row):
    """Convierte una fila a diccionario - CORREGIDO para dictionary cursor"""
    if row is None:
        return None
    # Si row ya es un diccionario (dictionary cursor), solo convertir decimales
    if isinstance(row, dict):
        return decimal_to_float(row)
    # Si es tupla, convertir a diccionario
    columns = [col[0] for col in cursor.description]
    result = dict(zip(columns, row))
    return decimal_to_float(result)

def rows_to_list(cursor, rows):
    """Convierte múltiples filas a lista de diccionarios - CORREGIDO"""
    if not rows:
        return []
    # Si las filas ya son diccionarios, solo convertir decimales
    if rows and isinstance(rows[0], dict):
        return [decimal_to_float(row) for row in rows]
    # Si son tuplas, convertir a diccionarios
    columns = [col[0] for col in cursor.description]
    return [decimal_to_float(dict(zip(columns, row))) for row in rows]

def format_datetime(dt):
    """Formatea datetime a string ISO para consistencia"""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return str(dt)

# ============== USER OPERATIONS ==============

def get_user(user_id):
    """Obtiene un usuario por ID - MEJORADO con mejor manejo de completed_tasks"""
    if not user_id:
        print("[get_user] ⚠️ user_id es None o vacío")
        return None
        
    user_id = str(user_id)
    
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM users WHERE user_id = %s
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                user = row_to_dict(cursor, row)
                
                # Parse completed_tasks JSON - manejo robusto
                raw_tasks = user.get('completed_tasks')
                
                if raw_tasks is None:
                    user['completed_tasks'] = []
                elif isinstance(raw_tasks, list):
                    user['completed_tasks'] = [str(t) for t in raw_tasks if t]
                elif isinstance(raw_tasks, str):
                    if raw_tasks.strip() == '' or raw_tasks.strip() == 'null':
                        user['completed_tasks'] = []
                    else:
                        try:
                            parsed = json.loads(raw_tasks)
                            if isinstance(parsed, list):
                                user['completed_tasks'] = [str(t) for t in parsed if t]
                            else:
                                user['completed_tasks'] = []
                        except (json.JSONDecodeError, TypeError) as e:
                            print(f"[get_user] Error parseando completed_tasks: {e}")
                            user['completed_tasks'] = []
                else:
                    user['completed_tasks'] = []
                
                # Asegurar que banned es booleano
                user['banned'] = bool(user.get('banned', 0))
                
                return user
            else:
                print(f"[get_user] Usuario {user_id} no encontrado en la base de datos")
            return None
    except Exception as e:
        print(f"[get_user] ❌ Error obteniendo usuario {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_user(user_id, username=None, first_name=None, referrer_id=None):
    """
    Crea un nuevo usuario - MEJORADO con sistema de referidos corregido.
    El referrer_id se guarda como pending_referrer y solo se valida cuando
    el usuario complete su primera tarea.
    """
    try:
        user_id = str(user_id)
        first_name = first_name or 'Usuario'
        
        print(f"[create_user] Intentando crear usuario: {user_id}")
        
        # Guardar referrer_id como pending_referrer - NO se valida aquí
        pending_referrer = str(referrer_id) if referrer_id else None
        
        execute_query("""
            INSERT INTO users (user_id, username, first_name, pending_referrer, banned, created_at)
            VALUES (%s, %s, %s, %s, 0, NOW())
            ON DUPLICATE KEY UPDATE 
                username = COALESCE(VALUES(username), username),
                first_name = COALESCE(VALUES(first_name), first_name)
        """, (user_id, username, first_name, pending_referrer))
        
        # Si hay un referrer, crear la entrada en referrals pero SIN validar
        if pending_referrer:
            print(f"[create_user] Registrando referido pendiente: {pending_referrer} -> {user_id}")
            add_referral(pending_referrer, user_id, username=username, first_name=first_name)
            increment_stat('total_referrals')
        
        result = get_user(user_id)
        if result:
            print(f"[create_user] ✅ Usuario {user_id} creado/actualizado exitosamente")
            if pending_referrer:
                print(f"[create_user] 📋 Referido pendiente de validación hasta completar primera tarea")
        else:
            print(f"[create_user] ⚠️ Usuario {user_id} insertado pero no se pudo recuperar")
        
        return result
    except Exception as e:
        print(f"[create_user] ❌ Error creating user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_user(user_id, **kwargs):
    """Actualiza campos de un usuario - MEJORADO con logging
    
    OPTIMIZED: Profile fields (username, first_name, last_ip, banned, etc.) are 
    throttled to update only once every 5 hours to reduce log spam and DB writes.
    Critical fields (se_balance, total_mined, last_claim, etc.) always update immediately.
    """
    if not kwargs:
        return False
    
    # ============== THROTTLING LOGIC (ADDED) ==============
    # Separate kwargs into throttled (profile) and critical fields
    throttled_kwargs = {}
    critical_kwargs = {}
    
    for key, value in kwargs.items():
        if key in _THROTTLED_FIELDS:
            throttled_kwargs[key] = value
        else:
            critical_kwargs[key] = value
    
    # Check if we should allow profile updates (5 hour throttle)
    allow_profile_update = _should_allow_profile_update(user_id)
    
    # Build final kwargs: always include critical, only include throttled if allowed
    final_kwargs = dict(critical_kwargs)  # Critical fields always included
    
    if throttled_kwargs:
        if allow_profile_update:
            final_kwargs.update(throttled_kwargs)
            # Mark that profile was updated (will update cache after successful DB write)
            should_mark_profile_updated = True
        else:
            # Skip throttled fields - not enough time has passed
            should_mark_profile_updated = False
    else:
        should_mark_profile_updated = False
    
    # If no fields to update after throttling, return early (no log, no DB write)
    if not final_kwargs:
        return True  # Return True since there's no error, just nothing to do
    
    # Replace kwargs with final_kwargs for the rest of the function
    kwargs = final_kwargs
    # ============== END THROTTLING LOGIC ==============
    
    # Handle completed_tasks JSON conversion
    if 'completed_tasks' in kwargs:
        tasks_to_save = kwargs['completed_tasks']
        if not isinstance(tasks_to_save, list):
            tasks_to_save = []
        kwargs['completed_tasks'] = json.dumps(tasks_to_save)
        print(f"[update_user] Guardando completed_tasks como JSON: {kwargs['completed_tasks']}")
    
    # Handle boolean conversion for banned field
    if 'banned' in kwargs:
        kwargs['banned'] = 1 if kwargs['banned'] else 0
    
    set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [str(user_id)]
    
    try:
        execute_query(f"""
            UPDATE users SET {set_clause}
            WHERE user_id = %s
        """, values)
        print(f"[update_user] ✅ Usuario {user_id} actualizado: {list(kwargs.keys())}")
        
        # Mark profile as updated if we included throttled fields
        if should_mark_profile_updated:
            _mark_profile_updated(user_id)
        
        return True
    except Exception as e:
        print(f"[update_user] ❌ Error updating user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_all_users(limit=500, offset=0):
    """Obtiene todos los usuarios con paginación"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM users 
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        users = rows_to_list(cursor, cursor.fetchall())
        
        for user in users:
            user['banned'] = bool(user.get('banned', 0))
        
        return users


def get_all_users_no_limit():
    """Obtiene TODOS los usuarios sin límite - para admin panel"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM users 
            ORDER BY created_at DESC
        """)
        users = rows_to_list(cursor, cursor.fetchall())
        
        for user in users:
            user['banned'] = bool(user.get('banned', 0))
        
        return users

def get_all_users_with_referrals_no_limit():
    """Obtiene TODOS los usuarios con sus referidos - para admin panel"""
    users = get_all_users_no_limit()
    
    for user in users:
        user['referral_list'] = get_referrals(user['user_id'])
    
    return users

def search_users(search_term, limit=50):
    """Busca usuarios por nombre, username o ID"""
    if not search_term:
        return get_all_users(limit=limit)
    
    search_pattern = f"%{search_term}%"
    
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM users 
            WHERE user_id LIKE %s 
               OR username LIKE %s 
               OR first_name LIKE %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (search_pattern, search_pattern, search_pattern, limit))
        users = rows_to_list(cursor, cursor.fetchall())
        
        for user in users:
            user['banned'] = bool(user.get('banned', 0))
        
        return users

def get_users_count():
    """Obtiene el conteo total de usuarios"""
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM users")
        row = cursor.fetchone()
        if isinstance(row, dict):
            return row.get('count', 0)
        return row[0] if row else 0

def get_banned_users_count():
    """Obtiene el conteo de usuarios baneados"""
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE banned = 1")
        row = cursor.fetchone()
        if isinstance(row, dict):
            return row.get('count', 0)
        return row[0] if row else 0

def ban_user(user_id, reason=None):
    """Banea a un usuario"""
    print(f"[ban_user] Baneando usuario {user_id}, razón: {reason}")
    result = update_user(user_id, banned=True, ban_reason=reason)
    if result:
        print(f"[ban_user] ✅ Usuario {user_id} baneado exitosamente")
    return result

def unban_user(user_id):
    """Desbanea a un usuario"""
    print(f"[unban_user] Desbaneando usuario {user_id}")
    result = update_user(user_id, banned=False, ban_reason=None)
    if result:
        print(f"[unban_user] ✅ Usuario {user_id} desbaneado exitosamente")
    return result

def update_balance(user_id, currency, amount, operation='add', description=None, allow_negative=False):
    """Actualiza el balance de un usuario
    
    Args:
        user_id: ID del usuario
        currency: Tipo de moneda (se, usdt, doge, ton)
        amount: Cantidad a modificar
        operation: 'add', 'subtract', o 'set'
        description: Descripción de la transacción
        allow_negative: Si True, permite saldo negativo (para penalizaciones/deudas)
    """
    column_map = {
        'se': 'se_balance',
        's-e': 'se_balance',
        'usdt': 'usdt_balance',
        'doge': 'doge_balance',
        'ton': 'ton_balance'
    }
    
    column = column_map.get(currency.lower())
    if not column:
        print(f"[update_balance] ❌ Moneda no válida: {currency}")
        return False
    
    try:
        user = get_user(user_id)
        if not user:
            print(f"[update_balance] ❌ Usuario {user_id} no encontrado")
            return False
        
        balance_before = float(user.get(column, 0) or 0)
        
        if operation == 'add':
            sql = f"UPDATE users SET {column} = {column} + %s WHERE user_id = %s"
            balance_after = balance_before + float(amount)
        elif operation == 'subtract':
            if allow_negative:
                # Permite saldo negativo (para penalizaciones/deudas)
                sql = f"UPDATE users SET {column} = {column} - %s WHERE user_id = %s"
                balance_after = balance_before - float(amount)
            else:
                # No permite saldo negativo (comportamiento original)
                sql = f"UPDATE users SET {column} = GREATEST(0, {column} - %s) WHERE user_id = %s"
                balance_after = max(0, balance_before - float(amount))
        elif operation == 'set':
            sql = f"UPDATE users SET {column} = %s WHERE user_id = %s"
            balance_after = float(amount)
        else:
            print(f"[update_balance] ❌ Operación no válida: {operation}")
            return False
        
        execute_query(sql, (float(amount), str(user_id)))
        
        log_balance_change(user_id, currency.upper(), amount, operation, description, balance_before, balance_after)
        
        print(f"[update_balance] ✅ Balance {operation}: {user_id} {currency} {amount} ({balance_before} -> {balance_after})")
        return True
    except Exception as e:
        print(f"[update_balance] ❌ Error updating balance: {e}")
        import traceback
        traceback.print_exc()
        return False

def log_balance_change(user_id, currency, amount, action, description=None, balance_before=None, balance_after=None):
    """Registra cambios de balance para auditoría"""
    try:
        execute_query("""
            INSERT INTO balance_history (user_id, currency, amount, action, description, balance_before, balance_after, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (str(user_id), currency, float(amount), action, description, balance_before, balance_after))
        print(f"[log_balance_change] ✅ Registrado: {user_id} {action} {amount} {currency}")
    except Exception as e:
        print(f"[log_balance_change] ⚠️ Error (no crítico): {e}")

def get_user_balance_history(user_id, limit=50):
    """Obtiene el historial de balance de un usuario"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM balance_history 
            WHERE user_id = %s 
            ORDER BY created_at DESC
            LIMIT %s
        """, (str(user_id), limit))
        return rows_to_list(cursor, cursor.fetchall())

def get_user_with_referrals(user_id):
    """Obtiene un usuario con su lista de referidos"""
    user = get_user(user_id)
    if not user:
        return None
    
    user['referral_list'] = get_referrals(user_id)
    return user

def get_all_users_with_referrals(limit=50, offset=0, search=None):
    """Obtiene todos los usuarios con sus referidos"""
    if search:
        users = search_users(search, limit=limit)
    else:
        users = get_all_users(limit=limit, offset=offset)
    
    for user in users:
        user['referral_list'] = get_referrals(user['user_id'])
    
    return users

# ============== REFERRAL OPERATIONS - FIXED ==============

def add_referral(referrer_id, referred_id, username=None, first_name=None):
    """
    Añade una relación de referido - NO VALIDA INMEDIATAMENTE.
    La validación se hace cuando el referido complete su primera tarea.
    """
    try:
        execute_query("""
            INSERT INTO referrals (referrer_id, referred_id, referred_username, referred_first_name, validated, bonus_paid, created_at)
            VALUES (%s, %s, %s, %s, 0, 0, NOW())
            ON DUPLICATE KEY UPDATE 
                referred_username = COALESCE(VALUES(referred_username), referred_username),
                referred_first_name = COALESCE(VALUES(referred_first_name), referred_first_name)
        """, (str(referrer_id), str(referred_id), username, first_name or 'Usuario'))
        print(f"[add_referral] ✅ Referido registrado (pendiente): {referrer_id} -> {referred_id}")
        return True
    except Exception as e:
        print(f"[add_referral] ❌ Error adding referral: {e}")
        return False

def validate_referral(referrer_id, referred_id):
    """
    Valida un referido y paga el bonus al referrer.
    Esta función se llama cuando el referido completa su primera tarea.
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT validated, bonus_paid FROM referrals 
                WHERE referrer_id = %s AND referred_id = %s
            """, (str(referrer_id), str(referred_id)))
            row = cursor.fetchone()
            
            if not row:
                print(f"[validate_referral] ⚠️ Referral no encontrado: {referrer_id} -> {referred_id}")
                return False
            
            validated = row.get('validated') if isinstance(row, dict) else row[0]
            bonus_paid = row.get('bonus_paid') if isinstance(row, dict) else row[1]
            
            if validated:
                print(f"[validate_referral] ⚠️ Referral ya validado: {referrer_id} -> {referred_id}")
                return True
        
        # Get bonus amount from config
        bonus = float(get_config('referral_bonus', 1.0))
        
        # Mark as validated and record bonus
        execute_query("""
            UPDATE referrals SET validated = 1, validated_at = NOW(), bonus_paid = %s
            WHERE referrer_id = %s AND referred_id = %s
        """, (bonus, str(referrer_id), str(referred_id)))
        
        # Pay bonus to referrer if not already paid
        if not bonus_paid or float(bonus_paid) == 0:
            update_balance(referrer_id, 'se', bonus, 'add', f'Referral bonus: user {referred_id} completed first task')
            print(f"[validate_referral] ✅ Bonus de {bonus} S-E pagado a {referrer_id}")
            
            # Agregar PTS por referido (50 PTS al invitador)
            pts_reward = 50  # PTS por invitación exitosa
            pts_added = False
            try:
                from onclicka_pts_system import add_pts
                success_pts, msg_pts = add_pts(referrer_id, pts_reward, 'referral', f'Referido validado: {referred_id}')
                if success_pts:
                    pts_added = True
                    print(f"[validate_referral] ✅ +{pts_reward} PTS agregados a {referrer_id}")
                else:
                    print(f"[validate_referral] ⚠️ No se pudieron agregar PTS: {msg_pts}")
            except Exception as pts_error:
                print(f"[validate_referral] ⚠️ Error agregando PTS: {pts_error}")
                import traceback
                traceback.print_exc()
            
            # Enviar notificación al invitador (incluye PTS si se agregaron)
            try:
                referred_user = get_user(referred_id)
                referred_name = referred_user.get('first_name', 'Usuario') if referred_user else 'Usuario'
                send_referral_notification(referrer_id, referred_name, bonus, pts_reward if pts_added else 0)
            except Exception as notif_error:
                print(f"[validate_referral] ⚠️ Error enviando notificación: {notif_error}")
        
        # Update referral count
        update_referral_count(referrer_id)
        
        # Update stats
        increment_stat('validated_referrals')
        
        # Clear pending_referrer from the referred user
        update_user(referred_id, pending_referrer=None, referral_validated=True)
        
        # Hook para el módulo de misiones de referidos (si está disponible)
        try:
            from referral_missions import on_new_referral
            referred_user = get_user(referred_id)
            referred_username = referred_user.get('username') if referred_user else None
            on_new_referral(referrer_id, referred_id, referred_username)
        except ImportError:
            pass  # El módulo de misiones no está disponible, continuar normalmente
        except Exception as e:
            print(f"[validate_referral] ⚠️ Error notificando misiones de referidos: {e}")
        
        print(f"[validate_referral] ✅ Referral validado: {referrer_id} <- {referred_id}")
        return True
    except Exception as e:
        print(f"[validate_referral] ❌ Error validating referral: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_first_task_completion(user_id):
    """
    Procesa la validación de referido cuando un usuario completa su primera tarea.
    Verifica si el usuario tiene un pending_referrer y valida el referido.
    Returns: (success, referrer_id, bonus_amount) or (False, None, 0)
    """
    try:
        user = get_user(user_id)
        if not user:
            return False, None, 0
        
        pending_referrer = user.get('pending_referrer')
        already_validated = user.get('referral_validated', False)
        
        # Si ya fue validado o no tiene referrer pendiente, no hacer nada
        if already_validated or not pending_referrer:
            print(f"[process_first_task_completion] Usuario {user_id}: no referrer pendiente o ya validado")
            return False, None, 0
        
        # Verificar que sea realmente la primera tarea
        completed_tasks = user.get('completed_tasks', [])
        if len(completed_tasks) > 1:
            print(f"[process_first_task_completion] Usuario {user_id}: ya tiene más de 1 tarea completada")
            return False, None, 0
        
        # Validar el referido
        bonus = float(get_config('referral_bonus', 1.0))
        success = validate_referral(pending_referrer, user_id)
        
        if success:
            print(f"[process_first_task_completion] ✅ Referido validado exitosamente: {pending_referrer} <- {user_id}")
            return True, pending_referrer, bonus
        
        return False, None, 0
        
    except Exception as e:
        print(f"[process_first_task_completion] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, None, 0

def is_first_task(user_id):
    """Verifica si el usuario está a punto de completar su primera tarea"""
    user = get_user(user_id)
    if not user:
        return False
    
    completed_tasks = user.get('completed_tasks', [])
    return len(completed_tasks) == 0

def update_referral_count(user_id):
    """Actualiza el conteo de referidos VALIDADOS"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM referrals 
                WHERE referrer_id = %s AND validated = TRUE
            """, (str(user_id),))
            row = cursor.fetchone()
            count = row.get('cnt', 0) if isinstance(row, dict) else row[0]
        
        update_user(user_id, referral_count=count)
        print(f"[update_referral_count] Usuario {user_id}: {count} referidos validados")
        return count
    except Exception as e:
        print(f"[update_referral_count] ❌ Error: {e}")
        return 0

def get_referrals(user_id):
    """Obtiene los referidos de un usuario (validados y pendientes)"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT r.*, u.username, u.first_name 
            FROM referrals r
            LEFT JOIN users u ON r.referred_id = u.user_id
            WHERE r.referrer_id = %s
            ORDER BY r.created_at DESC
        """, (str(user_id),))
        return rows_to_list(cursor, cursor.fetchall())

def get_referrals_paginated(user_id, page=1, per_page=20):
    """
    Obtiene los referidos de un usuario con paginación.
    Args:
        user_id: ID del usuario
        page: Número de página (1-indexed)
        per_page: Cantidad de referidos por página
    Returns:
        dict con 'referrals', 'total', 'page', 'per_page', 'has_more'
    """
    try:
        offset = (page - 1) * per_page
        
        with get_cursor() as cursor:
            # Obtener el total de referidos
            cursor.execute("""
                SELECT COUNT(*) as total FROM referrals 
                WHERE referrer_id = %s
            """, (str(user_id),))
            total_row = cursor.fetchone()
            total = total_row.get('total', 0) if isinstance(total_row, dict) else total_row[0]
            
            # Obtener referidos paginados
            cursor.execute("""
                SELECT r.*, u.username, u.first_name 
                FROM referrals r
                LEFT JOIN users u ON r.referred_id = u.user_id
                WHERE r.referrer_id = %s
                ORDER BY r.created_at DESC
                LIMIT %s OFFSET %s
            """, (str(user_id), per_page, offset))
            referrals = rows_to_list(cursor, cursor.fetchall())
            
            # Calcular si hay más páginas
            has_more = (offset + len(referrals)) < total
            
            return {
                'referrals': referrals,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_more': has_more
            }
    except Exception as e:
        print(f"[get_referrals_paginated] ❌ Error: {e}")
        return {
            'referrals': [],
            'total': 0,
            'page': page,
            'per_page': per_page,
            'has_more': False
        }

def get_referrals_counts(user_id):
    """
    Obtiene los conteos de referidos validados y pendientes.
    Returns: (validated_count, pending_count, total)
    """
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN validated = TRUE THEN 1 ELSE 0 END) as validated,
                    SUM(CASE WHEN validated = FALSE OR validated IS NULL THEN 1 ELSE 0 END) as pending
                FROM referrals 
                WHERE referrer_id = %s
            """, (str(user_id),))
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    return (
                        int(row.get('validated', 0) or 0),
                        int(row.get('pending', 0) or 0),
                        int(row.get('total', 0) or 0)
                    )
                else:
                    return (int(row[1] or 0), int(row[2] or 0), int(row[0] or 0))
            return (0, 0, 0)
    except Exception as e:
        print(f"[get_referrals_counts] ❌ Error: {e}")
        return (0, 0, 0)

def send_referral_notification(referrer_id, referred_name, bonus, pts_reward=0):
    """
    Envía una notificación al invitador cuando su referido completa la verificación.
    Args:
        referrer_id: ID de Telegram del invitador
        referred_name: Nombre del referido que completó la tarea
        bonus: Cantidad de S-E acreditados
        pts_reward: Cantidad de PTS acreditados (default 0)
    Returns: True si se envió correctamente, False en caso contrario
    """
    import os
    import requests
    
    try:
        bot_token = os.environ.get('BOT_TOKEN', '')
        if not bot_token:
            print("[send_referral_notification] ❌ BOT_TOKEN no configurado")
            return False
        
        # Escapar caracteres especiales en el nombre
        safe_name = referred_name.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;') if referred_name else 'Usuario'
        
        # Construir línea de recompensa
        reward_line = f"💰 <b>Recompensa:</b> +{bonus:.2f} S-E"
        if pts_reward > 0:
            reward_line += f" y +{pts_reward} PTS"
        
        # Mensaje de notificación en español
        message = (
            f"🎉 <b>¡Nuevo referido validado!</b>\n\n"
            f"👤 <b>Referido:</b> {safe_name}\n"
            f"✅ <b>Estado:</b> Tarea completada exitosamente\n"
            f"{reward_line}\n\n"
            f"💎 ¡La recompensa ya fue acreditada a tu cuenta!\n\n"
            f"Sigue invitando amigos para ganar más S-E 🚀"
        )
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': referrer_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print(f"[send_referral_notification] ✅ Notificación enviada a {referrer_id}")
                return True
            else:
                print(f"[send_referral_notification] ❌ Error API: {result.get('description')}")
                return False
        else:
            print(f"[send_referral_notification] ❌ HTTP Error: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"[send_referral_notification] ❌ Timeout enviando notificación a {referrer_id}")
        return False
    except Exception as e:
        print(f"[send_referral_notification] ❌ Error: {e}")
        return False

def get_validated_referrals_count(user_id):
    """Obtiene el conteo de referidos validados"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM referrals 
            WHERE referrer_id = %s AND validated = TRUE
        """, (str(user_id),))
        row = cursor.fetchone()
        return row.get('cnt', 0) if isinstance(row, dict) else row[0]

def get_pending_referrer(user_id):
    """Obtiene el referidor pendiente de un usuario"""
    user = get_user(user_id)
    return user.get('pending_referrer') if user else None

def clear_pending_referrer(user_id):
    """Limpia el referidor pendiente"""
    return update_user(user_id, pending_referrer=None)

# ============== TASK OPERATIONS ==============

def get_all_tasks():
    """Obtiene todas las tareas"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        tasks = rows_to_list(cursor, cursor.fetchall())
        for task in tasks:
            task['requires_channel_join'] = bool(task.get('requires_channel_join', 0))
            task['active'] = bool(task.get('active', 1))
        return tasks

def get_active_tasks():
    """Obtiene solo tareas activas"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM tasks WHERE active = TRUE ORDER BY created_at DESC")
        tasks = rows_to_list(cursor, cursor.fetchall())
        for task in tasks:
            task['requires_channel_join'] = bool(task.get('requires_channel_join', 0))
            task['active'] = bool(task.get('active', 1))
        return tasks

def get_task(task_id):
    """Obtiene una tarea por ID"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
        task = row_to_dict(cursor, cursor.fetchone())
        if task:
            task['requires_channel_join'] = bool(task.get('requires_channel_join', 0))
            task['active'] = bool(task.get('active', 1))
        return task

def create_task(title, description, reward, url=None, task_type='link', active=True, requires_channel_join=False, channel_username=None):
    """Crea una nueva tarea"""
    import uuid
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    try:
        if channel_username:
            channel_username = channel_username.strip()
            if channel_username.startswith('@'):
                channel_username = channel_username[1:]
        else:
            channel_username = None
        
        requires_channel_join = 1 if requires_channel_join else 0
        
        execute_query("""
            INSERT INTO tasks (task_id, title, description, reward, url, task_type, active, requires_channel_join, channel_username, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (task_id, title, description, float(reward), url, task_type, active, requires_channel_join, channel_username))
        
        print(f"[create_task] ✅ Tarea creada: {task_id}")
        return True
    except Exception as e:
        print(f"[create_task] ❌ Error creating task: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_task(task_id, **kwargs):
    """Actualiza una tarea"""
    if not kwargs:
        return False
    
    if 'channel_username' in kwargs:
        channel = kwargs['channel_username']
        if channel:
            channel = channel.strip()
            if channel.startswith('@'):
                channel = channel[1:]
            kwargs['channel_username'] = channel if channel else None
        else:
            kwargs['channel_username'] = None
    
    if 'requires_channel_join' in kwargs:
        kwargs['requires_channel_join'] = 1 if kwargs['requires_channel_join'] else 0
    
    if 'active' in kwargs:
        kwargs['active'] = 1 if kwargs['active'] else 0
    
    set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [task_id]
    
    try:
        execute_query(f"""
            UPDATE tasks SET {set_clause}
            WHERE task_id = %s
        """, values)
        print(f"[update_task] ✅ Tarea {task_id} actualizada")
        return True
    except Exception as e:
        print(f"[update_task] ❌ Error updating task: {e}")
        return False

def delete_task(task_id):
    """Elimina una tarea"""
    try:
        print(f"[delete_task] Intentando eliminar tarea: {task_id}")
        execute_query("DELETE FROM tasks WHERE task_id = %s", (task_id,))
        print(f"[delete_task] ✅ Tarea {task_id} eliminada")
        return True
    except Exception as e:
        print(f"[delete_task] ❌ Error deleting task {task_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def complete_task(user_id, task_id, reward=None):
    """
    Marca una tarea como completada y paga recompensa.
    FIXED: También procesa la validación del referido si es la primera tarea.
    Returns (success, message)
    """
    user = get_user(user_id)
    if not user:
        return False, "Usuario no encontrado"
    
    completed = user.get('completed_tasks', [])
    if str(task_id) in completed:
        return False, "Tarea ya completada"
    
    # Check if this is the first task (before adding to completed list)
    is_first = len(completed) == 0
    
    # Get task reward if not provided
    if reward is None:
        task = get_task(task_id)
        if task:
            reward = task.get('reward', 0)
        else:
            reward = 0
    
    # Mark as completed
    completed.append(str(task_id))
    update_user(user_id, completed_tasks=completed)
    
    # Pay reward
    if reward > 0:
        update_balance(user_id, 'se', reward, 'add', f'Task completed: {task_id}')
    
    # Update task completion count
    execute_query("""
        UPDATE tasks SET current_completions = current_completions + 1 
        WHERE task_id = %s
    """, (task_id,))
    
    # Update stats
    increment_stat('total_tasks_completed')
    
    # Process referral validation if this is the first task
    referral_message = ""
    if is_first:
        print(f"[complete_task] Primera tarea para usuario {user_id}, procesando referido...")
        success, referrer_id, bonus = process_first_task_completion(user_id)
        if success:
            referral_message = f" Tu referidor recibió {bonus} S-E."
            print(f"[complete_task] ✅ Referido validado: {referrer_id} recibió {bonus} S-E")
    
    return True, f"¡Tarea completada! +{reward:.4f} S-E{referral_message}"

def is_task_completed(user_id, task_id):
    """Verifica si un usuario completó una tarea"""
    user = get_user(user_id)
    if not user:
        return False
    completed = user.get('completed_tasks', [])
    return str(task_id) in completed

# ============== WITHDRAWAL OPERATIONS ==============

def create_withdrawal(user_id, currency, amount, wallet_address, fee=0):
    """Crea una solicitud de retiro"""
    import uuid
    withdrawal_id = f"wd_{uuid.uuid4().hex[:12]}"
    try:
        execute_query("""
            INSERT INTO withdrawals (withdrawal_id, user_id, currency, amount, fee, wallet_address, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW())
        """, (withdrawal_id, str(user_id), currency, float(amount), float(fee), wallet_address))
        return withdrawal_id
    except Exception as e:
        print(f"Error creating withdrawal: {e}")
        return None

def get_withdrawal(withdrawal_id):
    """Obtiene un retiro por ID"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM withdrawals WHERE withdrawal_id = %s", (withdrawal_id,))
        return row_to_dict(cursor, cursor.fetchone())

def get_user_withdrawals(user_id, limit=20):
    """Obtiene los retiros de un usuario"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM withdrawals 
            WHERE user_id = %s 
            ORDER BY created_at DESC
            LIMIT %s
        """, (str(user_id), limit))
        return rows_to_list(cursor, cursor.fetchall())

def get_pending_withdrawals():
    """Obtiene retiros pendientes"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM withdrawals 
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """)
        return rows_to_list(cursor, cursor.fetchall())

def get_withdrawals_by_status(status):
    """Obtiene retiros por estado"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM withdrawals 
            WHERE status = %s
            ORDER BY created_at DESC
        """, (status,))
        return rows_to_list(cursor, cursor.fetchall())

def get_all_withdrawals(limit=100):
    """Obtiene todos los retiros"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM withdrawals 
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        return rows_to_list(cursor, cursor.fetchall())

def update_withdrawal(withdrawal_id, **kwargs):
    """Actualiza un retiro"""
    if not kwargs:
        return False
    
    set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [withdrawal_id]
    
    try:
        execute_query(f"""
            UPDATE withdrawals SET {set_clause}
            WHERE withdrawal_id = %s
        """, values)
        return True
    except:
        return False

# ============== PROMO CODE OPERATIONS ==============

def get_all_promo_codes():
    """Obtiene todos los códigos promocionales"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
        codes = rows_to_list(cursor, cursor.fetchall())
        for code in codes:
            code['active'] = bool(code.get('active', 1))
        return codes

def get_promo_code(code):
    """Obtiene un código promocional por código"""
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM promo_codes WHERE code = %s", (code.upper(),))
        promo = row_to_dict(cursor, cursor.fetchone())
        if promo:
            promo['active'] = bool(promo.get('active', 1))
        return promo

def create_promo_code(code, reward, currency='SE', max_uses=None, expires_at=None, active=True):
    """Crea un nuevo código promocional"""
    try:
        execute_query("""
            INSERT INTO promo_codes (code, reward, currency, max_uses, current_uses, active, expires_at, created_at)
            VALUES (%s, %s, %s, %s, 0, %s, %s, NOW())
        """, (code.upper(), float(reward), currency, max_uses, 1 if active else 0, expires_at))
        print(f"[create_promo_code] ✅ Código creado: {code}")
        return True
    except Exception as e:
        print(f"[create_promo_code] ❌ Error: {e}")
        return False

def redeem_promo_code(user_id, code):
    """
    Canjea un código promocional.
    Returns (success, message)
    """
    try:
        code = code.upper().strip()
        promo = get_promo_code(code)
        
        if not promo:
            return False, "Código no válido"
        
        if not promo.get('active'):
            return False, "Este código ya no está activo"
        
        # Check expiration
        if promo.get('expires_at'):
            from datetime import datetime
            expires = promo['expires_at']
            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            if datetime.now() > expires:
                return False, "Este código ha expirado"
        
        # Check max uses
        if promo.get('max_uses') is not None:
            if promo.get('current_uses', 0) >= promo['max_uses']:
                return False, "Este código ya alcanzó su límite de usos"
        
        # Check if user already redeemed
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM promo_redemptions 
                WHERE user_id = %s AND code = %s
            """, (str(user_id), code))
            if cursor.fetchone():
                return False, "Ya canjeaste este código"
        
        # Redeem
        reward = float(promo.get('reward', 0))
        currency = promo.get('currency', 'SE').lower()
        
        # Add balance
        update_balance(user_id, currency, reward, 'add', f'Promo code: {code}')
        
        # Record redemption
        execute_query("""
            INSERT INTO promo_redemptions (user_id, code, reward, currency, redeemed_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (str(user_id), code, reward, currency.upper()))
        
        # Increment uses
        execute_query("""
            UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code = %s
        """, (code,))
        
        return True, f"¡Código canjeado! +{reward} {currency.upper()}"
        
    except Exception as e:
        print(f"[redeem_promo_code] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, "Error procesando el código"

def delete_promo_code(code):
    """Elimina un código promocional por código"""
    try:
        execute_query("DELETE FROM promo_codes WHERE code = %s", (code.upper(),))
        return True
    except:
        return False

def delete_promo_code_by_id(promo_id):
    """Elimina un código promocional por ID"""
    try:
        execute_query("DELETE FROM promo_codes WHERE id = %s", (promo_id,))
        return True
    except:
        return False

def has_available_promo_codes():
    """Verifica si hay códigos promocionales disponibles"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 1 FROM promo_codes 
            WHERE active = 1 
            AND (max_uses IS NULL OR current_uses < max_uses)
            AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
        """)
        return cursor.fetchone() is not None

def get_promo_stats():
    """Obtiene estadísticas de códigos promocionales"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_codes,
                SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) as active_codes,
                SUM(current_uses) as total_uses
            FROM promo_codes
        """)
        row = cursor.fetchone()
        if isinstance(row, dict):
            return row
        return {'total_codes': 0, 'active_codes': 0, 'total_uses': 0}

def toggle_promo_code(code):
    """Activa/desactiva un código promocional"""
    try:
        execute_query("""
            UPDATE promo_codes SET active = NOT active WHERE code = %s
        """, (code.upper(),))
        return True
    except:
        return False

def cleanup_empty_promo_codes():
    """Elimina códigos promocionales vacíos o expirados"""
    try:
        execute_query("""
            DELETE FROM promo_codes 
            WHERE (max_uses IS NOT NULL AND current_uses >= max_uses)
            OR (expires_at IS NOT NULL AND expires_at < NOW())
        """)
        return True
    except:
        return False

def get_promo_redemptions(code=None, limit=100):
    """Obtiene los canjes de códigos promocionales"""
    with get_cursor() as cursor:
        if code:
            cursor.execute("""
                SELECT pr.*, u.username, u.first_name
                FROM promo_redemptions pr
                LEFT JOIN users u ON pr.user_id = u.user_id
                WHERE pr.code = %s
                ORDER BY pr.redeemed_at DESC
                LIMIT %s
            """, (code.upper(), limit))
        else:
            cursor.execute("""
                SELECT pr.*, u.username, u.first_name
                FROM promo_redemptions pr
                LEFT JOIN users u ON pr.user_id = u.user_id
                ORDER BY pr.redeemed_at DESC
                LIMIT %s
            """, (limit,))
        return rows_to_list(cursor, cursor.fetchall())

def update_promo_code(code, **kwargs):
    """Actualiza un código promocional"""
    if not kwargs:
        return False
    
    if 'active' in kwargs:
        kwargs['active'] = 1 if kwargs['active'] else 0
    
    set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
    values = list(kwargs.values()) + [code.upper()]
    
    try:
        execute_query(f"""
            UPDATE promo_codes SET {set_clause}
            WHERE code = %s
        """, values)
        return True
    except:
        return False

# ============== CONFIG OPERATIONS ==============

def get_config(key, default=None):
    """Obtiene un valor de configuración"""
    with get_cursor() as cursor:
        cursor.execute("SELECT config_value FROM config WHERE config_key = %s", (key,))
        row = cursor.fetchone()
        if row:
            value = row.get('config_value') if isinstance(row, dict) else row[0]
            if value is not None:
                try:
                    if '.' in str(value):
                        return float(value)
                    return int(value)
                except (ValueError, TypeError):
                    if value == 'None' or value == 'null':
                        return False
                    return value
        return default

def set_config(key, value):
    """Establece un valor de configuración"""
    try:
        execute_query("""
            INSERT INTO config (config_key, config_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
        """, (key, str(value)))
        return True
    except:
        return False

def get_all_config():
    """Obtiene toda la configuración"""
    with get_cursor() as cursor:
        cursor.execute("SELECT config_key, config_value FROM config")
        rows = cursor.fetchall()
        if rows and isinstance(rows[0], dict):
            return {row['config_key']: row['config_value'] for row in rows}
        return {row[0]: row[1] for row in rows}

# ============== STATS OPERATIONS ==============

def get_stats():
    """Obtiene todas las estadísticas"""
    with get_cursor() as cursor:
        cursor.execute("SELECT stat_key, stat_value FROM stats")
        rows = cursor.fetchall()
        if rows and isinstance(rows[0], dict):
            return {row['stat_key']: int(row['stat_value']) for row in rows}
        return {row[0]: int(row[1]) for row in rows}

def get_stat(key, default=0):
    """Obtiene una estadística"""
    with get_cursor() as cursor:
        cursor.execute("SELECT stat_value FROM stats WHERE stat_key = %s", (key,))
        row = cursor.fetchone()
        if row:
            value = row.get('stat_value') if isinstance(row, dict) else row[0]
            return int(value) if value else default
        return default

def increment_stat(key, amount=1):
    """Incrementa una estadística"""
    try:
        execute_query("""
            INSERT INTO stats (stat_key, stat_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE stat_value = stat_value + VALUES(stat_value)
        """, (key, amount))
        return True
    except:
        return False

def set_stat(key, value):
    """Establece una estadística"""
    try:
        execute_query("""
            INSERT INTO stats (stat_key, stat_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE stat_value = VALUES(stat_value)
        """, (key, value))
        return True
    except:
        return False

# ============== IP OPERATIONS ==============

def record_user_ip(user_id, ip_address):
    """Registra la IP de un usuario"""
    if not ip_address:
        return
    try:
        update_user(user_id, last_ip=ip_address)
        
        execute_query("""
            INSERT INTO user_ips (user_id, ip_address, first_seen, last_seen)
            VALUES (%s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE last_seen = NOW(), times_seen = times_seen + 1
        """, (str(user_id), ip_address))
    except:
        pass

def get_users_by_ip(ip_address):
    """Obtiene usuarios con una IP específica"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT u.* FROM users u
            INNER JOIN user_ips ui ON u.user_id = ui.user_id
            WHERE ui.ip_address = %s
        """, (ip_address,))
        return rows_to_list(cursor, cursor.fetchall())

def get_duplicate_ips():
    """Obtiene IPs usadas por múltiples usuarios"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT ip_address, COUNT(DISTINCT user_id) as user_count,
                   GROUP_CONCAT(user_id) as user_ids
            FROM user_ips
            GROUP BY ip_address
            HAVING user_count > 1
            ORDER BY user_count DESC
            LIMIT 100
        """)
        return rows_to_list(cursor, cursor.fetchall())

def is_ip_banned(ip_address):
    """Verifica si una IP está baneada"""
    with get_cursor() as cursor:
        cursor.execute("SELECT 1 FROM ip_bans WHERE ip_address = %s", (ip_address,))
        return cursor.fetchone() is not None

def ban_ip(ip_address, reason=None):
    """Banea una IP"""
    try:
        execute_query("""
            INSERT INTO ip_bans (ip_address, reason, banned_at)
            VALUES (%s, %s, NOW())
            ON DUPLICATE KEY UPDATE reason = VALUES(reason)
        """, (ip_address, reason))
        return True
    except:
        return False

def unban_ip(ip_address):
    """Desbanea una IP"""
    try:
        execute_query("DELETE FROM ip_bans WHERE ip_address = %s", (ip_address,))
        return True
    except:
        return False

# ============== RANKING OPERATIONS ==============

def get_top_users_by_balance(limit=50):
    """Top usuarios por balance"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT user_id, username, first_name, se_balance, referral_count
            FROM users
            WHERE banned = FALSE
            ORDER BY se_balance DESC
            LIMIT %s
        """, (limit,))
        return rows_to_list(cursor, cursor.fetchall())

def get_top_users_by_referrals(limit=50):
    """Top usuarios por referidos VALIDADOS"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT user_id, username, first_name, se_balance, referral_count
            FROM users
            WHERE banned = FALSE
            ORDER BY referral_count DESC
            LIMIT %s
        """, (limit,))
        return rows_to_list(cursor, cursor.fetchall())

def get_top_users_by_mined(limit=50):
    """Top usuarios por total minado"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT user_id, username, first_name, total_mined, referral_count
            FROM users
            WHERE banned = FALSE
            ORDER BY total_mined DESC
            LIMIT %s
        """, (limit,))
        return rows_to_list(cursor, cursor.fetchall())

# ============== COMPATIBILITY FUNCTIONS ==============

def load_database():
    """Carga datos para compatibilidad con templates"""
    return {
        'users': {str(u['user_id']): u for u in get_all_users()},
        'tasks': {str(t['task_id']): t for t in get_all_tasks()},
        'promo_codes': {p['code']: p for p in get_all_promo_codes()},
        'config': get_all_config(),
        'stats': get_stats()
    }

def save_database(data):
    """No-op para compatibilidad - datos se guardan automáticamente"""
    pass

# ============== ADMIN SESSION ==============

def create_admin_session(admin_id, session_token):
    """Crea una sesión de admin"""
    try:
        execute_query("""
            INSERT INTO admin_sessions (admin_id, session_token, created_at, expires_at)
            VALUES (%s, %s, NOW(), DATE_ADD(NOW(), INTERVAL 7 DAY))
        """, (admin_id, session_token))
        return True
    except:
        return False

def validate_admin_session(session_token):
    """Valida una sesión de admin"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT admin_id FROM admin_sessions 
            WHERE session_token = %s AND expires_at > NOW()
        """, (session_token,))
        row = cursor.fetchone()
        if row:
            return row.get('admin_id') if isinstance(row, dict) else row[0]
        return None

def delete_admin_session(session_token):
    """Elimina una sesión de admin"""
    try:
        execute_query("DELETE FROM admin_sessions WHERE session_token = %s", (session_token,))
        return True
    except:
        return False


# ============================================
# GAME SESSIONS FUNCTIONS
# ============================================

def create_game_session(user_id, game_type, bet_amount, mine_count=3, mine_positions=None):
    """Create a new game session in the database"""
    import secrets
    session_id = secrets.token_hex(16)
    
    try:
        execute_query("""
            INSERT INTO game_sessions 
            (session_id, user_id, game_type, bet_amount, mine_count, mine_positions, revealed_cells, status, started_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', NOW())
        """, (
            session_id, 
            str(user_id), 
            game_type, 
            float(bet_amount), 
            mine_count,
            json.dumps(mine_positions) if mine_positions else None,
            json.dumps([])
        ))
        print(f"[create_game_session] ✅ Session created: {session_id} for user {user_id}")
        return session_id
    except Exception as e:
        print(f"[create_game_session] ❌ Error: {e}")
        return None


def get_game_session(session_id):
    """Get a game session by session_id"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM game_sessions WHERE session_id = %s
            """, (session_id,))
            row = cursor.fetchone()
            if row:
                session_data = dict(row) if isinstance(row, dict) else row_to_dict(cursor, row)
                # Parse JSON fields
                if session_data.get('mine_positions'):
                    session_data['mine_positions'] = json.loads(session_data['mine_positions'])
                if session_data.get('revealed_cells'):
                    session_data['revealed_cells'] = json.loads(session_data['revealed_cells'])
                return session_data
            return None
    except Exception as e:
        print(f"[get_game_session] ❌ Error: {e}")
        return None


def get_active_game_session(user_id, game_type='mines'):
    """Get active game session for a user"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM game_sessions 
                WHERE user_id = %s AND game_type = %s AND status = 'active'
                ORDER BY started_at DESC LIMIT 1
            """, (str(user_id), game_type))
            row = cursor.fetchone()
            if row:
                session_data = dict(row) if isinstance(row, dict) else row_to_dict(cursor, row)
                # Parse JSON fields
                if session_data.get('mine_positions'):
                    session_data['mine_positions'] = json.loads(session_data['mine_positions'])
                if session_data.get('revealed_cells'):
                    session_data['revealed_cells'] = json.loads(session_data['revealed_cells'])
                return session_data
            return None
    except Exception as e:
        print(f"[get_active_game_session] ❌ Error: {e}")
        return None


def update_game_session(session_id, revealed_cells=None, gems_found=None, current_multiplier=None, status=None, winnings=None):
    """Update a game session"""
    try:
        updates = []
        params = []
        
        if revealed_cells is not None:
            updates.append("revealed_cells = %s")
            params.append(json.dumps(revealed_cells))
        
        if gems_found is not None:
            updates.append("gems_found = %s")
            params.append(gems_found)
        
        if current_multiplier is not None:
            updates.append("current_multiplier = %s")
            params.append(float(current_multiplier))
        
        if status is not None:
            updates.append("status = %s")
            params.append(status)
            if status in ['won', 'lost', 'cashout']:
                updates.append("ended_at = NOW()")
        
        if winnings is not None:
            updates.append("winnings = %s")
            params.append(float(winnings))
        
        if not updates:
            return True
        
        params.append(session_id)
        execute_query(f"""
            UPDATE game_sessions SET {', '.join(updates)} WHERE session_id = %s
        """, tuple(params))
        
        print(f"[update_game_session] ✅ Session {session_id} updated")
        return True
    except Exception as e:
        print(f"[update_game_session] ❌ Error: {e}")
        return False


def end_game_session(session_id, status, winnings=0):
    """End a game session and record in history"""
    try:
        # Get the session data first
        session_data = get_game_session(session_id)
        if not session_data:
            return False
        
        # Update session status
        update_game_session(session_id, status=status, winnings=winnings)
        
        # Calculate profit
        bet_amount = float(session_data.get('bet_amount', 0))
        profit = float(winnings) - bet_amount if status in ['won', 'cashout'] else -bet_amount
        
        # Record in game history
        result = 'win' if status in ['won', 'cashout'] else 'loss'
        execute_query("""
            INSERT INTO game_history 
            (user_id, game_type, bet_amount, mine_count, gems_found, multiplier, result, winnings, profit, played_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            session_data.get('user_id'),
            session_data.get('game_type', 'mines'),
            bet_amount,
            session_data.get('mine_count'),
            session_data.get('gems_found', 0),
            session_data.get('current_multiplier', 1.0),
            result,
            float(winnings),
            profit
        ))
        
        print(f"[end_game_session] ✅ Session {session_id} ended with status {status}")
        return True
    except Exception as e:
        print(f"[end_game_session] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_game_history(user_id, game_type=None, limit=20):
    """Get game history for a user"""
    try:
        with get_cursor() as cursor:
            if game_type:
                cursor.execute("""
                    SELECT * FROM game_history 
                    WHERE user_id = %s AND game_type = %s
                    ORDER BY played_at DESC 
                    LIMIT %s
                """, (str(user_id), game_type, limit))
            else:
                cursor.execute("""
                    SELECT * FROM game_history 
                    WHERE user_id = %s
                    ORDER BY played_at DESC 
                    LIMIT %s
                """, (str(user_id), limit))
            
            rows = cursor.fetchall()
            return [dict(row) if isinstance(row, dict) else row_to_dict(cursor, row) for row in rows]
    except Exception as e:
        print(f"[get_game_history] ❌ Error: {e}")
        return []


def cleanup_old_game_sessions(hours=24):
    """Clean up old active sessions (abandoned games)"""
    try:
        execute_query("""
            UPDATE game_sessions 
            SET status = 'lost', ended_at = NOW()
            WHERE status = 'active' AND started_at < DATE_SUB(NOW(), INTERVAL %s HOUR)
        """, (hours,))
        print(f"[cleanup_old_game_sessions] ✅ Old sessions cleaned up")
        return True
    except Exception as e:
        print(f"[cleanup_old_game_sessions] ❌ Error: {e}")
        return False
