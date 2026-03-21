"""
vpn_system.py - Sistema de Detección de VPN/Proxy para SALLY-E
Detecta conexiones VPN, Proxy y Datacenter
Version: 2.0.0 - Fix falsos positivos
"""

import os
import time
import logging
import requests
from functools import lru_cache
from flask import Blueprint, request, jsonify, render_template

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN
# ============================================

VPN_CONFIG = {
    # Habilitar/deshabilitar detección de VPN
    'enabled': True,

    # ⚠️ FIX: block_hosting desactivado
    # ip-api.com marca como "hosting" a datacenters PERO también a muchos
    # ISPs móviles y redes corporativas, especialmente en Latinoamérica.
    # Activar esto causa falsos positivos masivos. Solo bloquear proxies reales.
    'block_hosting': False,

    # Bloquear proxies detectados (señal confiable)
    'block_proxy': True,

    # ⚠️ FIX: TTL reducido a 60s
    # Con 300s el usuario quedaba bloqueado 5 minutos aunque quitara la VPN.
    # Con 60s, al presionar "Verificar" el caché ya expiró y se re-verifica.
    'cache_ttl': 60,

    # IPs en whitelist (nunca bloquear)
    'whitelist_ips': [],

    # User agents que no se bloquean
    'whitelist_user_agents': [
        'TelegramBot',
    ],

    # Rutas excluidas de la verificación
    'excluded_paths': [
        '/vpn-blocked',
        '/admin',
        '/static',
        '/api/vpn-check',
        '/api/vpn-clear-cache',
    ],
}

# ============================================
# CACHÉ EN MEMORIA
# ============================================

_vpn_cache = {}

def _clean_old_cache():
    """Limpia entradas de caché expiradas"""
    current_time = time.time()
    expired_keys = [
        key for key, value in _vpn_cache.items()
        if current_time - value.get('timestamp', 0) > VPN_CONFIG['cache_ttl']
    ]
    for key in expired_keys:
        del _vpn_cache[key]

def _get_cached_result(ip):
    """Obtiene resultado cacheado si existe y no ha expirado"""
    if ip in _vpn_cache:
        cached = _vpn_cache[ip]
        if time.time() - cached.get('timestamp', 0) < VPN_CONFIG['cache_ttl']:
            return cached.get('result')
    return None

def _set_cached_result(ip, result):
    """Guarda resultado en caché"""
    _clean_old_cache()
    _vpn_cache[ip] = {
        'timestamp': time.time(),
        'result': result
    }

def clear_cache_for_ip(ip):
    """Elimina el caché de una IP específica (para cuando el usuario presiona Verificar)"""
    if ip in _vpn_cache:
        del _vpn_cache[ip]
        logger.info(f"[VPN] Cache cleared for {ip}")

# ============================================
# DETECCIÓN DE VPN/PROXY
# ============================================

def get_client_ip():
    """Obtiene la IP real del cliente"""
    if request.headers.get('CF-Connecting-IP'):
        return request.headers.get('CF-Connecting-IP')
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def check_vpn_api(ip):
    """
    Verifica si una IP es VPN/Proxy usando ip-api.com (gratis)
    Límite: 45 requests/minuto

    ⚠️ FIX CRÍTICO: 'is_vpn' ya NO se mapea a 'is_hosting'.
    El campo hosting=True en ip-api.com indica que la IP pertenece a un
    datacenter/proveedor de hosting, pero esto incluye ISPs móviles,
    redes universitarias y corporativas, causando falsos positivos.
    Solo 'proxy=True' es señal confiable de proxy/VPN real.
    """
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,message,proxy,hosting,query"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            if data.get('status') == 'success':
                is_proxy   = data.get('proxy', False)
                is_hosting = data.get('hosting', False)

                # ⚠️ FIX: is_vpn ahora requiere AMBAS señales (proxy + hosting)
                # Solo marcar como VPN si es proxy conocido Y viene de datacenter.
                # Esto elimina los falsos positivos de usuarios en redes corporativas/móviles.
                is_vpn = is_proxy and is_hosting

                return {
                    'ip': ip,
                    'is_vpn': is_vpn,
                    'is_proxy': is_proxy,
                    'is_hosting': is_hosting,
                    'raw_data': data
                }
            else:
                logger.warning(f"[VPN] API error for {ip}: {data.get('message', 'Unknown')}")
                return None
        else:
            logger.warning(f"[VPN] API HTTP error: {response.status_code}")
            return None

    except requests.Timeout:
        logger.warning(f"[VPN] API timeout for {ip}")
        return None
    except Exception as e:
        logger.error(f"[VPN] API error for {ip}: {e}")
        return None

