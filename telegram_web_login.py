"""
telegram_web_login.py - Sistema de Login con Telegram Web Widget
============================================================
Implementa autenticación segura usando el Telegram Login Widget,
con validación criptográfica HMAC-SHA256 del hash.

Compatible con la MiniApp existente - ambos usan telegram_id como identificador único.

Seguridad:
- Valida la firma criptográfica del hash de Telegram
- Verifica que auth_date no sea mayor a 24 horas
- Usa sesiones HTTP-only seguras
- Registra intentos de login sospechosos
"""

import os
import hmac
import hashlib
import time
import logging
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import parse_qs, unquote

from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template, make_response
from database import get_user, create_user, update_user

# ============================================
# CONFIGURACIÓN
# ============================================
logger = logging.getLogger(__name__)

# Token del bot de Telegram
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8490899064:AAHIlp5USATGbOokgxu0IWkGPWbG3E8wnok')
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'Nuevo18282bot')
WEBAPP_URL = os.environ.get('WEBAPP_URL', '')

# Tiempo máximo de validez del auth_date (24 horas)
AUTH_MAX_AGE_SECONDS = 24 * 60 * 60

# Crear Blueprint
telegram_web_login_bp = Blueprint('telegram_web_login', __name__)

# ============================================
# REGISTRO DE INTENTOS SOSPECHOSOS
# ============================================
_suspicious_attempts = {}

def _log_suspicious_attempt(ip_address, reason):
    """Registra un intento de login sospechoso"""
    now = datetime.now()
    key = ip_address

    if key not in _suspicious_attempts:
        _suspicious_attempts[key] = []

    _suspicious_attempts[key].append({
        'timestamp': now,
        'reason': reason
    })

    # Limpiar intentos antiguos (más de 1 hora)
    _suspicious_attempts[key] = [
        attempt for attempt in _suspicious_attempts[key]
        if (now - attempt['timestamp']).total_seconds() < 3600
    ]

    logger.warning(f"🚨 [TelegramWebLogin] Intento sospechoso desde {ip_address}: {reason}")

    # Si hay más de 10 intentos en 1 hora, loguear alerta crítica
    if len(_suspicious_attempts[key]) >= 10:
        logger.critical(f"🔴 [TelegramWebLogin] IP {ip_address} tiene {len(_suspicious_attempts[key])} intentos sospechosos en la última hora")

