# ============================================
# FUNCIONES PARA TAREAS DE ANUNCIOS
# Añadir al final de database.py
# ============================================

def get_ad_tasks():
    """Obtiene todas las tareas de anuncios activas"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE task_type = 'ads' AND active = TRUE 
            ORDER BY created_at DESC
        """)
        tasks = rows_to_list(cursor, cursor.fetchall())
        for task in tasks:
            task['active'] = bool(task.get('active', 1))
            task['is_ad_task'] = True
        return tasks


def get_ad_task_progress(user_id, task_id=None):
    """
    Obtiene el progreso de tareas de anuncios para un usuario.
    Si task_id es None, devuelve el progreso de todas las tareas.
    """
    with get_cursor() as cursor:
        if task_id:
            cursor.execute("""
                SELECT * FROM ad_task_progress 
                WHERE user_id = %s AND task_id = %s
            """, (str(user_id), str(task_id)))
            return row_to_dict(cursor, cursor.fetchone())
        else:
            cursor.execute("""
                SELECT * FROM ad_task_progress 
                WHERE user_id = %s
            """, (str(user_id),))
            results = rows_to_list(cursor, cursor.fetchall())
            return {str(p['task_id']): p for p in results}


def update_ad_task_progress(user_id, task_id, reward_per_ad):
    """
    Actualiza el progreso de una tarea de anuncios cuando el usuario ve un anuncio.
    Returns: (success, ads_watched, total_earned, task_completed)
    """
    try:
        task = get_task(task_id)
        if not task or task.get('task_type') != 'ads':
            return False, 0, 0, False
        
        ads_required = task.get('ads_required', 10)
        
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT ads_watched, total_earned, completed 
                FROM ad_task_progress 
                WHERE user_id = %s AND task_id = %s
            """, (str(user_id), str(task_id)))
            
            progress = row_to_dict(cursor, cursor.fetchone())
            
            if progress and progress.get('completed'):
                return False, progress.get('ads_watched', 0), progress.get('total_earned', 0), True
            
            if progress:
                new_ads_watched = progress.get('ads_watched', 0) + 1
                new_total_earned = float(progress.get('total_earned', 0)) + float(reward_per_ad)
                is_completed = new_ads_watched >= ads_required
                
                cursor.execute("""
                    UPDATE ad_task_progress 
                    SET ads_watched = %s, 
                        total_earned = %s, 
                        completed = %s,
                        last_ad_at = NOW(),
                        updated_at = NOW()
                    WHERE user_id = %s AND task_id = %s
                """, (new_ads_watched, new_total_earned, is_completed, str(user_id), str(task_id)))
            else:
                new_ads_watched = 1
                new_total_earned = float(reward_per_ad)
                is_completed = new_ads_watched >= ads_required
                
                cursor.execute("""
                    INSERT INTO ad_task_progress 
                    (user_id, task_id, ads_watched, total_earned, completed, last_ad_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                """, (str(user_id), str(task_id), new_ads_watched, new_total_earned, is_completed))
        
        # Dar recompensa al usuario
        update_balance(user_id, 'se', reward_per_ad, 'add', f'Ad watched in task {task_id}')
        
        # Si completó la tarea
        if is_completed:
            execute_query("""
                UPDATE tasks SET current_completions = current_completions + 1 
                WHERE task_id = %s
            """, (task_id,))
            increment_stat('total_tasks_completed')
            
            # Procesar referido si es primera tarea
            user = get_user(user_id)
            completed = user.get('completed_tasks', [])
            if not isinstance(completed, list):
                completed = []
            if len(completed) == 0:
                process_first_task_completion(user_id)
            
            # Marcar en completed_tasks del usuario
            if str(task_id) not in [str(t) for t in completed]:
                completed.append(str(task_id))
                update_user(user_id, completed_tasks=completed)
        
        # Registrar en log de anuncios
        try:
            execute_query("""
                INSERT INTO ad_completions (user_id, task_id, ad_type, reward, completed_at)
                VALUES (%s, %s, 'ad_task', %s, NOW())
            """, (str(user_id), str(task_id), float(reward_per_ad)))
        except:
            pass
        
        return True, new_ads_watched, new_total_earned, is_completed
        
    except Exception as e:
        print(f"[update_ad_task_progress] Error: {e}")
        import traceback
        traceback.print_exc()
        return False, 0, 0, False


def create_ad_task(title, description, ads_required, reward_per_ad, active=True):
    """Crea una nueva tarea de anuncios"""
    import uuid
    task_id = f"adtask_{uuid.uuid4().hex[:8]}"
    total_reward = float(ads_required) * float(reward_per_ad)
    
    try:
        execute_query("""
            INSERT INTO tasks 
            (task_id, title, description, reward, url, task_type, active, 
             ads_required, reward_per_ad, is_ad_task, created_at)
            VALUES (%s, %s, %s, %s, NULL, 'ads', %s, %s, %s, 1, NOW())
        """, (task_id, title, description, total_reward, active, 
              int(ads_required), float(reward_per_ad)))
        
        print(f"[create_ad_task] ✅ Tarea de anuncios creada: {task_id}")
        return True
    except Exception as e:
        print(f"[create_ad_task] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_ad_cooldown(user_id, task_id, cooldown_seconds=30):
    """Verifica si el usuario puede ver otro anuncio (cooldown)"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT last_ad_at FROM ad_task_progress 
            WHERE user_id = %s AND task_id = %s
        """, (str(user_id), str(task_id)))
        
        result = cursor.fetchone()
        if not result:
            return True, 0
        
        last_ad = result.get('last_ad_at') if isinstance(result, dict) else result[0]
        if not last_ad:
            return True, 0
        
        if isinstance(last_ad, str):
            last_ad = datetime.strptime(last_ad, '%Y-%m-%d %H:%M:%S')
        
        elapsed = (datetime.now() - last_ad).total_seconds()
        
        if elapsed >= cooldown_seconds:
            return True, 0
        
        return False, int(cooldown_seconds - elapsed)


def get_user_ad_stats(user_id):
    """Obtiene las estadísticas de anuncios de un usuario"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM user_ad_stats WHERE user_id = %s
        """, (str(user_id),))
        return row_to_dict(cursor, cursor.fetchone())
