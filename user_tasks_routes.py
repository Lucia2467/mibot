"""
user_tasks_routes.py - Rutas para el sistema de tareas promocionadas por usuarios
Incluye verificación de canales y sistema de penalizaciones
"""

from flask import Blueprint, request, jsonify, render_template
import os

user_tasks_bp = Blueprint('user_tasks', __name__)

# ============== PÁGINA DE PROMOCIÓN ==============

@user_tasks_bp.route('/promote')
def promote_page():
    """Página para crear tareas promocionadas"""
    from user_tasks_system import get_packages, get_user_created_tasks, get_user_task_stats, USER_TASK_COMPLETION_REWARD
    from database import get_user
    
    user_id = request.args.get('user_id')
    if not user_id:
        return "Error: user_id requerido", 400
    
    user = get_user(user_id)
    if not user:
        return "Error: Usuario no encontrado", 404
    
    packages = get_packages()
    user_tasks = get_user_created_tasks(user_id)
    stats = get_user_task_stats(user_id)
    
    return render_template('promote_task.html',
                         user=user,
                         user_id=user_id,
                         packages=packages,
                         user_tasks=user_tasks,
                         stats=stats,
                         reward_per_completion=USER_TASK_COMPLETION_REWARD)

# ============== APIs ==============

@user_tasks_bp.route('/api/user-tasks/packages', methods=['GET'])
def api_get_packages():
    """Obtiene los paquetes disponibles"""
    from user_tasks_system import get_packages
    packages = get_packages()
    return jsonify({
        'success': True,
        'packages': list(packages.values())
    })

@user_tasks_bp.route('/api/user-tasks/create', methods=['POST'])
def api_create_task():
    """Crea una nueva tarea promocionada"""
    from user_tasks_system import create_user_task
    from i18n_messages import get_user_lang, get_msg as _gm, MESSAGES

    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'user_id requerido'}), 400
    _lang = get_user_lang(user_id)

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': _gm('params_missing', _lang)}), 400

    task_type = data.get('task_type', 'telegram_channel')
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    url = data.get('url', '').strip()
    channel_username = data.get('channel_username', '').strip()
    requires_join = data.get('requires_join', False)
    package_id = data.get('package_id')

    if len(title) < 3:
        return jsonify({'success': False, 'message': _gm('title_too_short', _lang)}), 400

    if len(url) < 5:
        return jsonify({'success': False, 'message': _gm('invalid_url', _lang)}), 400

    if not package_id:
        return jsonify({'success': False, 'message': _gm('select_package', _lang)}), 400

    # Para Telegram con verificación, necesita channel_username
    if task_type in ['telegram_channel', 'telegram_group'] and requires_join and not channel_username:
        return jsonify({
            'success': False,
            'message': _gm('channel_required', _lang)
        }), 400
    
    success, message, task_id = create_user_task(
        creator_id=user_id,
        task_type=task_type,
        title=title,
        description=description,
        url=url,
        channel_username=channel_username,
        requires_join=requires_join,
        package_id=package_id
    )
    
    # Translate message key from system
    if message in MESSAGES:
        message = _gm(message, _lang)
    elif message and ':' in message:
        parts = message.split(':')
        if parts[0] in MESSAGES:
            if parts[0] == 'insufficient_balance_detail' and len(parts) == 3:
                message = _gm('insufficient_balance_detail', _lang, price=parts[1], balance=float(parts[2]))
            else:
                message = _gm(parts[0], _lang)

    if success:
        # Notificar a todos los usuarios en su idioma (background thread)
        print(f"[user_tasks] 🔔 Iniciando notificación para tarea {task_id}...")
        try:
            import sys, os
            print(f"[user_tasks] 🔍 sys.path: {sys.path[:3]}")
            print(f"[user_tasks] 🔍 BOT_TOKEN set: {bool(os.environ.get('BOT_TOKEN'))}")
            from task_notifications import notify_new_task
            from user_tasks_system import USER_TASK_COMPLETION_REWARD, USER_TASK_PACKAGES
            pkg    = USER_TASK_PACKAGES.get(package_id, {})
            spots  = pkg.get('max_completions', '?')
            print(f"[user_tasks] 📦 Paquete: {package_id}, spots: {spots}")
            notify_new_task(
                task_id=task_id,
                title=title,
                description=description,
                reward=USER_TASK_COMPLETION_REWARD,
                spots=spots,
            )
        except Exception as e:
            import traceback
            print(f"[user_tasks] ❌ Error en notificación: {e}")
            traceback.print_exc()
        return jsonify({'success': True, 'message': message, 'task_id': task_id})
    return jsonify({'success': False, 'message': message}), 400