def check_vpn_proxycheck(ip):
    """
    Alternativa: usar proxycheck.io (100 consultas/día gratis)
    Solo se llama si ip-api.com falla.
    """
    try:
        url = f"https://proxycheck.io/v2/{ip}?vpn=1&asn=1"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            if data.get('status') == 'ok' and ip in data:
                ip_data   = data[ip]
                is_proxy  = ip_data.get('proxy') == 'yes'
                # ⚠️ FIX: solo 'vpn' y 'tor' son señales confiables, no 'hosting'
                vpn_types = ['vpn', 'tor']
                is_vpn    = ip_data.get('type', '').lower() in vpn_types

                return {
                    'ip': ip,
                    'is_vpn': is_vpn,
                    'is_proxy': is_proxy,
                    'raw_data': data
                }

        return None

    except Exception as e:
        logger.error(f"[VPN] Proxycheck error for {ip}: {e}")
        return None

def is_vpn_or_proxy(ip=None):
    """
    Verifica si la IP es VPN o Proxy.
    Returns: dict con resultado o None si no se pudo verificar.
    """
    if not VPN_CONFIG['enabled']:
        return {'vpn_detected': False, 'reason': 'disabled'}

    if ip is None:
        ip = get_client_ip()

    # Whitelist
    if ip in VPN_CONFIG['whitelist_ips']:
        return {'vpn_detected': False, 'reason': 'whitelisted'}

    # IPs locales nunca son VPN
    if ip in ['127.0.0.1', 'localhost', '::1'] or ip.startswith('192.168.') or ip.startswith('10.'):
        return {'vpn_detected': False, 'reason': 'local_ip'}

    # Verificar caché
    cached = _get_cached_result(ip)
    if cached is not None:
        logger.debug(f"[VPN] Cache hit for {ip}: {cached}")
        return cached

    # Llamar a la API principal
    result = check_vpn_api(ip)

    # Si falla, usar alternativa
    if result is None:
        result = check_vpn_proxycheck(ip)

    # Si ambas fallan → fail-open (no bloquear)
    if result is None:
        final_result = {
            'vpn_detected': False,
            'reason': 'api_error',
            'ip': ip
        }
        _set_cached_result(ip, final_result)
        return final_result

    # Determinar si bloquear
    vpn_detected = False
    reasons = []

    # ⚠️ FIX: block_hosting está desactivado por default.
    # Solo se activa si el admin lo habilita conscientemente.
    if VPN_CONFIG['block_hosting'] and result.get('is_vpn'):
        vpn_detected = True
        reasons.append('vpn_hosting')

    # proxy=True solo → bloquear (señal más confiable)
    if VPN_CONFIG['block_proxy'] and result.get('is_proxy'):
        vpn_detected = True
        reasons.append('proxy')

    final_result = {
        'vpn_detected': vpn_detected,
        'reason': ','.join(reasons) if reasons else 'clean',
        'ip': ip,
        'details': {
            'is_vpn':     result.get('is_vpn', False),
            'is_proxy':   result.get('is_proxy', False),
            'is_hosting': result.get('is_hosting', False),
        }
    }

    _set_cached_result(ip, final_result)

    if vpn_detected:
        logger.warning(f"[VPN] Detected VPN/Proxy: {ip} - Reason: {final_result['reason']}")

    return final_result

# ============================================
# BLUEPRINT Y RUTAS
# ============================================

vpn_bp = Blueprint('vpn', __name__)