def _get_client_ip():
    """Obtiene la IP del cliente"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

# ============================================
# VALIDACIÓN CRIPTOGRÁFICA DE TELEGRAM
# ============================================

def validate_telegram_auth(auth_data: dict) -> tuple[bool, str]:
    """
    Valida la autenticidad de los datos del Telegram Login Widget.

    Proceso:
    1. Elimina el campo 'hash' del payload
    2. Ordena los campos restantes alfabéticamente
    3. Construye data_check_string en formato key=value
    4. Crea secret_key = SHA256(BOT_TOKEN)
    5. Calcula HMAC_SHA256(secret_key, data_check_string)
    6. Compara con el hash recibido
    7. Verifica que auth_date no tenga más de 24 horas

    Args:
        auth_data: Diccionario con los datos de autenticación de Telegram

    Returns:
        tuple: (is_valid, error_message)
    """
    client_ip = _get_client_ip()

    # Verificar que el BOT_TOKEN esté configurado
    if not BOT_TOKEN:
        logger.error("[TelegramWebLogin] BOT_TOKEN no configurado")
        return False, "Error de configuración del servidor"

    # Verificar campos obligatorios
    if 'hash' not in auth_data:
        _log_suspicious_attempt(client_ip, "Missing hash field")
        return False, "Hash no proporcionado"

    if 'id' not in auth_data:
        _log_suspicious_attempt(client_ip, "Missing id field")
        return False, "ID de Telegram no proporcionado"

    if 'auth_date' not in auth_data:
        _log_suspicious_attempt(client_ip, "Missing auth_date field")
        return False, "Fecha de autenticación no proporcionada"

    try:
        received_hash = auth_data['hash']

        # Crear data_check_string: ordenar campos alfabéticamente y formatear
        data_check_items = []
        for key in sorted(auth_data.keys()):
            if key != 'hash':
                data_check_items.append(f"{key}={auth_data[key]}")

        data_check_string = '\n'.join(data_check_items)

        # Crear secret_key = SHA256(BOT_TOKEN)
        secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()

        # Calcular HMAC-SHA256
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        # Comparar hashes de manera segura (timing-safe)
        if not hmac.compare_digest(computed_hash.lower(), received_hash.lower()):
            _log_suspicious_attempt(client_ip, f"Invalid hash for user {auth_data.get('id', 'unknown')}")
            return False, "Firma inválida - acceso denegado"

        # Verificar auth_date (no más de 24 horas)
        auth_date = int(auth_data['auth_date'])
        current_time = int(time.time())

        if current_time - auth_date > AUTH_MAX_AGE_SECONDS:
            _log_suspicious_attempt(client_ip, f"Expired auth_date for user {auth_data.get('id', 'unknown')}")
            return False, "Sesión expirada - por favor, inicia sesión de nuevo"

        # Verificar que auth_date no sea del futuro (tolerancia de 5 minutos)
        if auth_date > current_time + 300:
            _log_suspicious_attempt(client_ip, f"Future auth_date for user {auth_data.get('id', 'unknown')}")
            return False, "Fecha de autenticación inválida"

        logger.info(f"✅ [TelegramWebLogin] Validación exitosa para user {auth_data.get('id')}")
        return True, "OK"

    except Exception as e:
        logger.error(f"[TelegramWebLogin] Error en validación: {e}")
        _log_suspicious_attempt(client_ip, f"Validation error: {str(e)}")
        return False, "Error en la validación"

# ============================================
# GESTIÓN DE SESIONES
# ============================================

def create_web_session(telegram_id: str, username: str = None, first_name: str = None, photo_url: str = None):
    """
    Crea una sesión web segura para el usuario.

    Args:
        telegram_id: ID único de Telegram
        username: Username de Telegram (opcional)
        first_name: Nombre del usuario
        photo_url: URL de la foto de perfil (opcional)
    """
    session.permanent = True
    session['web_logged_in'] = True
    session['telegram_id'] = str(telegram_id)
    session['username'] = username
    session['first_name'] = first_name
    session['photo_url'] = photo_url
    session['login_time'] = datetime.now().isoformat()
    session['login_method'] = 'telegram_web_widget'

    logger.info(f"✅ [TelegramWebLogin] Sesión creada para user {telegram_id}")

def get_web_session_user():
    """
    Obtiene el usuario de la sesión web actual.

    Returns:
        dict o None: Datos del usuario si hay sesión válida, None si no
    """
    if not session.get('web_logged_in'):
        return None

    telegram_id = session.get('telegram_id')
    if not telegram_id:
        return None

    return get_user(telegram_id)

def destroy_web_session():
    """Destruye la sesión web actual"""
    session.clear()
    logger.info("[TelegramWebLogin] Sesión destruida")

def web_login_required(f):
    """
    Decorator para requerir autenticación web.
    Redirige a la página de login si no hay sesión.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('web_logged_in'):
            return redirect(url_for('telegram_web_login.web_login_page'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# RUTAS DE AUTENTICACIÓN
# ============================================

@telegram_web_login_bp.route('/web-login')
def web_login_page():
    """
    Página de login con el Telegram Login Widget.
    Si el usuario ya tiene sesión, redirige al dashboard.
    """
    # Si ya tiene sesión web, redirigir al dashboard
    if session.get('web_logged_in') and session.get('telegram_id'):
        return redirect(f"/?user_id={session.get('telegram_id')}")

    return render_template('web_login.html',
                         bot_username=BOT_USERNAME,
                         webapp_url=WEBAPP_URL)

@telegram_web_login_bp.route('/api/telegram-web-auth', methods=['POST'])
def telegram_web_auth():
    """
    Endpoint para validar la autenticación del Telegram Login Widget.

    Recibe los datos del widget, valida el hash criptográficamente,
    y crea/actualiza el usuario según corresponda.

    Request JSON:
        - id: Telegram ID (obligatorio)
        - first_name: Nombre (obligatorio de Telegram)
        - last_name: Apellido (opcional)
        - username: Username (opcional)
        - photo_url: URL de foto (opcional)
        - auth_date: Timestamp de autenticación (obligatorio)
        - hash: Firma criptográfica (obligatorio)

    Response JSON:
        - success: boolean
        - message: string
        - user_id: string (si success)
        - redirect_url: string (si success)
    """
    client_ip = _get_client_ip()

    # Verificar HTTPS en producción
    if not request.is_secure and not request.headers.get('X-Forwarded-Proto') == 'https':
        # Permitir en desarrollo local
        if 'localhost' not in request.host and '127.0.0.1' not in request.host:
            logger.warning(f"[TelegramWebLogin] Intento de login sin HTTPS desde {client_ip}")
            # No bloquear, solo advertir (para flexibilidad en desarrollo)

    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'message': 'Datos no proporcionados'
        }), 400

    # Validar firma criptográfica
    is_valid, error_msg = validate_telegram_auth(data)

    if not is_valid:
        return jsonify({
            'success': False,
            'message': error_msg
        }), 401

    # Extraer datos del usuario
    telegram_id = str(data.get('id'))
    username = data.get('username')
    first_name = data.get('first_name', 'Usuario')
    last_name = data.get('last_name')
    photo_url = data.get('photo_url')

    try:
        # Buscar usuario existente
        user = get_user(telegram_id)

        if user:
            # Usuario existente - actualizar datos de perfil si cambiaron
            # NUNCA sobrescribir balances, puntos o historial
            update_fields = {}

            if username and username != user.get('username'):
                update_fields['username'] = username

            if first_name and first_name != user.get('first_name'):
                update_fields['first_name'] = first_name

            if photo_url and photo_url != user.get('photo_url'):
                update_fields['photo_url'] = photo_url

            if update_fields:
                update_user(telegram_id, **update_fields)
                logger.info(f"[TelegramWebLogin] Usuario {telegram_id} actualizado: {list(update_fields.keys())}")

            logger.info(f"✅ [TelegramWebLogin] Login exitoso para usuario existente: {telegram_id}")
        else:
            # Usuario nuevo - crear cuenta
            new_user = create_user(
                user_id=telegram_id,
                username=username,
                first_name=first_name
            )

            if not new_user:
                logger.error(f"[TelegramWebLogin] Error creando usuario {telegram_id}")
                return jsonify({
                    'success': False,
                    'message': 'Error al crear la cuenta'
                }), 500

            # Guardar photo_url si está disponible
            if photo_url:
                update_user(telegram_id, photo_url=photo_url)

            logger.info(f"✅ [TelegramWebLogin] Usuario nuevo creado: {telegram_id}")

        # Crear sesión web segura
        create_web_session(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            photo_url=photo_url
        )

        # Establecer cookie con user_id para compatibilidad
        response = make_response(jsonify({
            'success': True,
            'message': 'Login exitoso',
            'user_id': telegram_id,
            'redirect_url': f"/?user_id={telegram_id}"
        }))

        # Cookie HTTP-only para seguridad
        response.set_cookie(
            'user_id',
            telegram_id,
            max_age=7 * 24 * 60 * 60,  # 7 días
            httponly=True,
            secure=True,
            samesite='Lax'
        )

        return response

    except Exception as e:
        logger.error(f"[TelegramWebLogin] Error en autenticación: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Error interno del servidor'
        }), 500