@user_tasks_bp.route('/api/user-tasks/list', methods=['GET'])
def api_list_tasks():
    """Lista tareas disponibles para completar"""
    from user_tasks_system import get_active_user_tasks, USER_TASK_COMPLETION_REWARD
    
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'user_id requerido', 'tasks': []}), 400
    
    penalties_applied = []
    warnings = []
    
    # Verificar penalizaciones de forma segura (no bloquea si falla)
    try:
        from user_tasks_system import check_user_channel_memberships, get_user_pending_warnings, mark_penalty_notified
        
        # Verificar si el usuario ha salido de canales antes de tiempo
        penalties_applied = check_user_channel_memberships(user_id)
        
        # Obtener advertencias pendientes de notificar
        pending_warnings = get_user_pending_warnings(user_id)
        
        # Formatear advertencias para el frontend
        for w in pending_warnings:
            warnings.append({
                'id': w.get('id'),
                'channel': w.get('channel_username', ''),
                'amount': float(w.get('penalty_amount', 0)),
                'reason': w.get('reason', '')
            })
            # Marcar como notificada
            mark_penalty_notified(w.get('id'))
        
        print(f"[user_tasks] Verificación para {user_id}: Penalties={len(penalties_applied)}, Warnings={len(warnings)}")
    except Exception as e:
        print(f"[user_tasks] ⚠️ Error en verificación (no crítico): {e}")
    
    # Obtener tareas (esto SIEMPRE debe funcionar)
    try:
        tasks = get_active_user_tasks(exclude_creator=user_id, exclude_completed_by=user_id)
        
        formatted = []
        for task in tasks:
            formatted.append({
                'task_id': task.get('task_id', ''),
                'title': task.get('title', ''),
                'description': task.get('description', ''),
                'url': task.get('url', ''),
                'task_type': task.get('task_type', 'other'),
                'requires_join': bool(task.get('requires_join', False)),
                'channel_username': task.get('channel_username', ''),
                'reward': float(task.get('reward_per_completion', USER_TASK_COMPLETION_REWARD)),
                'completions': f"{task.get('current_completions', 0)}/{task.get('max_completions', 0)}",
                'current_completions': int(task.get('current_completions', 0)),
                'max_completions': int(task.get('max_completions', 0))
            })
        
        print(f"[user_tasks] Tareas encontradas para {user_id}: {len(formatted)}")
        return jsonify({
            'success': True, 
            'tasks': formatted,
            'penalties_applied': penalties_applied,
            'warnings': warnings
        })
    except Exception as e:
        print(f"[user_tasks] ❌ Error listando tareas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e), 'tasks': []}), 500

@user_tasks_bp.route('/api/user-tasks/my-tasks', methods=['GET'])
def api_my_tasks():
    """Lista tareas creadas por el usuario"""
    from user_tasks_system import get_user_created_tasks, get_user_task_stats
    
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'user_id requerido'}), 400
    
    tasks = get_user_created_tasks(user_id)
    stats = get_user_task_stats(user_id)
    
    return jsonify({'success': True, 'tasks': tasks, 'stats': stats})

