"""
telegram_web_auth.py - Sistema de Autenticación Web con Telegram Login Widget

Este módulo implementa la verificación segura del Telegram Login Widget,
manteniendo compatibilidad total con los usuarios de la MiniApp.

El telegram_id es el identificador único para ambos entornos.
"""

import os
import hmac
import hashlib
import time
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, session, jsonify, redirect, url_for

# Configurar logging
logger = logging.getLogger(__name__)

# Configuración
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
AUTH_EXPIRY_SECONDS = 24 * 60 * 60  # 24 horas - tiempo máximo para auth_date
SESSION_LIFETIME_DAYS = 7  # Duración de la sesión

# Rate limiting en memoria (para producción usar Redis)
_login_attempts = {}  # {ip: [(timestamp, success), ...]}
MAX_FAILED_ATTEMPTS = 5  # Máximo intentos fallidos
LOCKOUT_DURATION = 300  # 5 minutos de bloqueo


class TelegramAuthError(Exception):
    """Excepción personalizada para errores de autenticación de Telegram"""
    pass


def _check_rate_limit(ip_address: str) -> bool:
    """
    Verifica si la IP está bloqueada por demasiados intentos fallidos.
    
    Returns:
        True si puede continuar, False si está bloqueada
    """
    if ip_address not in _login_attempts:
        return True
    
    now = time.time()
    attempts = _login_attempts[ip_address]
    
    # Limpiar intentos antiguos (más de 5 minutos)
    attempts = [(ts, success) for ts, success in attempts if now - ts < LOCKOUT_DURATION]
    _login_attempts[ip_address] = attempts
    
    # Contar intentos fallidos recientes
    failed_count = sum(1 for ts, success in attempts if not success)
    
    return failed_count < MAX_FAILED_ATTEMPTS


def _record_login_attempt(ip_address: str, success: bool):
    """Registra un intento de login"""
    if ip_address not in _login_attempts:
        _login_attempts[ip_address] = []
    
    _login_attempts[ip_address].append((time.time(), success))
    
    # Limitar tamaño del historial
    if len(_login_attempts[ip_address]) > 100:
        _login_attempts[ip_address] = _login_attempts[ip_address][-50:]


def log_auth_attempt(telegram_id: str, auth_method: str, status: str, 
                     ip_address: str = None, failure_reason: str = None):
    """
    Registra un intento de autenticación en la base de datos.
    
    Args:
        telegram_id: ID de Telegram del usuario
        auth_method: 'telegram_web_login' o 'miniapp'
        status: 'success', 'failed', 'blocked'
        ip_address: IP del cliente
        failure_reason: Razón del fallo (si aplica)
    """
    try:
        from db import execute_query
        execute_query("""
            INSERT INTO auth_logs (telegram_id, auth_method, auth_status, ip_address, failure_reason)
            VALUES (%s, %s, %s, %s, %s)
        """, (telegram_id or 'unknown', auth_method, status, ip_address, failure_reason))
    except Exception as e:
        # No fallar si la tabla no existe
        logger.debug(f"No se pudo registrar log de auth: {e}")


