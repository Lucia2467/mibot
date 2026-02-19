"""
app_patches_v2.py - Parches para app.py con el sistema de tareas mejorado

Este archivo contiene las rutas y funciones actualizadas que deben reemplazar
las existentes en app.py para implementar:
- Validación de membresía de canal
- Referidos con validación en primera tarea
- Tareas diarias automáticas
- UI mejorada de tareas
"""

import os
import requests

# ============================================
# NUEVAS FUNCIONES PARA VERIFICACIÓN DE CANAL
# ============================================

def verify_telegram_channel_membership(user_id, channel_username, bot_token):
    """
    Verifica si un usuario es miembro de un canal de Telegram usando la API
    
    Args:
        user_id: ID del usuario de Telegram
        channel_username: Username del canal (@canal) o chat_id
        bot_token: Token del bot de Telegram
    
    Returns:
        bool: True si es miembro, False si no
    """
    if not bot_token or not channel_username:
        return True  # Sin verificación, asumir OK
    
    try:
        # Limpiar el username del canal
        channel = channel_username.strip()
        if not channel.startswith('@') and not channel.startswith('-'):
            channel = f"@{channel}"
        
        url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
        params = {
            'chat_id': channel,
            'user_id': int(user_id)
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            status = data.get('result', {}).get('status', '')
            is_member = status in ['member', 'administrator', 'creator']
            print(f"[verify_channel] Usuario {user_id} en {channel}: {status} -> {'✅' if is_member else '❌'}")
            return is_member
        else:
            error = data.get('description', 'Unknown error')
            print(f"[verify_channel] API error: {error}")
            # Si el error es que el usuario no está en el chat, no es miembro
            if 'user not found' in error.lower() or 'chat not found' in error.lower():
                return False
            # Para otros errores, asumir OK para no bloquear
            return True
            
    except Exception as e:
        print(f"[verify_channel] Error: {e}")
        return True  # En caso de error, no bloquear al usuario


# ============================================
# RUTAS ACTUALIZADAS - COPIAR A app.py
# ============================================

"""
RUTA: /tasks
Reemplazar la función tasks() existente con esta versión
"""
def tasks_route_v2():
    '''
    @app.route('/tasks')
    def tasks():
        """Tasks page - Version 2 con sistema mejorado"""
        user_id = get_user_id()
        if not user_id:
            return redirect(url_for('index'))

        user = get_user(user_id)
        if not user:
            return redirect(url_for('index'))
        
        # Importar funciones del sistema v2 si está disponible
        try:
            from task_system import ensure_daily_task_exists, get_tasks_for_user
            
            # Asegurar que existe la tarea diaria
            ensure_daily_task_exists()
            
            # Obtener tareas con estado para el usuario
            tasks_data = get_tasks_for_user(user_id)
            available_tasks = tasks_data.get('available', {})
            completed_tasks = tasks_data.get('completed', {})
            
        except ImportError:
            # Fallback al sistema legacy
            all_tasks = get_active_tasks()
            completed_ids = set(str(t) for t in user.get('completed_tasks', []))
            
            available_tasks = {}
            completed_tasks = {}
            
            for task in all_tasks:
                task_id = str(task.get('task_id', ''))
                if task_id in completed_ids:
                    completed_tasks[task_id] = task
                else:
                    available_tasks[task_id] = task
        
        return render_template('tasks.html',
                             user=user,
                             user_id=user_id,
                             available_tasks=available_tasks,
                             completed_tasks=completed_tasks,
                             bot_token=os.environ.get('BOT_TOKEN', ''),
                             show_support_button=True)
    '''
    pass


"""
RUTA: /api/task/complete
Reemplazar la función api_task_complete() existente con esta versión
"""
def api_task_complete_v2():
    '''
    @app.route('/api/task/complete', methods=['POST'])
    def api_task_complete():
        """Complete a task - V2 con validación de canal y referidos"""
        user_id = get_user_id()
        if not user_id:
            print(f"[api_task_complete] ❌ No user_id provided")
            return jsonify({'success': False, 'error': 'User ID required'}), 400

        data = request.get_json() or {}
        task_id = data.get('task_id')

        if not task_id:
            print(f"[api_task_complete] ❌ No task_id provided")
            return jsonify({'success': False, 'error': 'Task ID required'}), 400

        print(f"[api_task_complete] Usuario {user_id} intentando completar tarea {task_id}")

        # Obtener la tarea
        task = get_task(task_id)
        if not task:
            print(f"[api_task_complete] ❌ Tarea {task_id} no encontrada")
            return jsonify({'success': False, 'error': 'Tarea no encontrada'}), 400
        
        # Verificar membresía de canal si es requerido
        if task.get('requires_channel_join') and task.get('channel_username'):
            bot_token = os.environ.get('BOT_TOKEN', '')
            if bot_token:
                is_member = verify_telegram_channel_membership(
                    user_id, 
                    task['channel_username'], 
                    bot_token
                )
                if not is_member:
                    print(f"[api_task_complete] ❌ Usuario {user_id} no es miembro del canal {task['channel_username']}")
                    return jsonify({
                        'success': False, 
                        'error': 'Debes unirte al canal para completar esta tarea',
                        'verification_failed': True
                    }), 400
        
        # Intentar usar el sistema v2
        try:
            from task_system import complete_task_v2
            success, message, reward = complete_task_v2(user_id, task_id)
        except ImportError:
            # Fallback al sistema legacy
            reward = float(task.get('reward', 0))
            success = complete_task(user_id, task_id)
            message = 'Tarea completada' if success else 'Ya completaste esta tarea'

        print(f"[api_task_complete] Resultado: success={success}, message={message}")

        if success:
            user = get_user(user_id)
            new_balance = float(user.get('se_balance', 0)) if user else 0
            completed_count = len(user.get('completed_tasks', [])) if user else 0
            print(f"[api_task_complete] ✅ Tarea completada. Nuevo balance: {new_balance}")
            
            return jsonify({
                'success': True,
                'message': message,
                'reward': reward,
                'new_balance': new_balance,
                'completed_count': completed_count
            })

        print(f"[api_task_complete] ❌ Error: {message}")
        return jsonify({'success': False, 'error': message, 'message': message}), 400
    '''
    pass


"""
RUTA: /api/task/verify
Reemplazar la función api_task_verify() existente con esta versión
"""
def api_task_verify_v2():
    '''
    @app.route('/api/task/verify', methods=['POST'])
    def api_task_verify():
        """Verify Telegram channel membership - V2"""
        user_id = get_user_id()
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400

        data = request.get_json() or {}
        task_id = data.get('task_id')
        channel_username = data.get('channel_username', '')

        # Obtener tarea para saber el canal si no se especificó
        if task_id and not channel_username:
            task = get_task(task_id)
            if task:
                channel_username = task.get('channel_username', '')

        if not channel_username:
            # Sin canal específico, asumir verificado
            return jsonify({'success': True, 'verified': True})

        # Verificar membresía usando la API de Telegram
        bot_token = os.environ.get('BOT_TOKEN', '')
        if not bot_token:
            print("[api_task_verify] ⚠️ No bot token configured")
            return jsonify({'success': True, 'verified': True, 'message': 'No bot token configured'})

        is_member = verify_telegram_channel_membership(user_id, channel_username, bot_token)

        return jsonify({
            'success': True, 
            'verified': is_member,
            'message': 'Verificación completada' if is_member else 'No eres miembro del canal'
        })
    '''
    pass


"""
RUTA: /admin/tasks/create
Actualizar para incluir los nuevos campos
"""
def admin_task_create_v2():
    '''
    @app.route('/admin/tasks/create', methods=['GET', 'POST'])
    @admin_required
    def admin_task_create():
        """Create new task - V2 con campos adicionales"""
        if request.method == 'GET':
            return render_template('admin_task_form.html', task=None)
        
        # Obtener datos del formulario
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '')
        reward = float(request.form.get('reward', 0))
        url = request.form.get('url', '').strip() or None
        task_type = request.form.get('type', 'link')
        active = request.form.get('active') == 'true'
        
        # Nuevos campos v2
        max_completions = request.form.get('max_completions', '')
        max_completions = int(max_completions) if max_completions and max_completions.isdigit() else None
        priority = int(request.form.get('priority', 0) or 0)
        requires_channel_join = request.form.get('requires_channel_join') == 'true'
        channel_username = request.form.get('channel_username', '').strip() or None
        
        # Intentar usar el sistema v2
        try:
            from task_system import create_task as create_task_v2
            task_id = create_task_v2(
                title=title,
                description=description,
                reward=reward,
                url=url,
                task_type=task_type,
                active=active,
                max_completions=max_completions,
                requires_channel_join=requires_channel_join,
                channel_username=channel_username,
                priority=priority
            )
            success = task_id is not None
        except ImportError:
            # Fallback al sistema legacy
            success = create_task(title, description, reward, url, task_type, active)
        
        if success:
            flash('Tarea creada exitosamente', 'success')
        else:
            flash('Error al crear la tarea', 'error')
        
        return redirect(url_for('admin_tasks'))
    '''
    pass


"""
RUTA: /admin/tasks/edit/<task_id>
Actualizar para incluir los nuevos campos
"""
def admin_task_edit_v2():
    '''
    @app.route('/admin/tasks/edit/<task_id>', methods=['GET', 'POST'])
    @admin_required
    def admin_task_edit(task_id):
        """Edit task - V2 con campos adicionales"""
        task = get_task(task_id)
        if not task:
            flash('Tarea no encontrada', 'error')
            return redirect(url_for('admin_tasks'))

        if request.method == 'POST':
            # Obtener datos del formulario
            max_completions = request.form.get('max_completions', '')
            max_completions = int(max_completions) if max_completions and max_completions.isdigit() else None
            
            updates = {
                'title': request.form.get('title', '').strip(),
                'description': request.form.get('description', ''),
                'reward': float(request.form.get('reward', 0)),
                'url': request.form.get('url', '').strip() or None,
                'task_type': request.form.get('type', 'link'),
                'active': request.form.get('active') == 'true',
                'max_completions': max_completions,
                'priority': int(request.form.get('priority', 0) or 0),
                'requires_channel_join': request.form.get('requires_channel_join') == 'true',
                'channel_username': request.form.get('channel_username', '').strip() or None
            }
            
            update_task(task_id, **updates)
            flash('Tarea actualizada exitosamente', 'success')
            return redirect(url_for('admin_tasks'))

        return render_template('admin_task_form.html', task=task)
    '''
    pass


# ============================================
# CÓDIGO ADICIONAL PARA database.py
# ============================================

"""
Agregar estas funciones a database.py si no existen
"""
def database_patches():
    '''
    def complete_task(user_id, task_id, reward=None):
        """Marca una tarea como completada y paga recompensa - MEJORADO con referidos"""
        user = get_user(user_id)
        if not user:
            return False, "Usuario no encontrado"
        
        completed = user.get('completed_tasks', [])
        if str(task_id) in [str(t) for t in completed]:
            return False, "Ya completaste esta tarea"
        
        # Get task reward if not provided
        if reward is None:
            task = get_task(task_id)
            if task:
                reward = float(task.get('reward', 0))
            else:
                reward = 0
        
        # Mark as completed
        completed.append(str(task_id))
        update_user(user_id, completed_tasks=completed)
        
        # Pay reward
        if reward > 0:
            update_balance(user_id, 'se', reward, 'add')
        
        # Update task completion count
        execute_query("""
            UPDATE tasks SET current_completions = current_completions + 1 
            WHERE task_id = %s
        """, (task_id,))
        
        # Check if first task and process referral
        is_first_task = len(completed) == 1
        if is_first_task:
            # Mark user as having completed first task
            update_user(user_id, first_task_completed=True)
            
            # Process pending referral
            referrer_id = user.get('referred_by') or user.get('pending_referrer')
            if referrer_id:
                validate_referral(referrer_id, user_id)
        
        # Update stats
        increment_stat('total_tasks_completed')
        
        return True, f"¡Tarea completada! +{reward} S-E"
    '''
    pass


if __name__ == '__main__':
    print("Este archivo contiene los parches para app.py")
    print("Importar las funciones necesarias o copiar el código manualmente")
