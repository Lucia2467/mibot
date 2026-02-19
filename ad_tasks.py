"""
ad_tasks.py - Sistema de Tareas de Anuncios para SALLY-E Bot
Este archivo contiene las funciones de base de datos y rutas para el sistema de tareas basadas en anuncios.

INSTRUCCIONES DE INSTALACIÓN:
1. Ejecutar migrate_ad_tasks.sql en la base de datos MySQL
2. Agregar estas funciones a database.py
3. Agregar las rutas a app.py
4. Reemplazar admin_task_form.html con admin_task_form_ads.html
5. Reemplazar tasks.html con tasks_ads.html
"""

# ============================================
# FUNCIONES PARA AGREGAR A database.py
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
            # Convertir a diccionario por task_id
            return {p['task_id']: p for p in results}


def update_ad_task_progress(user_id, task_id, reward_per_ad):
    """
    Actualiza el progreso de una tarea de anuncios cuando el usuario ve un anuncio.
    Returns: (success, ads_watched, total_earned, task_completed)
    """
    try:
        # Obtener información de la tarea
        task = get_task(task_id)
        if not task or task.get('task_type') != 'ads':
            return False, 0, 0, False
        
        ads_required = task.get('ads_required', 10)
        
        with get_cursor() as cursor:
            # Verificar progreso actual
            cursor.execute("""
                SELECT ads_watched, total_earned, completed 
                FROM ad_task_progress 
                WHERE user_id = %s AND task_id = %s
            """, (str(user_id), str(task_id)))
            
            progress = row_to_dict(cursor, cursor.fetchone())
            
            if progress and progress.get('completed'):
                # Tarea ya completada
                return False, progress.get('ads_watched', 0), progress.get('total_earned', 0), True
            
            if progress:
                # Actualizar progreso existente
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
                # Crear nuevo progreso
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
        
        # Si completó la tarea, actualizar contador de completaciones
        if is_completed:
            execute_query("""
                UPDATE tasks SET current_completions = current_completions + 1 
                WHERE task_id = %s
            """, (task_id,))
            increment_stat('total_tasks_completed')
            
            # Procesar referido si es primera tarea
            user = get_user(user_id)
            completed = user.get('completed_tasks', [])
            if len(completed) == 0:
                process_first_task_completion(user_id)
            
            # Marcar en completed_tasks del usuario
            if str(task_id) not in completed:
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
        return False


def get_user_ad_stats(user_id):
    """Obtiene las estadísticas de anuncios de un usuario"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM user_ad_stats WHERE user_id = %s
        """, (str(user_id),))
        return row_to_dict(cursor, cursor.fetchone())


def check_ad_cooldown(user_id, task_id, cooldown_seconds=30):
    """Verifica si el usuario puede ver otro anuncio (cooldown)"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT last_ad_at FROM ad_task_progress 
            WHERE user_id = %s AND task_id = %s
        """, (str(user_id), str(task_id)))
        
        result = cursor.fetchone()
        if not result or not result[0]:
            return True, 0
        
        from datetime import datetime, timedelta
        last_ad = result[0]
        if isinstance(last_ad, str):
            last_ad = datetime.strptime(last_ad, '%Y-%m-%d %H:%M:%S')
        
        elapsed = (datetime.now() - last_ad).total_seconds()
        
        if elapsed >= cooldown_seconds:
            return True, 0
        
        return False, int(cooldown_seconds - elapsed)


# ============================================
# RUTAS PARA AGREGAR A app.py
# ============================================

