"""
social_tasks_routes.py - Blueprint para el sistema de Tareas Sociales
Rutas admin: /admin/social-tasks/*
Rutas usuario: /social-tasks, /api/social-tasks/*
"""

import base64
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session

from social_tasks_system import (
    SOCIAL_PLATFORMS, SOCIAL_ACTIONS, PLATFORMS_MAP,
    init_social_tasks_tables,
    get_all_social_tasks,
    get_active_social_tasks,
    get_social_task,
    create_social_task,
    update_social_task,
    toggle_social_task,
    delete_social_task,
    submit_social_task,
    get_user_submissions,
    get_all_submissions,
    approve_submission,
    reject_submission,
)

social_tasks_bp = Blueprint('social_tasks', __name__)


# ──────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────
def _admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def _get_user_id():
    """Extrae user_id de query string o JSON body."""
    return (
        request.args.get('user_id')
        or (request.json or {}).get('user_id')
        or request.form.get('user_id')
    )


# ──────────────────────────────────────────────────
#  PÁGINA USUARIO: /social-tasks
# ──────────────────────────────────────────────────
@social_tasks_bp.route('/social-tasks')
def social_tasks_page():
    user_id = request.args.get('user_id')
    if not user_id:
        return "Error: user_id requerido", 400

    tasks = get_active_social_tasks(user_id=user_id)
    submissions = get_user_submissions(user_id)

    return render_template(
        'social_tasks.html',
        user_id=user_id,
        tasks=tasks,
        submissions=submissions,
        platforms=PLATFORMS_MAP,
    )


# ──────────────────────────────────────────────────
#  API USUARIO
# ──────────────────────────────────────────────────
@social_tasks_bp.route('/api/social-tasks/list')
def api_social_tasks_list():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'user_id requerido'}), 400

    tasks = get_active_social_tasks(user_id=user_id)
    # Convertir Decimal a float para JSON
    result = []
    for t in tasks:
        row = dict(t)
        if hasattr(row.get('reward_amount'), 'real'):
            row['reward_amount'] = float(row['reward_amount'])
        result.append(row)

    return jsonify({'success': True, 'tasks': result})


@social_tasks_bp.route('/api/social-tasks/status')
def api_social_tasks_status():
    """Devuelve estado simple: cuántas tareas activas hay."""
    tasks = get_active_social_tasks()
    return jsonify({'success': True, 'active_tasks': len(tasks)})


@social_tasks_bp.route('/api/social-tasks/submit', methods=['POST'])
def api_social_tasks_submit():
    data = request.json or {}
    user_id = data.get('user_id')
    task_id = data.get('task_id')

    if not user_id or not task_id:
        return jsonify({'success': False, 'error': 'user_id y task_id requeridos'}), 400

    screenshot_data = data.get('screenshot')  # base64 string
    user_note = data.get('note', '').strip() or None

    # Validar tamaño de screenshot (~5 MB)
    if screenshot_data and len(screenshot_data) > 7 * 1024 * 1024:
        return jsonify({'success': False, 'error': 'La imagen es demasiado grande (máx 5 MB)'}), 400

    ok, result = submit_social_task(
        task_id=task_id,
        user_id=user_id,
        screenshot_data=screenshot_data,
        user_note=user_note,
    )

    if ok:
        return jsonify({'success': True, 'submission_id': result,
                        'message': '¡Envío recibido! El admin lo revisará pronto.'})
    return jsonify({'success': False, 'error': result}), 400


@social_tasks_bp.route('/api/social-tasks/my-submissions')
def api_my_submissions():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'user_id requerido'}), 400

    subs = get_user_submissions(user_id)
    result = []
    for s in subs:
        row = dict(s)
        row.pop('screenshot_data', None)  # No enviar la imagen en el listado
        if hasattr(row.get('reward_amount'), 'real'):
            row['reward_amount'] = float(row['reward_amount'])
        result.append(row)

    return jsonify({'success': True, 'submissions': result})


# ──────────────────────────────────────────────────
#  ADMIN PAGES
# ──────────────────────────────────────────────────
@social_tasks_bp.route('/admin/social-tasks')
@_admin_required
def admin_social_tasks_page():
    tasks = get_all_social_tasks()
    # Contar envíos pendientes para el badge
    pending_submissions = get_all_submissions(status='pending')
    pending_count = len(pending_submissions)
    return render_template(
        'admin_social_tasks.html',
        tasks=tasks,
        platforms=SOCIAL_PLATFORMS,
        actions=SOCIAL_ACTIONS,
        pending_count=pending_count,
    )