def validate_telegram_login_data(auth_data: dict) -> dict:
    """
    Valida los datos de autenticación del Telegram Login Widget.
    
    PROCESO DE VALIDACIÓN (según documentación oficial de Telegram):
    1. Eliminar el campo 'hash' del payload
    2. Ordenar alfabéticamente los campos restantes
    3. Construir data_check_string en formato: key=value\nkey=value
    4. Crear clave secreta: SHA256(BOT_TOKEN)
    5. Calcular HMAC-SHA256(secret_key, data_check_string)
    6. Comparar con el hash recibido
    7. Verificar que auth_date no tenga más de 24 horas
    
    Args:
        auth_data: Diccionario con los datos recibidos de Telegram
        
    Returns:
        Diccionario con los datos validados del usuario
        
    Raises:
        TelegramAuthError: Si la validación falla
    """
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN no configurado")
        raise TelegramAuthError("Error de configuración del servidor")
    
    # Verificar campos obligatorios
    required_fields = ['id', 'auth_date', 'hash']
    for field in required_fields:
        if field not in auth_data:
            logger.warning(f"⚠️ Campo obligatorio faltante: {field}")
            raise TelegramAuthError(f"Campo obligatorio faltante: {field}")
    
    # Extraer el hash recibido
    received_hash = auth_data.get('hash', '')
    
    # Crear copia sin el hash para la verificación
    data_to_check = {k: v for k, v in auth_data.items() if k != 'hash'}
    
    # Ordenar alfabéticamente y construir data_check_string
    sorted_keys = sorted(data_to_check.keys())
    data_check_string = '\n'.join([f"{key}={data_to_check[key]}" for key in sorted_keys])
    
    # Crear clave secreta: SHA256(BOT_TOKEN)
    secret_key = hashlib.sha256(BOT_TOKEN.encode('utf-8')).digest()
    
    # Calcular HMAC-SHA256
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Comparar hashes (comparación segura contra timing attacks)
    if not hmac.compare_digest(calculated_hash, received_hash):
        logger.warning(f"⚠️ Hash inválido para usuario {auth_data.get('id')}")
        logger.debug(f"Expected: {calculated_hash}, Received: {received_hash}")
        raise TelegramAuthError("Firma criptográfica inválida")
    
    # Verificar auth_date (no más de 24 horas)
    try:
        auth_timestamp = int(auth_data.get('auth_date', 0))
        current_timestamp = int(time.time())
        time_diff = current_timestamp - auth_timestamp
        
        if time_diff > AUTH_EXPIRY_SECONDS:
            logger.warning(f"⚠️ auth_date expirado: {time_diff} segundos de antigüedad")
            raise TelegramAuthError("Los datos de autenticación han expirado")
        
        if time_diff < -60:  # Permitir 1 minuto de margen por desfase de reloj
            logger.warning(f"⚠️ auth_date en el futuro: {time_diff} segundos")
            raise TelegramAuthError("Fecha de autenticación inválida")
            
    except ValueError:
        raise TelegramAuthError("auth_date inválido")
    
    logger.info(f"✅ Autenticación Telegram validada para usuario {auth_data.get('id')}")
    
    # Retornar datos validados
    return {
        'telegram_id': str(auth_data.get('id')),
        'username': auth_data.get('username'),
        'first_name': auth_data.get('first_name', 'Usuario'),
        'last_name': auth_data.get('last_name'),
        'photo_url': auth_data.get('photo_url'),
        'auth_date': datetime.fromtimestamp(auth_timestamp)
    }


def process_telegram_web_login(auth_data: dict, db_module) -> dict:
    """
    Procesa el login web de Telegram: valida, crea/actualiza usuario y genera sesión.
    
    Args:
        auth_data: Datos recibidos del Telegram Login Widget
        db_module: Módulo de base de datos con get_user, create_user, update_user
        
    Returns:
        Diccionario con información del usuario y estado del login
    """
    # Validar datos de Telegram
    validated_data = validate_telegram_login_data(auth_data)
    telegram_id = validated_data['telegram_id']
    
    # Buscar usuario existente
    user = db_module.get_user(telegram_id)
    
    if user:
        # Usuario existente - actualizar datos de perfil si cambiaron
        updates = {}
        
        if validated_data.get('username') and validated_data['username'] != user.get('username'):
            updates['username'] = validated_data['username']
        
        if validated_data.get('first_name') and validated_data['first_name'] != user.get('first_name'):
            updates['first_name'] = validated_data['first_name']
        
        if validated_data.get('photo_url') and validated_data['photo_url'] != user.get('photo_url'):
            updates['photo_url'] = validated_data['photo_url']
        
        if updates:
            # Solo actualizar campos de perfil, NUNCA balances ni puntos
            db_module.update_user(telegram_id, **updates)
            logger.info(f"📝 Usuario {telegram_id} actualizado: {list(updates.keys())}")
        
        is_new_user = False
    else:
        # Crear nuevo usuario
        user = db_module.create_user(
            user_id=telegram_id,
            username=validated_data.get('username'),
            first_name=validated_data.get('first_name', 'Usuario')
        )
        
        if not user:
            raise TelegramAuthError("Error creando usuario")
        
        is_new_user = True
        logger.info(f"🆕 Nuevo usuario creado via Web Login: {telegram_id}")
    
    # Actualizar foto si está disponible y el usuario existe
    if validated_data.get('photo_url'):
        try:
            db_module.update_user(telegram_id, photo_url=validated_data['photo_url'])
        except Exception as e:
            logger.warning(f"⚠️ No se pudo actualizar photo_url: {e}")
    
    return {
        'success': True,
        'telegram_id': telegram_id,
        'username': validated_data.get('username'),
        'first_name': validated_data.get('first_name'),
        'photo_url': validated_data.get('photo_url'),
        'is_new_user': is_new_user
    }


def create_secure_session(telegram_id: str, remember: bool = True):
    """
    Crea una sesión segura después de autenticación exitosa.
    
    Args:
        telegram_id: ID de Telegram del usuario
        remember: Si True, la sesión será permanente (7 días)
    """
    session.permanent = remember
    session['telegram_id'] = telegram_id
    session['auth_method'] = 'telegram_web_login'
    session['auth_time'] = datetime.now().isoformat()
    session['is_authenticated'] = True
    
    logger.info(f"🔐 Sesión creada para usuario {telegram_id}")


def get_authenticated_user_id():
    """
    Obtiene el telegram_id del usuario autenticado desde la sesión.
    
    Returns:
        telegram_id si está autenticado, None si no
    """
    if session.get('is_authenticated'):
        return session.get('telegram_id')
    return None