"""
# Agregar estos imports al inicio de app.py:
from database import (
    # ... imports existentes ...
    get_ad_tasks, get_ad_task_progress, update_ad_task_progress,
    create_ad_task, get_user_ad_stats, check_ad_cooldown
)

# Actualizar la ruta /tasks:
@app.route('/tasks')
def tasks():
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    if user.get('banned'):
        return render_template('banned.html', user=user)

    # Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    # Obtener tareas normales
    all_tasks = get_active_tasks()
    
    raw_completed = user.get('completed_tasks', [])
    if not isinstance(raw_completed, list):
        raw_completed = []
    completed_ids_set = set(str(t) for t in raw_completed if t)

    available_tasks = {}
    completed_tasks = {}
    ad_tasks = {}
    completed_ad_tasks = {}

    for task in all_tasks:
        task_id = str(task.get('task_id', ''))
        
        # Separar tareas de anuncios
        if task.get('task_type') == 'ads':
            ad_tasks[task_id] = task
        elif task_id in completed_ids_set:
            completed_tasks[task_id] = task
        else:
            available_tasks[task_id] = task

    # Obtener progreso de tareas de anuncios
    ad_progress = get_ad_task_progress(user_id)
    
    # Separar tareas de anuncios completadas
    for task_id, task in list(ad_tasks.items()):
        progress = ad_progress.get(task_id, {})
        if progress.get('completed'):
            task['total_earned'] = progress.get('total_earned', 0)
            completed_ad_tasks[task_id] = task
            del ad_tasks[task_id]

    return render_template('tasks_ads.html',
                         user=user,
                         available_tasks=available_tasks,
                         completed_tasks=completed_tasks,
                         ad_tasks=ad_tasks,
                         ad_progress=ad_progress,
                         completed_ad_tasks=completed_ad_tasks,
                         user_id=user_id,
                         show_support_button=True)


# Nueva ruta API para ver anuncios:
@app.route('/api/ad-task/watch', methods=['POST'])
def api_ad_task_watch():
    '''Registra que un usuario vio un anuncio en una tarea'''
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    data = request.get_json() or {}
    task_id = data.get('task_id')
    
    if not task_id:
        return jsonify({'success': False, 'error': 'Task ID required'}), 400

    # Obtener la tarea
    task = get_task(task_id)
    if not task:
        return jsonify({'success': False, 'error': 'Task not found'}), 404

    if task.get('task_type') != 'ads':
        return jsonify({'success': False, 'error': 'Not an ad task'}), 400

    if not task.get('active'):
        return jsonify({'success': False, 'error': 'Task is not active'}), 400

    # Verificar cooldown
    cooldown_seconds = int(get_config('ad_task_cooldown_seconds') or 30)
    can_watch, remaining = check_ad_cooldown(user_id, task_id, cooldown_seconds)
    
    if not can_watch:
        return jsonify({
            'success': False, 
            'error': 'Cooldown active',
            'message': f'Espera {remaining} segundos',
            'cooldown_remaining': remaining
        }), 429

    # Procesar visualización de anuncio
    reward_per_ad = float(task.get('reward_per_ad') or 0.1)
    ads_required = int(task.get('ads_required') or 10)
    
    success, ads_watched, total_earned, task_completed = update_ad_task_progress(
        user_id, task_id, reward_per_ad
    )

    if not success:
        if task_completed:
            return jsonify({
                'success': False,
                'error': 'Task already completed',
                'message': 'Ya completaste esta tarea'
            }), 400
        return jsonify({'success': False, 'error': 'Failed to update progress'}), 500

    # Obtener balance actualizado
    updated_user = get_user(user_id)
    new_balance = float(updated_user.get('se_balance', 0)) if updated_user else 0

    logger.info(f"[AdTask] User {user_id} watched ad in {task_id}: {ads_watched}/{ads_required}")

    return jsonify({
        'success': True,
        'reward': reward_per_ad,
        'ads_watched': ads_watched,
        'ads_required': ads_required,
        'total_earned': total_earned,
        'task_completed': task_completed,
        'new_balance': new_balance,
        'message': f'+{reward_per_ad} S-E'
    })


# Actualizar la ruta de crear tarea en admin:
@app.route('/admin/tasks/new', methods=['GET', 'POST'])
@admin_required
def admin_task_new():
    '''Create new task'''
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        task_type = request.form.get('task_type', 'link')
        
        if task_type == 'ads':
            # Tarea de anuncios
            ads_required = int(request.form.get('ads_required', 10))
            reward_per_ad = float(request.form.get('reward_per_ad', 0.1))
            
            if create_ad_task(title, description, ads_required, reward_per_ad):
                flash('Tarea de anuncios creada exitosamente', 'success')
            else:
                flash('Error al crear tarea de anuncios', 'error')
        else:
            # Tarea normal
            reward = float(request.form.get('reward', 0))
            url = request.form.get('url', '').strip() or None
            requires_channel_join = request.form.get('requires_channel_join') == 'on'
            channel_username = request.form.get('channel_username', '').strip() or None

            if create_task(title, description, reward, url, task_type, True, 
                          requires_channel_join, channel_username):
                flash('Tarea creada exitosamente', 'success')
            else:
                flash('Error al crear tarea', 'error')

        return redirect(url_for('admin_tasks'))

    return render_template('admin_task_form_ads.html', task=None)


# Actualizar la ruta de editar tarea:
@app.route('/admin/tasks/<task_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_task_edit(task_id):
    '''Edit a task'''
    task = get_task(task_id)
    if not task:
        flash('Tarea no encontrada', 'error')
        return redirect(url_for('admin_tasks'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        task_type = request.form.get('task_type', 'link')
        active = request.form.get('active') == 'on'
        
        update_data = {
            'title': title,
            'description': description,
            'task_type': task_type,
            'active': active
        }
        
        if task_type == 'ads':
            ads_required = int(request.form.get('ads_required', 10))
            reward_per_ad = float(request.form.get('reward_per_ad', 0.1))
            total_reward = ads_required * reward_per_ad
            
            update_data.update({
                'ads_required': ads_required,
                'reward_per_ad': reward_per_ad,
                'reward': total_reward,
                'is_ad_task': 1
            })
        else:
            reward = float(request.form.get('reward', 0))
            url = request.form.get('url', '').strip() or None
            requires_channel_join = request.form.get('requires_channel_join') == 'on'
            channel_username = request.form.get('channel_username', '').strip() or None
            
            update_data.update({
                'reward': reward,
                'url': url,
                'requires_channel_join': requires_channel_join,
                'channel_username': channel_username,
                'is_ad_task': 0
            })

        if update_task(task_id, **update_data):
            flash('Tarea actualizada', 'success')
        else:
            flash('Error al actualizar tarea', 'error')

        return redirect(url_for('admin_tasks'))

    return render_template('admin_task_form_ads.html', task=task)
"""