@user_tasks_bp.route('/api/user-tasks/complete', methods=['POST'])
def api_complete_task():
    """Completa una tarea de usuario"""
    from user_tasks_system import get_user_task, complete_user_task
    
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'user_id requerido'}), 400
    
    data = request.get_json()
    task_id = data.get('task_id')
    
    if not task_id:
        return jsonify({'success': False, 'message': 'task_id requerido'}), 400
    
    task = get_user_task(task_id)
    if not task:
        return jsonify({'success': False, 'message': 'Tarea no encontrada'}), 404
    
    # Verificar membresía si es requerido
    if task.get('requires_join') and task.get('channel_username'):
        channel = task['channel_username']
        
        try:
            BOT_TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
            if BOT_TOKEN:
                import requests
                
                chat_id = f"@{channel}" if not channel.startswith('@') else channel
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
                response = requests.get(url, params={'chat_id': chat_id, 'user_id': user_id}, timeout=10)
                result = response.json()
                
                print(f"[user_tasks] Verificación @{channel} para {user_id}: {result}")
                
                if result.get('ok'):
                    status = result.get('result', {}).get('status', '')
                    if status not in ['member', 'administrator', 'creator']:
                        from i18n_messages import get_user_lang, get_msg as _gm
                        _lang = get_user_lang(user_id)
                        _msg = _gm('must_join_channel', _lang, channel=f'@{channel}')
                        return jsonify({
                            'success': False,
                            'message': _msg,
                            'verification_failed': True
                        }), 400
                else:
                    error = result.get('description', '')
                    if 'not enough rights' in error.lower() or 'chat not found' in error.lower():
                        print(f"[user_tasks] ⚠️ Bot no puede verificar @{channel}")
                    else:
                        return jsonify({
                            'success': False,
                            'message': f'Error verificando: {error}',
                            'verification_failed': True
                        }), 400
        except Exception as e:
            print(f"[user_tasks] ⚠️ Error verificación: {e}")
    
    # Registrar IP antes de completar (necesario para anti-fraude de referidos)
    try:
        from database import record_user_ip
        from referral_utils import get_client_ip_safe
        record_user_ip(user_id, get_client_ip_safe())
    except Exception:
        pass

    # Completar
    success, message, reward = complete_user_task(task_id, user_id)

    # Translate message key
    from i18n_messages import get_user_lang, get_msg as _gm, MESSAGES
    _lang = get_user_lang(user_id)
    if message and ':' in message and message.split(':')[0] in MESSAGES:
        _key, _val = message.split(':', 1)
        translated = _gm(_key, _lang, reward=_val)
    elif message in MESSAGES:
        translated = _gm(message, _lang)
    else:
        translated = message

    if success:
        # Validar referido en primera tarea
        try:
            from referral_utils import validate_referral_on_first_task
            validate_referral_on_first_task(user_id)
        except Exception as _vr_err:
            print(f"[user_tasks] referral validation error: {_vr_err}")

        return jsonify({'success': True, 'message': translated, 'reward': reward})
    return jsonify({'success': False, 'message': translated}), 400