@telegram_web_login_bp.route('/api/telegram-web-auth/callback', methods=['GET'])
def telegram_web_auth_callback():
    """
    Callback para el Telegram Login Widget (método redirect).
    Valida los parámetros de la URL y redirige al dashboard.
    """
    # Obtener todos los parámetros de la URL
    auth_data = {
        'id': request.args.get('id'),
        'first_name': request.args.get('first_name'),
        'last_name': request.args.get('last_name'),
        'username': request.args.get('username'),
        'photo_url': request.args.get('photo_url'),
        'auth_date': request.args.get('auth_date'),
        'hash': request.args.get('hash')
    }

    # Eliminar valores None
    auth_data = {k: v for k, v in auth_data.items() if v is not None}

    # Validar
    is_valid, error_msg = validate_telegram_auth(auth_data)

    if not is_valid:
        return render_template('web_login.html',
                             bot_username=BOT_USERNAME,
                             webapp_url=WEBAPP_URL,
                             error=error_msg)

    telegram_id = str(auth_data.get('id'))
    username = auth_data.get('username')
    first_name = auth_data.get('first_name', 'Usuario')
    photo_url = auth_data.get('photo_url')

    try:
        # Buscar o crear usuario
        user = get_user(telegram_id)

        if not user:
            create_user(
                user_id=telegram_id,
                username=username,
                first_name=first_name
            )
            if photo_url:
                update_user(telegram_id, photo_url=photo_url)
        else:
            # Actualizar datos de perfil si cambiaron
            update_fields = {}
            if username and username != user.get('username'):
                update_fields['username'] = username
            if first_name and first_name != user.get('first_name'):
                update_fields['first_name'] = first_name
            if photo_url and photo_url != user.get('photo_url'):
                update_fields['photo_url'] = photo_url
            if update_fields:
                update_user(telegram_id, **update_fields)

        # Crear sesión
        create_web_session(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            photo_url=photo_url
        )

        # Redirigir al dashboard con cookie
        response = make_response(redirect(f"/?user_id={telegram_id}"))
        response.set_cookie(
            'user_id',
            telegram_id,
            max_age=7 * 24 * 60 * 60,
            httponly=True,
            secure=True,
            samesite='Lax'
        )

        return response

    except Exception as e:
        logger.error(f"[TelegramWebLogin] Error en callback: {e}")
        return render_template('web_login.html',
                             bot_username=BOT_USERNAME,
                             webapp_url=WEBAPP_URL,
                             error="Error al procesar el login")