# ============================================
# SCRIPT DE INSTALACIÓN AUTOMÁTICA
# ============================================

def install_ad_tasks_system():
    """
    Script para instalar automáticamente el sistema de tareas de anuncios.
    Ejecuta las migraciones de base de datos necesarias.
    """
    from db import execute_query, get_cursor
    
    print("=" * 50)
    print("Instalando Sistema de Tareas de Anuncios")
    print("=" * 50)
    
    migrations = [
        # 1. Añadir columnas a tasks
        """
        ALTER TABLE tasks 
            ADD COLUMN IF NOT EXISTS ads_required INT DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS reward_per_ad DECIMAL(10, 4) DEFAULT 0.1000,
            ADD COLUMN IF NOT EXISTS is_ad_task TINYINT(1) DEFAULT 0
        """,
        
        # 2. Crear tabla ad_task_progress
        """
        CREATE TABLE IF NOT EXISTS ad_task_progress (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            task_id VARCHAR(50) NOT NULL,
            ads_watched INT DEFAULT 0,
            total_earned DECIMAL(10, 4) DEFAULT 0.0000,
            completed TINYINT(1) DEFAULT 0,
            last_ad_at DATETIME DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_user_task (user_id, task_id),
            INDEX idx_user_id (user_id),
            INDEX idx_task_id (task_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # 3. Crear tabla user_ad_stats si no existe
        """
        CREATE TABLE IF NOT EXISTS user_ad_stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL UNIQUE,
            ads_watched_today INT DEFAULT 0,
            total_ads_watched INT DEFAULT 0,
            total_earnings DECIMAL(20, 8) DEFAULT 0.00000000,
            last_ad_date DATE DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # 4. Crear tabla ad_completions si no existe
        """
        CREATE TABLE IF NOT EXISTS ad_completions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            task_id VARCHAR(50) DEFAULT NULL,
            ad_type VARCHAR(50) DEFAULT 'task_center',
            reward DECIMAL(10, 4) NOT NULL,
            completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_task_id (task_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        
        # 5. Añadir configuraciones
        """
        INSERT INTO config (config_key, config_value) VALUES
            ('ad_task_cooldown_seconds', '30'),
            ('ad_task_default_reward', '0.1'),
            ('ad_task_max_daily_completions', '50')
        ON DUPLICATE KEY UPDATE config_value = config_value
        """
    ]
    
    for i, migration in enumerate(migrations, 1):
        try:
            execute_query(migration)
            print(f"✅ Migración {i} completada")
        except Exception as e:
            print(f"⚠️ Migración {i}: {e}")
    
    print("=" * 50)
    print("✅ Sistema de tareas de anuncios instalado")
    print("=" * 50)
    
    return True


if __name__ == "__main__":
    install_ad_tasks_system()