@user_tasks_bp.route('/api/user-tasks/verify', methods=['POST'])
def api_verify_membership():
    """Verifica membresía en canal"""
    from user_tasks_system import get_user_task
    
    user_id = request.args.get('user_id')
    data = request.get_json()
    task_id = data.get('task_id')
    
    if not user_id or not task_id:
        return jsonify({'verified': False, 'message': 'Parámetros faltantes'})
    
    task = get_user_task(task_id)
    if not task or not task.get('channel_username'):
        return jsonify({'verified': False, 'message': 'Tarea no válida'})
    
    channel = task['channel_username']
    
    try:
        BOT_TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
        if not BOT_TOKEN:
            return jsonify({'verified': True, 'message': 'Sin verificación'})
        
        import requests
        chat_id = f"@{channel}" if not channel.startswith('@') else channel
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        response = requests.get(url, params={'chat_id': chat_id, 'user_id': user_id}, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            status = result.get('result', {}).get('status', '')
            is_member = status in ['member', 'administrator', 'creator']
            return jsonify({
                'verified': is_member,
                'status': status,
                'message': 'OK' if is_member else 'No eres miembro'
            })
        return jsonify({'verified': False, 'message': result.get('description', 'Error')})
    except Exception as e:
        print(f"[user_tasks] ❌ Error: {e}")
        return jsonify({'verified': False, 'message': 'Error de conexión'})

@user_tasks_bp.route('/api/user-tasks/pause', methods=['POST'])
def api_pause_task():
    """Pausa una tarea"""
    from user_tasks_system import pause_user_task
    
    user_id = request.args.get('user_id')
    data = request.get_json()
    task_id = data.get('task_id')
    
    if not user_id or not task_id:
        return jsonify({'success': False, 'message': 'Parámetros faltantes'}), 400
    
    success, message = pause_user_task(task_id, user_id)
    return jsonify({'success': success, 'message': message})

@user_tasks_bp.route('/api/user-tasks/resume', methods=['POST'])
def api_resume_task():
    """Reactiva una tarea"""
    from user_tasks_system import resume_user_task
    
    user_id = request.args.get('user_id')
    data = request.get_json()
    task_id = data.get('task_id')
    
    if not user_id or not task_id:
        return jsonify({'success': False, 'message': 'Parámetros faltantes'}), 400
    
    success, message = resume_user_task(task_id, user_id)
    return jsonify({'success': success, 'message': message})

@user_tasks_bp.route('/api/user-tasks/delete', methods=['POST'])
def api_delete_task():
    """Elimina una tarea del creador"""
    from user_tasks_system import delete_user_task

    user_id = request.args.get('user_id')
    data    = request.get_json()
    task_id = data.get('task_id')

    if not user_id or not task_id:
        return jsonify({'success': False, 'message': 'Parámetros faltantes'}), 400

    success, message = delete_user_task(task_id, user_id)
    return jsonify({'success': success, 'message': message})

# ============== CRON JOB PARA VERIFICACIÓN ==============

@user_tasks_bp.route('/api/user-tasks/cron/check-penalties', methods=['POST', 'GET'])
def api_cron_check_penalties():
    """
    Endpoint para verificar usuarios que salieron de canales y aplicar penalizaciones.
    Llamar cada 1-2 horas via cron job.
    
    Ejemplo cron: 0 * * * * curl -X POST https://tudominio.com/api/user-tasks/cron/check-penalties?key=SECRET_KEY
    """
    # Verificar clave secreta
    secret_key = request.args.get('key', '')
    expected_key = os.environ.get('CRON_SECRET_KEY', '')
    if not expected_key:
        return jsonify({'success': False, 'message': 'CRON_SECRET_KEY no configurada en variables de entorno'}), 500
    if secret_key != expected_key:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        from user_tasks_system import process_penalties_and_notify
        
        penalties, notifications = process_penalties_and_notify()
        
        return jsonify({
            'success': True,
            'message': f'Procesado: {penalties} penalizaciones, {notifications} notificaciones',
            'penalties_applied': penalties,
            'notifications_sent': notifications
        })
    except Exception as e:
        print(f"[user_tasks] ❌ Error en cron: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@user_tasks_bp.route('/api/user-tasks/check-my-penalties', methods=['GET', 'POST'])
def api_check_my_penalties():
    """
    Verifica si el usuario ha salido de canales y aplica penalizaciones.
    Se llama cuando el usuario interactúa con la app.
    """
    from user_tasks_system import check_user_channel_memberships, get_user_pending_warnings, mark_penalty_notified
    
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'user_id requerido'}), 400
    
    try:
        # Verificar membresías y aplicar penalizaciones si es necesario
        penalties_applied = check_user_channel_memberships(user_id)
        
        # Obtener advertencias pendientes
        pending_warnings = get_user_pending_warnings(user_id)
        
        # Formatear advertencias para el frontend
        warnings = []
        for w in pending_warnings:
            warnings.append({
                'id': w.get('id'),
                'channel': w.get('channel_username', ''),
                'amount': float(w.get('penalty_amount', 0)),
                'reason': w.get('reason', '')
            })
            # Marcar como notificada
            mark_penalty_notified(w.get('id'))
        
        return jsonify({
            'success': True,
            'penalties_applied': penalties_applied,
            'warnings': warnings,
            'has_penalties': len(penalties_applied) > 0 or len(warnings) > 0
        })
    except Exception as e:
        print(f"[user_tasks] ❌ Error verificando penalizaciones: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
