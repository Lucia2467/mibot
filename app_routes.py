# ============================================
# RUTAS PARA TAREAS DE ANUNCIOS
# Actualizar/añadir en app.py
# ============================================

# ============================================
# 1. ACTUALIZAR IMPORTS (al inicio de app.py)
# ============================================
# Buscar la línea de imports de database y añadir:

from database import (
    # ... imports existentes ...,
    # Funciones de tareas de anuncios
    get_ad_tasks, get_ad_task_progress, update_ad_task_progress,
    create_ad_task, check_ad_cooldown
)


# ============================================
# 2. REEMPLAZAR RUTA /tasks
# ============================================

@app.route('/tasks')
def tasks():
    """Tasks page - with ad tasks support"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    if user.get('banned'):
        return render_template('banned.html', user=user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    all_tasks = get_active_tasks()

    raw_completed = user.get('completed_tasks', [])
    if not isinstance(raw_completed, list):
        raw_completed = []
    completed_ids_set = set(str(t) for t in raw_completed if t)

    print(f"[tasks] Usuario {user_id} - Tareas completadas: {completed_ids_set}")

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
    ad_progress = {}
    try:
        ad_progress = get_ad_task_progress(user_id)
    except Exception as e:
        print(f"[tasks] Error getting ad progress: {e}")
    
    # Separar tareas de anuncios completadas
    for task_id in list(ad_tasks.keys()):
        task = ad_tasks[task_id]
        progress = ad_progress.get(task_id, {})
        if progress.get('completed'):
            task['total_earned'] = progress.get('total_earned', 0)
            completed_ad_tasks[task_id] = task
            del ad_tasks[task_id]

    print(f"[tasks] Disponibles: {list(available_tasks.keys())}, Completadas: {list(completed_tasks.keys())}")
    print(f"[tasks] Ad Tasks: {list(ad_tasks.keys())}, Completed Ad Tasks: {list(completed_ad_tasks.keys())}")

    return render_template('tasks.html',
                         user=user,
                         available_tasks=available_tasks,
                         completed_tasks=completed_tasks,
                         ad_tasks=ad_tasks,
                         ad_progress=ad_progress,
                         completed_ad_tasks=completed_ad_tasks,
                         user_id=user_id,
                         show_support_button=True)


# ============================================
# 3. AÑADIR RUTA API /api/ad-task/watch
# ============================================

@app.route('/api/ad-task/watch', methods=['POST'])
def api_ad_task_watch():
    """Register an ad watch for ad-based tasks"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    data = request.get_json() or {}
    task_id = data.get('task_id')

    if not task_id:
        return jsonify({'success': False, 'error': 'Task ID required'}), 400

    # Obtener información de la tarea
    task = get_task(task_id)
    if not task:
        return jsonify({'success': False, 'error': 'Task not found'}), 404

    if task.get('task_type') != 'ads':
        return jsonify({'success': False, 'error': 'Not an ad task'}), 400

    if not task.get('active'):
        return jsonify({'success': False, 'error': 'Task is not active'}), 400

    ads_required = task.get('ads_required', 10)
    reward_per_ad = float(task.get('reward_per_ad', 0.1))

    # Verificar cooldown (30 segundos entre anuncios)
    can_watch, remaining = check_ad_cooldown(user_id, task_id, 30)
    if not can_watch:
        return jsonify({
            'success': False,
            'error': f'Please wait {remaining} seconds',
            'cooldown_remaining': remaining
        }), 429

    # Actualizar progreso
    success, ads_watched, total_earned, task_completed = update_ad_task_progress(
        user_id, task_id, reward_per_ad
    )

    if not success:
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


# ============================================
# 4. ACTUALIZAR RUTA /admin/tasks
# ============================================

@app.route('/admin/tasks')
@admin_required
def admin_tasks():
    """Admin tasks page with ad tasks support"""
    all_tasks = get_all_tasks()
    ad_tasks_list = [t for t in all_tasks if t.get('task_type') == 'ads']
    regular_tasks = [t for t in all_tasks if t.get('task_type') != 'ads']
    
    tareas = {t.get('task_id', ''): t for t in all_tasks} if all_tasks else {}
    return render_template('admin_tasks.html', 
                          tasks=all_tasks, 
                          tareas=tareas,
                          ad_tasks=ad_tasks_list,
                          regular_tasks=regular_tasks)


# ============================================
# 5. ACTUALIZAR RUTA /admin/tasks/new
# ============================================

@app.route('/admin/tasks/new', methods=['GET', 'POST'])
@admin_required
def admin_task_new():
    """Create new task with ad task support"""
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

            if create_task(title, description, reward, url, task_type, True, requires_channel_join, channel_username):
                flash('Tarea creada exitosamente', 'success')
            else:
                flash('Error al crear tarea', 'error')

        return redirect(url_for('admin_tasks'))

    return render_template('admin_task_form.html', task=None)


# ============================================
# 6. ACTUALIZAR RUTA /admin/tasks/<task_id>/edit
# ============================================

@app.route('/admin/tasks/<task_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_task_edit(task_id):
    """Edit a task with ad task support"""
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
            # Tarea de anuncios
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
            # Tarea normal
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

    return render_template('admin_task_form.html', task=task)
