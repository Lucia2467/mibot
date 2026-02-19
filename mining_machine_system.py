"""
mining_machine_system.py - Sistema de Máquinas de Minería DOGE
Permite a los usuarios comprar máquinas de minería que generan DOGE pasivamente.

Especificaciones:
- Precio: 10 DOGE
- Ganancia total: 15 DOGE en 30 días
- Distribución: Lineal (0.5 DOGE/día)
- Solo 1 máquina activa por usuario
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from db import execute_query, get_cursor

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURACIÓN DE LA MÁQUINA DE MINERÍA
# ============================================
MACHINE_CONFIG = {
    'price': Decimal('10.0'),           # Precio en DOGE
    'total_earnings': Decimal('15.0'),   # Ganancia total en DOGE
    'duration_days': 30,                 # Duración en días
    'daily_rate': Decimal('0.5'),        # 15 DOGE / 30 días = 0.5 DOGE/día
    'name': 'DOGE Miner Pro',
    'description': 'Máquina de minería premium que genera DOGE automáticamente',
    'level': 'Premium'
}

# ============================================
# INICIALIZACIÓN DE TABLA
# ============================================
def init_mining_machines_table():
    """Crea la tabla de máquinas de minería si no existe"""
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS mining_machines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                machine_type VARCHAR(50) DEFAULT 'doge_miner_pro',
                price_paid DECIMAL(20, 8) NOT NULL,
                total_earnings DECIMAL(20, 8) NOT NULL,
                duration_days INT NOT NULL DEFAULT 30,
                daily_rate DECIMAL(20, 8) NOT NULL,
                earned_so_far DECIMAL(20, 8) DEFAULT 0.00000000,
                last_claim_at DATETIME DEFAULT NULL,
                started_at DATETIME NOT NULL,
                ends_at DATETIME NOT NULL,
                is_active TINYINT(1) DEFAULT 1,
                is_completed TINYINT(1) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_is_active (is_active),
                INDEX idx_ends_at (ends_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("✅ Tabla mining_machines creada/verificada")
        return True
    except Exception as e:
        logger.error(f"❌ Error creando tabla mining_machines: {e}")
        return False


# ============================================
# FUNCIONES PRINCIPALES
# ============================================
def get_user_active_machine(user_id):
    """Obtiene la máquina activa del usuario (si existe)"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM mining_machines 
                WHERE user_id = %s AND is_active = 1 AND is_completed = 0
                ORDER BY created_at DESC 
                LIMIT 1
            """, (str(user_id),))
            machine = cursor.fetchone()
            
            if machine:
                return dict(machine) if hasattr(machine, 'keys') else machine
            return None
    except Exception as e:
        logger.error(f"Error obteniendo máquina activa: {e}")
        return None


def get_user_machine_history(user_id, limit=10):
    """Obtiene el historial de máquinas del usuario"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM mining_machines 
                WHERE user_id = %s
                ORDER BY created_at DESC 
                LIMIT %s
            """, (str(user_id), limit))
            machines = cursor.fetchall()
            return [dict(m) if hasattr(m, 'keys') else m for m in machines]
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        return []


def can_purchase_machine(user_id, doge_balance):
    """Verifica si el usuario puede comprar una máquina"""
    # Verificar balance suficiente
    if Decimal(str(doge_balance)) < MACHINE_CONFIG['price']:
        return False, 'insufficient_balance', f"Necesitas {MACHINE_CONFIG['price']} DOGE para comprar"
    
    # Verificar si ya tiene una máquina activa
    active_machine = get_user_active_machine(user_id)
    if active_machine:
        ends_at = active_machine.get('ends_at')
        if isinstance(ends_at, str):
            ends_at = datetime.fromisoformat(ends_at)
        
        remaining = ends_at - datetime.now()
        days_left = max(0, remaining.days)
        
        return False, 'machine_active', f"Ya tienes una máquina activa. Termina en {days_left} días"
    
    return True, 'can_purchase', "Puedes comprar la máquina"


def purchase_machine(user_id):
    """
    Procesa la compra de una máquina de minería.
    IMPORTANTE: Esta función asume que ya se verificó que el usuario puede comprar.
    La deducción del balance se hace en app.py para mantener consistencia.
    """
    try:
        now = datetime.now()
        ends_at = now + timedelta(days=MACHINE_CONFIG['duration_days'])
        
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO mining_machines 
                (user_id, machine_type, price_paid, total_earnings, duration_days, 
                 daily_rate, earned_so_far, last_claim_at, started_at, ends_at, 
                 is_active, is_completed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(user_id),
                'doge_miner_pro',
                str(MACHINE_CONFIG['price']),
                str(MACHINE_CONFIG['total_earnings']),
                MACHINE_CONFIG['duration_days'],
                str(MACHINE_CONFIG['daily_rate']),
                '0.00000000',
                now,  # last_claim_at inicial
                now,
                ends_at,
                1,  # is_active
                0   # is_completed
            ))
        
        logger.info(f"✅ Máquina de minería comprada por usuario {user_id}")
        
        return {
            'success': True,
            'machine': {
                'user_id': str(user_id),
                'machine_type': 'doge_miner_pro',
                'price_paid': float(MACHINE_CONFIG['price']),
                'total_earnings': float(MACHINE_CONFIG['total_earnings']),
                'duration_days': MACHINE_CONFIG['duration_days'],
                'daily_rate': float(MACHINE_CONFIG['daily_rate']),
                'started_at': now.isoformat(),
                'ends_at': ends_at.isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"❌ Error comprando máquina: {e}")
        return {'success': False, 'error': str(e)}


def calculate_available_earnings(machine):
    """
    Calcula las ganancias disponibles para reclamar.
    Las ganancias se acumulan de forma lineal basado en el tiempo transcurrido.
    """
    if not machine:
        return Decimal('0')
    
    now = datetime.now()
    
    # Parsear fechas si son strings
    started_at = machine.get('started_at')
    ends_at = machine.get('ends_at')
    last_claim_at = machine.get('last_claim_at')
    
    if isinstance(started_at, str):
        started_at = datetime.fromisoformat(started_at)
    if isinstance(ends_at, str):
        ends_at = datetime.fromisoformat(ends_at)
    if isinstance(last_claim_at, str):
        last_claim_at = datetime.fromisoformat(last_claim_at)
    
    # Si la máquina ya terminó
    if now >= ends_at:
        total_earnings = Decimal(str(machine.get('total_earnings', 0)))
        earned_so_far = Decimal(str(machine.get('earned_so_far', 0)))
        return (total_earnings - earned_so_far).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
    
    # Calcular tiempo transcurrido desde el último claim
    time_since_claim = now - last_claim_at
    hours_elapsed = Decimal(str(time_since_claim.total_seconds())) / Decimal('3600')
    
    # Calcular ganancia por hora (daily_rate / 24)
    daily_rate = Decimal(str(machine.get('daily_rate', '0.5')))
    hourly_rate = daily_rate / Decimal('24')
    
    # Ganancias acumuladas desde el último claim
    pending_earnings = (hourly_rate * hours_elapsed).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
    
    # Asegurar que no exceda el máximo restante
    total_earnings = Decimal(str(machine.get('total_earnings', 0)))
    earned_so_far = Decimal(str(machine.get('earned_so_far', 0)))
    max_remaining = total_earnings - earned_so_far
    
    return min(pending_earnings, max_remaining)


def claim_machine_earnings(user_id):
    """
    Reclama las ganancias disponibles de la máquina.
    Retorna el monto reclamado y actualiza la base de datos.
    """
    try:
        machine = get_user_active_machine(user_id)
        if not machine:
            return {
                'success': False,
                'error': 'no_active_machine',
                'message': 'No tienes ninguna máquina de minería activa'
            }
        
        available = calculate_available_earnings(machine)
        
        if available <= Decimal('0'):
            return {
                'success': False,
                'error': 'no_earnings',
                'message': 'No hay ganancias disponibles para reclamar'
            }
        
        now = datetime.now()
        new_earned = Decimal(str(machine.get('earned_so_far', 0))) + available
        
        # Parsear ends_at
        ends_at = machine.get('ends_at')
        if isinstance(ends_at, str):
            ends_at = datetime.fromisoformat(ends_at)
        
        # Verificar si la máquina se completó
        total_earnings = Decimal(str(machine.get('total_earnings', 0)))
        is_completed = (new_earned >= total_earnings) or (now >= ends_at)
        
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE mining_machines 
                SET earned_so_far = %s,
                    last_claim_at = %s,
                    is_completed = %s,
                    is_active = %s,
                    updated_at = %s
                WHERE id = %s
            """, (
                str(new_earned),
                now,
                1 if is_completed else 0,
                0 if is_completed else 1,
                now,
                machine['id']
            ))
        
        logger.info(f"✅ Usuario {user_id} reclamó {available} DOGE de la máquina")
        
        return {
            'success': True,
            'amount': float(available),
            'new_total_earned': float(new_earned),
            'is_completed': is_completed,
            'message': f'¡Has reclamado {float(available):.4f} DOGE!'
        }
    
    except Exception as e:
        logger.error(f"❌ Error reclamando ganancias: {e}")
        return {
            'success': False,
            'error': 'claim_error',
            'message': str(e)
        }


