"""
RUTAS DEL SISTEMA DE TAREAS SOCIALES
"""
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from social_tasks_system import (
    init_social_tasks_tables, admin_create_social_task, admin_update_social_task,
    admin_delete_social_task, admin_get_all_tasks, admin_get_pending_submissions,
    admin_get_all_submissions, admin_approve_submission, admin_reject_submission,
    get_active_social_tasks, get_social_task, submit_social_task,
    get_user_submissions, get_platforms, get_actions
)
from database import get_user

social_tasks_bp = Blueprint('social_tasks', __name__)

# Init tables on import
init_social_tasks_tables()


def admin_logged_in():
    return session.get('admin_logged_in', False)


# ============================================================
# RUTAS ADMIN
# ============================================================

@social_tasks_bp.route('/admin/social-tasks')
def admin_social_tasks():
    if not admin_logged_in():
        return redirect(url_for('admin_login'))
    tasks = admin_get_all_tasks(include_inactive=True)
    pending_count = len(admin_get_pending_submissions())
    platforms = get_platforms()
    actions = get_actions()
    return render_template('admin_social_tasks.html',
                           tasks=tasks,
                           pending_count=pending_count,
                           platforms=platforms,
                           actions=actions)


@social_tasks_bp.route('/admin/social-tasks/create', methods=['POST'])
def admin_create_task():
    if not admin_logged_in():
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    data = request.get_json()
    result = admin_create_social_task(
        platform=data.get('platform'),
        action_type=data.get('action_type'),
        title=data.get('title'),
        description=data.get('description', ''),
        target_url=data.get('target_url', ''),
        target_username=data.get('target_username', ''),
        instructions=data.get('instructions', ''),
        reward_amount=data.get('reward_amount', 1.0),
        reward_currency=data.get('reward_currency', 'se'),
        max_completions=data.get('max_completions', 100),
        requires_screenshot=data.get('requires_screenshot', True)
    )
    return jsonify(result)


@social_tasks_bp.route('/admin/social-tasks/<task_id>/update', methods=['POST'])
def admin_update_task(task_id):
    if not admin_logged_in():
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    data = request.get_json()
    result = admin_update_social_task(task_id, **data)
    return jsonify(result)


@social_tasks_bp.route('/admin/social-tasks/<task_id>/toggle', methods=['POST'])
def admin_toggle_task(task_id):
    if not admin_logged_in():
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    data = request.get_json()
    result = admin_update_social_task(task_id, is_active=data.get('is_active', True))
    return jsonify(result)


@social_tasks_bp.route('/admin/social-tasks/<task_id>/delete', methods=['POST'])
def admin_delete_task(task_id):
    if not admin_logged_in():
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    result = admin_delete_social_task(task_id)
    return jsonify(result)


@social_tasks_bp.route('/admin/social-tasks/submissions')
def admin_submissions():
    if not admin_logged_in():
        return redirect(url_for('admin_login'))
    status = request.args.get('status', None)
    task_id = request.args.get('task_id', None)
    if task_id:
        submissions = admin_get_pending_submissions(task_id)
    else:
        submissions = admin_get_all_submissions(status=status)
    pending_count = len(admin_get_pending_submissions())
    return render_template('admin_social_submissions.html',
                           submissions=submissions,
                           current_status=status,
                           pending_count=pending_count)


@social_tasks_bp.route('/admin/social-tasks/submissions/<submission_id>/approve', methods=['POST'])
def approve_submission(submission_id):
    if not admin_logged_in():
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    data = request.get_json() or {}
    result = admin_approve_submission(submission_id, data.get('admin_note', ''))
    return jsonify(result)


@social_tasks_bp.route('/admin/social-tasks/submissions/<submission_id>/reject', methods=['POST'])
def reject_submission(submission_id):
    if not admin_logged_in():
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    data = request.get_json() or {}
    result = admin_reject_submission(submission_id, data.get('admin_note', ''))
    return jsonify(result)


# ============================================================
# RUTAS USUARIO
# ============================================================

@social_tasks_bp.route('/social-tasks')
def social_tasks_page():
    user_id = request.args.get('user_id')
    if not user_id:
        return redirect('/')
    user = get_user(user_id)
    if not user:
        return redirect('/')
    tasks = get_active_social_tasks(user_id=user_id)
    submissions = get_user_submissions(user_id)
    platforms = {p['id']: p for p in get_platforms()}
    actions = {a['id']: a for a in get_actions()}
    return render_template('social_tasks.html',
                           user=user,
                           user_id=user_id,
                           tasks=tasks,
                           submissions=submissions,
                           platforms=platforms,
                           actions=actions)


@social_tasks_bp.route('/api/social-tasks/submit', methods=['POST'])
def api_submit_task():
    data = request.get_json()
    user_id = data.get('user_id')
    task_id = data.get('task_id')
    screenshot = data.get('screenshot')  # base64
    note = data.get('note', '')

    if not all([user_id, task_id, screenshot]):
        return jsonify({'success': False, 'error': 'Faltan datos requeridos'})

    # Limit screenshot size (5MB base64 ~ 3.75MB file)
    if len(screenshot) > 5_000_000:
        return jsonify({'success': False, 'error': 'La imagen es demasiado grande (máx 5MB)'})

    result = submit_social_task(task_id, user_id, screenshot, note)
    return jsonify(result)


@social_tasks_bp.route('/api/social-tasks/my-submissions')
def api_my_submissions():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify([])
    return jsonify(get_user_submissions(user_id))
