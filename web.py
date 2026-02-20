"""
app.py - Aplicación Flask para SALLY-E Bot
Incluye rutas de usuario, admin y API
FIXED VERSION - Mandatory channel verification + Fixed referral system + Complete integration
"""

import os
import sys
import json
import secrets
import random
import logging
import requests
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS

# ============================================
# CONFIGURACIÓN DE LOGGING
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Redirigir print a logger para capturar todos los mensajes
class LoggerWriter:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.buffer = ''

    def write(self, message):
        if message and message.strip():
            self.logger.log(self.level, message.strip())

    def flush(self):
        pass

# Solo redirigir si no estamos en modo debug
if not os.environ.get('FLASK_DEBUG'):
    sys.stdout = LoggerWriter(logger, logging.INFO)
    sys.stderr = LoggerWriter(logger, logging.ERROR)

# Import database operations
from database import (
    get_user, create_user, update_user, get_all_users, get_users_count,
    get_banned_users_count, search_users, get_all_users_with_referrals,
    get_all_users_no_limit, get_all_users_with_referrals_no_limit,
    get_user_balance_history, get_user_with_referrals,
    ban_user, unban_user, update_balance,
    add_referral, validate_referral, get_referrals, get_referrals_paginated, get_referrals_counts,
    get_pending_referrer, clear_pending_referrer,
    process_first_task_completion, is_first_task, get_validated_referrals_count,
    get_all_tasks, get_active_tasks, get_task, create_task, update_task, delete_task,
    complete_task, is_task_completed,
    create_withdrawal, get_withdrawal, get_user_withdrawals, get_pending_withdrawals,
    get_withdrawals_by_status, get_all_withdrawals, update_withdrawal,
    get_all_promo_codes, get_promo_code, create_promo_code, redeem_promo_code, delete_promo_code,
    has_available_promo_codes, get_promo_stats, toggle_promo_code, cleanup_empty_promo_codes,
    delete_promo_code_by_id, get_promo_redemptions, update_promo_code,
    get_config, set_config, get_all_config,
    get_stats, get_stat, increment_stat, set_stat,
    record_user_ip, get_users_by_ip, get_duplicate_ips, is_ip_banned, ban_ip, unban_ip,
    get_top_users_by_balance, get_top_users_by_referrals, get_top_users_by_mined,
    load_database, update_referral_count,
    # Game session functions
    create_game_session, get_game_session, get_active_game_session,
    update_game_session, end_game_session, get_game_history
)

# Import execute_query for direct queries
from db import execute_query

# Import wallet functions
try:
    from wallet import (
        create_withdrawal_request, approve_withdrawal, reject_withdrawal,
        link_wallet_address, get_withdrawal_stats
    )
    WALLET_AVAILABLE = True
except ImportError:
    WALLET_AVAILABLE = False
    logger.warning("wallet.py not available")

# Import ban system
try:
    from ban_system import (
        get_user_ban_status, auto_ban_check, record_device_info,
        initialize_ban_system, get_ban_statistics, get_user_ban_details,
        ban_user_manual, unban_user_manual, update_ban_reason,
        get_banned_users_list, get_ban_logs
    )
    BAN_SYSTEM_AVAILABLE = True
    logger.info("✅ Ban system loaded successfully")
except ImportError as e:
    BAN_SYSTEM_AVAILABLE = False
    logger.warning(f"⚠️ Ban system not available: {e}")

# Import mining machine system
try:
    from mining_machine_system import (
        get_machine_status, get_machine_config, MACHINE_CONFIG
    )
    MINING_MACHINE_AVAILABLE = True
    logger.info("✅ Mining machine system loaded successfully")
except ImportError as e:
    MINING_MACHINE_AVAILABLE = False
    logger.warning(f"⚠️ Mining machine system not available: {e}")

# Import auto payment system
try:
    from auto_pay import (
        process_withdrawal_if_auto, is_auto_mode,
        get_auto_pay_status, check_wallet_status
    )
    AUTO_PAY_AVAILABLE = True
    logger.info("✅ Auto payment system loaded successfully")
except ImportError as e:
    AUTO_PAY_AVAILABLE = False
    logger.warning(f"⚠️ Auto payment system not available: {e}")

# Import transactions system
try:
    from transactions_system import get_user_unified_transactions, format_transaction_for_api, CURRENCIES, get_translations
    TRANSACTIONS_SYSTEM_AVAILABLE = True
    logger.info("✅ Transactions system loaded successfully")
except ImportError as e:
    TRANSACTIONS_SYSTEM_AVAILABLE = False
    logger.warning(f"⚠️ Transactions system not available: {e}")

# Import withdrawal notifications
try:
    from withdrawal_notifications import on_withdrawal_created, on_withdrawal_completed, on_withdrawal_rejected
    WITHDRAWAL_NOTIFICATIONS_AVAILABLE = True
    logger.info("✅ Withdrawal notifications loaded successfully")
except ImportError as e:
    WITHDRAWAL_NOTIFICATIONS_AVAILABLE = False
    logger.warning(f"⚠️ Withdrawal notifications not available: {e}")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=7)

# ============================================================
# ✅ EJECUTAR MIGRACIONES DE BASE DE DATOS AL ARRANCAR
# Soluciona: Unknown column 'active' / 'activa' in where clause
# ============================================================
try:
    from migrate_railway import run_migrations
    logger.info("🔧 Ejecutando migraciones de base de datos...")
    run_migrations()
    logger.info("✅ Migraciones completadas correctamente")
except Exception as e:
    logger.error(f"⚠️ Error en migraciones (no crítico): {e}")

# Enable CORS for API routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Register ban routes
if BAN_SYSTEM_AVAILABLE:
    try:
        from ban_routes import register_ban_routes
        register_ban_routes(app)
        logger.info("✅ Ban routes registered successfully")
    except Exception as e:
        logger.warning(f"⚠️ Could not register ban routes: {e}")

# ============== TELEGRAM WEB LOGIN SYSTEM ==============
try:
    from telegram_web_login import register_telegram_web_login
    register_telegram_web_login(app)
    TELEGRAM_WEB_LOGIN_AVAILABLE = True
    logger.info("✅ Telegram Web Login system loaded successfully")
except ImportError as e:
    TELEGRAM_WEB_LOGIN_AVAILABLE = False
    logger.warning(f"⚠️ Telegram Web Login not available: {e}")
except Exception as e:
    TELEGRAM_WEB_LOGIN_AVAILABLE = False
    logger.error(f"❌ Error loading Telegram Web Login: {e}")

# ============== VPN/PROXY DETECTION SYSTEM ==============
try:
    from vpn_system import init_vpn_system, is_vpn_or_proxy, get_client_ip, VPN_CONFIG
    init_vpn_system(app)
    VPN_SYSTEM_AVAILABLE = True
except ImportError as e:
    VPN_SYSTEM_AVAILABLE = False
    logger.warning(f"⚠️ VPN Detection system not available: {e}")
except Exception as e:
    VPN_SYSTEM_AVAILABLE = False
    logger.error(f"❌ Error loading VPN Detection system: {e}")

# Admin configuration
ADMIN_IDS = os.environ.get('ADMIN_IDS', '5515244003').split(',')

# Bot configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'SallyEbot')
SUPPORT_GROUP = os.environ.get('SUPPORT_GROUP', 'https://t.me/Soporte_Sally')

# Official channels - comma separated list
OFFICIAL_CHANNELS_STR = os.environ.get('OFFICIAL_CHANNELS', '@SallyE_Comunity')
if not OFFICIAL_CHANNELS_STR or OFFICIAL_CHANNELS_STR == '@SallyE_Comunity':
    single_channel = os.environ.get('OFFICIAL_CHANNEL', '@SallyE_Comunity')
    OFFICIAL_CHANNELS_STR = single_channel

# Parse channels into list
OFFICIAL_CHANNELS = [ch.strip() for ch in OFFICIAL_CHANNELS_STR.split(',') if ch.strip()]

# ============== CHANNEL MEMBERSHIP CACHE SYSTEM ==============
# In-memory cache to throttle Telegram API calls for membership verification
# Format: { "user_id:channel": {"last_check": datetime, "result": (bool, str)} }
_channel_membership_cache = {}

# Throttle interval in seconds (30 seconds between API calls per user+channel)
_MEMBERSHIP_CHECK_THROTTLE_SECONDS = 30

def _get_membership_cache_key(user_id, channel_username):
    """Generate a unique cache key for user+channel combination."""
    return f"{user_id}:{channel_username.lower().strip()}"

def _get_cached_membership(user_id, channel_username):
    """
    Check if we have a cached membership result that is still valid (within 30 seconds).
    Returns (is_cached, result) where result is (bool, str) or None.
    """
    cache_key = _get_membership_cache_key(user_id, channel_username)

    if cache_key not in _channel_membership_cache:
        return False, None

    cached = _channel_membership_cache[cache_key]
    last_check = cached.get('last_check')

    if last_check is None:
        return False, None

    elapsed_seconds = (datetime.now() - last_check).total_seconds()

    if elapsed_seconds < _MEMBERSHIP_CHECK_THROTTLE_SECONDS:
        # Cache is still valid, return cached result
        return True, cached.get('result')

    # Cache expired
    return False, None

def _cache_membership_result(user_id, channel_username, result):
    """Store membership result in cache with current timestamp."""
    cache_key = _get_membership_cache_key(user_id, channel_username)
    _channel_membership_cache[cache_key] = {
        'last_check': datetime.now(),
        'result': result
    }

# ============== TELEGRAM VERIFICATION FUNCTIONS ==============