def get_machine_status(user_id):
    """Obtiene el estado completo de la máquina del usuario"""
    machine = get_user_active_machine(user_id)
    
    if not machine:
        return {
            'has_machine': False,
            'can_purchase': True,
            'machine_config': {
                'price': float(MACHINE_CONFIG['price']),
                'total_earnings': float(MACHINE_CONFIG['total_earnings']),
                'duration_days': MACHINE_CONFIG['duration_days'],
                'daily_rate': float(MACHINE_CONFIG['daily_rate']),
                'name': MACHINE_CONFIG['name'],
                'level': MACHINE_CONFIG['level']
            }
        }
    
    now = datetime.now()
    
    # Parsear fechas
    started_at = machine.get('started_at')
    ends_at = machine.get('ends_at')
    
    if isinstance(started_at, str):
        started_at = datetime.fromisoformat(started_at)
    if isinstance(ends_at, str):
        ends_at = datetime.fromisoformat(ends_at)
    
    # Calcular progreso
    total_duration = (ends_at - started_at).total_seconds()
    elapsed = (now - started_at).total_seconds()
    progress_percent = min(100, (elapsed / total_duration) * 100) if total_duration > 0 else 0
    
    # Tiempo restante
    remaining = ends_at - now
    days_remaining = max(0, remaining.days)
    hours_remaining = max(0, int((remaining.seconds // 3600)))
    
    # Ganancias
    earned_so_far = Decimal(str(machine.get('earned_so_far', 0)))
    total_earnings = Decimal(str(machine.get('total_earnings', 0)))
    available_earnings = calculate_available_earnings(machine)
    
    return {
        'has_machine': True,
        'can_purchase': False,
        'machine': {
            'id': machine['id'],
            'type': machine.get('machine_type', 'doge_miner_pro'),
            'name': MACHINE_CONFIG['name'],
            'level': MACHINE_CONFIG['level'],
            'price_paid': float(machine.get('price_paid', 0)),
            'total_earnings': float(total_earnings),
            'daily_rate': float(machine.get('daily_rate', 0)),
            'earned_so_far': float(earned_so_far),
            'available_earnings': float(available_earnings),
            'started_at': started_at.isoformat(),
            'ends_at': ends_at.isoformat(),
            'is_active': bool(machine.get('is_active')),
            'is_completed': bool(machine.get('is_completed'))
        },
        'progress': {
            'percent': round(progress_percent, 2),
            'days_remaining': days_remaining,
            'hours_remaining': hours_remaining,
            'earnings_percent': round((float(earned_so_far) / float(total_earnings)) * 100, 2) if float(total_earnings) > 0 else 0
        },
        'machine_config': {
            'price': float(MACHINE_CONFIG['price']),
            'total_earnings': float(MACHINE_CONFIG['total_earnings']),
            'duration_days': MACHINE_CONFIG['duration_days'],
            'daily_rate': float(MACHINE_CONFIG['daily_rate']),
            'name': MACHINE_CONFIG['name'],
            'level': MACHINE_CONFIG['level']
        }
    }


def complete_expired_machines():
    """
    Marca como completadas las máquinas que han expirado.
    Esta función debe ejecutarse periódicamente (cron job).
    """
    try:
        now = datetime.now()
        
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE mining_machines 
                SET is_completed = 1, is_active = 0, updated_at = %s
                WHERE ends_at <= %s AND is_completed = 0 AND is_active = 1
            """, (now, now))
            
            affected = cursor.rowcount
        
        if affected > 0:
            logger.info(f"✅ {affected} máquinas marcadas como completadas")
        
        return affected
    
    except Exception as e:
        logger.error(f"❌ Error completando máquinas expiradas: {e}")
        return 0


# ============================================
# UTILIDADES
# ============================================
def get_machine_config():
    """Retorna la configuración de la máquina"""
    return {
        'price': float(MACHINE_CONFIG['price']),
        'total_earnings': float(MACHINE_CONFIG['total_earnings']),
        'duration_days': MACHINE_CONFIG['duration_days'],
        'daily_rate': float(MACHINE_CONFIG['daily_rate']),
        'name': MACHINE_CONFIG['name'],
        'description': MACHINE_CONFIG['description'],
        'level': MACHINE_CONFIG['level'],
        'roi_percent': round((float(MACHINE_CONFIG['total_earnings']) / float(MACHINE_CONFIG['price']) - 1) * 100, 1)
    }


# Inicializar tabla al importar el módulo
try:
    init_mining_machines_table()
except Exception as e:
    logger.warning(f"⚠️ No se pudo inicializar tabla mining_machines al importar: {e}")