def logout_user():
    """
    Cierra la sesión del usuario.
    """
    telegram_id = session.get('telegram_id')
    session.clear()
    if telegram_id:
        logger.info(f"👋 Usuario {telegram_id} cerró sesión")


def web_login_required(f):
    """
    Decorador para proteger rutas que requieren autenticación web.
    
    Verifica:
    1. Sesión válida con telegram_id
    2. O parámetros de query con user_id (compatibilidad MiniApp)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Primero verificar sesión web
        telegram_id = get_authenticated_user_id()
        
        if not telegram_id:
            # Compatibilidad con MiniApp - verificar query params
            telegram_id = (
                request.args.get('user_id') or 
                request.args.get('userId') or
                request.headers.get('X-User-Id') or
                request.headers.get('X-Telegram-User-Id')
            )
        
        if not telegram_id:
            # No autenticado
            if request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Autenticación requerida',
                    'redirect': '/web-login'
                }), 401
            return redirect(url_for('web_login_page'))
        
        # Agregar telegram_id al contexto
        request.telegram_id = str(telegram_id)
        return f(*args, **kwargs)
    
    return decorated_function


def register_telegram_web_auth_routes(app, db_module):
    """
    Registra las rutas de autenticación web con Telegram.
    
    Args:
        app: Instancia de Flask
        db_module: Módulo de base de datos
    """
    
    @app.route('/web-login')
    def web_login_page():
        """Página de login con Telegram Widget"""
        # Si ya está autenticado, redirigir al inicio
        if get_authenticated_user_id():
            return redirect(url_for('index'))
        
        from flask import render_template
        bot_username = os.environ.get('BOT_USERNAME', 'SallyEbot')
        webapp_url = os.environ.get('WEBAPP_URL', '')
        
        return render_template('web_login.html', 
                               bot_username=bot_username,
                               webapp_url=webapp_url)
    
    @app.route('/api/telegram-web-login', methods=['POST'])
    def api_telegram_web_login():
        """
        Endpoint para procesar el callback del Telegram Login Widget.
        
        Recibe los datos firmados de Telegram, los valida y crea la sesión.
        Incluye rate limiting y logging de seguridad.
        """
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        telegram_id = None
        
        try:
            # Verificar rate limiting
            if not _check_rate_limit(client_ip):
                logger.warning(f"🚫 IP bloqueada por rate limit: {client_ip}")
                log_auth_attempt('unknown', 'telegram_web_login', 'blocked', 
                               client_ip, 'Rate limit exceeded')
                return jsonify({
                    'success': False,
                    'error': 'Demasiados intentos. Espera unos minutos e intenta de nuevo.'
                }), 429
            
            # Obtener datos del request
            auth_data = request.get_json() or {}
            
            if not auth_data:
                # También aceptar form data (callback directo de Telegram)
                auth_data = request.form.to_dict()
            
            if not auth_data:
                _record_login_attempt(client_ip, False)
                return jsonify({
                    'success': False,
                    'error': 'No se recibieron datos de autenticación'
                }), 400
            
            telegram_id = str(auth_data.get('id', 'unknown'))
            logger.info(f"🔄 Intento de login web desde {client_ip} - Usuario: {telegram_id}")
            
            # Procesar login (incluye validación de hash)
            result = process_telegram_web_login(auth_data, db_module)
            
            if result['success']:
                # Login exitoso
                _record_login_attempt(client_ip, True)
                log_auth_attempt(result['telegram_id'], 'telegram_web_login', 'success', client_ip)
                
                # Crear sesión segura
                create_secure_session(result['telegram_id'])
                
                # Actualizar last_login
                try:
                    db_module.update_user(result['telegram_id'], 
                                         auth_method='telegram_web_login')
                except Exception:
                    pass
                
                # Registrar IP del usuario
                try:
                    from database import record_user_ip
                    record_user_ip(result['telegram_id'], client_ip)
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo registrar IP: {e}")
                
                return jsonify({
                    'success': True,
                    'message': 'Login exitoso',
                    'user': {
                        'telegram_id': result['telegram_id'],
                        'username': result.get('username'),
                        'first_name': result.get('first_name'),
                        'photo_url': result.get('photo_url'),
                        'is_new_user': result.get('is_new_user', False)
                    },
                    'redirect': '/'
                })
            
            # Login fallido
            _record_login_attempt(client_ip, False)
            log_auth_attempt(telegram_id, 'telegram_web_login', 'failed', 
                           client_ip, 'Unknown error')
            return jsonify({
                'success': False,
                'error': 'Error procesando login'
            }), 500
            
        except TelegramAuthError as e:
            # Error de validación de Telegram
            _record_login_attempt(client_ip, False)
            log_auth_attempt(telegram_id or 'unknown', 'telegram_web_login', 'failed',
                           client_ip, str(e))
            logger.warning(f"⚠️ Error de autenticación Telegram: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 401
            
        except Exception as e:
            _record_login_attempt(client_ip, False)
            log_auth_attempt(telegram_id or 'unknown', 'telegram_web_login', 'failed',
                           client_ip, str(e))
            logger.error(f"❌ Error en telegram-web-login: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor'
            }), 500
    
    @app.route('/api/telegram-web-login/callback', methods=['GET', 'POST'])
    def telegram_login_callback():
        """
        Callback directo del Telegram Login Widget (redirección).
        
        Telegram puede redirigir aquí directamente después del login.
        """
        try:
            # Obtener datos de query params o form
            auth_data = request.args.to_dict() if request.method == 'GET' else request.form.to_dict()
            
            if not auth_data or 'hash' not in auth_data:
                from flask import render_template
                return render_template('web_login.html', 
                                       error="No se recibieron datos de autenticación válidos")
            
            # Procesar login
            result = process_telegram_web_login(auth_data, db_module)
            
            if result['success']:
                create_secure_session(result['telegram_id'])
                return redirect('/')
            
            from flask import render_template
            return render_template('web_login.html', error="Error en autenticación")
            
        except TelegramAuthError as e:
            from flask import render_template
            return render_template('web_login.html', error=str(e))
        except Exception as e:
            logger.error(f"❌ Error en callback: {e}")
            from flask import render_template
            return render_template('web_login.html', error="Error interno")
    
    @app.route('/web-logout')
    def web_logout():
        """Endpoint para cerrar sesión web"""
        logout_user()
        return redirect(url_for('web_login_page'))
    
    @app.route('/api/auth/status')
    def api_auth_status():
        """
        Verifica el estado de autenticación actual.
        
        Útil para el frontend para verificar si el usuario tiene sesión activa.
        """
        telegram_id = get_authenticated_user_id()
        
        if telegram_id:
            user = db_module.get_user(telegram_id)
            return jsonify({
                'authenticated': True,
                'telegram_id': telegram_id,
                'auth_method': session.get('auth_method'),
                'user': {
                    'username': user.get('username') if user else None,
                    'first_name': user.get('first_name') if user else None,
                    'photo_url': user.get('photo_url') if user else None
                } if user else None
            })
        
        return jsonify({
            'authenticated': False,
            'telegram_id': None
        })
    
    logger.info("✅ Rutas de autenticación web Telegram registradas")


# ============== VALIDACIÓN DE MINIAPP INITDATA ==============

def validate_miniapp_init_data(init_data_string: str) -> dict:
    """
    Valida el initData de la MiniApp de Telegram.
    
    El initData viene en formato URL-encoded con un hash HMAC-SHA256.
    
    Args:
        init_data_string: String de initData de Telegram WebApp
        
    Returns:
        Diccionario con datos del usuario validados
        
    Raises:
        TelegramAuthError: Si la validación falla
    """
    if not BOT_TOKEN:
        raise TelegramAuthError("BOT_TOKEN no configurado")
    
    if not init_data_string:
        raise TelegramAuthError("initData vacío")
    
    import urllib.parse
    
    # Parsear el initData
    try:
        params = dict(urllib.parse.parse_qsl(init_data_string, keep_blank_values=True))
    except Exception as e:
        raise TelegramAuthError(f"Error parseando initData: {e}")
    
    if 'hash' not in params:
        raise TelegramAuthError("Hash no encontrado en initData")
    
    # Extraer hash
    received_hash = params.pop('hash')
    
    # Crear data_check_string
    sorted_params = sorted(params.items())
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted_params])
    
    # Para MiniApp, la clave secreta es HMAC-SHA256("WebAppData", BOT_TOKEN)
    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    # Calcular hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Verificar hash
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramAuthError("Hash de initData inválido")
    
    # Verificar auth_date
    try:
        auth_date = int(params.get('auth_date', 0))
        if time.time() - auth_date > AUTH_EXPIRY_SECONDS:
            raise TelegramAuthError("initData expirado")
    except ValueError:
        raise TelegramAuthError("auth_date inválido")
    
    # Parsear user data
    user_data_str = params.get('user', '{}')
    try:
        import json
        user_data = json.loads(user_data_str)
    except json.JSONDecodeError:
        raise TelegramAuthError("Datos de usuario inválidos")
    
    return {
        'telegram_id': str(user_data.get('id')),
        'username': user_data.get('username'),
        'first_name': user_data.get('first_name', 'Usuario'),
        'last_name': user_data.get('last_name'),
        'language_code': user_data.get('language_code', 'es'),
        'is_premium': user_data.get('is_premium', False),
        'auth_date': datetime.fromtimestamp(auth_date)
    }