def verify_channel_membership(user_id, channel_username):
    """
    Verifica si un usuario es miembro de un canal de Telegram.
    Usa la API de Telegram Bot para verificar la membresía.

    Args:
        user_id: ID del usuario de Telegram
        channel_username: Username del canal (sin @)

    Returns:
        (bool, str): (es_miembro, mensaje)

    OPTIMIZED: Results are cached for 30 seconds to reduce Telegram API calls.
    """
    if not BOT_TOKEN:
        logger.error("[verify_channel_membership] ❌ BOT_TOKEN no configurado")
        return False, "Error de configuración del bot"

    if not channel_username:
        logger.error("[verify_channel_membership] ❌ channel_username vacío")
        return False, "Canal no especificado"

    # Limpiar el username del canal
    channel = channel_username.strip()
    if not channel.startswith('@'):
        channel = f"@{channel}"

    # ============== CACHE CHECK (ADDED) ==============
    # Check if we have a recent cached result (within 30 seconds)
    is_cached, cached_result = _get_cached_membership(user_id, channel)
    if is_cached and cached_result is not None:
        # Return cached result without calling Telegram API or logging
        return cached_result
    # ============== END CACHE CHECK ==============

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"

        params = {
            'chat_id': channel,
            'user_id': user_id
        }

        logger.info(f"[verify_channel_membership] Verificando user {user_id} en canal {channel}")

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        logger.info(f"[verify_channel_membership] Respuesta de Telegram: {data}")

        if not data.get('ok'):
            error_description = data.get('description', 'Error desconocido')
            logger.error(f"[verify_channel_membership] ❌ Error de Telegram: {error_description}")

            if 'user not found' in error_description.lower() or 'USER_NOT_PARTICIPANT' in error_description:
                result = (False, "No eres miembro del canal")
                _cache_membership_result(user_id, channel, result)  # Cache result
                return result

            if 'chat not found' in error_description.lower():
                result = (False, "Error verificando el canal")
                _cache_membership_result(user_id, channel, result)  # Cache result
                return result

            result = (False, f"Error de verificación: {error_description}")
            _cache_membership_result(user_id, channel, result)  # Cache result
            return result

        result = data.get('result', {})
        status = result.get('status', '')

        logger.info(f"[verify_channel_membership] Status del usuario: {status}")

        member_statuses = ['creator', 'administrator', 'member']

        if status in member_statuses:
            logger.info(f"[verify_channel_membership] ✅ Usuario {user_id} ES miembro del canal {channel}")
            result = (True, "Verificación exitosa")
            _cache_membership_result(user_id, channel, result)  # Cache result
            return result

        if status in ['left', 'kicked', 'restricted']:
            logger.info(f"[verify_channel_membership] ❌ Usuario {user_id} NO es miembro del canal {channel}")
            result = (False, "No eres miembro del canal")
            _cache_membership_result(user_id, channel, result)  # Cache result
            return result

        logger.warning(f"[verify_channel_membership] ⚠️ Estado desconocido: {status}")
        result = (False, "Estado de membresía desconocido")
        _cache_membership_result(user_id, channel, result)  # Cache result
        return result

    except requests.exceptions.Timeout:
        logger.error("[verify_channel_membership] ❌ Timeout al conectar con Telegram")
        return False, "Error de conexión con Telegram"
    except requests.exceptions.RequestException as e:
        logger.error(f"[verify_channel_membership] ❌ Error de conexión: {e}")
        return False, "Error de conexión"
    except Exception as e:
        logger.error(f"[verify_channel_membership] ❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False, "Error interno de verificación"


def verify_all_channels_membership(user_id):
    """
    Verifica si un usuario es miembro de TODOS los canales oficiales.

    Returns:
        (bool, list): (es_miembro_de_todos, lista_de_canales_faltantes)
    """
    missing_channels = []

    for channel in OFFICIAL_CHANNELS:
        if not channel:
            continue

        # Remove @ for verification
        channel_clean = channel.replace('@', '')
        is_member, _ = verify_channel_membership(user_id, channel_clean)

        if not is_member:
            missing_channels.append(channel)

    return (len(missing_channels) == 0, missing_channels)


def check_channel_or_redirect(user_id):
    """
    Verifica membresía en canales y retorna página de error si no es miembro.
    Returns None if member, or render_template if not member.
    """
    is_member, missing_channels = verify_all_channels_membership(user_id)

    if not is_member:
        return render_template('channel_required.html',
                             user_id=user_id,
                             channel=missing_channels[0].replace('@', '') if missing_channels else 'SallyE_Comunity',
                             missing_channels=missing_channels,
                             support_group=SUPPORT_GROUP)

    return None


# ============== HELPER FUNCTIONS ==============

def get_user_id():
    """Extract user_id from request - MEJORADO para múltiples fuentes incluyendo sesión web"""
    user_id = request.args.get('user_id') or request.args.get('userId')

    if not user_id:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id') or data.get('userId')

    if not user_id:
        user_id = request.form.get('user_id') or request.form.get('userId')

    if not user_id:
        user_id = request.cookies.get('user_id')

    if not user_id:
        user_id = request.headers.get('X-User-Id') or request.headers.get('X-Telegram-User-Id')

    # NUEVO: Verificar sesión web de Telegram Login
    if not user_id:
        if session.get('web_logged_in') and session.get('telegram_id'):
            user_id = session.get('telegram_id')

    return str(user_id) if user_id else None

def get_client_ip():
    """Get client IP address"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def admin_required(f):
    """Decorator for admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def calculate_unclaimed(user):
    """Calculate unclaimed mining rewards"""
    if not user:
        return 0

    last_claim = user.get('last_claim')
    if not last_claim:
        last_claim = user.get('created_at', datetime.now())

    if isinstance(last_claim, str):
        try:
            last_claim = datetime.fromisoformat(last_claim.replace('Z', '+00:00'))
        except:
            last_claim = datetime.now()

    elapsed = datetime.now() - last_claim
    hours = min(elapsed.total_seconds() / 3600, 24)

    base_rate = float(get_config('base_mining_rate', 0.1))
    global_power = float(get_config('global_mining_power', 1.0))
    user_power = float(user.get('mining_power', 1.0) or 1.0)

    # Cálculo base sin modificar
    base_unclaimed = round(hours * base_rate * global_power * user_power, 4)

    user_id = user.get('user_id')
    if not user_id:
        return base_unclaimed

    # Obtener el mayor multiplicador de boost activo (NO se acumulan)
    boost_multiplier = 1.0

    # Verificar boost de AdsGram
    try:
        from adsgram_boost import get_boost_multiplier as get_adsgram_boost
        adsgram_mult = get_adsgram_boost(user_id)
        if adsgram_mult > boost_multiplier:
            boost_multiplier = adsgram_mult
    except:
        pass

    # Verificar boost de OnClickA
    try:
        from onclicka_pts_system import get_onclicka_boost_multiplier
        onclicka_mult = get_onclicka_boost_multiplier(user_id)
        if onclicka_mult > boost_multiplier:
            boost_multiplier = onclicka_mult
    except:
        pass

    # Aplicar el mayor multiplicador
    if boost_multiplier > 1.0:
        return round(base_unclaimed * boost_multiplier, 4)

    return base_unclaimed

def get_effective_rate(user):
    """Calculate effective mining rate per hour"""
    base_rate = float(get_config('base_mining_rate', 0.1))
    global_power = float(get_config('global_mining_power', 1.0))
    user_power = float(user.get('mining_power', 1.0) or 1.0) if user else 1.0

    # Tasa base sin modificar
    base_rate_final = round(base_rate * global_power * user_power, 4)

    user_id = user.get('user_id') if user else None
    if not user_id:
        return base_rate_final

    # Obtener el mayor multiplicador de boost activo (NO se acumulan)
    boost_multiplier = 1.0

    # Verificar boost de AdsGram
    try:
        from adsgram_boost import get_boost_multiplier as get_adsgram_boost
        adsgram_mult = get_adsgram_boost(user_id)
        if adsgram_mult > boost_multiplier:
            boost_multiplier = adsgram_mult
    except:
        pass

    # Verificar boost de OnClickA
    try:
        from onclicka_pts_system import get_onclicka_boost_multiplier
        onclicka_mult = get_onclicka_boost_multiplier(user_id)
        if onclicka_mult > boost_multiplier:
            boost_multiplier = onclicka_mult
    except:
        pass

    # Aplicar el mayor multiplicador
    if boost_multiplier > 1.0:
        return round(base_rate_final * boost_multiplier, 4)

    return base_rate_final

def get_config_dict():
    """Get all config as a dictionary for templates"""
    all_config = get_all_config()
    config = {}
    for key, value in all_config.items():
        try:
            if '.' in str(value):
                config[key] = float(value)
            else:
                config[key] = int(value)
        except (ValueError, TypeError):
            if str(value).lower() == 'true':
                config[key] = True
            elif str(value).lower() == 'false':
                config[key] = False
            else:
                config[key] = value
    return config

def safe_user_dict(user):
    """Ensure user dict has all expected keys with defaults"""
    if not user:
        return {
            'user_id': '',
            'username': '',
            'first_name': 'Usuario',
            'se_balance': 0,
            'usdt_balance': 0,
            'doge_balance': 0,
            'ton_balance': 0,
            'mining_power': 1.0,
            'mining_level': 1,
            'total_mined': 0,
            'referral_count': 0,
            'completed_tasks': [],
            'wallet_address': None,
            'ton_wallet_address': None,
            'banned': False,
            'collector': False,
            'language': 'es'
        }

    defaults = {
        'username': '',
        'first_name': 'Usuario',
        'se_balance': 0,
        'usdt_balance': 0,
        'doge_balance': 0,
        'ton_balance': 0,
        'mining_power': 1.0,
        'mining_level': 1,
        'total_mined': 0,
        'referral_count': 0,
        'completed_tasks': [],
        'wallet_address': None,
        'ton_wallet_address': None,
        'banned': False,
        'collector': False,
        'language': 'es'
    }

    for key, default in defaults.items():
        if key not in user or user[key] is None:
            user[key] = default

    return user

# ============== USER ROUTES ==============

@app.route('/')
def index():
    """Main dashboard"""
    user_id = get_user_id()

    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    # Record IP
    client_ip = get_client_ip()
    record_user_ip(user_id, client_ip)

    # Auto-ban check (if ban system available)
    if BAN_SYSTEM_AVAILABLE:
        try:
            device_hash = request.headers.get('X-Device-Hash') or request.cookies.get('_se_dfp_hash')

            # Run auto-ban check
            ban_result = auto_ban_check(user_id, client_ip, device_hash)

            if ban_result.get('was_banned') or ban_result.get('already_banned'):
                # Refresh user data after potential ban
                user = get_user(user_id)
                if user and (user.get('banned') or user.get('account_state') == 'BANNED'):
                    user = safe_user_dict(user)
                    support_link = os.environ.get('SUPPORT_GROUP', SUPPORT_GROUP)
                    return render_template('banned_premium.html', user=user, support_link=support_link)
        except Exception as e:
            logger.error(f"[index] Auto-ban check error: {e}")

    user = safe_user_dict(user)

    # Check if user is banned (using both fields for compatibility)
    if user.get('banned') or user.get('account_state') == 'BANNED':
        support_link = os.environ.get('SUPPORT_GROUP', SUPPORT_GROUP)
        return render_template('banned_premium.html', user=user, support_link=support_link)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    unclaimed = calculate_unclaimed(user)
    mining_rate = get_effective_rate(user)

    promo_config = get_config('show_promo_fab', 'true')
    show_promo_fab = str(promo_config).lower() == 'true' and has_available_promo_codes()

    return render_template('index.html',
                         user=user,
                         unclaimed=unclaimed,
                         mining_rate=mining_rate,
                         user_id=user_id,
                         bot_username=BOT_USERNAME,
                         show_promo_fab=show_promo_fab,
                         show_support_button=True)

@app.route('/tasks')
def tasks():
    """Tasks page with PTS system"""
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

    for task in all_tasks:
        task_id = str(task.get('task_id', ''))

        if task_id in completed_ids_set:
            completed_tasks[task_id] = task
        else:
            available_tasks[task_id] = task

    print(f"[tasks] Disponibles: {list(available_tasks.keys())}, Completadas: {list(completed_tasks.keys())}")

    # Usar el nuevo template con sistema PTS
    return render_template('tasks_pts.html',
                         user=user,
                         available_tasks=available_tasks,
                         completed_tasks=completed_tasks,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/explore')
def explore():
    """Exploration page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    return render_template('explore.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/explore/games')
def explore_games():
    """Games hub page via explore"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    user = safe_user_dict(user)

    return render_template('games.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/explore/games/mines')
def explore_mines():
    """Mines game page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    return render_template('mines.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/explore/games/roulette')
def explore_roulette():
    """Roulette game page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    return render_template('roulette.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/explore/mining')
def explore_mining():
    """Mining page via explore"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    unclaimed = calculate_unclaimed(user)
    mining_rate = get_effective_rate(user)

    # Get mining machine status
    machine_status = None
    machine_config = None
    if MINING_MACHINE_AVAILABLE:
        try:
            machine_status = get_machine_status(user_id)
            machine_config = get_machine_config()
        except Exception as e:
            logger.warning(f"Could not get mining machine status: {e}")

    return render_template('mining.html',
                         user=user,
                         unclaimed=unclaimed,
                         mining_rate=mining_rate,
                         user_id=user_id,
                         machine_status=machine_status,
                         machine_config=machine_config,
                         show_support_button=True)

@app.route('/explore/upgrades')
def explore_upgrades():
    """Upgrades page via explore"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    return render_template('upgrades.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/explore/ads-center')
def explore_ads_center():
    """Centro de ADS - Hub for all ad platforms"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    return render_template('ads_center.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)


@app.route('/explore/watch-ads')
def explore_watch_ads():
    """Watch Ads mission page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    # Get user's watch ads progress for today
    progress = get_watch_ads_progress(user_id)

    return render_template('watch_ads.html',
                         user=user,
                         user_id=user_id,
                         progress=progress,
                         show_support_button=True)


@app.route('/explore/reward-video')
def explore_reward_video():
    """Reward Video page - Independent ad system"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    # Get user's reward video progress for today
    progress = get_reward_video_progress(user_id)

    return render_template('reward_video.html',
                         user=user,
                         user_id=user_id,
                         progress=progress,
                         show_support_button=True)


@app.route('/referidos')
def referidos():
    """Referral page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    refs = get_referrals(user_id)
    referral_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    # Calculate S-E earned from VALIDATED referrals only
    validated_refs = [r for r in refs if r.get('validated')]
    referral_bonus = float(get_config('referral_bonus', 1.0))
    total_se_earned = len(validated_refs) * referral_bonus

    config = get_config_dict()

    return render_template('referidos.html',
                         user=user,
                         referrals=refs,
                         referral_link=referral_link,
                         user_id=user_id,
                         bot_username=BOT_USERNAME,
                         total_se_earned=total_se_earned,
                         validated_count=len(validated_refs),
                         pending_count=len(refs) - len(validated_refs),
                         config=config,
                         show_support_button=True)

@app.route('/ranking')
def ranking():
    """Leaderboards page with PTS Competition System"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    user = safe_user_dict(user)

    top_users = get_top_users_by_referrals(50)

    user_rank = "N/A"
    for i, u in enumerate(top_users, 1):
        if str(u.get('user_id')) == str(user_id):
            user_rank = i
            break

    if user_rank == "N/A":
        user_referrals = user.get('referral_count', 0)
        position = 1
        all_users = get_all_users(limit=10000)
        for u in all_users:
            if u.get('referral_count', 0) > user_referrals:
                position += 1
        user_rank = position

    # Use the new competition template
    return render_template('ranking_competition.html',
                         user=user,
                         top_users=top_users,
                         user_rank=user_rank,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/wallet')
def wallet():
    """Wallet page"""
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

    se_to_usdt = float(get_config('se_to_usdt_rate', 0.01))
    se_to_doge = float(get_config('se_to_doge_rate', 0.06))

    min_usdt = float(get_config('min_withdrawal_usdt', 0.5))
    min_doge = float(get_config('min_withdrawal_doge', 0.3))

    return render_template('wallet.html',
                         user=user,
                         se_to_usdt=se_to_usdt,
                         se_to_doge=se_to_doge,
                         min_usdt=min_usdt,
                         min_doge=min_doge,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/historial')
def historial():
    """Unified transaction history page - supports all currencies"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)
    withdrawals = get_user_withdrawals(user_id)

    # Use new unified historial template
    return render_template('historial_new.html',
                         user=user,
                         withdrawals=withdrawals,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/mining')
def mining():
    """Mining page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    unclaimed = calculate_unclaimed(user)
    mining_rate = get_effective_rate(user)

    # Get mining machine status
    machine_status = None
    machine_config = None
    if MINING_MACHINE_AVAILABLE:
        try:
            machine_status = get_machine_status(user_id)
            machine_config = get_machine_config()
        except Exception as e:
            logger.warning(f"Could not get mining machine status: {e}")

    return render_template('mining.html',
                         user=user,
                         unclaimed=unclaimed,
                         mining_rate=mining_rate,
                         user_id=user_id,
                         machine_status=machine_status,
                         machine_config=machine_config,
                         show_support_button=True)

@app.route('/upgrade')
@app.route('/upgrades')
def upgrades():
    """Upgrades page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    return render_template('upgrades.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/games')
def games():
    """Games hub page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    user = safe_user_dict(user)

    return render_template('games.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)

@app.route('/promo')
def promo():
    """Promo code page"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    return render_template('promo.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)

# ============== API ROUTES ==============

@app.route('/api/channel/verify', methods=['POST'])
def api_channel_verify():
    """API to verify channel membership for all official channels"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    is_member, missing_channels = verify_all_channels_membership(user_id)

    return jsonify({
        'success': True,
        'is_member': is_member,
        'missing_channels': missing_channels
    })

@app.route('/api/claim', methods=['POST'])
def api_claim():
    """Claim mining rewards"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    unclaimed = calculate_unclaimed(user)
    if unclaimed <= 0:
        return jsonify({'success': False, 'error': 'Nothing to claim'}), 400

    # Get balance before update for logging
    balance_before = float(user.get('se_balance', 0))
    new_balance = balance_before + unclaimed
    total_mined = float(user.get('total_mined', 0) or 0) + unclaimed

    update_user(user_id,
                se_balance=new_balance,
                total_mined=total_mined,
                last_claim=datetime.now())

    # Log the mining transaction
    from database import log_balance_change
    log_balance_change(user_id, 'SE', unclaimed, 'add', 'Mining claim', balance_before, new_balance)

    return jsonify({
        'success': True,
        'claimed': unclaimed,
        'new_balance': new_balance,
        'total_mined': total_mined
    })

# ============================================
# REWARDED ADS API ENDPOINTS
# ============================================

@app.route('/api/ads/task-center/complete', methods=['POST'])
def api_ads_task_center_complete():
    """Complete a task center ad view and grant reward"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    # Get ad configuration from config table
    ad_reward = float(get_config('task_center_ad_reward') or 0.05)
    max_daily_ads = int(get_config('task_center_max_daily_ads') or 20)

    # NOTE: user_ad_stats table may not exist - using balance_history as alternative
    # For now, we'll use a simple approach without per-user ad tracking
    # This can be enhanced when user_ad_stats table is created

    ads_watched_today = 0  # Default - no tracking without user_ad_stats table

    # Try to check ad stats if table exists
    try:
        from db import get_cursor
        with get_cursor() as cursor:
            # Check if table exists first
            cursor.execute("SHOW TABLES LIKE 'user_ad_stats'")
            table_exists = cursor.fetchone()

            if table_exists:
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute(
                    """SELECT ads_watched_today, last_ad_date
                       FROM user_ad_stats WHERE user_id = %s""",
                    (user_id,)
                )
                ad_stats = cursor.fetchone()

                if ad_stats:
                    last_date = str(ad_stats.get('last_ad_date', ''))
                    if last_date == today:
                        ads_watched_today = int(ad_stats.get('ads_watched_today', 0))
    except Exception as e:
        logger.warning(f"[Ads] Could not check ad stats: {e}")
        ads_watched_today = 0

    # Check if user has reached daily limit
    if ads_watched_today >= max_daily_ads:
        return jsonify({
            'success': False,
            'error': 'Daily ad limit reached',
            'message': 'You have reached your daily ad limit. Come back tomorrow!'
        }), 400

    # Grant reward
    new_balance = float(user.get('se_balance', 0)) + ad_reward

    # Update user balance using existing update_balance function
    update_balance(user_id, 'se', ad_reward, 'add', 'Task center ad reward')

    # Try to update ad stats if table exists
    try:
        from db import get_cursor
        with get_cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'user_ad_stats'")
            if cursor.fetchone():
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute(
                    """INSERT INTO user_ad_stats (user_id, ads_watched_today, total_ads_watched, last_ad_date, total_earnings, created_at)
                       VALUES (%s, 1, 1, %s, %s, NOW())
                       ON DUPLICATE KEY UPDATE
                           ads_watched_today = IF(last_ad_date = %s, ads_watched_today + 1, 1),
                           total_ads_watched = total_ads_watched + 1,
                           total_earnings = total_earnings + %s,
                           last_ad_date = %s""",
                    (user_id, today, ad_reward, today, ad_reward, today)
                )
    except Exception as e:
        logger.warning(f"[Ads] Could not update ad stats: {e}")

    # Try to log ad completion if table exists
    try:
        from db import get_cursor
        with get_cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'ad_completions'")
            if cursor.fetchone():
                cursor.execute(
                    """INSERT INTO ad_completions (user_id, ad_type, reward, completed_at)
                       VALUES (%s, 'task_center', %s, NOW())""",
                    (user_id, ad_reward)
                )
    except Exception as e:
        logger.warning(f"[Ads] Could not log ad completion: {e}")

    logger.info(f"[Ads] User {user_id} completed task center ad, earned {ad_reward} S-E")

    # Get updated balance
    updated_user = get_user(user_id)
    new_balance = float(updated_user.get('se_balance', 0)) if updated_user else new_balance

    return jsonify({
        'success': True,
        'reward': ad_reward,
        'new_balance': new_balance,
        'ads_remaining': max_daily_ads - (ads_watched_today + 1),
        'message': f'Reward granted! +{ad_reward} S-E'
    })


@app.route('/api/ads/config', methods=['GET'])
def api_ads_config():
    """Get current ads configuration"""
    return jsonify({
        'success': True,
        'config': {
            'mining': {
                'cooldown': int(get_config('mining_ad_cooldown') or 30),
                'min_watch_time': int(get_config('mining_ad_min_watch') or 5)
            },
            'task_center': {
                'cooldown': int(get_config('task_center_ad_cooldown') or 20),
                'min_watch_time': int(get_config('task_center_ad_min_watch') or 5),
                'reward': float(get_config('task_center_ad_reward') or 0.05),
                'max_per_day': int(get_config('task_center_max_daily_ads') or 20)
            }
        }
    })

# ============================================
# WATCH ADS MISSION API ENDPOINTS
# ============================================

def get_watch_ads_progress(user_id):
    """
    Get user's watch ads progress for today.
    Returns dict with: ads_watched, total_earned, completed, last_ad_at
    Automatically resets progress when the date changes.
    """
    from db import get_cursor
    today = datetime.now().date()

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT ads_watched, total_earned, completed, last_ad_at, progress_date
                   FROM watch_ads_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            result = cursor.fetchone()

            if result:
                # Check if date changed - reset progress if needed
                progress_date = result.get('progress_date')
                if progress_date:
                    if isinstance(progress_date, str):
                        progress_date = datetime.strptime(progress_date, '%Y-%m-%d').date()
                    elif hasattr(progress_date, 'date'):
                        progress_date = progress_date.date() if callable(getattr(progress_date, 'date', None)) else progress_date

                # If progress_date is different from today, reset the counter
                if progress_date != today:
                    cursor.execute(
                        """UPDATE watch_ads_progress
                           SET ads_watched = 0, total_earned = 0, completed = 0,
                               progress_date = %s, updated_at = NOW()
                           WHERE user_id = %s""",
                        (today, str(user_id))
                    )
                    return {
                        'ads_watched': 0,
                        'total_earned': 0.0,
                        'completed': False,
                        'last_ad_at': result.get('last_ad_at')
                    }

                # Same day - return current progress
                return {
                    'ads_watched': int(result.get('ads_watched', 0)),
                    'total_earned': float(result.get('total_earned', 0)),
                    'completed': bool(result.get('completed', 0)),
                    'last_ad_at': result.get('last_ad_at')
                }

        # No record exists - return fresh progress
        return {
            'ads_watched': 0,
            'total_earned': 0.0,
            'completed': False,
            'last_ad_at': None
        }

    except Exception as e:
        logger.warning(f"[WatchAds] Error getting progress: {e}")
        return {
            'ads_watched': 0,
            'total_earned': 0.0,
            'completed': False,
            'last_ad_at': None
        }


def check_watch_ads_cooldown(user_id, cooldown_seconds=10):
    """
    Check if user can watch another ad (cooldown check).
    Returns: (can_watch, seconds_remaining)
    """
    try:
        progress = get_watch_ads_progress(user_id)
        last_ad_at = progress.get('last_ad_at')

        if not last_ad_at:
            return True, 0

        if isinstance(last_ad_at, str):
            last_ad_at = datetime.strptime(last_ad_at, '%Y-%m-%d %H:%M:%S')

        elapsed = (datetime.now() - last_ad_at).total_seconds()

        if elapsed >= cooldown_seconds:
            return True, 0

        return False, int(cooldown_seconds - elapsed)

    except Exception as e:
        logger.warning(f"[WatchAds] Error checking cooldown: {e}")
        return True, 0


@app.route('/api/watch-ads/complete', methods=['POST'])
def api_watch_ads_complete():
    """Complete a watch ad view and grant DOGE reward"""
    data = request.get_json() or {}
    user_id = data.get('user_id') or get_user_id()

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    # Configuration
    MAX_ADS = 15
    COOLDOWN_SECONDS = 60
    REWARD_PER_AD = 0.005 # DOGE

    # Get current progress
    progress = get_watch_ads_progress(user_id)

    # Check if already completed
    if progress['completed'] or progress['ads_watched'] >= MAX_ADS:
        return jsonify({
            'success': False,
            'error': 'Mission already completed',
            'completed': True,
            'ads_watched': progress['ads_watched'],
            'total_earned': progress['total_earned']
        })

    # Check cooldown
    can_watch, cooldown_remaining = check_watch_ads_cooldown(user_id, COOLDOWN_SECONDS)
    if not can_watch:
        return jsonify({
            'success': False,
            'error': 'Cooldown active',
            'cooldown_remaining': cooldown_remaining,
            'ads_watched': progress['ads_watched'],
            'total_earned': progress['total_earned']
        })

    # Update progress
    new_ads_watched = progress['ads_watched'] + 1
    new_total_earned = progress['total_earned'] + REWARD_PER_AD
    is_completed = new_ads_watched >= MAX_ADS

    try:
        from db import get_cursor
        today = datetime.now().date()

        with get_cursor() as cursor:
            # Check if record exists
            cursor.execute(
                """SELECT user_id FROM watch_ads_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing record - increment counter and set progress_date to today
                cursor.execute(
                    """UPDATE watch_ads_progress
                       SET ads_watched = ads_watched + 1,
                           total_earned = total_earned + %s,
                           completed = %s,
                           last_ad_at = NOW(),
                           progress_date = %s,
                           updated_at = NOW()
                       WHERE user_id = %s""",
                    (REWARD_PER_AD, is_completed, today, str(user_id))
                )
            else:
                # Insert new record with progress_date
                cursor.execute(
                    """INSERT INTO watch_ads_progress
                       (user_id, ads_watched, total_earned, completed, last_ad_at, progress_date, updated_at)
                       VALUES (%s, 1, %s, %s, NOW(), %s, NOW())""",
                    (str(user_id), REWARD_PER_AD, is_completed, today)
                )

        # Grant DOGE reward to user
        update_balance(user_id, 'doge', REWARD_PER_AD, 'add', 'Watch Ads mission reward')

        # Agregar PTS al ranking
        pts_reward = 5
        try:
            from onclicka_pts_system import add_pts
            add_pts(user_id, pts_reward, 'ad_watched', 'Adsgram ad')
        except Exception as pts_error:
            logger.warning(f"[WatchAds] Error adding PTS: {pts_error}")

        logger.info(f"[WatchAds] User {user_id} watched ad #{new_ads_watched}, earned {REWARD_PER_AD} DOGE +{pts_reward} PTS")

        # Get updated user balance
        updated_user = get_user(user_id)
        new_doge_balance = float(updated_user.get('doge_balance', 0)) if updated_user else 0

        return jsonify({
            'success': True,
            'reward': REWARD_PER_AD,
            'ads_watched': new_ads_watched,
            'total_earned': new_total_earned,
            'completed': is_completed,
            'cooldown': COOLDOWN_SECONDS,
            'new_doge_balance': new_doge_balance,
            'message': f'+{REWARD_PER_AD} DOGE'
        })

    except Exception as e:
        logger.error(f"[WatchAds] Error completing ad: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@app.route('/api/watch-ads/progress', methods=['GET'])
def api_watch_ads_progress():
    """Get current watch ads progress"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    progress = get_watch_ads_progress(user_id)

    return jsonify({
        'success': True,
        'progress': progress,
        'max_ads': 1,
        'reward_per_ad': 0.01,
        'total_possible_reward': 0.20
    })


# ============================================
# REWARD VIDEO ADS SYSTEM
# Sistema independiente de anuncios de video recompensado
# ============================================

import secrets
import hashlib

# Configuración de Reward Video
REWARD_VIDEO_CONFIG = {
    'max_daily_videos': 10,
    'cooldown_seconds': 200,  # 3 minutos
    'min_watch_seconds': 10,
    'reward_per_video': 0.003,  # DOG COIN
    'token_expiry_seconds': 120  # Token válido por 2 minutos
}


def get_reward_video_progress(user_id):
    """
    Obtiene el progreso de Reward Video del usuario para hoy.
    Resetea automáticamente cuando cambia la fecha.
    """
    from db import get_cursor
    today = datetime.now().date()

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT videos_watched, total_earned, completed, last_video_at, progress_date
                   FROM reward_video_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            result = cursor.fetchone()

            if result:
                progress_date = result.get('progress_date')
                if progress_date:
                    if isinstance(progress_date, str):
                        progress_date = datetime.strptime(progress_date, '%Y-%m-%d').date()
                    elif hasattr(progress_date, 'date'):
                        progress_date = progress_date.date() if callable(getattr(progress_date, 'date', None)) else progress_date

                # Si la fecha es diferente a hoy, resetear
                if progress_date != today:
                    cursor.execute(
                        """UPDATE reward_video_progress
                           SET videos_watched = 0, total_earned = 0, completed = 0,
                               progress_date = %s, session_token = NULL, updated_at = NOW()
                           WHERE user_id = %s""",
                        (today, str(user_id))
                    )
                    return {
                        'videos_watched': 0,
                        'total_earned': 0.0,
                        'completed': False,
                        'last_video_at': None
                    }

                return {
                    'videos_watched': int(result.get('videos_watched', 0)),
                    'total_earned': float(result.get('total_earned', 0)),
                    'completed': bool(result.get('completed', 0)),
                    'last_video_at': result.get('last_video_at')
                }

        return {
            'videos_watched': 0,
            'total_earned': 0.0,
            'completed': False,
            'last_video_at': None
        }

    except Exception as e:
        logger.warning(f"[RewardVideo] Error getting progress: {e}")
        return {
            'videos_watched': 0,
            'total_earned': 0.0,
            'completed': False,
            'last_video_at': None
        }


def check_reward_video_cooldown(user_id):
    """
    Verifica el cooldown de Reward Video.
    Returns: (can_watch, seconds_remaining)
    """
    try:
        progress = get_reward_video_progress(user_id)
        last_video_at = progress.get('last_video_at')

        if not last_video_at:
            return True, 0

        if isinstance(last_video_at, str):
            last_video_at = datetime.strptime(last_video_at, '%Y-%m-%d %H:%M:%S')

        elapsed = (datetime.now() - last_video_at).total_seconds()
        cooldown = REWARD_VIDEO_CONFIG['cooldown_seconds']

        if elapsed >= cooldown:
            return True, 0

        return False, int(cooldown - elapsed)

    except Exception as e:
        logger.warning(f"[RewardVideo] Error checking cooldown: {e}")
        return True, 0


def generate_session_token(user_id):
    """Genera un token único para la sesión de visualización"""
    random_bytes = secrets.token_bytes(32)
    timestamp = str(datetime.now().timestamp())
    data = f"{user_id}:{timestamp}:{random_bytes.hex()}"
    return hashlib.sha256(data.encode()).hexdigest()


def validate_session_token(user_id, token):
    """Valida que el token de sesión sea válido y no haya expirado"""
    from db import get_cursor

    try:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT session_token, token_created_at
                   FROM reward_video_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            result = cursor.fetchone()

            if not result:
                return False, "No session found"

            stored_token = result.get('session_token')
            token_created_at = result.get('token_created_at')

            if not stored_token or stored_token != token:
                return False, "Invalid token"

            if not token_created_at:
                return False, "Token timestamp missing"

            if isinstance(token_created_at, str):
                token_created_at = datetime.strptime(token_created_at, '%Y-%m-%d %H:%M:%S')

            elapsed = (datetime.now() - token_created_at).total_seconds()
            if elapsed > REWARD_VIDEO_CONFIG['token_expiry_seconds']:
                return False, "Token expired"

            return True, "Valid"

    except Exception as e:
        logger.warning(f"[RewardVideo] Error validating token: {e}")
        return False, str(e)


@app.route('/api/reward-video/status', methods=['GET'])
def api_reward_video_status():
    """Obtiene el estado actual del sistema de Reward Video para el usuario"""
    user_id = request.args.get('user_id') or get_user_id()

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    progress = get_reward_video_progress(user_id)
    can_watch, cooldown_remaining = check_reward_video_cooldown(user_id)

    config = REWARD_VIDEO_CONFIG
    videos_remaining = config['max_daily_videos'] - progress['videos_watched']

    return jsonify({
        'success': True,
        'progress': {
            'videos_watched': progress['videos_watched'],
            'total_earned': progress['total_earned'],
            'completed': progress['completed'],
            'videos_remaining': max(0, videos_remaining)
        },
        'can_watch': can_watch and not progress['completed'] and videos_remaining > 0,
        'cooldown_remaining': cooldown_remaining,
        'config': {
            'max_daily_videos': config['max_daily_videos'],
            'cooldown_seconds': config['cooldown_seconds'],
            'min_watch_seconds': config['min_watch_seconds'],
            'reward_per_video': config['reward_per_video'],
            'total_possible_reward': config['max_daily_videos'] * config['reward_per_video']
        }
    })


@app.route('/api/reward-video/start', methods=['POST'])
def api_reward_video_start():
    """
    Inicia una sesión de visualización de Reward Video.
    Genera un token único para verificar la visualización completa.
    """
    data = request.get_json() or {}
    user_id = data.get('user_id') or get_user_id()

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    config = REWARD_VIDEO_CONFIG
    progress = get_reward_video_progress(user_id)

    # Verificar límite diario
    if progress['completed'] or progress['videos_watched'] >= config['max_daily_videos']:
        return jsonify({
            'success': False,
            'error': 'Daily limit reached',
            'completed': True,
            'videos_watched': progress['videos_watched']
        })

    # Verificar cooldown
    can_watch, cooldown_remaining = check_reward_video_cooldown(user_id)
    if not can_watch:
        return jsonify({
            'success': False,
            'error': 'Cooldown active',
            'cooldown_remaining': cooldown_remaining
        })

    # Generar token de sesión
    session_token = generate_session_token(user_id)
    today = datetime.now().date()

    try:
        from db import get_cursor

        with get_cursor() as cursor:
            # Verificar si existe registro
            cursor.execute(
                "SELECT user_id FROM reward_video_progress WHERE user_id = %s",
                (str(user_id),)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """UPDATE reward_video_progress
                       SET session_token = %s, token_created_at = NOW(), updated_at = NOW()
                       WHERE user_id = %s""",
                    (session_token, str(user_id))
                )
            else:
                cursor.execute(
                    """INSERT INTO reward_video_progress
                       (user_id, videos_watched, total_earned, completed, progress_date, session_token, token_created_at)
                       VALUES (%s, 0, 0, 0, %s, %s, NOW())""",
                    (str(user_id), today, session_token)
                )

            # Registrar inicio en historial
            cursor.execute(
                """INSERT INTO reward_video_history
                   (user_id, session_token, status, ip_address, user_agent, started_at)
                   VALUES (%s, %s, 'started', %s, %s, NOW())""",
                (str(user_id), session_token, request.remote_addr, request.headers.get('User-Agent', '')[:255])
            )

        logger.info(f"[RewardVideo] Session started for user {user_id}, token: {session_token[:16]}...")

        return jsonify({
            'success': True,
            'session_token': session_token,
            'min_watch_seconds': config['min_watch_seconds'],
            'reward': config['reward_per_video']
        })

    except Exception as e:
        logger.error(f"[RewardVideo] Error starting session: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@app.route('/api/reward-video/complete', methods=['POST'])
def api_reward_video_complete():
    """
    Completa una sesión de Reward Video y otorga la recompensa.
    Requiere el token de sesión y la duración de visualización.
    """
    data = request.get_json() or {}
    user_id = data.get('user_id') or get_user_id()
    session_token = data.get('session_token')
    watch_duration = data.get('watch_duration', 0)

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    if not session_token:
        return jsonify({'success': False, 'error': 'Session token required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if user.get('banned'):
        return jsonify({'success': False, 'error': 'User banned'}), 403

    config = REWARD_VIDEO_CONFIG

    # Validar token de sesión
    is_valid, validation_msg = validate_session_token(user_id, session_token)
    if not is_valid:
        logger.warning(f"[RewardVideo] Invalid token for user {user_id}: {validation_msg}")
        return jsonify({
            'success': False,
            'error': 'Invalid or expired session',
            'detail': validation_msg
        }), 400

    # Validar duración mínima
    try:
        watch_duration = int(watch_duration)
    except (ValueError, TypeError):
        watch_duration = 0

    if watch_duration < config['min_watch_seconds']:
        logger.warning(f"[RewardVideo] Insufficient watch time for user {user_id}: {watch_duration}s < {config['min_watch_seconds']}s")

        # Actualizar historial como fallido
        try:
            from db import get_cursor
            with get_cursor() as cursor:
                cursor.execute(
                    """UPDATE reward_video_history
                       SET status = 'failed', watch_duration = %s, completed_at = NOW()
                       WHERE session_token = %s AND user_id = %s""",
                    (watch_duration, session_token, str(user_id))
                )
        except:
            pass

        return jsonify({
            'success': False,
            'error': 'Video not watched completely',
            'watch_duration': watch_duration,
            'required_duration': config['min_watch_seconds']
        })

    # Obtener progreso actual
    progress = get_reward_video_progress(user_id)

    # Verificar límite nuevamente (prevención de race conditions)
    if progress['completed'] or progress['videos_watched'] >= config['max_daily_videos']:
        return jsonify({
            'success': False,
            'error': 'Daily limit reached',
            'completed': True
        })

    # Otorgar recompensa
    reward = config['reward_per_video']
    new_videos_watched = progress['videos_watched'] + 1
    new_total_earned = progress['total_earned'] + reward
    is_completed = new_videos_watched >= config['max_daily_videos']
    today = datetime.now().date()

    try:
        from db import get_cursor

        with get_cursor() as cursor:
            # Actualizar progreso e invalidar token
            cursor.execute(
                """UPDATE reward_video_progress
                   SET videos_watched = videos_watched + 1,
                       total_earned = total_earned + %s,
                       completed = %s,
                       last_video_at = NOW(),
                       progress_date = %s,
                       session_token = NULL,
                       token_created_at = NULL,
                       updated_at = NOW()
                   WHERE user_id = %s AND session_token = %s""",
                (reward, is_completed, today, str(user_id), session_token)
            )

            if cursor.rowcount == 0:
                return jsonify({
                    'success': False,
                    'error': 'Session already completed or invalid'
                }), 400

            # Actualizar historial
            cursor.execute(
                """UPDATE reward_video_history
                   SET status = 'completed', watch_duration = %s, reward_amount = %s, completed_at = NOW()
                   WHERE session_token = %s AND user_id = %s""",
                (watch_duration, reward, session_token, str(user_id))
            )

        # Otorgar DOGE al usuario
        update_balance(user_id, 'doge', reward, 'add', 'Reward Video ad reward')

        logger.info(f"[RewardVideo] User {user_id} completed video #{new_videos_watched}, earned {reward} DOGE")

        # Obtener balance actualizado
        updated_user = get_user(user_id)
        new_doge_balance = float(updated_user.get('doge_balance', 0)) if updated_user else 0

        return jsonify({
            'success': True,
            'reward': reward,
            'videos_watched': new_videos_watched,
            'total_earned': new_total_earned,
            'completed': is_completed,
            'videos_remaining': max(0, config['max_daily_videos'] - new_videos_watched),
            'cooldown': config['cooldown_seconds'],
            'new_doge_balance': new_doge_balance,
            'message': f'+{reward} DOGE'
        })

    except Exception as e:
        logger.error(f"[RewardVideo] Error completing video: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


@app.route('/api/reward-video/cancel', methods=['POST'])
def api_reward_video_cancel():
    """Cancela una sesión de Reward Video (usuario cerró el anuncio)"""
    data = request.get_json() or {}
    user_id = data.get('user_id') or get_user_id()
    session_token = data.get('session_token')
    watch_duration = data.get('watch_duration', 0)

    if not user_id or not session_token:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    try:
        from db import get_cursor

        with get_cursor() as cursor:
            # Invalidar token
            cursor.execute(
                """UPDATE reward_video_progress
                   SET session_token = NULL, token_created_at = NULL
                   WHERE user_id = %s AND session_token = %s""",
                (str(user_id), session_token)
            )

            # Actualizar historial
            cursor.execute(
                """UPDATE reward_video_history
                   SET status = 'skipped', watch_duration = %s, completed_at = NOW()
                   WHERE session_token = %s AND user_id = %s""",
                (watch_duration, session_token, str(user_id))
            )

        logger.info(f"[RewardVideo] Session cancelled for user {user_id}")

        return jsonify({
            'success': True,
            'message': 'Session cancelled'
        })

    except Exception as e:
        logger.error(f"[RewardVideo] Error cancelling session: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500


# ============================================
# TELEGA.IO AD REWARD CALLBACK ENDPOINT
# Este endpoint es llamado por Telega.io cuando un usuario
# completa la visualización de un anuncio con recompensa
# IMPORTANTE: Este es el ÚNICO lugar donde se otorgan recompensas
# ============================================

@app.route('/ad_reward', methods=['POST', 'GET'])
def telega_ad_reward_callback():
    """
    Telega.io Rewarded Ads Callback

    Este endpoint es llamado por Telega.io cuando un usuario completa
    la visualización de un anuncio con recompensa.

    Telega.io puede enviar los siguientes parámetros (varios formatos):
    - user_id / userId / user: ID del usuario que vio el anuncio
    - block_id / blockId / adBlockUuid: ID del bloque de anuncio
    - reward: Cantidad de recompensa (opcional)

    SIEMPRE responde 200 OK para confirmar recepción a Telega.io
    """
    try:
        # Log completo de la request para debugging
        logger.info(f"[Telega.io] === CALLBACK RECEIVED ===")
        logger.info(f"[Telega.io] Method: {request.method}")
        logger.info(f"[Telega.io] URL: {request.url}")
        logger.info(f"[Telega.io] Args: {dict(request.args)}")
        logger.info(f"[Telega.io] Headers: {dict(request.headers)}")

        user_id = None
        block_id = None

        # Telega.io puede enviar datos como GET params, POST JSON, o form data
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            logger.info(f"[Telega.io] POST JSON data: {data}")
            logger.info(f"[Telega.io] POST form data: {dict(request.form)}")

            # Intentar múltiples nombres de parámetros
            user_id = (data.get('user_id') or data.get('userId') or data.get('user') or
                      request.form.get('user_id') or request.form.get('userId') or request.form.get('user'))
            block_id = (data.get('block_id') or data.get('blockId') or data.get('adBlockUuid') or
                       request.form.get('block_id') or request.form.get('blockId') or request.form.get('adBlockUuid'))
        else:
            # GET request - intentar múltiples nombres de parámetros
            user_id = request.args.get('user_id') or request.args.get('userId') or request.args.get('user')
            block_id = request.args.get('block_id') or request.args.get('blockId') or request.args.get('adBlockUuid')

        logger.info(f"[Telega.io] Parsed - user_id: {user_id}, block_id: {block_id}")

        if not user_id:
            logger.warning("[Telega.io] No user_id in callback - cannot grant reward")
            return jsonify({'status': 'ok', 'message': 'no user_id'}), 200

        # Verificar que el block_id sea el correcto (opcional pero recomendado)
        expected_block_id = "3a1b92a1-f630-4632-a0c3-992a3a3790a2"
        if block_id and block_id != expected_block_id:
            logger.warning(f"[Telega.io] Unexpected block_id: {block_id} (expected: {expected_block_id})")

        # Obtener configuración de recompensa
        reward_amount = float(get_config('telega_reward_amount') or 0.003)
        max_daily_videos = int(get_config('telega_max_daily_videos') or 10)
        cooldown_seconds = int(get_config('telega_cooldown_seconds') or 180)

        today = datetime.now().strftime('%Y-%m-%d')

        from db import get_cursor

        with get_cursor() as cursor:
            # Verificar si el usuario existe y no está baneado
            # NOTA: La columna es user_id, no telegram_id; y banned, no is_banned
            cursor.execute(
                "SELECT user_id, se_balance, banned FROM users WHERE user_id = %s",
                (str(user_id),)
            )
            user = cursor.fetchone()

            if not user:
                logger.warning(f"[Telega.io] User {user_id} not found")
                return jsonify({'status': 'ok', 'message': 'user not found'}), 200

            if user.get('banned'):
                logger.warning(f"[Telega.io] User {user_id} is banned")
                return jsonify({'status': 'ok', 'message': 'user banned'}), 200

            # Obtener o crear progreso del usuario
            # IMPORTANTE: Usar las columnas correctas (progress_date, last_video_at)
            cursor.execute(
                """SELECT videos_watched, total_earned, progress_date, last_video_at
                   FROM reward_video_progress WHERE user_id = %s""",
                (str(user_id),)
            )
            progress = cursor.fetchone()

            videos_today = 0
            total_earned = 0.0

            if progress:
                progress_date = progress.get('progress_date', '')
                # Manejar diferentes formatos de fecha
                if progress_date:
                    if hasattr(progress_date, 'strftime'):
                        progress_date_str = progress_date.strftime('%Y-%m-%d')
                    else:
                        progress_date_str = str(progress_date)
                else:
                    progress_date_str = ''

                if progress_date_str == today:
                    videos_today = int(progress.get('videos_watched', 0))
                    total_earned = float(progress.get('total_earned', 0))

                    # Verificar cooldown
                    last_video_at = progress.get('last_video_at')
                    if last_video_at:
                        elapsed = (datetime.now() - last_video_at).total_seconds()
                        if elapsed < cooldown_seconds:
                            logger.info(f"[Telega.io] User {user_id} in cooldown ({elapsed}s < {cooldown_seconds}s)")
                            return jsonify({'status': 'ok', 'message': 'cooldown active'}), 200

            # Verificar límite diario
            if videos_today >= max_daily_videos:
                logger.info(f"[Telega.io] User {user_id} reached daily limit ({videos_today}/{max_daily_videos})")
                return jsonify({'status': 'ok', 'message': 'daily limit reached'}), 200

            # ¡OTORGAR RECOMPENSA!
            new_videos_count = videos_today + 1
            new_total_earned = total_earned + reward_amount
            new_balance = float(user.get('se_balance', 0)) + reward_amount

            # Actualizar balance del usuario
            cursor.execute(
                "UPDATE users SET se_balance = %s WHERE user_id = %s",
                (new_balance, str(user_id))
            )

            # Actualizar progreso - USAR COLUMNAS CORRECTAS (progress_date, last_video_at)
            if progress:
                cursor.execute(
                    """UPDATE reward_video_progress
                       SET videos_watched = %s, total_earned = %s,
                           progress_date = %s, last_video_at = NOW(), updated_at = NOW()
                       WHERE user_id = %s""",
                    (new_videos_count, new_total_earned, today, str(user_id))
                )
            else:
                cursor.execute(
                    """INSERT INTO reward_video_progress
                       (user_id, videos_watched, total_earned, progress_date, last_video_at, updated_at)
                       VALUES (%s, %s, %s, %s, NOW(), NOW())""",
                    (str(user_id), new_videos_count, new_total_earned, today)
                )

            # Registrar en historial
            try:
                cursor.execute(
                    """INSERT INTO reward_video_history
                       (user_id, status, reward_amount, ip_address, user_agent, completed_at)
                       VALUES (%s, 'completed', %s, %s, %s, NOW())""",
                    (str(user_id), reward_amount, request.remote_addr, 'Telega.io Callback')
                )
            except Exception as hist_err:
                logger.warning(f"[Telega.io] Could not log to history: {hist_err}")

            # Actualizar balance_history si existe
            try:
                cursor.execute(
                    """INSERT INTO balance_history
                       (user_id, amount, type, description, created_at)
                       VALUES (%s, %s, 'credit', 'Telega.io Rewarded Ad', NOW())""",
                    (str(user_id), reward_amount)
                )
            except Exception:
                pass  # La tabla puede no existir

        logger.info(f"[Telega.io] ✅ Reward granted to user {user_id}: +{reward_amount} DOGE (Total: {new_total_earned})")

        return jsonify({
            'status': 'ok',
            'message': 'reward granted',
            'reward': reward_amount,
            'total_earned': new_total_earned,
            'videos_today': new_videos_count
        }), 200

    except Exception as e:
        logger.error(f"[Telega.io] Error processing callback: {e}")
        # Siempre responder 200 OK para evitar reintentos
        return jsonify({'status': 'ok', 'error': str(e)}), 200


@app.route('/api/ads/stats', methods=['GET'])
def api_ads_stats():
    """Get user's ad statistics"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    today = datetime.now().strftime('%Y-%m-%d')
    max_daily_ads = int(get_config('task_center_max_daily_ads') or 20)

    # Try to get ad stats if table exists
    ads_today = 0
    total_ads = 0
    total_earnings = 0

    try:
        from db import get_cursor
        with get_cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'user_ad_stats'")
            if cursor.fetchone():
                cursor.execute(
                    """SELECT ads_watched_today, total_ads_watched, total_earnings, last_ad_date
                       FROM user_ad_stats WHERE user_id = %s""",
                    (user_id,)
                )
                ad_stats = cursor.fetchone()

                if ad_stats:
                    last_date = str(ad_stats.get('last_ad_date', ''))
                    if last_date == today:
                        ads_today = int(ad_stats.get('ads_watched_today', 0))
                    total_ads = int(ad_stats.get('total_ads_watched', 0))
                    total_earnings = float(ad_stats.get('total_earnings', 0))
    except Exception as e:
        logger.warning(f"[Ads] Could not get ad stats: {e}")

    return jsonify({
        'success': True,
        'stats': {
            'ads_watched_today': ads_today,
            'ads_remaining_today': max_daily_ads - ads_today,
            'total_ads_watched': total_ads,
            'total_earnings': total_earnings
        }
    })

@app.route('/api/task/complete', methods=['POST'])
def api_task_complete():
    """
    Complete a task - FIXED with referral validation on first task.
    """
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

    task = get_task(task_id)
    if not task:
        print(f"[api_task_complete] ❌ Tarea {task_id} no encontrada")
        return jsonify({'success': False, 'error': 'Tarea no encontrada'}), 400

    if is_task_completed(user_id, task_id):
        print(f"[api_task_complete] ❌ Tarea {task_id} ya completada por usuario {user_id}")
        return jsonify({'success': False, 'error': 'Ya completaste esta tarea'}), 400

    reward = float(task.get('reward', 0))

    # ====== VERIFICACIÓN DE MEMBRESÍA EN CANAL DE TELEGRAM ======
    requires_channel = task.get('requires_channel_join', False)
    channel_username = task.get('channel_username', '')

    print(f"[api_task_complete] Tarea requiere canal: {requires_channel}, Canal: {channel_username}")

    if requires_channel and channel_username:
        print(f"[api_task_complete] Verificando membresía del usuario {user_id} en canal {channel_username}")

        is_member, verification_message = verify_channel_membership(user_id, channel_username)

        if not is_member:
            print(f"[api_task_complete] ❌ Usuario {user_id} NO es miembro del canal {channel_username}")
            return jsonify({
                'success': False,
                'error': f'Debes unirte al canal @{channel_username} primero',
                'message': f'Debes unirte al canal @{channel_username} primero',
                'requires_join': True,
                'channel': f'@{channel_username}'
            }), 400

        print(f"[api_task_complete] ✅ Usuario {user_id} ES miembro del canal {channel_username}")
    # ====== FIN DE VERIFICACIÓN ======

    # Completar la tarea y dar la recompensa
    # This function now also handles referral validation on first task
    success, message = complete_task(user_id, task_id)
    print(f"[api_task_complete] Resultado: success={success}, message={message}")

    if success:
        user = get_user(user_id)
        new_balance = user.get('se_balance', 0) if user else 0
        completed_count = len(user.get('completed_tasks', [])) if user else 0
        print(f"[api_task_complete] ✅ Tarea completada. Nuevo balance: {new_balance}, Total completadas: {completed_count}")
        return jsonify({
            'success': True,
            'message': message,
            'reward': reward,
            'new_balance': new_balance,
            'completed_count': completed_count
        })

    print(f"[api_task_complete] ❌ Error: {message}")
    return jsonify({'success': False, 'error': message, 'message': message}), 400

@app.route('/api/task/verify', methods=['POST'])
def api_task_verify():
    """Verify Telegram channel membership"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    data = request.get_json() or {}
    task_id = data.get('task_id')
    channel_username = data.get('channel_username')

    if task_id and not channel_username:
        task = get_task(task_id)
        if task:
            channel_username = task.get('channel_username')

    if not channel_username:
        return jsonify({'success': False, 'error': 'Canal no especificado'}), 400

    is_member, message = verify_channel_membership(user_id, channel_username)

    return jsonify({
        'success': is_member,
        'verified': is_member,
        'message': message,
        'channel': channel_username
    })

@app.route('/api/promo/redeem', methods=['POST'])
def api_promo_redeem():
    """Redeem promo code"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    data = request.get_json() or {}
    code = data.get('code', '').strip()

    if not code:
        return jsonify({'success': False, 'error': 'Code required'}), 400

    success, message = redeem_promo_code(user_id, code)

    if success:
        user = get_user(user_id)
        return jsonify({
            'success': True,
            'message': message,
            'new_balance': float(user.get('se_balance', 0)) if user else 0
        })

    return jsonify({'success': False, 'error': message, 'message': message}), 400

@app.route('/api/swap', methods=['POST'])
def api_swap():
    """Swap S-E to USDT, DOGE or TON"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    data = request.get_json() or {}
    amount = float(data.get('amount', 0))
    to_currency = data.get('to_currency', '').upper()

    if amount <= 0:
        return jsonify({'success': False, 'error': 'Invalid amount'}), 400

    if to_currency not in ['USDT', 'DOGE', 'TON']:
        return jsonify({'success': False, 'error': 'Invalid currency'}), 400

    se_balance = float(user.get('se_balance', 0))
    if amount > se_balance:
        return jsonify({'success': False, 'error': 'Insufficient S-E balance'}), 400

    if to_currency == 'USDT':
        rate = float(get_config('se_to_usdt_rate', 0.01))
    elif to_currency == 'DOGE':
        rate = float(get_config('se_to_doge_rate', 0.06))
    else:  # TON
        rate = float(get_config('se_to_ton_rate', 0.005))

    received = round(amount * rate, 6)

    update_balance(user_id, 'se', amount, 'subtract', f'Swap: {amount} S-E to {to_currency}')
    update_balance(user_id, to_currency.lower(), received, 'add', f'Swap: Received {received} {to_currency}')

    user = get_user(user_id)

    return jsonify({
        'success': True,
        'swapped': amount,
        'received': received,
        'new_se_balance': float(user.get('se_balance', 0)),
        'new_usdt_balance': float(user.get('usdt_balance', 0)),
        'new_doge_balance': float(user.get('doge_balance', 0)),
        'new_ton_balance': float(user.get('ton_balance', 0))
    })

@app.route('/api/withdraw', methods=['POST'])
def api_withdraw():
    """Create withdrawal request"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    data = request.get_json() or {}
    currency = data.get('currency', '').upper()
    amount = float(data.get('amount', 0))
    wallet_address = data.get('wallet_address', '').strip()

    if currency not in ['USDT', 'DOGE']:
        return jsonify({'success': False, 'error': 'Invalid currency'}), 400

    if not wallet_address:
        return jsonify({'success': False, 'error': 'Wallet address required'}), 400

    balance_key = 'usdt_balance' if currency == 'USDT' else 'doge_balance'
    balance = float(user.get(balance_key, 0))

    if amount > balance:
        return jsonify({'success': False, 'error': 'Insufficient balance'}), 400

    min_key = f'min_withdrawal_{currency.lower()}'
    min_amount = float(get_config(min_key, 0.5))

    if amount < min_amount:
        return jsonify({'success': False, 'error': f'Minimum withdrawal is {min_amount} {currency}'}), 400

    update_balance(user_id, currency.lower(), amount, 'subtract', f'Withdrawal: {amount} {currency} to {wallet_address[:10]}...')

    withdrawal_id = create_withdrawal(user_id, currency, amount, wallet_address)

    increment_stat('total_withdrawals')

    # Send notification about new withdrawal
    if WITHDRAWAL_NOTIFICATIONS_AVAILABLE:
        try:
            on_withdrawal_created(
                withdrawal_id=withdrawal_id,
                user_id=user_id,
                currency=currency,
                amount=amount,
                wallet_address=wallet_address
            )
        except Exception as e:
            logger.error(f"Error sending withdrawal creation notification: {e}")

    return jsonify({
        'success': True,
        'withdrawal_id': withdrawal_id,
        'amount': amount,
        'currency': currency
    })

@app.route('/api/referrals', methods=['GET'])
def api_referrals():
    """Get user referrals"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    refs = get_referrals(user_id)
    validated_count = sum(1 for r in refs if r.get('validated'))
    pending_count = len(refs) - validated_count

    return jsonify({
        'success': True,
        'referrals': refs,
        'total': len(refs),
        'validated': validated_count,
        'pending': pending_count
    })

@app.route('/api/set-language', methods=['POST'])
def api_set_language():
    """Save user's preferred language"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    data = request.get_json() or {}
    lang = data.get('language', 'es')

    # Validate language
    valid_langs = ['en', 'es', 'pt', 'ru', 'ar']
    if lang not in valid_langs:
        lang = 'es'

    # Update user language in database
    try:
        update_user(user_id, language_code=lang)
        return jsonify({'success': True, 'language': lang})
    except Exception as e:
        logger.error(f"Error saving language: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/referrals/list', methods=['GET'])
def api_referrals_list():
    """Get user referrals list with detailed info and pagination - for frontend"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    # Obtener parámetros de paginación
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)

    # Limitar per_page a un máximo razonable
    per_page = min(per_page, 50)
    page = max(page, 1)

    # Obtener conteos totales (eficiente, sin cargar todos los datos)
    validated_count, pending_count, total_refs = get_referrals_counts(user_id)

    # Obtener referidos paginados
    paginated_data = get_referrals_paginated(user_id, page, per_page)

    # Calculate total SE earned from validated referrals only
    referral_bonus = float(get_config('referral_bonus', 1.0))
    total_se_earned = validated_count * referral_bonus

    # Format referrals for frontend
    formatted_refs = []
    for ref in paginated_data['referrals']:
        formatted_refs.append({
            'referred_id': ref.get('referred_id'),
            'username': ref.get('username') or ref.get('referred_username'),
            'first_name': ref.get('first_name') or ref.get('referred_first_name', 'Usuario'),
            'full_name': ref.get('first_name') or ref.get('referred_first_name', ''),
            'validated': bool(ref.get('validated')),
            'bonus_paid': float(ref.get('bonus_paid') or 0),
            'joined_at': str(ref.get('created_at', '')),
            'validated_at': str(ref.get('validated_at', '')) if ref.get('validated_at') else None
        })

    return jsonify({
        'success': True,
        'referrals': formatted_refs,
        'total_referrals': total_refs,
        'validated_count': validated_count,
        'pending_count': pending_count,
        'total_se_earned': total_se_earned,
        'total_commission': 0,  # TODO: Calculate from mining activity
        # Datos de paginación
        'page': page,
        'per_page': per_page,
        'has_more': paginated_data['has_more'],
        'total_pages': (total_refs + per_page - 1) // per_page if per_page > 0 else 1
    })

@app.route('/api/user', methods=['GET'])
def api_user():
    """Get user data"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    user = safe_user_dict(user)

    return jsonify({
        'success': True,
        'user': user
    })

@app.route('/api/sync-telegram-data', methods=['POST'])
def api_sync_telegram():
    """Sync user data from Telegram - MEJORADO con throttling de 2 horas"""
    data = request.get_json() or {}
    user_id = data.get('user_id') or data.get('userId')
    username = data.get('username')
    first_name = data.get('first_name') or data.get('firstName') or 'Usuario'
    last_name = data.get('last_name') or data.get('lastName')
    init_data = data.get('init_data')

    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user_id = str(user_id)

    try:
        user = get_user(user_id)
        if user:
            # THROTTLING: Solo actualizar cada 2 horas
            should_update = False
            last_updated = user.get('updated_at')

            if last_updated:
                if isinstance(last_updated, str):
                    try:
                        last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    except:
                        last_updated = None

                if last_updated:
                    hours_since_update = (datetime.now() - last_updated).total_seconds() / 3600
                    should_update = hours_since_update >= 2
                else:
                    should_update = True
            else:
                should_update = True

            if should_update:
                update_user(user_id,
                           username=username if username else user.get('username'),
                           first_name=first_name if first_name else user.get('first_name'))
                return jsonify({
                    'success': True,
                    'message': 'User updated',
                    'user_id': user_id,
                    'is_new': False
                })
            else:
                # No actualizar, pero confirmar que existe
                return jsonify({
                    'success': True,
                    'message': 'User exists (no update needed)',
                    'user_id': user_id,
                    'is_new': False
                })
        else:
            new_user = create_user(user_id, username=username, first_name=first_name)
            if new_user:
                return jsonify({
                    'success': True,
                    'message': 'User created',
                    'user_id': user_id,
                    'is_new': True
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create user'
                }), 500
    except Exception as e:
        print(f"Error in sync-telegram-data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============== USER LANGUAGE API ==============

@app.route('/api/user/language', methods=['GET', 'POST'])
def api_user_language():
    """
    GET: Obtener el idioma del usuario
    POST: Cambiar el idioma del usuario
    """
    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({'success': False, 'error': 'user_id required'}), 400

    try:
        if request.method == 'GET':
            # Obtener idioma del usuario
            cursor.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()

            if result:
                lang = result.get('language', 'es') or 'es'
                return jsonify({'success': True, 'language': lang})
            else:
                return jsonify({'success': True, 'language': 'es'})

        elif request.method == 'POST':
            # Cambiar idioma del usuario
            data = request.get_json() or {}
            new_lang = data.get('language', 'es')

            # Validar idioma
            valid_langs = ['en', 'es', 'pt', 'ru', 'ar']
            if new_lang not in valid_langs:
                new_lang = 'es'

            # Actualizar en la base de datos
            cursor.execute(
                "UPDATE users SET language = %s WHERE user_id = %s",
                (new_lang, user_id)
            )
            conn.commit()

            return jsonify({
                'success': True,
                'language': new_lang,
                'message': 'Language updated'
            })

    except Exception as e:
        print(f"Error in user language API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============== USER PROFILE PHOTO API ==============

@app.route('/api/user-photo/<user_id>')
def api_user_photo(user_id):
    """
    Obtener la URL de la foto de perfil del usuario de Telegram.
    Devuelve la URL de la foto o una URL vacía si no tiene foto.
    """
    if not BOT_TOKEN:
        return jsonify({'success': False, 'error': 'Bot token not configured', 'photo_url': None})

    try:
        # Obtener las fotos de perfil del usuario
        photos_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUserProfilePhotos"
        photos_response = requests.get(photos_url, params={
            'user_id': user_id,
            'limit': 1
        }, timeout=10)

        photos_data = photos_response.json()

        if not photos_data.get('ok') or not photos_data.get('result', {}).get('photos'):
            return jsonify({
                'success': True,
                'photo_url': None,
                'message': 'No profile photo'
            })

        # Obtener el file_id de la foto más pequeña (primera en la lista)
        photos = photos_data['result']['photos']
        if not photos or not photos[0]:
            return jsonify({
                'success': True,
                'photo_url': None,
                'message': 'No profile photo'
            })

        # Usar la foto de tamaño medio para mejor calidad sin ser muy pesada
        photo_sizes = photos[0]
        # Elegir tamaño medio si hay más de 2 opciones
        photo_index = min(1, len(photo_sizes) - 1)
        file_id = photo_sizes[photo_index]['file_id']

        # Obtener la ruta del archivo
        file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
        file_response = requests.get(file_url, params={
            'file_id': file_id
        }, timeout=10)

        file_data = file_response.json()

        if not file_data.get('ok'):
            return jsonify({
                'success': True,
                'photo_url': None,
                'message': 'Could not get file path'
            })

        file_path = file_data['result']['file_path']

        # Construir la URL completa de la foto
        photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        return jsonify({
            'success': True,
            'photo_url': photo_url
        })

    except requests.Timeout:
        return jsonify({
            'success': False,
            'error': 'Timeout getting photo',
            'photo_url': None
        })
    except Exception as e:
        logger.error(f"Error getting user photo for {user_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'photo_url': None
        })


# ============== WALLET API ROUTES ==============

@app.route('/api/wallet/balance/<user_id>')
def api_wallet_balance(user_id):
    """Get wallet balances"""
    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    return jsonify({
        'success': True,
        'se_balance': user.get('se_balance', 0),
        'usdt_balance': user.get('usdt_balance', 0),
        'doge_balance': user.get('doge_balance', 0),
        'ton_balance': user.get('ton_balance', 0),
        'wallet_address': user.get('wallet_address'),
        'ton_wallet_address': user.get('ton_wallet_address')
    })

@app.route('/api/wallet/withdraw', methods=['POST'])
def api_wallet_withdraw():
    """Request withdrawal - uses linked wallet address automatically"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    data = request.get_json() or {}
    currency = data.get('currency', '').upper()
    amount = data.get('amount', 0)

    # Validar moneda
    if currency not in ['USDT', 'DOGE', 'TON']:
        return jsonify({'success': False, 'error': 'Invalid currency. Use USDT, DOGE or TON'}), 400

    # Validar monto
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid amount'}), 400

    if WALLET_AVAILABLE:
        # Usar la dirección vinculada automáticamente (no pasamos wallet_address)
        success, result = create_withdrawal_request(user_id, currency, amount)
        if success:
            withdrawal_id = result

            # Send notification about new withdrawal
            if WITHDRAWAL_NOTIFICATIONS_AVAILABLE:
                try:
                    withdrawal = get_withdrawal(withdrawal_id)
                    if withdrawal:
                        on_withdrawal_created(
                            withdrawal_id=withdrawal_id,
                            user_id=user_id,
                            currency=currency,
                            amount=amount,
                            wallet_address=withdrawal.get('wallet_address', '')
                        )
                except Exception as e:
                    logger.error(f"Error sending withdrawal creation notification: {e}")

            # Intentar procesar automáticamente
            auto_result = {'processed': False, 'auto_success': False, 'auto_message': 'Manual mode'}
            if AUTO_PAY_AVAILABLE:
                try:
                    processed, auto_success, message = process_withdrawal_if_auto(withdrawal_id)
                    auto_result = {'processed': processed, 'auto_success': auto_success, 'auto_message': message}

                    # If auto processed successfully, send completion notification
                    if auto_success and WITHDRAWAL_NOTIFICATIONS_AVAILABLE:
                        try:
                            withdrawal = get_withdrawal(withdrawal_id)
                            if withdrawal:
                                on_withdrawal_completed(
                                    withdrawal_id=withdrawal_id,
                                    user_id=user_id,
                                    currency=currency,
                                    amount=amount,
                                    wallet_address=withdrawal.get('wallet_address', ''),
                                    tx_hash=withdrawal.get('tx_hash', '')
                                )
                        except Exception as e:
                            logger.error(f"Error sending auto-completion notification: {e}")
                except Exception as e:
                    logger.error(f"Error in auto payment: {e}")

            response_msg = 'Withdrawal processed automatically!' if auto_result['auto_success'] else 'Withdrawal request created'
            return jsonify({
                'success': True,
                'withdrawal_id': withdrawal_id,
                'message': response_msg,
                'auto_processed': auto_result['processed'],
                'auto_success': auto_result['auto_success']
            })
        return jsonify({'success': False, 'error': result}), 400

    # Fallback sin módulo wallet
    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Obtener dirección según moneda
    if currency == 'TON':
        wallet_address = user.get('ton_wallet_address')
        if not wallet_address:
            return jsonify({'success': False, 'error': 'Please link your TON wallet address first'}), 400
    else:
        wallet_address = user.get('wallet_address')
        if not wallet_address:
            return jsonify({'success': False, 'error': 'Please link your wallet address first'}), 400

    # Mapeo de balances
    balance_map = {
        'USDT': 'usdt_balance',
        'DOGE': 'doge_balance',
        'TON': 'ton_balance'
    }

    balance_key = balance_map.get(currency)
    balance = float(user.get(balance_key, 0))

    if amount > balance:
        return jsonify({'success': False, 'error': 'Insufficient balance'}), 400

    min_key = f'min_withdrawal_{currency.lower()}'
    min_amount = float(get_config(min_key, 0.5 if currency != 'TON' else 0.1))

    if amount < min_amount:
        return jsonify({'success': False, 'error': f'Minimum withdrawal is {min_amount} {currency}'}), 400

    update_balance(user_id, currency.lower(), amount, 'subtract', f'Withdrawal: {amount} {currency} to {wallet_address[:10]}...')
    withdrawal_id = create_withdrawal(user_id, currency, amount, wallet_address)

    # Intentar procesar automáticamente si el modo está activado
    auto_result = {
        'processed': False,
        'auto_success': False,
        'auto_message': 'Manual mode - pending approval'
    }

    if AUTO_PAY_AVAILABLE:
        try:
            processed, success, message = process_withdrawal_if_auto(withdrawal_id)
            auto_result = {
                'processed': processed,
                'auto_success': success,
                'auto_message': message
            }
        except Exception as e:
            logger.error(f"Error in auto payment: {e}")
            auto_result['auto_message'] = f"Auto-pay error: {str(e)}"

    response_message = 'Withdrawal request created'
    if auto_result['processed']:
        if auto_result['auto_success']:
            response_message = 'Withdrawal processed automatically!'
        else:
            response_message = f"Withdrawal created (auto-pay failed: {auto_result['auto_message']})"

    return jsonify({
        'success': True,
        'withdrawal_id': withdrawal_id,
        'message': response_message,
        'auto_processed': auto_result['processed'],
        'auto_success': auto_result['auto_success']
    })

@app.route('/api/wallet/link', methods=['POST'])
def api_wallet_link():
    """Link wallet address (BEP20 or TON)"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    data = request.get_json() or {}
    wallet_address = data.get('wallet_address', '').strip()
    wallet_type = data.get('wallet_type', 'bep20').lower()  # 'bep20' or 'ton'

    if not wallet_address:
        return jsonify({'success': False, 'error': 'Wallet address required'}), 400

    if WALLET_AVAILABLE:
        success, message = link_wallet_address(user_id, wallet_address, wallet_type)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400

    # Fallback without wallet module
    is_valid = False

    if wallet_type == 'ton':
        # Validar dirección TON
        if wallet_address.startswith(('EQ', 'UQ', 'Ef', 'Uf', 'kQ', 'kf', '0Q', '0f')) and len(wallet_address) == 48:
            is_valid = True
        elif ':' in wallet_address:  # Raw format
            parts = wallet_address.split(':')
            if len(parts) == 2 and parts[0] in ['0', '-1'] and len(parts[1]) == 64:
                is_valid = True

        if is_valid:
            update_user(user_id, ton_wallet_address=wallet_address)
            return jsonify({'success': True, 'message': 'TON wallet linked successfully'})
        return jsonify({'success': False, 'error': 'Invalid TON address format'}), 400

    else:  # BEP20
        # ERC20/BEP20 addresses (0x...)
        if wallet_address.startswith('0x') and len(wallet_address) == 42:
            is_valid = True
        # TRC20 addresses (T...)
        elif wallet_address.startswith('T') and len(wallet_address) == 34:
            is_valid = True
        # Allow other formats for flexibility
        elif len(wallet_address) >= 20:
            is_valid = True

        if is_valid:
            update_user(user_id, wallet_address=wallet_address)
            return jsonify({'success': True, 'message': 'Wallet linked successfully'})

    return jsonify({'success': False, 'error': 'Invalid address format'}), 400

@app.route('/api/wallet/history/<user_id>')
def api_wallet_history(user_id):
    """Get withdrawal history"""
    withdrawals = get_user_withdrawals(user_id)
    return jsonify({
        'success': True,
        'withdrawals': withdrawals
    })

@app.route('/api/wallet/stats/<user_id>')
def api_wallet_stats(user_id):
    """Get withdrawal statistics"""
    if WALLET_AVAILABLE:
        stats = get_withdrawal_stats(user_id)
        return jsonify({'success': True, 'stats': stats})

    # Fallback
    withdrawals = get_user_withdrawals(user_id)
    total_usdt = sum(float(w['amount']) for w in withdrawals if w['currency'] == 'USDT' and w['status'] == 'completed')
    total_doge = sum(float(w['amount']) for w in withdrawals if w['currency'] == 'DOGE' and w['status'] == 'completed')
    total_ton = sum(float(w['amount']) for w in withdrawals if w['currency'] == 'TON' and w['status'] == 'completed')

    return jsonify({
        'success': True,
        'stats': {
            'total_usdt': total_usdt,
            'total_doge': total_doge,
            'total_ton': total_ton,
            'pending_count': len([w for w in withdrawals if w['status'] == 'pending'])
        }
    })

@app.route('/api/wallet/info')
def api_wallet_info():
    """Get system wallet info"""
    return jsonify({
        'success': True,
        'min_withdrawal_usdt': float(get_config('min_withdrawal_usdt', 0.5)),
        'min_withdrawal_doge': float(get_config('min_withdrawal_doge', 0.3)),
        'min_withdrawal_ton': float(get_config('min_withdrawal_ton', 0.1)),
        'supported_currencies': ['USDT', 'DOGE', 'TON'],
        'networks': {
            'USDT': 'BEP20 (BSC)',
            'DOGE': 'BEP20 (BSC)',
            'TON': 'TON Network'
        }
    })

# ============== TRANSACTIONS API ==============

@app.route('/api/transactions')
def api_transactions():
    """Get unified user transactions history - supports all currencies (DOGE, TON, USDT, SE)"""
    user_id = request.args.get('user_id') or get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    # Parámetros opcionales
    currency = request.args.get('currency')
    tx_type = request.args.get('type')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    lang = request.args.get('lang', 'en')

    try:
        # Use new unified transactions system if available
        if TRANSACTIONS_SYSTEM_AVAILABLE:
            transactions = get_user_unified_transactions(
                user_id=user_id,
                currency=currency.upper() if currency else None,
                tx_type=tx_type,
                limit=limit,
                offset=offset
            )

            # Format for API
            formatted = [format_transaction_for_api(tx, lang) for tx in transactions]

            # Calculate stats
            stats = {
                'total_received': 0,
                'total_sent': 0,
                'by_currency': {}
            }

            for tx in transactions:
                curr = tx.get('currency', 'SE')
                amount = float(tx.get('amount', 0))

                if curr not in stats['by_currency']:
                    stats['by_currency'][curr] = {'received': 0, 'sent': 0}

                if tx.get('tx_type') == 'withdrawal':
                    stats['total_sent'] += amount
                    stats['by_currency'][curr]['sent'] += amount
                else:
                    stats['total_received'] += amount
                    stats['by_currency'][curr]['received'] += amount

            return jsonify({
                'success': True,
                'transactions': formatted,
                'count': len(formatted),
                'stats': stats,
                'currencies': list(CURRENCIES.keys()) if TRANSACTIONS_SYSTEM_AVAILABLE else ['SE', 'DOGE', 'TON', 'USDT']
            })

        # Fallback to legacy implementation
        from db import get_cursor
        transactions = []

        # Obtener historial de balance (mining, referidos, tareas, etc.)
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, user_id, action, currency, amount, description, created_at
                FROM balance_history
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (str(user_id), limit))
            balance_history = cursor.fetchall()

        if balance_history:
            for row in balance_history:
                if isinstance(row, dict):
                    desc = (row.get('description') or '').lower()
                    action = (row.get('action') or '').lower()

                    # Detectar tipo basado en descripción
                    tx_type_detected = 'other'

                    if 'withdrawal' in desc or 'retiro' in desc:
                        tx_type_detected = 'withdrawal'
                    elif 'deposit' in desc or 'depósito' in desc:
                        tx_type_detected = 'deposit'
                    elif 'mining' in desc or 'minería' in desc:
                        tx_type_detected = 'mining'
                    elif 'swap' in desc or 'intercambio' in desc:
                        tx_type_detected = 'swap'
                    elif 'roulette' in desc or 'mines game' in desc or 'game' in desc:
                        tx_type_detected = 'game'
                    elif 'task' in desc or 'tarea' in desc:
                        tx_type_detected = 'task'
                    elif 'referral bonus' in desc or 'comisión' in desc:
                        tx_type_detected = 'commission'
                    elif 'referral' in desc or 'referido' in desc:
                        tx_type_detected = 'referral'
                    elif 'promo' in desc:
                        tx_type_detected = 'promo'
                    elif 'upgrade' in desc or 'mejora' in desc:
                        tx_type_detected = 'upgrade'
                    elif 'ad reward' in desc or 'ad watched' in desc or 'telega' in desc:
                        tx_type_detected = 'ad_reward'
                    elif 'penalty' in desc or 'left @' in desc:
                        tx_type_detected = 'penalty'
                    elif 'refund' in desc or 'reembolso' in desc:
                        tx_type_detected = 'refund'
                    elif action == 'add':
                        tx_type_detected = 'deposit'
                    elif action == 'subtract':
                        tx_type_detected = 'withdrawal'

                    transactions.append({
                        'id': row.get('id'),
                        'type': tx_type_detected,
                        'description': row.get('description') or row.get('action', ''),
                        'amount': float(row.get('amount', 0)),
                        'currency': row.get('currency', 'SE'),
                        'status': 'completed',
                        'timestamp': row.get('created_at').isoformat() if row.get('created_at') else None,
                        'date': row.get('created_at').isoformat() if row.get('created_at') else None
                    })

        # Obtener retiros
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, withdrawal_id, currency, amount, wallet_address, status, tx_hash, created_at
                FROM withdrawals
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (str(user_id), limit))
            withdrawals = cursor.fetchall()

        if withdrawals:
            for row in withdrawals:
                if isinstance(row, dict):
                    transactions.append({
                        'id': row.get('id'),
                        'type': 'withdrawal',
                        'description': f"Retiro de {row.get('currency', 'SE')}",
                        'amount': float(row.get('amount', 0)),
                        'currency': row.get('currency', 'SE'),
                        'status': row.get('status', 'pending'),
                        'tx_hash': row.get('tx_hash'),
                        'wallet_address': row.get('wallet_address'),
                        'timestamp': row.get('created_at').isoformat() if row.get('created_at') else None,
                        'date': row.get('created_at').isoformat() if row.get('created_at') else None
                    })

        # Obtener transacciones TON
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT id, user_id, amount, payment_type, status, tx_hash, wallet_address, created_at
                    FROM ton_payments
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (str(user_id), limit))
                ton_payments = cursor.fetchall()

            if ton_payments:
                for row in ton_payments:
                    if isinstance(row, dict):
                        transactions.append({
                            'id': row.get('id'),
                            'type': row.get('payment_type', 'deposit'),
                            'description': f"TON {row.get('payment_type', 'transaction')}",
                            'amount': float(row.get('amount', 0)),
                            'currency': 'TON',
                            'status': row.get('status', 'pending'),
                            'tx_hash': row.get('tx_hash'),
                            'wallet_address': row.get('wallet_address'),
                            'timestamp': row.get('created_at').isoformat() if row.get('created_at') else None,
                            'date': row.get('created_at').isoformat() if row.get('created_at') else None
                        })
        except Exception as ton_error:
            logger.warning(f"[api_transactions] Could not fetch TON transactions: {ton_error}")

        # Ordenar por fecha
        transactions.sort(key=lambda x: x.get('timestamp') or '', reverse=True)

        return jsonify({
            'success': True,
            'transactions': transactions[:limit],
            'count': len(transactions)
        })

    except Exception as e:
        logger.error(f"[api_transactions] Error: {e}")
        return jsonify({
            'success': False,
            'error': 'Error al obtener transacciones',
            'transactions': []
        }), 500

# ============== GAMES API ROUTES ==============

@app.route('/api/mines/start', methods=['POST'])
def api_mines_start():
    """Start a mines game - saves to database"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    data = request.get_json() or {}
    bet_amount = float(data.get('bet_amount', 0))
    mine_count = int(data.get('mine_count', 3))

    if bet_amount <= 0:
        return jsonify({'success': False, 'error': 'Invalid bet amount'}), 400

    if mine_count < 1 or mine_count > 24:
        return jsonify({'success': False, 'error': 'Mine count must be between 1 and 24'}), 400

    se_balance = float(user.get('se_balance', 0))
    if bet_amount > se_balance:
        return jsonify({'success': False, 'error': 'Insufficient balance'}), 400

    # Check for existing active game
    existing_game = get_active_game_session(user_id, 'mines')
    if existing_game:
        # Return existing game state
        return jsonify({
            'success': True,
            'message': 'Resuming active game',
            'session_id': existing_game.get('session_id'),
            'new_balance': se_balance,
            'bet_amount': float(existing_game.get('bet_amount', 0)),
            'mine_count': existing_game.get('mine_count', 3),
            'mine_positions': existing_game.get('mine_positions', []),
            'revealed_cells': existing_game.get('revealed_cells', []),
            'gems_found': existing_game.get('gems_found', 0),
            'current_multiplier': float(existing_game.get('current_multiplier', 1.0)),
            'resumed': True
        })

    # Deduct bet FIRST - before creating session
    success = update_balance(user_id, 'se', bet_amount, 'subtract', f'Mines game bet')
    if not success:
        return jsonify({'success': False, 'error': 'Error deducting balance'}), 500

    # Generate mine positions (25 cells, 0-24)
    mine_positions = random.sample(range(25), mine_count)

    # Create game session in database
    session_id = create_game_session(
        user_id=user_id,
        game_type='mines',
        bet_amount=bet_amount,
        mine_count=mine_count,
        mine_positions=mine_positions
    )

    if not session_id:
        # Refund if session creation failed
        update_balance(user_id, 'se', bet_amount, 'add', 'Mines game refund - session error')
        return jsonify({'success': False, 'error': 'Error creating game session'}), 500

    # Also store in Flask session for backwards compatibility
    session['mines_game'] = {
        'session_id': session_id,
        'user_id': user_id,
        'bet_amount': bet_amount,
        'mine_count': mine_count,
        'mine_positions': mine_positions,
        'revealed': [],
        'started_at': datetime.now().isoformat()
    }

    # Get updated balance
    user = get_user(user_id)
    new_balance = float(user.get('se_balance', 0)) if user else se_balance - bet_amount

    return jsonify({
        'success': True,
        'message': 'Game started',
        'session_id': session_id,
        'new_balance': new_balance,
        'bet_amount': bet_amount,
        'mine_count': mine_count,
        'mine_positions': mine_positions
    })

@app.route('/api/mines/reveal', methods=['POST'])
def api_mines_reveal():
    """Reveal a cell in mines game - uses database"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    data = request.get_json() or {}
    session_id = data.get('session_id')
    cell_index = int(data.get('cell_index', -1))

    # Try to get game from database first, fall back to Flask session
    game = None
    if session_id:
        game = get_game_session(session_id)

    if not game:
        game = get_active_game_session(user_id, 'mines')

    if not game:
        # Fall back to Flask session for backwards compatibility
        flask_game = session.get('mines_game')
        if flask_game and flask_game.get('user_id') == user_id:
            game = flask_game
            session_id = flask_game.get('session_id')

    if not game:
        return jsonify({'success': False, 'error': 'No active game'}), 400

    if str(game.get('user_id')) != str(user_id):
        return jsonify({'success': False, 'error': 'Invalid session'}), 400

    if cell_index < 0 or cell_index > 24:
        return jsonify({'success': False, 'error': 'Invalid cell index'}), 400

    revealed_cells = game.get('revealed_cells') or game.get('revealed') or []
    if cell_index in revealed_cells:
        return jsonify({'success': False, 'error': 'Cell already revealed'}), 400

    mine_positions = game.get('mine_positions', [])
    is_mine = cell_index in mine_positions
    revealed_cells.append(cell_index)

    # Update Flask session
    if 'mines_game' in session:
        session['mines_game']['revealed'] = revealed_cells
        session.modified = True

    if is_mine:
        # Game over - player hit a mine
        session_id = game.get('session_id') or session.get('mines_game', {}).get('session_id')
        if session_id:
            end_game_session(session_id, 'lost', 0)

        session.pop('mines_game', None)

        return jsonify({
            'success': True,
            'is_mine': True,
            'game_over': True,
            'won': False,
            'mine_positions': mine_positions
        })

    gems_found = len(revealed_cells)
    mine_count = game.get('mine_count', 3)

    multipliers = {
        3: 1.12, 5: 1.24, 10: 1.56, 15: 2.1, 20: 3.5
    }
    base_mult = multipliers.get(mine_count, 1.12)
    current_multiplier = base_mult ** gems_found

    # Update database session
    session_id = game.get('session_id') or session.get('mines_game', {}).get('session_id')
    if session_id:
        update_game_session(
            session_id,
            revealed_cells=revealed_cells,
            gems_found=gems_found,
            current_multiplier=current_multiplier
        )

    return jsonify({
        'success': True,
        'is_mine': False,
        'gems_found': gems_found,
        'multiplier': round(current_multiplier, 2)
    })

@app.route('/api/mines/cashout', methods=['POST'])
def api_mines_cashout():
    """Cash out from mines game - uses database"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    data = request.get_json() or {}
    session_id = data.get('session_id')

    # Try to get game from database first
    game = None
    if session_id:
        game = get_game_session(session_id)

    if not game:
        game = get_active_game_session(user_id, 'mines')

    if not game:
        # Fall back to Flask session
        flask_game = session.get('mines_game')
        if flask_game and flask_game.get('user_id') == user_id:
            game = flask_game
            session_id = flask_game.get('session_id')

    if not game:
        return jsonify({'success': False, 'error': 'No active game'}), 400

    bet_amount = float(data.get('bet_amount', game.get('bet_amount', 0)))
    multiplier = float(data.get('multiplier', game.get('current_multiplier', 1.0)))

    revealed_cells = game.get('revealed_cells') or game.get('revealed') or []
    gems_found = len(revealed_cells)

    if gems_found == 0:
        return jsonify({'success': False, 'error': 'Must reveal at least one gem'}), 400

    winnings = round(bet_amount * multiplier, 4)

    # Add winnings to balance
    success = update_balance(user_id, 'se', winnings, 'add', f'Mines game win - {multiplier:.2f}x')
    if not success:
        return jsonify({'success': False, 'error': 'Error adding winnings'}), 500

    # End game session in database
    session_id = game.get('session_id') or session.get('mines_game', {}).get('session_id')
    if session_id:
        end_game_session(session_id, 'cashout', winnings)

    # Clear Flask session
    session.pop('mines_game', None)

    user = get_user(user_id)

    return jsonify({
        'success': True,
        'winnings': winnings,
        'multiplier': multiplier,
        'new_balance': float(user.get('se_balance', 0)) if user else 0
    })


@app.route('/api/mines/history', methods=['GET'])
def api_mines_history():
    """Get game history for user"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    limit = request.args.get('limit', 20, type=int)
    game_type = request.args.get('type', 'mines')

    history = get_game_history(user_id, game_type if game_type != 'all' else None, limit)

    # Format history for frontend
    formatted_history = []
    for game in history:
        formatted_history.append({
            'id': game.get('id'),
            'game_type': game.get('game_type', 'mines'),
            'bet_amount': float(game.get('bet_amount', 0)),
            'mine_count': game.get('mine_count'),
            'gems_found': game.get('gems_found', 0),
            'multiplier': float(game.get('multiplier', 1.0)),
            'result': game.get('result'),
            'winnings': float(game.get('winnings', 0)),
            'profit': float(game.get('profit', 0)),
            'played_at': game.get('played_at').isoformat() if game.get('played_at') else None
        })

    return jsonify({
        'success': True,
        'history': formatted_history,
        'count': len(formatted_history)
    })


@app.route('/api/mines/active', methods=['GET'])
def api_mines_active():
    """Check if user has an active game"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID required'}), 400

    game = get_active_game_session(user_id, 'mines')

    if not game:
        # Check Flask session as fallback
        flask_game = session.get('mines_game')
        if flask_game and flask_game.get('user_id') == user_id:
            return jsonify({
                'success': True,
                'has_active_game': True,
                'game': {
                    'bet_amount': flask_game.get('bet_amount'),
                    'mine_count': flask_game.get('mine_count'),
                    'revealed_cells': flask_game.get('revealed', []),
                    'gems_found': len(flask_game.get('revealed', [])),
                    'mine_positions': flask_game.get('mine_positions', [])
                }
            })
        return jsonify({'success': True, 'has_active_game': False})

    return jsonify({
        'success': True,
        'has_active_game': True,
        'game': {
            'session_id': game.get('session_id'),
            'bet_amount': float(game.get('bet_amount', 0)),
            'mine_count': game.get('mine_count'),
            'revealed_cells': game.get('revealed_cells', []),
            'gems_found': game.get('gems_found', 0),
            'current_multiplier': float(game.get('current_multiplier', 1.0)),
            'mine_positions': game.get('mine_positions', [])
        }
    })


# ============================================
# SISTEMA DE RULETA SIMPLIFICADO (SIN SESIONES)
# ============================================
ROULETTE_CONFIG = {
    'spin_cost': 2,
    'required_ads': 3,
    'prizes': [
        {'text': '2 S-E', 'value': 2, 'currency': 'SE', 'color': '#FF0080'},
        {'text': '0.02 TON', 'value': 0.02, 'currency': 'TON', 'color': '#0088CC'},
        {'text': ':((', 'value': 0, 'currency': 'NONE', 'color': '#2D2D3D'},
        {'text': '1 S-E', 'value': 1, 'currency': 'SE', 'color': '#4C00FF'},
        {'text': 'T_T', 'value': 0, 'currency': 'NONE', 'color': '#1a1a2e'},
        {'text': '0.01 TON', 'value': 0.01, 'currency': 'TON', 'color': '#0098EA'},
        {'text': '0.5 S-E', 'value': 0.5, 'currency': 'SE', 'color': '#FF006E'},
        {'text': ':_(', 'value': 0, 'currency': 'NONE', 'color': '#2D2D3D'},
        {'text': '0.002 TON', 'value': 0.002, 'currency': 'TON', 'color': '#0077B5'},
        {'text': '0.5 S-E', 'value': 0.5, 'currency': 'SE', 'color': '#E91E63'},
        {'text': '>_<', 'value': 0, 'currency': 'NONE', 'color': '#1a1a2e'},
        {'text': '1 S-E', 'value': 1, 'currency': 'SE', 'color': '#673AB7'}
    ],
    'weights': [4, 5, 18, 12, 18, 8, 10, 18, 12, 10, 18, 7]
}


@app.route('/api/roulette/spin', methods=['POST'])
def api_roulette_spin():
    """Ejecuta el giro de la ruleta - versión simplificada sin sesiones"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id') or get_user_id()
        ads_watched = int(data.get('ads_watched', 0))

        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400

        user = get_user(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        config = ROULETTE_CONFIG

        # Verificar que vio los 3 anuncios (reportados por el cliente)
        if ads_watched < config['required_ads']:
            return jsonify({
                'success': False,
                'error': f'Debes ver {config["required_ads"]} anuncios primero',
                'require_ads': True
            }), 400

        # Verificar balance
        se_balance = float(user.get('se_balance', 0))
        spin_cost = config['spin_cost']

        if se_balance < spin_cost:
            return jsonify({
                'success': False,
                'error': f'Balance insuficiente. Necesitas {spin_cost} S-E'
            }), 400

        # DESCONTAR COSTO
        update_balance(user_id, 'se', spin_cost, 'subtract', f'Roulette spin cost')

        # CALCULAR PREMIO
        prizes = config['prizes']
        weights = config['weights']
        prize_index = random.choices(range(len(prizes)), weights=weights)[0]
        prize = prizes[prize_index]

        # ENTREGAR RECOMPENSA
        if prize['value'] > 0 and prize['currency'] != 'NONE':
            currency_map = {
                'SE': 'se',
                'DOGE': 'doge',
                'USDT': 'usdt',
                'TON': 'ton'
            }
            db_currency = currency_map.get(prize['currency'])
            if db_currency:
                update_balance(user_id, db_currency, prize['value'], 'add', f'Roulette win: {prize["value"]} {prize["currency"]}')

        # Obtener nuevo balance
        user = get_user(user_id)
        new_balance = float(user.get('se_balance', 0))

        return jsonify({
            'success': True,
            'prize_index': prize_index,
            'prize': prize,
            'prize_text': prize['text'],
            'prize_value': prize['value'],
            'prize_currency': prize['currency'],
            'spin_cost': spin_cost,
            'new_balance': new_balance,
            'won': prize['value'] > 0
        })

    except Exception as e:
        print(f"[Roulette] Spin error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Error al procesar giro'}), 500


@app.route('/api/roulette/config', methods=['GET'])
def api_roulette_config():
    """Obtiene la configuración de la ruleta"""
    try:
        user_id = request.args.get('user_id') or get_user_id()

        user = get_user(user_id) if user_id else None
        se_balance = float(user.get('se_balance', 0)) if user else 0

        config = ROULETTE_CONFIG

        return jsonify({
            'success': True,
            'spin_cost': config['spin_cost'],
            'required_ads': config['required_ads'],
            'balance': se_balance,
            'can_afford': se_balance >= config['spin_cost']
        })

    except Exception as e:
        print(f"[Roulette] Config error: {e}")
        return jsonify({
            'success': True,
            'spin_cost': 3,
            'required_ads': 3,
            'balance': 0,
            'can_afford': False
        })


# ============== ADMIN ROUTES ==============

@app.route('/admin')
def admin_redirect():
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password', '')

        admin_password = get_config('admin_password', 'admin123')

        if password == admin_password:
            session.permanent = True
            session['admin_logged_in'] = True
            flash('Login exitoso', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Contraseña incorrecta', 'error')

    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    flash('Sesión cerrada', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    from db import get_cursor

    # Calcular estadísticas para el dashboard
    total_users = get_users_count()
    try:
        banned_users = get_banned_users_count()
    except:
        banned_users = 0

    pending_withdrawals_list = get_pending_withdrawals()
    pending_withdrawals = len(pending_withdrawals_list) if pending_withdrawals_list else 0

    # Calcular totales de balances
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COALESCE(SUM(se_balance), 0) as total_se,
                    COALESCE(SUM(usdt_balance), 0) as total_usdt,
                    COALESCE(SUM(doge_balance), 0) as total_doge
                FROM users
            """)
            balances = cursor.fetchone()
        total_se_balance = float(balances.get('total_se', 0) if balances else 0)
        total_usdt = float(balances.get('total_usdt', 0) if balances else 0)
        total_doge = float(balances.get('total_doge', 0) if balances else 0)
    except:
        total_se_balance = 0.0
        total_usdt = 0.0
        total_doge = 0.0

    # Contar usuarios activos (últimas 24 horas)
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count FROM users
                WHERE last_interaction >= NOW() - INTERVAL 24 HOUR
            """)
            active_result = cursor.fetchone()
        active_users = int(active_result.get('count', 0) if active_result else 0)
    except:
        active_users = 0

    # Contar tareas activas
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE active = 1")
            tasks_result = cursor.fetchone()
        total_tasks = int(tasks_result.get('count', 0) if tasks_result else 0)
    except:
        total_tasks = 0

    # Contar códigos promo activos
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM promo_codes WHERE active = 1")
            promos_result = cursor.fetchone()
        total_promos = int(promos_result.get('count', 0) if promos_result else 0)
    except:
        total_promos = 0

    # Contar referidos totales
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM referrals")
            referrals_result = cursor.fetchone()
        total_referrals = int(referrals_result.get('count', 0) if referrals_result else 0)
    except:
        total_referrals = 0

    # Crear objeto de estadísticas para el template
    class Stats:
        pass

    stats = Stats()
    stats.total_users = total_users
    stats.active_users = active_users
    stats.total_se_balance = total_se_balance
    stats.total_usdt = total_usdt
    stats.total_doge = total_doge
    stats.total_tasks = total_tasks
    stats.pending_withdrawals = pending_withdrawals
    stats.total_promos = total_promos
    stats.total_referrals = total_referrals
    stats.banned_users = banned_users

    return render_template('admin_dashboard.html',
                         stats=stats,
                         total_users=total_users,
                         banned_users=banned_users,
                         pending_withdrawals=pending_withdrawals)


@app.route('/admin/competition')
@admin_required
def admin_competition():
    """Admin competition management page"""
    return render_template('admin_competition.html')


@app.route('/admin/users')
@admin_required
def admin_users():
    """Admin users page"""
    page = int(request.args.get('page', 1))
    per_page = 5
    search = request.args.get('search', '').strip()

    if search:
        users = search_users(search, limit=per_page)
        total = len(users)
    else:
        users = get_all_users(limit=per_page, offset=(page-1)*per_page)
        total = get_users_count()

    total_pages = (total + per_page - 1) // per_page

    # For template compatibility
    try:
        banned_count = get_banned_users_count()
    except:
        banned_count = sum(1 for u in users if u.get('banned'))

    # Get auto-banned count if ban system available
    auto_banned_count = 0
    if BAN_SYSTEM_AVAILABLE:
        try:
            ban_stats = get_ban_statistics()
            auto_banned_count = ban_stats.get('automatic_bans', 0)
        except Exception as e:
            logger.error(f"Error getting ban stats: {e}")

    return render_template('admin_users.html',
                         users=users,
                         usuarios=users,  # Template compatibility
                         page=page,
                         total_pages=total_pages,
                         search=search,
                         total=total,
                         banned_count=banned_count,
                         auto_banned_count=auto_banned_count)

@app.route('/admin/users/<user_id>/ban', methods=['POST'])
@admin_required
def admin_ban_user(user_id):
    """Ban a user with enhanced logging"""
    reason = request.form.get('reason', 'Banned by admin')
    admin_id = session.get('admin_id', 'unknown')

    if BAN_SYSTEM_AVAILABLE:
        result = ban_user_manual(user_id, reason, admin_id)
        if result.get('success'):
            flash(f'Usuario {user_id} baneado exitosamente', 'success')
        else:
            flash(f'Error: {result.get("error", "Unknown error")}', 'error')
    else:
        ban_user(user_id, reason)
        flash(f'Usuario {user_id} baneado', 'success')

    return redirect(url_for('admin_users'))

@app.route('/admin/users/<user_id>/unban', methods=['POST'])
@admin_required
def admin_unban_user(user_id):
    """Unban a user with logging"""
    reason = request.form.get('reason', 'Unbanned by admin')
    admin_id = session.get('admin_id', 'unknown')

    if BAN_SYSTEM_AVAILABLE:
        result = unban_user_manual(user_id, reason, admin_id)
        if result.get('success'):
            flash(f'Usuario {user_id} desbaneado exitosamente', 'success')
        else:
            flash(f'Error: {result.get("error", "Unknown error")}', 'error')
    else:
        unban_user(user_id)
        flash(f'Usuario {user_id} desbaneado', 'success')

    return redirect(url_for('admin_users'))

@app.route('/admin/users/ban/<user_id>', methods=['POST'])
@admin_required
def admin_ban_user_alt(user_id):
    """Ban a user - alternative route"""
    reason = request.form.get('reason', 'Banned by admin')
    admin_id = session.get('admin_id', 'unknown')

    if BAN_SYSTEM_AVAILABLE:
        result = ban_user_manual(user_id, reason, admin_id)
        if result.get('success'):
            flash(f'Usuario {user_id} baneado exitosamente', 'success')
        else:
            flash(f'Error: {result.get("error", "Unknown error")}', 'error')
    else:
        ban_user(user_id, reason)
        flash(f'Usuario {user_id} baneado', 'success')

    return redirect(url_for('admin_users'))

@app.route('/admin/users/unban/<user_id>', methods=['POST'])
@admin_required
def admin_unban_user_alt(user_id):
    """Unban a user - alternative route"""
    reason = request.form.get('reason', 'Unbanned by admin')
    admin_id = session.get('admin_id', 'unknown')

    if BAN_SYSTEM_AVAILABLE:
        result = unban_user_manual(user_id, reason, admin_id)
        if result.get('success'):
            flash(f'Usuario {user_id} desbaneado exitosamente', 'success')
        else:
            flash(f'Error: {result.get("error", "Unknown error")}', 'error')
    else:
        unban_user(user_id)
        flash(f'Usuario {user_id} desbaneado', 'success')

    return redirect(url_for('admin_users'))

@app.route('/admin/users/power/<user_id>', methods=['POST'])
@admin_required
def admin_update_power(user_id):
    """Update user mining power"""
    mining_power = request.form.get('mining_power')
    if mining_power:
        try:
            update_user(user_id, mining_power=float(mining_power))
            flash(f'Poder de minería actualizado para {user_id}', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/balance/<user_id>', methods=['POST'])
@admin_required
def admin_update_balance(user_id):
    """Update user balance (add/subtract)"""
    action = request.form.get('action', 'add')
    amount = request.form.get('amount')
    currency = request.form.get('currency', 'SE').upper()
    reason = request.form.get('reason', f'{action} by admin')
    allow_negative = request.form.get('allow_negative') == 'on'  # Para penalizaciones/deudas

    if not amount:
        flash('Cantidad requerida', 'error')
        return redirect(url_for('admin_users'))

    try:
        amount = float(amount)
        currency_map = {'SE': 'se', 'USDT': 'usdt', 'DOGE': 'doge', 'TON': 'ton'}
        currency_key = currency_map.get(currency, 'se')

        if action == 'add':
            update_balance(user_id, currency_key, amount, 'add', reason)
            flash(f'+{amount} {currency} agregado a {user_id}', 'success')
        elif action == 'subtract':
            update_balance(user_id, currency_key, amount, 'subtract', reason, allow_negative=allow_negative)
            if allow_negative:
                flash(f'-{amount} {currency} restado de {user_id} (permitido saldo negativo/deuda)', 'warning')
            else:
                flash(f'-{amount} {currency} restado de {user_id}', 'success')

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_users'))

@app.route('/admin/users/update/<user_id>', methods=['POST'])
@admin_required
def admin_update_user(user_id):
    """Update user details"""
    mining_power = request.form.get('mining_power')
    se_balance = request.form.get('se_balance')
    usdt_balance = request.form.get('usdt_balance')
    doge_balance = request.form.get('doge_balance')

    updates = {}
    if mining_power:
        updates['mining_power'] = float(mining_power)
    if se_balance:
        updates['se_balance'] = float(se_balance)
    if usdt_balance:
        updates['usdt_balance'] = float(usdt_balance)
    if doge_balance:
        updates['doge_balance'] = float(doge_balance)

    if updates:
        update_user(user_id, **updates)
        flash(f'Usuario {user_id} actualizado', 'success')

    return redirect(url_for('admin_users'))


@app.route('/admin/users/pts/<user_id>', methods=['POST'])
@admin_required
def admin_update_pts(user_id):
    """Update user PTS (add/subtract) - Admin only"""
    action = request.form.get('action', 'add')
    amount = request.form.get('amount')
    reason = request.form.get('reason', f'PTS {action} by admin')

    if not amount:
        flash('Cantidad de PTS requerida', 'error')
        return redirect(url_for('admin_users'))

    try:
        amount = int(float(amount))
        if amount <= 0:
            flash('La cantidad debe ser mayor a 0', 'error')
            return redirect(url_for('admin_users'))

        from db import get_cursor
        from datetime import datetime, timedelta

        today = datetime.now().strftime('%Y-%m-%d')
        today_date = datetime.now().date()

        # Calculate week start for ranking
        period_start = today_date - timedelta(days=today_date.weekday())
        period_end = period_start + timedelta(days=6)

        with get_cursor() as cursor:
            if action == 'add':
                # Add PTS to user_pts table
                cursor.execute("""
                    INSERT INTO user_pts (user_id, pts_balance, pts_total_earned, pts_today, last_pts_date)
                    VALUES (%s, %s, %s, 0, %s)
                    ON DUPLICATE KEY UPDATE
                        pts_balance = pts_balance + %s,
                        pts_total_earned = pts_total_earned + %s
                """, (str(user_id), amount, amount, today, amount, amount))

                # Add to pts_history
                cursor.execute("""
                    INSERT INTO pts_history (user_id, amount, action, description)
                    VALUES (%s, %s, %s, %s)
                """, (str(user_id), amount, 'admin_add', reason))

                # Update ranking
                cursor.execute("""
                    INSERT INTO pts_ranking (user_id, period_type, period_start, period_end, pts_earned)
                    VALUES (%s, 'weekly', %s, %s, %s)
                    ON DUPLICATE KEY UPDATE pts_earned = pts_earned + %s
                """, (str(user_id), period_start, period_end, amount, amount))

                flash(f'+{amount} PTS agregados a {user_id}', 'success')
                logger.info(f"[Admin PTS] +{amount} PTS to {user_id} - {reason}")

            elif action == 'subtract':
                # Get current PTS
                cursor.execute("SELECT pts_balance FROM user_pts WHERE user_id = %s", (str(user_id),))
                result = cursor.fetchone()
                current_pts = int(result['pts_balance']) if result else 0

                if current_pts < amount:
                    flash(f'Usuario solo tiene {current_pts} PTS', 'error')
                    return redirect(url_for('admin_users'))

                # Subtract PTS from user_pts
                cursor.execute("""
                    UPDATE user_pts
                    SET pts_balance = pts_balance - %s
                    WHERE user_id = %s
                """, (amount, str(user_id)))

                # Add to pts_history (negative amount)
                cursor.execute("""
                    INSERT INTO pts_history (user_id, amount, action, description)
                    VALUES (%s, %s, %s, %s)
                """, (str(user_id), -amount, 'admin_subtract', reason))

                # Update ranking (subtract)
                cursor.execute("""
                    UPDATE pts_ranking
                    SET pts_earned = GREATEST(0, pts_earned - %s)
                    WHERE user_id = %s AND period_type = 'weekly' AND period_start = %s
                """, (amount, str(user_id), period_start))

                flash(f'-{amount} PTS restados de {user_id}', 'success')
                logger.info(f"[Admin PTS] -{amount} PTS from {user_id} - {reason}")

    except Exception as e:
        logger.error(f"[Admin PTS] Error: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_users'))


@app.route('/api/admin/user-pts/<user_id>', methods=['GET'])
@admin_required
def api_get_user_pts(user_id):
    """Get user PTS info - Admin API"""
    try:
        from db import get_cursor
        from datetime import datetime, timedelta

        today_date = datetime.now().date()
        period_start = today_date - timedelta(days=today_date.weekday())

        with get_cursor() as cursor:
            # Get PTS balance
            cursor.execute("""
                SELECT pts_balance, pts_total_earned, pts_today
                FROM user_pts WHERE user_id = %s
            """, (str(user_id),))
            pts_result = cursor.fetchone()

            # Get ranking PTS
            cursor.execute("""
                SELECT pts_earned FROM pts_ranking
                WHERE user_id = %s AND period_type = 'weekly' AND period_start = %s
            """, (str(user_id), period_start))
            ranking_result = cursor.fetchone()

            return jsonify({
                'success': True,
                'pts_balance': int(pts_result['pts_balance']) if pts_result else 0,
                'pts_total_earned': int(pts_result['pts_total_earned']) if pts_result else 0,
                'pts_today': int(pts_result['pts_today']) if pts_result else 0,
                'pts_week': int(ranking_result['pts_earned']) if ranking_result else 0
            })
    except Exception as e:
        logger.error(f"[API User PTS] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== FAKE REFERRALS ADMIN ==============

@app.route('/admin/users/referrals/<user_id>', methods=['POST'])
@admin_required
def admin_update_referrals(user_id):
    """Add or remove fake referrals to boost user ranking - Admin only"""
    action = request.form.get('action', 'add')
    amount = request.form.get('amount')

    if not amount:
        flash('Cantidad de referidos requerida', 'error')
        return redirect(url_for('admin_users'))

    try:
        amount = int(float(amount))
        if amount <= 0:
            flash('La cantidad debe ser mayor a 0', 'error')
            return redirect(url_for('admin_users'))

        from db import get_cursor
        import time

        with get_cursor() as cursor:
            if action == 'add':
                # Create fake referrals with negative IDs (won't conflict with real users)
                # Each fake referral gets a unique negative ID based on timestamp + counter
                base_fake_id = -int(time.time() * 1000)

                for i in range(amount):
                    fake_referred_id = base_fake_id - i
                    fake_username = f'fake_ref_{abs(fake_referred_id)}'

                    cursor.execute("""
                        INSERT INTO referrals (referrer_id, referred_id, referred_username, referred_first_name, validated, bonus_paid, created_at, validated_at)
                        VALUES (%s, %s, %s, %s, 1, 0, NOW(), NOW())
                    """, (str(user_id), str(fake_referred_id), fake_username, 'Fake Referral'))

                # Update the referral_count in users table
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM referrals
                    WHERE referrer_id = %s AND validated = TRUE
                """, (str(user_id),))
                row = cursor.fetchone()
                new_count = row['cnt'] if row else 0

                cursor.execute("""
                    UPDATE users SET referral_count = %s WHERE user_id = %s
                """, (new_count, str(user_id)))

                flash(f'+{amount} referidos agregados a {user_id} (Total: {new_count})', 'success')
                logger.info(f"[Admin Referrals] +{amount} fake referrals added to {user_id}")

            elif action == 'subtract':
                # Get current fake referrals count
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM referrals
                    WHERE referrer_id = %s AND referred_id < 0
                """, (str(user_id),))
                result = cursor.fetchone()
                fake_count = int(result['cnt']) if result else 0

                if fake_count < amount:
                    flash(f'Usuario solo tiene {fake_count} referidos falsos', 'error')
                    return redirect(url_for('admin_users'))

                # Delete fake referrals (negative IDs only)
                cursor.execute("""
                    DELETE FROM referrals
                    WHERE referrer_id = %s AND referred_id < 0
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (str(user_id), amount))

                # Update the referral_count in users table
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM referrals
                    WHERE referrer_id = %s AND validated = TRUE
                """, (str(user_id),))
                row = cursor.fetchone()
                new_count = row['cnt'] if row else 0

                cursor.execute("""
                    UPDATE users SET referral_count = %s WHERE user_id = %s
                """, (new_count, str(user_id)))

                flash(f'-{amount} referidos falsos removidos de {user_id} (Total: {new_count})', 'success')
                logger.info(f"[Admin Referrals] -{amount} fake referrals removed from {user_id}")

    except Exception as e:
        logger.error(f"[Admin Referrals] Error: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_users'))


@app.route('/api/admin/user-referrals/<user_id>', methods=['GET'])
@admin_required
def api_get_user_referrals_admin(user_id):
    """Get user referrals info including fake count - Admin API"""
    try:
        from db import get_cursor

        with get_cursor() as cursor:
            # Get total validated referrals
            cursor.execute("""
                SELECT COUNT(*) as total FROM referrals
                WHERE referrer_id = %s AND validated = TRUE
            """, (str(user_id),))
            total_result = cursor.fetchone()

            # Get fake referrals count (negative IDs)
            cursor.execute("""
                SELECT COUNT(*) as fake FROM referrals
                WHERE referrer_id = %s AND referred_id < 0
            """, (str(user_id),))
            fake_result = cursor.fetchone()

            # Get real referrals count
            cursor.execute("""
                SELECT COUNT(*) as real_count FROM referrals
                WHERE referrer_id = %s AND referred_id > 0 AND validated = TRUE
            """, (str(user_id),))
            real_result = cursor.fetchone()

            # Get user's referral_count from users table
            cursor.execute("""
                SELECT referral_count FROM users WHERE user_id = %s
            """, (str(user_id),))
            user_result = cursor.fetchone()

            return jsonify({
                'success': True,
                'total_referrals': int(total_result['total']) if total_result else 0,
                'fake_referrals': int(fake_result['fake']) if fake_result else 0,
                'real_referrals': int(real_result['real_count']) if real_result else 0,
                'user_referral_count': int(user_result['referral_count']) if user_result else 0
            })
    except Exception as e:
        logger.error(f"[API User Referrals] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== BAN SYSTEM API ENDPOINTS ==============

@app.route('/api/admin/ban-statistics', methods=['GET'])
@admin_required
def api_ban_statistics():
    """Get ban statistics"""
    if not BAN_SYSTEM_AVAILABLE:
        return jsonify({'error': 'Ban system not available'}), 503

    try:
        stats = get_ban_statistics()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"[api_ban_statistics] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/user-ban-details/<user_id>', methods=['GET'])
@admin_required
def api_user_ban_details(user_id):
    """Get detailed ban info for a user"""
    if not BAN_SYSTEM_AVAILABLE:
        return jsonify({'error': 'Ban system not available'}), 503

    try:
        details = get_user_ban_details(user_id)
        return jsonify(details)
    except Exception as e:
        logger.error(f"[api_user_ban_details] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/banned-users', methods=['GET'])
@admin_required
def api_banned_users():
    """Get list of banned users"""
    if not BAN_SYSTEM_AVAILABLE:
        return jsonify({'error': 'Ban system not available'}), 503

    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        users = get_banned_users_list(limit, offset)
        return jsonify({'users': users, 'count': len(users)})
    except Exception as e:
        logger.error(f"[api_banned_users] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/ban-logs', methods=['GET'])
@admin_required
def api_ban_logs():
    """Get ban event logs"""
    if not BAN_SYSTEM_AVAILABLE:
        return jsonify({'error': 'Ban system not available'}), 503

    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        logs = get_ban_logs(limit, offset)
        return jsonify({'logs': logs, 'count': len(logs)})
    except Exception as e:
        logger.error(f"[api_ban_logs] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/update-ban-reason/<user_id>', methods=['POST'])
@admin_required
def api_update_ban_reason(user_id):
    """Update ban reason for a user"""
    if not BAN_SYSTEM_AVAILABLE:
        return jsonify({'error': 'Ban system not available'}), 503

    try:
        data = request.get_json() or {}
        new_reason = data.get('reason', request.form.get('reason', ''))
        admin_id = session.get('admin_id', 'unknown')

        if not new_reason:
            return jsonify({'error': 'Reason is required'}), 400

        result = update_ban_reason(user_id, new_reason, admin_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"[api_update_ban_reason] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/system/auto-ban-check', methods=['POST'])
def system_auto_ban_check():
    """Auto-ban check endpoint (called by device fingerprint script)"""
    if not BAN_SYSTEM_AVAILABLE:
        return jsonify({'error': 'Ban system not available'}), 503

    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        device_hash = data.get('device_hash')
        device_info = data.get('device_info', {})

        if not user_id:
            return jsonify({'error': 'user_id required'}), 400

        # Get client IP
        client_ip = get_client_ip()

        # Record device info if provided
        if device_hash and device_info:
            record_device_info(user_id, device_hash, device_info)

        # Run auto-ban check
        result = auto_ban_check(user_id, client_ip, device_hash)

        return jsonify(result)
    except Exception as e:
        logger.error(f"[system_auto_ban_check] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/check-ban-status/<user_id>', methods=['GET'])
def api_check_ban_status(user_id):
    """Quick ban status check"""
    if not BAN_SYSTEM_AVAILABLE:
        # Fallback to simple check
        user = get_user(user_id)
        if user:
            return jsonify({
                'banned': bool(user.get('banned')),
                'reason': user.get('ban_reason', '')
            })
        return jsonify({'error': 'User not found'}), 404

    try:
        status = get_user_ban_status(user_id)
        return jsonify(status)
    except Exception as e:
        logger.error(f"[api_check_ban_status] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/antifraud-config', methods=['GET', 'POST'])
@admin_required
def api_antifraud_config():
    """Get or update antifraud configuration"""
    if not BAN_SYSTEM_AVAILABLE:
        return jsonify({'success': False, 'error': 'Ban system not available'}), 500

    try:
        from ban_system import get_antifraud_config, update_antifraud_config

        if request.method == 'POST':
            data = request.get_json() or {}

            # Process config updates
            config_updates = {}

            if 'auto_ban_enabled' in data:
                config_updates['auto_ban_enabled'] = 'true' if data['auto_ban_enabled'] else 'false'

            if 'antifraud_enabled' in data:
                config_updates['antifraud_enabled'] = 'true' if data['antifraud_enabled'] else 'false'

            if 'max_accounts_per_ip' in data:
                config_updates['max_accounts_per_ip'] = str(int(data['max_accounts_per_ip']))

            if 'max_accounts_per_device' in data:
                config_updates['max_accounts_per_device'] = str(int(data['max_accounts_per_device']))

            if 'ban_related_accounts' in data:
                config_updates['ban_related_accounts'] = 'true' if data['ban_related_accounts'] else 'false'

            if config_updates:
                update_antifraud_config(config_updates)
                logger.info(f"[antifraud] Config updated: {config_updates}")

            return jsonify({'success': True, 'message': 'Configuration updated'})

        # GET request - return current config
        config = get_antifraud_config()
        return jsonify({'success': True, 'config': config})

    except Exception as e:
        logger.error(f"[api_antifraud_config] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/clear-user-ip', methods=['POST'])
@admin_required
def api_clear_user_ip():
    """Clear IP history for a user"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400

        from db import get_cursor

        with get_cursor() as cursor:
            # Clear last_ip from user
            cursor.execute(
                "UPDATE users SET last_ip = NULL WHERE user_id = %s",
                (str(user_id),)
            )

            # Clear from user_ips table if it exists
            cursor.execute("SHOW TABLES LIKE 'user_ips'")
            if cursor.fetchone():
                cursor.execute(
                    "DELETE FROM user_ips WHERE user_id = %s",
                    (str(user_id),)
                )

            # Clear device_hash too
            cursor.execute(
                "UPDATE users SET device_hash = NULL WHERE user_id = %s",
                (str(user_id),)
            )

            # Clear from user_device_history if exists
            cursor.execute("SHOW TABLES LIKE 'user_device_history'")
            if cursor.fetchone():
                cursor.execute(
                    "DELETE FROM user_device_history WHERE user_id = %s",
                    (str(user_id),)
                )

        logger.info(f"[clear_ip] Cleared IP/device history for user {user_id}")
        return jsonify({'success': True, 'message': 'IP history cleared'})

    except Exception as e:
        logger.error(f"[api_clear_user_ip] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/related-accounts/<user_id>', methods=['GET'])
@admin_required
def api_related_accounts(user_id):
    """Get accounts related by IP or device"""
    try:
        from db import get_cursor

        related = []

        with get_cursor() as cursor:
            # Get user's IP and device
            cursor.execute(
                "SELECT last_ip, device_hash FROM users WHERE user_id = %s",
                (str(user_id),)
            )
            user = cursor.fetchone()

            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            last_ip = user.get('last_ip')
            device_hash = user.get('device_hash')

            # Find users with same IP
            if last_ip:
                # Check user_ips table first
                cursor.execute("SHOW TABLES LIKE 'user_ips'")
                if cursor.fetchone():
                    cursor.execute(
                        """SELECT DISTINCT u.user_id, u.username, u.first_name, u.banned, u.ban_reason
                           FROM users u
                           INNER JOIN user_ips ui ON u.user_id = ui.user_id
                           WHERE ui.ip_address = %s AND u.user_id != %s""",
                        (last_ip, str(user_id))
                    )
                else:
                    cursor.execute(
                        """SELECT user_id, username, first_name, banned, ban_reason
                           FROM users WHERE last_ip = %s AND user_id != %s""",
                        (last_ip, str(user_id))
                    )

                for row in cursor.fetchall() or []:
                    row['relation'] = 'same_ip'
                    related.append(row)

            # Find users with same device
            if device_hash:
                cursor.execute(
                    """SELECT user_id, username, first_name, banned, ban_reason
                       FROM users WHERE device_hash = %s AND user_id != %s""",
                    (device_hash, str(user_id))
                )

                for row in cursor.fetchall() or []:
                    # Check if already in list
                    if str(row.get('user_id')) not in [str(r.get('user_id')) for r in related]:
                        row['relation'] = 'same_device'
                        related.append(row)

        return jsonify({'success': True, 'accounts': related})

    except Exception as e:
        logger.error(f"[api_related_accounts] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/tasks')
@admin_required
def admin_tasks():
    """Admin tasks page"""
    all_tasks = get_all_tasks()
    tareas = {t.get('task_id', ''): t for t in all_tasks} if all_tasks else {}
    return render_template('admin_tasks.html', tasks=all_tasks, tareas=tareas)

@app.route('/admin/tasks/new', methods=['GET', 'POST'])
@admin_required
def admin_task_new():
    """Create new task"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        reward = float(request.form.get('reward', 0))
        url = request.form.get('url', '').strip() or None
        task_type = request.form.get('task_type', 'link')
        requires_channel_join = request.form.get('requires_channel_join') == 'on'
        channel_username = request.form.get('channel_username', '').strip() or None

        if create_task(title, description, reward, url, task_type, True, requires_channel_join, channel_username):
            flash('Tarea creada exitosamente', 'success')
        else:
            flash('Error al crear tarea', 'error')

        return redirect(url_for('admin_tasks'))

    return render_template('admin_task_form.html', task=None)

@app.route('/admin/tasks/create', methods=['GET', 'POST'])
@admin_required
def admin_task_create():
    """Create new task - alias"""
    return admin_task_new()

@app.route('/admin/tasks/<task_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_task_edit(task_id):
    """Edit a task"""
    task = get_task(task_id)
    if not task:
        flash('Tarea no encontrada', 'error')
        return redirect(url_for('admin_tasks'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        reward = float(request.form.get('reward', 0))
        url = request.form.get('url', '').strip() or None
        task_type = request.form.get('task_type', 'link')
        active = request.form.get('active') == 'on'
        requires_channel_join = request.form.get('requires_channel_join') == 'on'
        channel_username = request.form.get('channel_username', '').strip() or None

        if update_task(task_id, title=title, description=description, reward=reward,
                      url=url, task_type=task_type, active=active,
                      requires_channel_join=requires_channel_join, channel_username=channel_username):
            flash('Tarea actualizada', 'success')
        else:
            flash('Error al actualizar tarea', 'error')

        return redirect(url_for('admin_tasks'))

    return render_template('admin_task_form.html', task=task)

@app.route('/admin/tasks/edit/<task_id>', methods=['GET', 'POST'])
@admin_required
def admin_task_edit_alt(task_id):
    """Edit a task - alternative route"""
    return admin_task_edit(task_id)

@app.route('/admin/tasks/<task_id>/delete', methods=['POST'])
@admin_required
def admin_task_delete(task_id):
    """Delete a task"""
    if delete_task(task_id):
        flash('Tarea eliminada', 'success')
    else:
        flash('Error al eliminar tarea', 'error')
    return redirect(url_for('admin_tasks'))

@app.route('/admin/tasks/delete/<task_id>', methods=['POST'])
@admin_required
def admin_task_delete_alt(task_id):
    """Delete a task - alternative route"""
    return admin_task_delete(task_id)

@app.route('/admin/tasks/toggle/<task_id>', methods=['POST'])
@admin_required
def admin_task_toggle(task_id):
    """Toggle task active status"""
    task = get_task(task_id)
    if task:
        new_status = not task.get('active', True)
        update_task(task_id, active=new_status)
        status_text = 'activada' if new_status else 'desactivada'
        flash(f'Tarea {status_text}', 'success')
    else:
        flash('Tarea no encontrada', 'error')
    return redirect(url_for('admin_tasks'))

@app.route('/admin/withdrawals')
@admin_required
def admin_withdrawals():
    """Admin withdrawals page"""
    # Get all withdrawals
    all_withdrawals = get_all_withdrawals(limit=1000)

    # Separate by status
    pending = [w for w in all_withdrawals if w.get('status') == 'pending']
    approved = [w for w in all_withdrawals if w.get('status') == 'completed']
    rejected = [w for w in all_withdrawals if w.get('status') == 'rejected']

    # Get withdrawal mode config
    withdrawal_mode = get_config('withdrawal_mode', 'manual')  # manual or auto

    # Stats for template
    stats = {
        'pending_count': len(pending),
        'approved_count': len(approved),
        'rejected_count': len(rejected),
        'total_amount': sum(float(w.get('amount', 0)) for w in approved),
        'total_pending_amount': sum(float(w.get('amount', 0)) for w in pending)
    }

    return render_template('admin_withdrawals.html',
                         pending=pending,
                         approved=approved,
                         rejected=rejected,
                         withdrawal_mode=withdrawal_mode,
                         stats=stats)

@app.route('/admin/withdrawals/<withdrawal_id>/approve', methods=['POST'])
@admin_required
def admin_withdrawal_approve(withdrawal_id):
    """Approve a withdrawal"""
    tx_hash = request.form.get('tx_hash', '')

    # Get withdrawal info before approval
    withdrawal = get_withdrawal(withdrawal_id)

    if WALLET_AVAILABLE:
        success, message = approve_withdrawal(withdrawal_id, tx_hash)
        if success:
            flash(f'Retiro {withdrawal_id} aprobado', 'success')
            # Send notification
            if WITHDRAWAL_NOTIFICATIONS_AVAILABLE and withdrawal:
                try:
                    on_withdrawal_completed(
                        withdrawal_id=withdrawal_id,
                        user_id=withdrawal['user_id'],
                        currency=withdrawal['currency'],
                        amount=withdrawal['amount'],
                        wallet_address=withdrawal['wallet_address'],
                        tx_hash=tx_hash
                    )
                except Exception as e:
                    logger.error(f"Error sending withdrawal notification: {e}")
        else:
            flash(f'Error: {message}', 'error')
    else:
        update_withdrawal(withdrawal_id, status='completed', tx_hash=tx_hash, processed_at=datetime.now())
        flash(f'Retiro {withdrawal_id} aprobado', 'success')
        # Send notification
        if WITHDRAWAL_NOTIFICATIONS_AVAILABLE and withdrawal:
            try:
                on_withdrawal_completed(
                    withdrawal_id=withdrawal_id,
                    user_id=withdrawal['user_id'],
                    currency=withdrawal['currency'],
                    amount=withdrawal['amount'],
                    wallet_address=withdrawal['wallet_address'],
                    tx_hash=tx_hash
                )
            except Exception as e:
                logger.error(f"Error sending withdrawal notification: {e}")

    return redirect(url_for('admin_withdrawals'))

@app.route('/admin/withdrawals/<withdrawal_id>/reject', methods=['POST'])
@admin_required
def admin_withdrawal_reject(withdrawal_id):
    """Reject a withdrawal and refund"""
    reason = request.form.get('reason', 'Rejected by admin')

    withdrawal = get_withdrawal(withdrawal_id)
    if withdrawal:
        user_id = withdrawal['user_id']
        currency = withdrawal['currency'].lower()
        amount = float(withdrawal['amount'])

        update_balance(user_id, currency, amount, 'add', f'Refund: {reason}')
        update_withdrawal(withdrawal_id, status='rejected', error_message=reason, processed_at=datetime.now())

        # Send rejection notification
        if WITHDRAWAL_NOTIFICATIONS_AVAILABLE:
            try:
                on_withdrawal_rejected(
                    withdrawal_id=withdrawal_id,
                    user_id=user_id,
                    currency=withdrawal['currency'],
                    amount=amount,
                    reason=reason
                )
            except Exception as e:
                logger.error(f"Error sending rejection notification: {e}")

        flash(f'Retiro {withdrawal_id} rechazado y reembolsado', 'success')
    else:
        flash('Retiro no encontrado', 'error')

    return redirect(url_for('admin_withdrawals'))

@app.route('/admin/withdrawals/set-mode', methods=['POST'])
@admin_required
def admin_set_withdrawal_mode():
    """Set withdrawal mode (manual or auto)"""
    mode = request.form.get('mode', 'manual')
    if mode not in ['manual', 'auto']:
        mode = 'manual'

    set_config('withdrawal_mode', mode)
    flash(f'Modo de retiro cambiado a: {"Automático" if mode == "auto" else "Manual"}', 'success')
    return redirect(url_for('admin_withdrawals'))

@app.route('/api/admin/auto-pay/status')
@admin_required
def api_admin_auto_pay_status():
    """Get auto payment system status"""
    if not AUTO_PAY_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Auto payment system not available'
        })

    try:
        status = get_auto_pay_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/auto-pay/process/<withdrawal_id>', methods=['POST'])
@admin_required
def api_admin_process_withdrawal(withdrawal_id):
    """Manually trigger auto-payment for a specific withdrawal"""
    if not AUTO_PAY_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Auto payment system not available'
        })

    try:
        from auto_pay import process_withdrawal
        success, message = process_withdrawal(withdrawal_id)

        if success:
            flash(f'Retiro {withdrawal_id} procesado automáticamente', 'success')
        else:
            flash(f'Error al procesar: {message}', 'error')

        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/auto-pay/process-all', methods=['POST'])
@admin_required
def api_admin_process_all_pending():
    """Process all pending withdrawals"""
    if not AUTO_PAY_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Auto payment system not available'
        })

    try:
        from auto_pay import process_all_pending
        # Temporarily enable auto mode for this batch
        original_mode = get_config('withdrawal_mode', 'manual')
        set_config('withdrawal_mode', 'auto')

        results = process_all_pending()

        # Restore original mode
        set_config('withdrawal_mode', original_mode)

        flash(f'Procesados: {results["success"]}/{results["processed"]} retiros',
              'success' if results['failed'] == 0 else 'warning')

        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/admin/promo')
@admin_required
def admin_promo():
    """Admin promo codes page"""
    cleanup_empty_promo_codes()
    codes = get_all_promo_codes()
    stats = get_promo_stats()
    codigos = {p.get('code', ''): p for p in codes if p.get('code')} if codes else {}
    return render_template('admin_promo.html', codes=codes, promos=codes, codigos=codigos, stats=stats, promo_stats=stats)

@app.route('/admin/promo/new', methods=['GET', 'POST'])
@admin_required
def admin_promo_new():
    """Create new promo code"""
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        reward = float(request.form.get('reward', 0))
        currency = request.form.get('currency', 'SE')
        max_uses = request.form.get('max_uses', '').strip()
        max_uses = int(max_uses) if max_uses else None

        if create_promo_code(code, reward, currency, max_uses):
            flash('Código creado exitosamente', 'success')
        else:
            flash('Error al crear código', 'error')

        return redirect(url_for('admin_promo'))

    return render_template('admin_promo_form.html', promo=None, action='new')

@app.route('/admin/promo/create', methods=['GET', 'POST'])
@admin_required
def admin_promo_create():
    """Create new promo code - alias"""
    return admin_promo_new()

@app.route('/admin/promo/<code>/toggle', methods=['POST'])
@admin_required
def admin_promo_toggle(code):
    """Toggle promo code active status"""
    toggle_promo_code(code)
    flash(f'Estado del código {code} cambiado', 'success')
    return redirect(url_for('admin_promo'))

@app.route('/admin/promo/toggle/<path:code>', methods=['POST'])
@admin_required
def admin_toggle_promo(code):
    """Toggle promo code - alternative route"""
    return admin_promo_toggle(code)

@app.route('/admin/promo/<code>/delete', methods=['POST'])
@admin_required
def admin_promo_delete(code):
    """Delete promo code"""
    delete_promo_code(code)
    flash(f'Código {code} eliminado', 'success')
    return redirect(url_for('admin_promo'))

@app.route('/admin/promo/delete/<path:code>', methods=['POST'])
@admin_required
def admin_promo_delete_alt(code):
    """Delete promo code - alternative route"""
    if not code or code.strip() == '' or code == 'None':
        cleanup_empty_promo_codes()
        flash('Códigos vacíos eliminados', 'success')
    else:
        if delete_promo_code(code):
            flash(f'Código {code} eliminado exitosamente', 'success')
        else:
            flash(f'Error al eliminar código {code}', 'error')
    return redirect(url_for('admin_promo'))

@app.route('/admin/promo/delete_by_id/<int:promo_id>', methods=['POST'])
@admin_required
def admin_promo_delete_by_id(promo_id):
    """Delete promo code by ID"""
    if delete_promo_code_by_id(promo_id):
        flash('Código eliminado exitosamente', 'success')
    else:
        flash('Error al eliminar código', 'error')
    return redirect(url_for('admin_promo'))

@app.route('/admin/promo/cleanup', methods=['POST'])
@admin_required
def admin_promo_cleanup():
    """Clean up empty/invalid promo codes"""
    cleanup_empty_promo_codes()
    flash('Códigos vacíos/inválidos eliminados', 'success')
    return redirect(url_for('admin_promo'))

@app.route('/admin/promo/edit/<path:code>', methods=['GET', 'POST'])
@admin_required
def admin_edit_promo(code):
    """Edit promo code"""
    promo = get_promo_code(code)
    if not promo:
        flash('Código no encontrado', 'error')
        return redirect(url_for('admin_promo'))

    if request.method == 'POST':
        try:
            reward = float(request.form.get('reward', 0))
            if reward <= 0:
                flash('La recompensa debe ser mayor a 0', 'error')
                return render_template('admin_promo_form.html', promo=promo, action='edit')
        except (ValueError, TypeError):
            flash('Recompensa inválida', 'error')
            return render_template('admin_promo_form.html', promo=promo, action='edit')

        max_uses_str = request.form.get('max_uses', '').strip()
        if max_uses_str and max_uses_str != '0':
            try:
                max_uses = int(max_uses_str)
                if max_uses <= 0:
                    max_uses = None
            except (ValueError, TypeError):
                max_uses = None
        else:
            max_uses = None

        active = request.form.get('active') in ['true', 'on', '1', 'True']

        update_promo_code(code, reward=reward, max_uses=max_uses, active=active)
        flash(f'Código {code} actualizado exitosamente', 'success')
        return redirect(url_for('admin_promo'))

    redemptions = get_promo_redemptions(code)
    return render_template('admin_promo_form.html', promo=promo, action='edit', redemptions=redemptions)

@app.route('/admin/promo/redemptions/<path:code>')
@admin_required
def admin_promo_redemptions(code):
    """View redemption history for a promo code"""
    promo = get_promo_code(code)
    if not promo:
        flash('Código no encontrado', 'error')
        return redirect(url_for('admin_promo'))

    redemptions = get_promo_redemptions(code)
    return render_template('admin_promo_redemptions.html', promo=promo, redemptions=redemptions)

@app.route('/admin/config', methods=['GET', 'POST'])
@admin_required
def admin_config():
    """Admin configuration page"""
    if request.method == 'POST':
        checkbox_fields = ['auto_ban_duplicate_ip', 'show_promo_fab']
        percentage_fields = ['referral_commission']

        for key in request.form:
            if key != 'csrf_token':
                value = request.form[key]

                if key == 'admin_password' and not value.strip():
                    continue

                if key in percentage_fields:
                    try:
                        value = float(value) / 100.0
                    except (ValueError, TypeError):
                        value = 0.05

                set_config(key, value)

        for checkbox in checkbox_fields:
            if checkbox not in request.form:
                set_config(checkbox, 'false')

        flash('Configuración actualizada', 'success')
        return redirect(url_for('admin_config'))

    config = get_all_config()

    for key in ['auto_ban_duplicate_ip', 'show_promo_fab']:
        if key in config:
            config[key] = str(config[key]).lower() == 'true'
        else:
            config[key] = False

    return render_template('admin_config.html', config=config)

# ============================================
# ADMIN MAINTENANCE SYSTEM
# Sistema profesional de mantenimiento y errores
# ============================================

# Mensajes por defecto (sin emojis - se usan iconos SVG en las plantillas)
DEFAULT_ERROR_MESSAGE = """Se ha producido una incidencia temporal en el sistema. Nuestro equipo técnico ya se encuentra trabajando para restablecer el servicio a la mayor brevedad posible. Por favor, intenta nuevamente en unos minutos."""
DEFAULT_MAINTENANCE_MESSAGE = """La plataforma se encuentra actualmente en mantenimiento programado. Estamos realizando mejoras para optimizar la estabilidad, seguridad y el rendimiento del servicio. Agradecemos tu comprensión."""
DEFAULT_ERROR_TITLE = "Incidencia Temporal"
DEFAULT_MAINTENANCE_TITLE = "Mantenimiento Programado"

def is_maintenance_mode():
    """Verifica si el modo mantenimiento está activo"""
    try:
        mode = get_config('maintenance_mode', 'false')
        return str(mode).lower() == 'true'
    except:
        return False

def get_maintenance_config():
    """Obtiene toda la configuración de mantenimiento"""
    try:
        return {
            'enabled': is_maintenance_mode(),
            'message': get_config('maintenance_message', DEFAULT_MAINTENANCE_MESSAGE),
            'title': get_config('maintenance_title', DEFAULT_MAINTENANCE_TITLE),
            'estimated_time': get_config('maintenance_estimated_time', ''),
            'started_at': get_config('maintenance_started_at', ''),
            'allow_admin': str(get_config('maintenance_allow_admin', 'true')).lower() == 'true'
        }
    except:
        return {
            'enabled': False,
            'message': DEFAULT_MAINTENANCE_MESSAGE,
            'title': DEFAULT_MAINTENANCE_TITLE,
            'estimated_time': '',
            'started_at': '',
            'allow_admin': True
        }

def get_error_config():
    """Obtiene la configuración de mensajes de error"""
    try:
        return {
            'message': get_config('error_message', DEFAULT_ERROR_MESSAGE),
            'title': get_config('error_title', DEFAULT_ERROR_TITLE),
            'show_retry_button': str(get_config('error_show_retry', 'true')).lower() == 'true',
            'show_support_link': str(get_config('error_show_support', 'true')).lower() == 'true',
            'support_link': get_config('support_group', SUPPORT_GROUP)
        }
    except:
        return {
            'message': DEFAULT_ERROR_MESSAGE,
            'title': DEFAULT_ERROR_TITLE,
            'show_retry_button': True,
            'show_support_link': True,
            'support_link': SUPPORT_GROUP
        }

@app.route('/admin/maintenance', methods=['GET'])
@admin_required
def admin_maintenance():
    """Página de administración del sistema de mantenimiento"""
    try:
        maintenance_config = get_maintenance_config()
        error_config = get_error_config()

        config = {
            'maintenance_enabled': maintenance_config['enabled'],
            'maintenance_title': maintenance_config['title'],
            'maintenance_message': maintenance_config['message'],
            'maintenance_estimated_time': maintenance_config['estimated_time'],
            'maintenance_started_at': maintenance_config['started_at'],
            'maintenance_allow_admin': maintenance_config['allow_admin'],
            'error_title': error_config['title'],
            'error_message': error_config['message'],
            'error_show_retry': error_config['show_retry_button'],
            'error_show_support': error_config['show_support_link']
        }

        return render_template('admin_maintenance.html', config=config)
    except Exception as e:
        logger.error(f"[admin_maintenance] Error: {e}")
        return render_template('admin_maintenance.html', config={
            'maintenance_enabled': False,
            'maintenance_title': DEFAULT_MAINTENANCE_TITLE,
            'maintenance_message': DEFAULT_MAINTENANCE_MESSAGE,
            'error_title': DEFAULT_ERROR_TITLE,
            'error_message': DEFAULT_ERROR_MESSAGE,
            'error_show_retry': True,
            'error_show_support': True,
            'maintenance_allow_admin': True
        })

@app.route('/admin/maintenance/save', methods=['POST'])
@admin_required
def admin_maintenance_save():
    """Guarda la configuración del sistema de mantenimiento"""
    try:
        # Obtener datos del formulario
        maintenance_mode = 'maintenance_mode' in request.form
        maintenance_title = request.form.get('maintenance_title', DEFAULT_MAINTENANCE_TITLE)
        maintenance_message = request.form.get('maintenance_message', DEFAULT_MAINTENANCE_MESSAGE)
        maintenance_estimated_time = request.form.get('maintenance_estimated_time', '')
        maintenance_allow_admin = 'maintenance_allow_admin' in request.form

        error_title = request.form.get('error_title', DEFAULT_ERROR_TITLE)
        error_message = request.form.get('error_message', DEFAULT_ERROR_MESSAGE)
        error_show_retry = 'error_show_retry' in request.form
        error_show_support = 'error_show_support' in request.form

        # Guardar configuración de mantenimiento
        set_config('maintenance_mode', 'true' if maintenance_mode else 'false')
        set_config('maintenance_title', maintenance_title)
        set_config('maintenance_message', maintenance_message)
        set_config('maintenance_estimated_time', maintenance_estimated_time)
        set_config('maintenance_allow_admin', 'true' if maintenance_allow_admin else 'false')

        if maintenance_mode:
            set_config('maintenance_started_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        else:
            set_config('maintenance_started_at', '')

        # Guardar configuración de errores
        set_config('error_title', error_title)
        set_config('error_message', error_message)
        set_config('error_show_retry', 'true' if error_show_retry else 'false')
        set_config('error_show_support', 'true' if error_show_support else 'false')

        logger.info(f"[admin_maintenance_save] Configuration saved. Maintenance mode: {maintenance_mode}")

        return jsonify({
            'success': True,
            'message': 'Configuración guardada correctamente',
            'maintenance_enabled': maintenance_mode
        })

    except Exception as e:
        logger.error(f"[admin_maintenance_save] Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/maintenance/toggle', methods=['POST'])
@admin_required
def admin_maintenance_toggle():
    """Activa o desactiva rápidamente el modo mantenimiento"""
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', False)

        set_config('maintenance_mode', 'true' if enabled else 'false')

        if enabled:
            set_config('maintenance_started_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        else:
            set_config('maintenance_started_at', '')

        logger.info(f"[admin_maintenance_toggle] Maintenance mode {'ENABLED' if enabled else 'DISABLED'}")

        return jsonify({
            'success': True,
            'maintenance_enabled': enabled,
            'message': 'Modo mantenimiento ' + ('activado' if enabled else 'desactivado')
        })

    except Exception as e:
        logger.error(f"[admin_maintenance_toggle] Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/maintenance/preview')
@admin_required
def admin_maintenance_preview():
    """Vista previa de la página de mantenimiento"""
    config = get_maintenance_config()
    return render_template('maintenance.html',
                         config=config,
                         title=config['title'],
                         message=config['message'],
                         estimated_time=config['estimated_time'])

@app.route('/admin/error/preview')
@admin_required
def admin_error_preview():
    """Vista previa de la página de error"""
    config = get_error_config()
    return render_template('system_error.html',
                         config=config,
                         title=config['title'],
                         message=config['message'],
                         error_type='general',
                         show_retry=config['show_retry_button'],
                         show_support=config['show_support_link'],
                         support_link=config['support_link'])

@app.route('/api/maintenance/status')
def api_maintenance_status():
    """API para verificar estado de mantenimiento (pública)"""
    config = get_maintenance_config()
    return jsonify({
        'maintenance': config['enabled'],
        'message': config['message'] if config['enabled'] else None,
        'estimated_time': config['estimated_time'] if config['enabled'] else None
    })

# Middleware de mantenimiento - rutas excluidas
MAINTENANCE_EXCLUDED_ROUTES = [
    '/admin', '/static/', '/favicon.ico', '/health', '/api/maintenance/status'
]

@app.before_request
def check_maintenance_mode():
    """Verificación de mantenimiento antes de cada request"""
    try:
        if not is_maintenance_mode():
            return None

        # Verificar si la ruta está excluida
        for excluded in MAINTENANCE_EXCLUDED_ROUTES:
            if request.path.startswith(excluded):
                return None

        # Permitir admin si está configurado
        config = get_maintenance_config()
        if config['allow_admin'] and session.get('admin_logged_in'):
            return None

        # Para solicitudes API, devolver JSON
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'maintenance': True,
                'message': config['message'],
                'title': config['title']
            }), 503

        # Para otras solicitudes, mostrar página de mantenimiento
        return render_template('maintenance.html',
                             config=config,
                             title=config['title'],
                             message=config['message'],
                             estimated_time=config['estimated_time'])
    except Exception as e:
        logger.error(f"[check_maintenance_mode] Error: {e}")
        return None

logger.info("✅ Sistema de Mantenimiento integrado correctamente")
logger.info("   Panel admin: /admin/maintenance")
logger.info("   API status: /api/maintenance/status")

# ============================================
# SISTEMA DE MANEJO DE ERRORES PREMIUM
# Captura errores de templates, servidor, etc.
# ============================================
from jinja2 import TemplateNotFound

def render_premium_error(title=None, message=None, error_type="general"):
    """Renderiza la página de error premium con configuración de BD"""
    error_config = get_error_config()

    # Usar valores de la BD si no se especifican
    if title is None:
        title = error_config['title']
    if message is None:
        message = error_config['message']

    # Intentar usar el template, si falla usar HTML inline
    try:
        return render_template('system_error.html',
                             title=title,
                             message=message,
                             error_type=error_type,
                             show_retry=error_config['show_retry_button'],
                             show_support=error_config['show_support_link'],
                             support_link=error_config['support_link'])
    except:
        # Fallback: HTML inline premium (sin emojis, con SVG)
        return f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - SALLY-E</title>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:linear-gradient(135deg,#0D0A1A,#1A0E2E,#2D1B4E);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff}}
        .container{{text-align:center;padding:40px;max-width:500px}}
        .icon{{width:80px;height:80px;margin:0 auto 30px;animation:pulse 2s infinite}}
        .icon svg{{width:100%;height:100%}}
        .icon svg path{{fill:none;stroke:#ffa726;stroke-width:2}}
        @keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.1)}}}}
        h1{{font-size:28px;margin-bottom:20px;background:linear-gradient(135deg,#fff,#ffa726);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
        p{{font-size:16px;line-height:1.7;opacity:0.8;margin-bottom:30px}}
        .btn{{display:inline-block;padding:16px 40px;background:linear-gradient(135deg,#C21883,#E852AA);border:none;border-radius:12px;color:#fff;font-size:16px;font-weight:600;cursor:pointer;text-decoration:none}}
        .btn:hover{{transform:translateY(-3px);box-shadow:0 10px 30px rgba(194,24,131,0.4)}}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">
            <svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13" stroke="#ffa726" stroke-width="2"/><line x1="12" y1="17" x2="12.01" y2="17" stroke="#ffa726" stroke-width="2"/></svg>
        </div>
        <h1>{title}</h1>
        <p>{message}</p>
        <a href="javascript:location.reload()" class="btn">Intentar de nuevo</a>
    </div>
</body>
</html>'''

@app.errorhandler(TemplateNotFound)
def handle_template_not_found(e):
    """Maneja errores cuando falta un archivo HTML/template"""
    logger.error(f"[TemplateNotFound] Template no encontrado: {e.name}")
    # Usa la configuración de la BD
    return render_premium_error(error_type="resource"), 500

@app.errorhandler(500)
def handle_500_error(e):
    """Maneja errores internos del servidor"""
    logger.error(f"[500 Error] Error interno: {e}")
    # Usa la configuración de la BD
    return render_premium_error(error_type="general"), 500

@app.errorhandler(404)
def handle_404_error(e):
    """Maneja errores de página no encontrada"""
    logger.warning(f"[404 Error] Página no encontrada: {request.path}")
    # Usa la configuración de la BD
    return render_premium_error(error_type="notfound"), 404

@app.errorhandler(503)
def handle_503_error(e):
    """Maneja errores de servicio no disponible"""
    logger.error(f"[503 Error] Servicio no disponible: {e}")
    # Usa la configuración de la BD
    return render_premium_error(error_type="connection"), 503

@app.errorhandler(Exception)
def handle_generic_exception(e):
    """Manejador genérico de excepciones no capturadas"""
    logger.error(f"[Unhandled Exception] {type(e).__name__}: {str(e)}")

    # Para APIs devolver JSON
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': True,
            'message': 'Se ha producido un error temporal. Por favor, intenta nuevamente.'
        }), 500

    # Usa la configuración de la BD
    return render_premium_error(error_type="general"), 500

logger.info("✅ Sistema de Manejo de Errores Premium activado")

# ============================================
# ADMIN ADS CONFIGURATION
# ============================================

@app.route('/admin/ads')
@admin_required
def admin_ads():
    """Admin ads configuration page"""
    from db import get_cursor

    config = get_all_config()

    # Initialize default values
    total_ads = 0
    ads_today = 0
    total_ad_earnings = 0.0
    active_ad_users = 0
    recent_logs = []

    # Try to get ads statistics if tables exist
    try:
        with get_cursor() as cursor:
            # Check if user_ad_stats table exists
            cursor.execute("SHOW TABLES LIKE 'user_ad_stats'")
            if cursor.fetchone():
                # Get total ads watched
                cursor.execute("SELECT COALESCE(SUM(total_ads_watched), 0) as total FROM user_ad_stats")
                result = cursor.fetchone()
                total_ads = int(result.get('total', 0) if result else 0)

                # Get ads watched today
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute(
                    "SELECT COALESCE(SUM(ads_watched_today), 0) as total FROM user_ad_stats WHERE last_ad_date = %s",
                    (today,)
                )
                result = cursor.fetchone()
                ads_today = int(result.get('total', 0) if result else 0)

                # Get total earnings
                cursor.execute("SELECT COALESCE(SUM(total_earnings), 0) as total FROM user_ad_stats")
                result = cursor.fetchone()
                total_ad_earnings = float(result.get('total', 0) if result else 0)

                # Get active ad users today
                cursor.execute(
                    "SELECT COUNT(DISTINCT user_id) as count FROM user_ad_stats WHERE last_ad_date = %s",
                    (today,)
                )
                result = cursor.fetchone()
                active_ad_users = int(result.get('count', 0) if result else 0)
    except Exception as e:
        logger.warning(f"[Admin Ads] Could not get user_ad_stats: {e}")

    # Try to get recent logs if table exists
    try:
        with get_cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'ad_completions'")
            if cursor.fetchone():
                cursor.execute(
                    """SELECT user_id, ad_type, reward, completed_at
                       FROM ad_completions
                       ORDER BY completed_at DESC
                       LIMIT 20"""
                )
                recent_logs = cursor.fetchall() or []
    except Exception as e:
        logger.warning(f"[Admin Ads] Could not get ad_completions: {e}")
        recent_logs = []

    return render_template('admin_ads.html',
                          config=config,
                          total_ads_watched=total_ads,
                          ads_today=ads_today,
                          total_ad_earnings=total_ad_earnings,
                          active_ad_users=active_ad_users,
                          recent_logs=recent_logs)


@app.route('/admin/ads/save', methods=['POST'])
@admin_required
def admin_ads_save():
    """Save ads configuration"""
    try:
        data = request.get_json()

        config_keys = [
            'mining_ad_enabled', 'mining_ad_cooldown', 'mining_ad_min_watch',
            'task_center_ads_enabled', 'task_center_ad_reward', 'task_center_max_daily_ads',
            'task_center_ad_cooldown', 'task_center_ad_min_watch',
            'ad_sdk_url', 'ad_zone_id', 'ad_sdk_function'
        ]

        for key in config_keys:
            if key in data:
                set_config(key, data[key])

        logger.info(f"[Admin] Ads configuration updated")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"[Admin] Error saving ads config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/ips')
@admin_required
def admin_ips():
    """Admin IPs page - show duplicate IPs"""
    duplicates = get_duplicate_ips()

    ips = []
    for dup in duplicates:
        ip_address = dup.get('ip_address', '')
        user_ids = dup.get('user_ids', '').split(',') if dup.get('user_ids') else []
        user_count = dup.get('user_count', 0)

        users = get_users_by_ip(ip_address)

        ips.append({
            'ip_address': ip_address,
            'ip_hash': ip_address,
            'user_count': user_count,
            'user_ids': user_ids,
            'users': users,
            'is_suspicious': user_count > 1,
            'is_banned': is_ip_banned(ip_address),
            'first_seen': users[0].get('created_at', '') if users else '',
            'last_seen': users[0].get('last_interaction', '') if users else ''
        })

    return render_template('admin_ips.html', ips=ips, duplicates=duplicates)

@app.route('/admin/ips/ban/<ip_hash>', methods=['POST'])
@admin_required
def admin_ban_ip(ip_hash):
    """Ban an IP address and optionally its users"""
    ban_users = request.form.get('ban_users', 'false') == 'true'

    ban_ip(ip_hash, reason='Banned by admin')

    if ban_users:
        users = get_users_by_ip(ip_hash)
        for user in users:
            ban_user(user.get('user_id'), reason='IP banned by admin')
        flash(f'IP {ip_hash} y {len(users)} usuarios baneados', 'success')
    else:
        flash(f'IP {ip_hash} baneada', 'success')

    return redirect(url_for('admin_ips'))

@app.route('/admin/ips/unban/<ip_hash>', methods=['POST'])
@admin_required
def admin_unban_ip(ip_hash):
    """Unban an IP address"""
    unban_ip(ip_hash)
    flash(f'IP {ip_hash} desbaneada', 'success')
    return redirect(url_for('admin_ips'))

@app.route('/admin/balance-protection')
@admin_required
def admin_balance_protection():
    """Balance protection tools"""
    return render_template('admin_balance_protection.html')

@app.route('/admin/emergency')
@admin_required
def admin_emergency():
    """Admin emergency tools page"""
    return render_template('admin_emergency.html')

# ============== EMERGENCY API ENDPOINTS ==============

@app.route('/api/emergency/add-referral', methods=['POST'])
@admin_required
def api_emergency_add_referral():
    """Manually add a referral relationship"""
    referrer_id = request.form.get('referrer_id')
    referred_id = request.form.get('referred_id')

    if not referrer_id or not referred_id:
        flash('IDs requeridos', 'error')
        return redirect(url_for('admin_emergency'))

    try:
        add_referral(referrer_id, referred_id)
        flash(f'Referido agregado: {referrer_id} -> {referred_id}', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_emergency'))

@app.route('/api/emergency/validate-referral', methods=['POST'])
@admin_required
def api_emergency_validate_referral():
    """Manually validate a referral and pay bonus"""
    referrer_id = request.form.get('referrer_id')
    referred_id = request.form.get('referred_id')

    if not referrer_id or not referred_id:
        flash('IDs requeridos', 'error')
        return redirect(url_for('admin_emergency'))

    try:
        validate_referral(referrer_id, referred_id)
        flash(f'Referido validado y bonus pagado: {referrer_id} <- {referred_id}', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_emergency'))

@app.route('/api/emergency/restore-balance', methods=['POST'])
@admin_required
def api_emergency_restore_balance():
    """Restore user balance"""
    user_id = request.form.get('user_id')
    currency = request.form.get('currency', 'SE').upper()
    amount = request.form.get('amount')
    reason = request.form.get('reason', 'Emergency restore')

    if not user_id or not amount:
        flash('Datos requeridos', 'error')
        return redirect(url_for('admin_emergency'))

    try:
        amount = float(amount)
        currency_map = {'SE': 'se', 'USDT': 'usdt', 'DOGE': 'doge'}
        currency_key = currency_map.get(currency, 'se')

        update_balance(user_id, currency_key, amount, 'add', reason)
        flash(f'Balance restaurado: +{amount} {currency} para {user_id}', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_emergency'))

@app.route('/api/emergency/unban-ip', methods=['POST'])
@admin_required
def api_emergency_unban_ip():
    """Unban all users with a specific IP"""
    ip_address = request.form.get('ip_address')

    if not ip_address:
        flash('IP requerida', 'error')
        return redirect(url_for('admin_emergency'))

    try:
        users = get_users_by_ip(ip_address)
        unbanned = 0
        for user in users:
            if user.get('banned'):
                unban_user(user['user_id'])
                unbanned += 1

        flash(f'{unbanned} usuarios desbaneados de IP {ip_address}', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_emergency'))

@app.route('/api/emergency/recalc-referrals', methods=['POST'])
@admin_required
def api_emergency_recalc_referrals():
    """Recalculate referral count for a user"""
    user_id = request.form.get('user_id')

    if not user_id:
        flash('ID requerido', 'error')
        return redirect(url_for('admin_emergency'))

    try:
        count = update_referral_count(user_id)
        flash(f'Referidos recalculados para {user_id}: {count}', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_emergency'))

@app.route('/api/emergency/reset-mining', methods=['POST'])
@admin_required
def api_emergency_reset_mining():
    """Reset mining timer for a user"""
    user_id = request.form.get('user_id')

    if not user_id:
        flash('ID requerido', 'error')
        return redirect(url_for('admin_emergency'))

    try:
        past_time = datetime.now() - timedelta(hours=24)
        update_user(user_id, last_claim=past_time)
        flash(f'Timer de minería reiniciado para {user_id}', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin_emergency'))

# ============== API ADMIN ENDPOINTS ==============

@app.route('/api/admin/user-balance-history/<user_id>')
@admin_required
def api_admin_user_balance_history(user_id):
    """Get user balance history"""
    try:
        history = get_user_balance_history(user_id, limit=50)
        return jsonify({
            'success': True,
            'user_id': user_id,
            'history': history
        })
    except Exception as e:
        logger.error(f"Error fetching balance history for {user_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/user/<user_id>')
@admin_required
def api_admin_get_user(user_id):
    """Get user details"""
    try:
        user = get_user_with_referrals(user_id)

        if user:
            return jsonify({
                'success': True,
                'user': user
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Usuario no encontrado'
            })
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/search-users')
@admin_required
def api_admin_search_users():
    """Search users"""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 20)), 100)

        if not query:
            return jsonify({
                'success': False,
                'error': 'Query parameter required'
            })

        users = search_users(query, limit=limit)

        return jsonify({
            'success': True,
            'query': query,
            'count': len(users),
            'users': users
        })
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/admin/users-stats')
@admin_required
def api_admin_users_stats():
    """Get users statistics"""
    try:
        total = get_users_count()
        try:
            banned = get_banned_users_count()
        except:
            banned = 0

        return jsonify({
            'success': True,
            'total_users': total,
            'banned_users': banned,
            'active_users': total - banned
        })
    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(e):
    return render_template('telegram_required.html'), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# ============== MÓDULO DE MISIONES DE REFERIDOS ==============
# Importar y registrar el blueprint de misiones de referidos
# Este módulo es completamente independiente del sistema de tareas existente

try:
    from referral_missions import (
        referral_missions_bp,
        init_referral_missions_tables,
        on_new_referral
    )

    # Registrar el blueprint
    app.register_blueprint(referral_missions_bp)

    # Inicializar las tablas al arrancar (solo crea si no existen)
    with app.app_context():
        init_referral_missions_tables()

    logger.info("✅ Módulo de Misiones de Referidos cargado correctamente")
    REFERRAL_MISSIONS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo de Misiones de Referidos no disponible: {e}")
    REFERRAL_MISSIONS_AVAILABLE = False
    on_new_referral = None


# Hook para agregar referidos a las misiones cuando son validados
def notify_referral_missions(referrer_id, referred_id, referred_username=None, ip_address=None):
    """
    Notifica al módulo de misiones de referidos cuando un nuevo referido es validado.
    Esta función es segura para llamar incluso si el módulo no está disponible.
    """
    if REFERRAL_MISSIONS_AVAILABLE and on_new_referral:
        try:
            on_new_referral(referrer_id, referred_id, referred_username, ip_address)
        except Exception as e:
            logger.error(f"Error al notificar misiones de referidos: {e}")


# ============== BAN SYSTEM INITIALIZATION ==============
if BAN_SYSTEM_AVAILABLE:
    try:
        with app.app_context():
            initialize_ban_system()
        logger.info("✅ Ban system tables initialized")
    except Exception as e:
        logger.error(f"⚠️ Error initializing ban system: {e}")


# ============== MÓDULO DE ADEXIUM ==============
# Plataforma de anuncios INDEPENDIENTE de Adsgram y Telega.io
# NO comparte lógica, endpoints ni variables con otras plataformas
# Agregar esta ruta en tu adexium.py

try:
    from adexium import adexium_bp, ADEXIUM_CONFIG

    # Registrar el blueprint
    app.register_blueprint(adexium_bp)

    logger.info("✅ Módulo de Adexium cargado correctamente")
    logger.info(f"   Widget ID: {ADEXIUM_CONFIG['widget_id']}")
    logger.info(f"   Límite diario: {ADEXIUM_CONFIG['max_daily_ads']} anuncios")
    logger.info(f"   Cooldown: {ADEXIUM_CONFIG['cooldown_seconds']}s ({ADEXIUM_CONFIG['cooldown_seconds']//60} min)")
    ADEXIUM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo de Adexium no disponible: {e}")
    ADEXIUM_AVAILABLE = False

# ============== RUTA DE PRUEBA ADEXIUM ==============
# Página de diagnóstico para probar el SDK de Adexium
@app.route('/adexium/test')
def adexium_test_page():
    """Página de diagnóstico de Adexium"""
    user_id = request.args.get('user_id') or get_user_id()

    if not user_id:
        user_id = "test_user"

    return render_template('adexium_test.html', user_id=user_id)

# ============== MÓDULO DE MONETAG ==============
# Cuarta plataforma de anuncios - MISMA moneda y MISMA recompensa que las demás
# Zone ID: 10311387

try:
    from monetag import monetag_bp, MONETAG_CONFIG, init_monetag_tables

    # Registrar el blueprint
    app.register_blueprint(monetag_bp)

    # Inicializar tablas de Monetag
    with app.app_context():
        init_monetag_tables()

    logger.info("✅ Módulo de Monetag cargado correctamente")
    logger.info(f"   Zone ID: {MONETAG_CONFIG['zone_id']}")
    logger.info(f"   Límite diario: {MONETAG_CONFIG['max_daily_ads']} anuncios")
    logger.info(f"   Cooldown: {MONETAG_CONFIG['cooldown_seconds']}s ({MONETAG_CONFIG['cooldown_seconds']//60} min)")
    logger.info(f"   Recompensa: {MONETAG_CONFIG['reward_per_ad']} DOGE por anuncio")
    MONETAG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo de Monetag no disponible: {e}")
    MONETAG_AVAILABLE = False


# ============== MÓDULO DE GIGAPUB ==============
# Quinta plataforma de anuncios - MISMA moneda y MISMA recompensa que las demás
# Tipo: Reward-based (on-demand)
# Placement: "principal"

try:
    from gigapub import gigapub_bp, GIGAPUB_CONFIG, init_gigapub_tables

    # Registrar el blueprint
    app.register_blueprint(gigapub_bp)

    # Inicializar tablas de GigaPub
    with app.app_context():
        init_gigapub_tables()

    logger.info("✅ Módulo de GigaPub cargado correctamente")
    logger.info(f"   Placement: {GIGAPUB_CONFIG['placement']}")
    logger.info(f"   Límite diario: {GIGAPUB_CONFIG['max_daily_ads']} anuncios")
    logger.info(f"   Cooldown: {GIGAPUB_CONFIG['cooldown_seconds']}s")
    logger.info(f"   Recompensa: {GIGAPUB_CONFIG['reward_per_ad']} DOGE por anuncio")
    GIGAPUB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo de GigaPub no disponible: {e}")
    GIGAPUB_AVAILABLE = False


# ============== MÓDULO DE TON PAYMENTS ==============
# Sistema de pagos en TON con panel de administración completo
# Soporta pagos automáticos y manuales

try:
    from ton_payment_routes import register_ton_routes

    # Registrar las rutas de TON
    register_ton_routes(app)

    logger.info("✅ Módulo de TON Payments cargado correctamente")
    logger.info("   Panel admin: /admin/ton-payments")
    logger.info("   API endpoints: /api/ton/*")
    TON_PAYMENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo de TON Payments no disponible: {e}")
    TON_PAYMENTS_AVAILABLE = False


# ============== MÓDULO DE ADSGRAM BOOST ==============
# Sistema de Boost de Minería x2 con anuncios AdsGram
# NO paga dinero directo, solo activa boost
# Block ID: 20479

try:
    from adsgram_boost import adsgram_boost_bp, init_adsgram_boost_tables, ADSGRAM_BOOST_CONFIG

    # Registrar el blueprint
    app.register_blueprint(adsgram_boost_bp)

    # Inicializar tablas
    with app.app_context():
        init_adsgram_boost_tables()

    logger.info("✅ Módulo de AdsGram Boost cargado correctamente")
    logger.info(f"   Block ID: {ADSGRAM_BOOST_CONFIG['block_id']}")
    logger.info(f"   Multiplicador: x{ADSGRAM_BOOST_CONFIG['boost_multiplier']}")
    logger.info(f"   Duración: {ADSGRAM_BOOST_CONFIG['boost_duration_minutes']} minutos")
    logger.info(f"   Límite diario: {ADSGRAM_BOOST_CONFIG['max_daily_boosts']} boosts")
    logger.info(f"   Cooldown: {ADSGRAM_BOOST_CONFIG['cooldown_minutes']} minutos")
    ADSGRAM_BOOST_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo de AdsGram Boost no disponible: {e}")
    ADSGRAM_BOOST_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Error cargando módulo de AdsGram Boost: {e}")
    ADSGRAM_BOOST_AVAILABLE = False


# ============== MÓDULO DE ONCLICKA PTS ==============
# Sistema de PTS con anuncios OnClickA
# - Tareas de anuncios
# - Check-in diario
# - Ranking semanal con premios DOGE
# - Boost de minería x2
# AD Code ID: 408797

try:
    from onclicka_pts_system import (
        onclicka_bp, init_pts_tables,
        ONCLICKA_CONFIG, PTS_CONFIG, BOOST_CONFIG, RANKING_CONFIG,
        get_onclicka_boost_multiplier
    )

    # Registrar el blueprint
    app.register_blueprint(onclicka_bp)

    # Inicializar tablas
    with app.app_context():
        init_pts_tables()

    logger.info("✅ Módulo de OnClickA PTS cargado correctamente")
    logger.info(f"   AD Code ID: {ONCLICKA_CONFIG['ad_code_id']}")
    logger.info(f"   Cooldown anuncios: {ONCLICKA_CONFIG['cooldown_seconds']}s")
    logger.info(f"   PTS por anuncio: {PTS_CONFIG['ad_reward']}")
    logger.info(f"   Límite diario PTS: {PTS_CONFIG['daily_limit']}")
    logger.info(f"   Boost x{BOOST_CONFIG['multiplier']} por {BOOST_CONFIG['duration_minutes']} min")
    logger.info(f"   Ranking: {RANKING_CONFIG['period']} - TOP {RANKING_CONFIG['top_count']}")
    ONCLICKA_PTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo de OnClickA PTS no disponible: {e}")
    ONCLICKA_PTS_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Error cargando módulo de OnClickA PTS: {e}")
    ONCLICKA_PTS_AVAILABLE = False


# ============================================
# ROULETTE PTS SYSTEM
# ============================================
# Ruleta gratuita de PTS cada 20 minutos
# Premios: 5, 7, 10, 13, 15 PTS
# Opción de duplicar viendo anuncio Monetag

try:
    from roulette_pts_system import (
        roulette_pts_bp, init_roulette_tables
    )

    # Registrar el blueprint
    app.register_blueprint(roulette_pts_bp)

    # Inicializar tablas
    with app.app_context():
        init_roulette_tables()

    logger.info("✅ Módulo de Ruleta PTS cargado correctamente")
    logger.info("   Premios: 5, 7, 10, 13, 15 PTS")
    logger.info("   Cooldown: 20 minutos")
    logger.info("   Duplicar con anuncio Monetag")
    ROULETTE_PTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo de Ruleta PTS no disponible: {e}")
    ROULETTE_PTS_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Error cargando módulo de Ruleta PTS: {e}")
    ROULETTE_PTS_AVAILABLE = False


# ============================================
# PTS COMPETITION SYSTEM - Weekly Rankings
# ============================================
# Sistema de competencia semanal automatica
# Estados: ACTIVE, ENDED, DISTRIBUTING, DISTRIBUTED, PREPARATION
# Premios: Top 1-5 (5, 2, 1, 0.5, 0.2 DOGE)
# Minimo 2000 PTS para clasificar

try:
    from pts_competition_system import (
        pts_competition_bp, init_competition_tables,
        get_competition_state, can_earn_pts, check_and_process_competition,
        COMPETITION_CONFIG
    )

    # Registrar el blueprint
    app.register_blueprint(pts_competition_bp)

    # Inicializar tablas
    with app.app_context():
        init_competition_tables()

    logger.info("✅ Sistema de Competencia PTS cargado correctamente")
    logger.info(f"   Periodo: {COMPETITION_CONFIG['period']}")
    logger.info(f"   Distribucion: {COMPETITION_CONFIG['distribution_duration_minutes']} min")
    logger.info(f"   Preparacion: {COMPETITION_CONFIG['preparation_duration_minutes']} min")
    logger.info(f"   Min PTS: {COMPETITION_CONFIG['min_pts_qualify']}")
    PTS_COMPETITION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Sistema de Competencia PTS no disponible: {e}")
    PTS_COMPETITION_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Error cargando Sistema de Competencia PTS: {e}")
    import traceback
    traceback.print_exc()
    PTS_COMPETITION_AVAILABLE = False


# ============== MINING MACHINE ROUTES ==============
try:
    from mining_machine_routes import register_mining_machine_routes
    register_mining_machine_routes(
        app, get_user, update_user, get_user_id,
        check_channel_or_redirect, safe_user_dict,
        calculate_unclaimed, get_effective_rate, execute_query
    )
    logger.info("✅ Mining machine routes registered successfully")
except ImportError as e:
    logger.warning(f"⚠️ Mining machine routes not available: {e}")
except Exception as e:
    logger.error(f"❌ Error registering mining machine routes: {e}")


# ============== MANUAL DEPOSITS SYSTEM ==============
try:
    from manual_deposit_routes import register_manual_deposits
    register_manual_deposits(app)
    logger.info("✅ Manual Deposits system loaded successfully")
    MANUAL_DEPOSITS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Manual Deposits system not available: {e}")
    MANUAL_DEPOSITS_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Error loading Manual Deposits system: {e}")
    MANUAL_DEPOSITS_AVAILABLE = False


# ============== USER TASKS PROMOTION SYSTEM ==============
try:
    from user_tasks_routes import user_tasks_bp
    from user_tasks_system import init_user_tasks_table

    # Registrar el blueprint
    app.register_blueprint(user_tasks_bp)

    # Inicializar tablas
    with app.app_context():
        init_user_tasks_table()

    logger.info("✅ User Tasks Promotion system loaded successfully")
    USER_TASKS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ User Tasks Promotion system not available: {e}")
    USER_TASKS_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Error loading User Tasks Promotion system: {e}")
    import traceback
    traceback.print_exc()
    USER_TASKS_AVAILABLE = False


# ============================================
# 🔗 SHRINKEARN LINK SYSTEM
# ============================================
try:
    from shrinkearn_system import (
        shrinkearn_bp,
        init_shrinkearn_tables,
        SHRINKEARN_CONFIG,
        SHRINKEARN_MISSIONS
    )

    # Registrar el blueprint
    app.register_blueprint(shrinkearn_bp)

    # Inicializar tablas
    with app.app_context():
        init_shrinkearn_tables()

    SHRINKEARN_AVAILABLE = True
    logger.info("✅ ShrinkEarn system loaded successfully")
except ImportError as e:
    SHRINKEARN_AVAILABLE = False
    logger.warning(f"⚠️ ShrinkEarn system not available: {e}")
except Exception as e:
    SHRINKEARN_AVAILABLE = False
    logger.error(f"❌ Error loading ShrinkEarn system: {e}")


# ============================================
# 🔗 LINK CENTER ROUTE (Hub for link platforms)
# ============================================

@app.route('/explore/link-center')
def explore_link_center():
    """Centro de Enlaces - Hub for all link shortener platforms"""
    user_id = get_user_id()
    if not user_id:
        return render_template('telegram_required.html')

    user = get_user(user_id)
    if not user:
        return render_template('telegram_required.html')

    user = safe_user_dict(user)

    # MANDATORY: Check channel membership
    channel_check = check_channel_or_redirect(user_id)
    if channel_check:
        return channel_check

    return render_template('link_center.html',
                         user=user,
                         user_id=user_id,
                         show_support_button=True)


# ============== MAIN ==============

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