@telegram_web_login_bp.route('/web-logout')
def web_logout():
    """Cierra la sesión web del usuario"""
    destroy_web_session()

    response = make_response(redirect(url_for('telegram_web_login.web_login_page')))
    response.delete_cookie('user_id')

    return response

@telegram_web_login_bp.route('/api/web-session/status')
def web_session_status():
    """
    Verifica el estado de la sesión web actual.

    Response JSON:
        - logged_in: boolean
        - user_id: string (si logged_in)
        - username: string (si logged_in)
        - login_method: string (si logged_in)
    """
    if session.get('web_logged_in'):
        return jsonify({
            'logged_in': True,
            'user_id': session.get('telegram_id'),
            'username': session.get('username'),
            'first_name': session.get('first_name'),
            'login_method': session.get('login_method', 'unknown')
        })

    return jsonify({
        'logged_in': False
    })

# ============================================
# VALIDACIÓN DE INIT DATA (MiniApp)
# ============================================

def validate_init_data(init_data: str) -> tuple[bool, dict, str]:
    """
    Valida el initData de Telegram MiniApp.

    Esta función valida los datos de la MiniApp de la misma manera
    que validamos el Web Login Widget, asegurando compatibilidad.

    Args:
        init_data: String con los datos de inicialización de la MiniApp

    Returns:
        tuple: (is_valid, user_data, error_message)
    """
    if not init_data:
        return False, {}, "initData vacío"

    if not BOT_TOKEN:
        return False, {}, "BOT_TOKEN no configurado"

    try:
        # Parsear el initData
        parsed = {}
        for part in init_data.split('&'):
            if '=' in part:
                key, value = part.split('=', 1)
                parsed[key] = unquote(value)

        if 'hash' not in parsed:
            return False, {}, "Hash no encontrado en initData"

        received_hash = parsed.pop('hash')

        # Crear data_check_string
        data_check_items = []
        for key in sorted(parsed.keys()):
            data_check_items.append(f"{key}={parsed[key]}")

        data_check_string = '\n'.join(data_check_items)

        # Crear HMAC key: HMAC-SHA256(secret_key, "WebAppData")
        secret_key = hmac.new(
            b'WebAppData',
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        # Calcular hash
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash.lower(), received_hash.lower()):
            return False, {}, "Firma de initData inválida"

        # Verificar auth_date
        auth_date = int(parsed.get('auth_date', 0))
        current_time = int(time.time())

        if current_time - auth_date > AUTH_MAX_AGE_SECONDS:
            return False, {}, "initData expirado"

        # Extraer datos del usuario
        user_data = {}
        if 'user' in parsed:
            import json
            try:
                user_data = json.loads(parsed['user'])
            except:
                pass

        return True, user_data, "OK"

    except Exception as e:
        logger.error(f"[TelegramWebLogin] Error validando initData: {e}")
        return False, {}, f"Error de validación: {str(e)}"

# ============================================
# FUNCIÓN DE REGISTRO DEL BLUEPRINT
# ============================================

def register_telegram_web_login(app):
    """
    Registra el Blueprint de Telegram Web Login en la aplicación Flask.

    Args:
        app: Instancia de Flask
    """
    app.register_blueprint(telegram_web_login_bp)
    logger.info("✅ [TelegramWebLogin] Blueprint registrado correctamente")
    logger.info(f"   - Página de login: /web-login")
    logger.info(f"   - API de auth: /api/telegram-web-auth")
    logger.info(f"   - Callback: /api/telegram-web-auth/callback")
    logger.info(f"   - Logout: /web-logout")
    logger.info(f"   - Status: /api/web-session/status")