@social_tasks_bp.route('/admin/social-tasks/submissions')
@_admin_required
def admin_social_submissions_page():
    status = request.args.get('status')
    task_id = request.args.get('task_id')
    submissions = get_all_submissions(status=status, task_id=task_id)
    pending_count = len(get_all_submissions(status='pending'))

    return render_template(
        'admin_social_submissions.html',
        submissions=submissions,
        current_status=status,
        current_task_id=task_id,
        pending_count=pending_count,
    )


# ──────────────────────────────────────────────────
#  ADMIN API
# ──────────────────────────────────────────────────
@social_tasks_bp.route('/admin/social-tasks/create', methods=['POST'])
@_admin_required
def admin_create_task():
    data = request.json or {}
    if not data.get('title'):
        return jsonify({'success': False, 'error': 'Título requerido'}), 400

    task_id = create_social_task(data)
    if task_id:
        return jsonify({'success': True, 'task_id': task_id})
    return jsonify({'success': False, 'error': 'Error al crear la tarea'}), 500


@social_tasks_bp.route('/admin/social-tasks/<task_id>/update', methods=['POST'])
@_admin_required
def admin_update_task(task_id):
    data = request.json or {}
    ok = update_social_task(task_id, data)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Error al actualizar'}), 500


@social_tasks_bp.route('/admin/social-tasks/<task_id>/toggle', methods=['POST'])
@_admin_required
def admin_toggle_task(task_id):
    data = request.json or {}
    active = bool(data.get('active', True))
    ok = toggle_social_task(task_id, active)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Error'}), 500


@social_tasks_bp.route('/admin/social-tasks/<task_id>/delete', methods=['POST'])
@_admin_required
def admin_delete_task(task_id):
    ok = delete_social_task(task_id)
    if ok:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Error al eliminar'}), 500


@social_tasks_bp.route('/admin/social-tasks/submissions/<submission_id>/approve', methods=['POST'])
@_admin_required
def admin_approve_submission(submission_id):
    data = request.json or {}
    admin_note = data.get('note', '').strip() or None
    ok, msg = approve_submission(submission_id, admin_note=admin_note)
    if ok:
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'error': msg}), 400


@social_tasks_bp.route('/admin/social-tasks/submissions/<submission_id>/reject', methods=['POST'])
@_admin_required
def admin_reject_submission(submission_id):
    data = request.json or {}
    admin_note = data.get('note', '').strip() or None
    ok, msg = reject_submission(submission_id, admin_note=admin_note)
    if ok:
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'error': msg}), 400

# ──────────────────────────────────────────────────
#  AUTO-TRADUCCIÓN CON IA (MyMemory - Gratis, sin key)
# ──────────────────────────────────────────────────
@social_tasks_bp.route('/admin/social-tasks/auto-translate', methods=['POST'])
@_admin_required
def admin_auto_translate():
    """
    Traduce title/description/instructions del español a EN, PT, RU, AR
    usando MyMemory API (gratuita, sin API key).
    """
    import requests as req

    data = request.json or {}
    title        = (data.get('title') or '').strip()
    description  = (data.get('description') or '').strip()
    instructions = (data.get('instructions') or '').strip()

    if not title:
        return jsonify({'success': False, 'error': 'Se requiere al menos el título'}), 400

    def translate_text(text, target_lang):
        """Traduce un texto de ES a target_lang usando MyMemory."""
        if not text:
            return ''
        try:
            r = req.get(
                'https://api.mymemory.translated.net/get',
                params={'q': text, 'langpair': f'es|{target_lang}'},
                timeout=10
            )
            result = r.json()
            translated = result.get('responseData', {}).get('translatedText', '')
            # Si retorna error o vacío, devolver original
            if not translated or 'MYMEMORY WARNING' in translated.upper():
                return text
            return translated
        except Exception:
            return text

    target_langs = ['en', 'pt', 'ru', 'ar']
    translations = {}

    for lang in target_langs:
        translations[lang] = {}
        if title:
            translations[lang]['title'] = translate_text(title, lang)
        if description:
            translations[lang]['description'] = translate_text(description, lang)
        if instructions:
            translations[lang]['instructions'] = translate_text(instructions, lang)

    return jsonify({'success': True, 'translations': translations})