@vpn_bp.route('/api/vpn-check', methods=['GET'])
def api_vpn_check():
    """
    Endpoint para verificar si la conexión usa VPN/Proxy.
    Llamado desde el frontend (vpn_detector.js).
    """
    try:
        ip = get_client_ip()
        result = is_vpn_or_proxy(ip)

        return jsonify({
            'success': True,
            'vpn_detected': result.get('vpn_detected', False),
            'ip': ip,
            'reason': result.get('reason', 'unknown')
        })

    except Exception as e:
        logger.error(f"[VPN] Check error: {e}")
        return jsonify({
            'success': False,
            'vpn_detected': False,
            'error': str(e)
        })

@vpn_bp.route('/api/vpn-clear-cache', methods=['POST'])
def api_vpn_clear_cache():
    """
    ⚠️ NUEVO: Limpia el caché de una IP para forzar re-verificación.
    Llamado cuando el usuario presiona "Verificar Conexión" en vpn_blocked.html.
    Sin esto, el usuario quedaba bloqueado hasta que expirara el caché (antes 5 min).
    """
    try:
        ip = get_client_ip()
        clear_cache_for_ip(ip)
        return jsonify({'success': True, 'ip': ip})
    except Exception as e:
        logger.error(f"[VPN] Clear cache error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@vpn_bp.route('/vpn-blocked')
def vpn_blocked_page():
    """Página mostrada cuando se detecta VPN/Proxy"""
    user_id = request.args.get('user_id', '')
    return render_template('vpn_blocked.html', user_id=user_id)

# ============================================
# MIDDLEWARE / DECORADOR
# ============================================

def vpn_check_required(f):
    """
    Decorador para rutas que requieren verificación de VPN.
    Uso: @vpn_check_required
    """
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not VPN_CONFIG['enabled']:
            return f(*args, **kwargs)

        # Verificar si la ruta está excluida
        for excluded in VPN_CONFIG['excluded_paths']:
            if request.path.startswith(excluded):
                return f(*args, **kwargs)

        # Verificar user agent
        user_agent = request.headers.get('User-Agent', '')
        for whitelisted in VPN_CONFIG['whitelist_user_agents']:
            if whitelisted.lower() in user_agent.lower():
                return f(*args, **kwargs)

        # Verificar VPN
        result = is_vpn_or_proxy()

        if result.get('vpn_detected'):
            user_id = request.args.get('user_id', '')
            return render_template('vpn_blocked.html', user_id=user_id), 403

        return f(*args, **kwargs)

    return decorated_function

# ============================================
# FUNCIONES DE ADMINISTRACIÓN
# ============================================

def add_ip_to_whitelist(ip):
    """Añade una IP a la whitelist"""
    if ip not in VPN_CONFIG['whitelist_ips']:
        VPN_CONFIG['whitelist_ips'].append(ip)
        if ip in _vpn_cache:
            del _vpn_cache[ip]
        return True
    return False

def remove_ip_from_whitelist(ip):
    """Elimina una IP de la whitelist"""
    if ip in VPN_CONFIG['whitelist_ips']:
        VPN_CONFIG['whitelist_ips'].remove(ip)
        return True
    return False

def get_vpn_stats():
    """Obtiene estadísticas del sistema VPN"""
    return {
        'enabled':         VPN_CONFIG['enabled'],
        'cache_size':      len(_vpn_cache),
        'whitelist_count': len(VPN_CONFIG['whitelist_ips']),
        'block_hosting':   VPN_CONFIG['block_hosting'],
        'block_proxy':     VPN_CONFIG['block_proxy']
    }

def toggle_vpn_system(enabled):
    """Activa/desactiva el sistema de detección de VPN"""
    VPN_CONFIG['enabled'] = enabled
    return VPN_CONFIG['enabled']

# ============================================
# INICIALIZACIÓN
# ============================================

def init_vpn_system(app):
    """Inicializa el sistema de VPN en la aplicación Flask"""
    app.register_blueprint(vpn_bp)
    logger.info("✅ VPN/Proxy Detection System loaded")
    logger.info(f"   Enabled:          {VPN_CONFIG['enabled']}")
    logger.info(f"   Block Hosting:    {VPN_CONFIG['block_hosting']} (desactivado para evitar falsos positivos)")
    logger.info(f"   Block Proxy:      {VPN_CONFIG['block_proxy']}")
    logger.info(f"   Cache TTL:        {VPN_CONFIG['cache_ttl']}s")
