"""
manual_deposit_routes.py - Sistema de Depósitos Manuales
Control total desde el panel administrativo
No hay acreditación automática
"""

import os
import uuid
import logging
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from db import get_cursor, execute_query

logger = logging.getLogger(__name__)

# Blueprint
manual_deposits_bp = Blueprint('manual_deposits', __name__)

# Configuración de uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'deposits')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Crear carpeta de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================
# CONFIGURACIÓN DE DEPÓSITO
# ============================================
DEPOSIT_CONFIG = {
    'wallet_address': 'DJDb6WTDhHv6r8E23ZXEZguJeHJjy72tfk',  # Wallet DOGE - CAMBIAR POR TU WALLET REAL
    'binance_pay_id': '366671719',  # Binance Pay ID - CAMBIAR POR TU ID REAL
    'min_deposit': 1.0,  # Mínimo 1 DOGE
    'wallet_currencies': ['DOGE'],  # Solo DOGE para wallet
    'binance_currencies': ['DOGE', 'USDT', 'BNB', 'BTC', 'ETH', 'USDC', 'BUSD', 'XRP', 'ADA', 'SOL', 'DOT', 'MATIC', 'SHIB', 'LTC', 'TRX']  # Monedas Binance Pay
}

# Estados de depósito
DEPOSIT_STATUS = {
    'pending': 'Pendiente',
    'approved': 'Aprobado',
    'rejected': 'Rechazado',
    'auto_rejected': 'Rechazado (Monto mínimo)'
}


def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    """Decorador para requerir autenticación de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# TABLA DE DEPÓSITOS - Inicialización
# ============================================
def init_deposits_table():
    """Crear tabla de depósitos si no existe"""
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS manual_deposits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                deposit_id VARCHAR(100) NOT NULL UNIQUE,
                user_id VARCHAR(50) NOT NULL,
                amount DECIMAL(20, 8) NOT NULL,
                currency VARCHAR(20) NOT NULL DEFAULT 'DOGE',
                method VARCHAR(50) NOT NULL DEFAULT 'wallet',
                proof_image VARCHAR(500) NOT NULL,
                tx_hash VARCHAR(200) DEFAULT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                admin_notes TEXT DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_at DATETIME DEFAULT NULL,
                processed_by VARCHAR(50) DEFAULT NULL,
                INDEX idx_user_id (user_id),
                INDEX idx_status (status),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("✅ Tabla manual_deposits creada/verificada")
        return True
    except Exception as e:
        logger.error(f"❌ Error creando tabla manual_deposits: {e}")
        return False


# ============================================
# API - USUARIO
# ============================================

@manual_deposits_bp.route('/api/deposit/config', methods=['GET'])
def get_deposit_config():
    """Obtener configuración de depósito"""
    return jsonify({
        'success': True,
        'config': {
            'wallet_address': DEPOSIT_CONFIG['wallet_address'],
            'binance_pay_id': DEPOSIT_CONFIG['binance_pay_id'],
            'min_deposit': DEPOSIT_CONFIG['min_deposit'],
            'wallet_currencies': DEPOSIT_CONFIG['wallet_currencies'],
            'binance_currencies': DEPOSIT_CONFIG['binance_currencies']
        }
    })


@manual_deposits_bp.route('/api/deposit/submit', methods=['POST'])
def submit_deposit():
    """Enviar solicitud de depósito"""
    try:
        user_id = request.form.get('user_id')
        amount = request.form.get('amount')
        currency = request.form.get('currency', 'DOGE').upper()
        method = request.form.get('method', 'wallet').lower()
        tx_hash = request.form.get('tx_hash', '').strip()

        # Validaciones básicas
        if not user_id:
            return jsonify({'success': False, 'error': 'ID de usuario requerido'}), 400

        if not amount:
            return jsonify({'success': False, 'error': 'Monto requerido'}), 400

        try:
            amount = float(amount)
        except ValueError:
            return jsonify({'success': False, 'error': 'Monto inválido'}), 400

        # Validar método
        if method not in ['wallet', 'binance']:
            return jsonify({'success': False, 'error': 'Método no válido'}), 400

        # Validar moneda según método
        if method == 'wallet' and currency not in DEPOSIT_CONFIG['wallet_currencies']:
            return jsonify({'success': False, 'error': f'Solo se permite {", ".join(DEPOSIT_CONFIG["wallet_currencies"])} para depósitos por wallet'}), 400

        if method == 'binance' and currency not in DEPOSIT_CONFIG['binance_currencies']:
            return jsonify({'success': False, 'error': f'Moneda no soportada por Binance Pay'}), 400

        # Validar comprobante
        if 'proof_image' not in request.files:
            return jsonify({'success': False, 'error': 'Comprobante de pago requerido'}), 400

        file = request.files['proof_image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Comprobante de pago requerido'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Formato de imagen no permitido. Use PNG, JPG, JPEG, GIF o WEBP'}), 400

        # Verificar tamaño del archivo
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > MAX_FILE_SIZE:
            return jsonify({'success': False, 'error': 'La imagen es demasiado grande. Máximo 5MB'}), 400

        # Determinar estado inicial
        # Si el monto es menor a 1 DOGE, rechazar automáticamente
        if amount < DEPOSIT_CONFIG['min_deposit']:
            status = 'auto_rejected'
        else:
            status = 'pending'

        # Generar ID único y guardar imagen
        deposit_id = f"DEP-{uuid.uuid4().hex[:12].upper()}"
        filename = secure_filename(f"{deposit_id}_{file.filename}")
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Guardar URL relativa
        proof_url = f"/static/uploads/deposits/{filename}"

        # Insertar en base de datos
        execute_query("""
            INSERT INTO manual_deposits
            (deposit_id, user_id, amount, currency, method, proof_image, tx_hash, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (deposit_id, user_id, amount, currency, method, proof_url, tx_hash or None, status))

        logger.info(f"📥 Nuevo depósito: {deposit_id} - Usuario: {user_id} - {amount} {currency} - Estado: {status}")

        # Mensaje según estado
        if status == 'auto_rejected':
            return jsonify({
                'success': False,
                'error': f'El monto mínimo de depósito es {DEPOSIT_CONFIG["min_deposit"]} DOGE. Tu depósito ha sido rechazado automáticamente.',
                'deposit_id': deposit_id,
                'status': status
            }), 400

        return jsonify({
            'success': True,
            'message': 'Depósito enviado correctamente. Será revisado por un administrador.',
            'deposit_id': deposit_id,
            'status': status
        })

    except Exception as e:
        logger.error(f"❌ Error en submit_deposit: {e}")
        return jsonify({'success': False, 'error': 'Error al procesar el depósito'}), 500


@manual_deposits_bp.route('/api/deposit/history', methods=['GET'])
def get_deposit_history():
    """Obtener historial de depósitos del usuario"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'ID de usuario requerido'}), 400

        with get_cursor() as cursor:
            cursor.execute("""
                SELECT deposit_id, amount, currency, method, status, created_at, processed_at
                FROM manual_deposits
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 50
            """, (user_id,))
            deposits = cursor.fetchall()

        # Formatear fechas
        formatted_deposits = []
        for dep in deposits:
            formatted_deposits.append({
                'deposit_id': dep['deposit_id'],
                'amount': float(dep['amount']),
                'currency': dep['currency'],
                'method': dep['method'],
                'status': dep['status'],
                'status_text': DEPOSIT_STATUS.get(dep['status'], dep['status']),
                'created_at': dep['created_at'].isoformat() if dep['created_at'] else None,
                'processed_at': dep['processed_at'].isoformat() if dep['processed_at'] else None
            })

        return jsonify({
            'success': True,
            'deposits': formatted_deposits
        })

    except Exception as e:
        logger.error(f"❌ Error en get_deposit_history: {e}")
        return jsonify({'success': False, 'error': 'Error al obtener historial'}), 500


# ============================================
# PANEL ADMINISTRATIVO
# ============================================

@manual_deposits_bp.route('/admin/deposits')
@admin_required
def admin_deposits():
    """Panel de administración de depósitos"""
    try:
        # Obtener filtros
        status_filter = request.args.get('status', 'all')
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page

        with get_cursor() as cursor:
            # Contar totales por estado
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM manual_deposits
                GROUP BY status
            """)
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}

            # Query con filtro
            if status_filter == 'all':
                cursor.execute("""
                    SELECT d.*, u.username, u.first_name
                    FROM manual_deposits d
                    LEFT JOIN users u ON d.user_id = u.user_id
                    ORDER BY d.created_at DESC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
            else:
                cursor.execute("""
                    SELECT d.*, u.username, u.first_name
                    FROM manual_deposits d
                    LEFT JOIN users u ON d.user_id = u.user_id
                    WHERE d.status = %s
                    ORDER BY d.created_at DESC
                    LIMIT %s OFFSET %s
                """, (status_filter, per_page, offset))

            deposits = cursor.fetchall()

            # Contar total para paginación
            if status_filter == 'all':
                cursor.execute("SELECT COUNT(*) as total FROM manual_deposits")
            else:
                cursor.execute("SELECT COUNT(*) as total FROM manual_deposits WHERE status = %s", (status_filter,))

            total = cursor.fetchone()['total']
            total_pages = (total + per_page - 1) // per_page

        return render_template('admin_manual_deposits.html',
            deposits=deposits,
            status_counts=status_counts,
            status_filter=status_filter,
            page=page,
            total_pages=total_pages,
            total=total,
            DEPOSIT_STATUS=DEPOSIT_STATUS,
            min_deposit=DEPOSIT_CONFIG['min_deposit']
        )

    except Exception as e:
        logger.error(f"❌ Error en admin_deposits: {e}")
        flash('Error al cargar depósitos', 'error')
        return redirect(url_for('admin_dashboard'))


@manual_deposits_bp.route('/admin/deposit/<deposit_id>')
@admin_required
def admin_deposit_detail(deposit_id):
    """Ver detalle de un depósito"""
    try:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT d.*, u.username, u.first_name, u.doge_balance, u.usdt_balance
                FROM manual_deposits d
                LEFT JOIN users u ON d.user_id = u.user_id
                WHERE d.deposit_id = %s
            """, (deposit_id,))
            deposit = cursor.fetchone()

        if not deposit:
            flash('Depósito no encontrado', 'error')
            return redirect(url_for('manual_deposits.admin_deposits'))

        return render_template('admin_deposit_detail.html',
            deposit=deposit,
            DEPOSIT_STATUS=DEPOSIT_STATUS,
            min_deposit=DEPOSIT_CONFIG['min_deposit']
        )

    except Exception as e:
        logger.error(f"❌ Error en admin_deposit_detail: {e}")
        flash('Error al cargar depósito', 'error')
        return redirect(url_for('manual_deposits.admin_deposits'))


@manual_deposits_bp.route('/admin/deposit/approve', methods=['POST'])
@admin_required
def approve_deposit():
    """Aprobar un depósito y acreditar saldo"""
    try:
        deposit_id = request.form.get('deposit_id')
        admin_notes = request.form.get('admin_notes', '')

        if not deposit_id:
            flash('ID de depósito requerido', 'error')
            return redirect(url_for('manual_deposits.admin_deposits'))

        with get_cursor() as cursor:
            # Obtener depósito
            cursor.execute("""
                SELECT * FROM manual_deposits WHERE deposit_id = %s
            """, (deposit_id,))
            deposit = cursor.fetchone()

            if not deposit:
                flash('Depósito no encontrado', 'error')
                return redirect(url_for('manual_deposits.admin_deposits'))

            # Verificar que no esté ya procesado
            if deposit['status'] in ['approved', 'rejected']:
                flash('Este depósito ya fue procesado', 'warning')
                return redirect(url_for('manual_deposits.admin_deposits'))

            # REGLA CRÍTICA: No aprobar depósitos menores a 1 DOGE
            if float(deposit['amount']) < DEPOSIT_CONFIG['min_deposit']:
                flash(f'No se puede aprobar. Monto mínimo: {DEPOSIT_CONFIG["min_deposit"]} DOGE', 'error')
                return redirect(url_for('manual_deposits.admin_deposits'))

            # Obtener datos del usuario
            cursor.execute("""
                SELECT user_id, doge_balance, usdt_balance
                FROM users WHERE user_id = %s
            """, (deposit['user_id'],))
            user = cursor.fetchone()

            if not user:
                flash('Usuario no encontrado', 'error')
                return redirect(url_for('manual_deposits.admin_deposits'))

            # Determinar balance a actualizar según moneda
            currency = deposit['currency'].upper()
            amount = float(deposit['amount'])

            # Acreditar saldo según moneda
            if currency == 'DOGE':
                new_balance = float(user['doge_balance']) + amount
                cursor.execute("""
                    UPDATE users SET doge_balance = %s WHERE user_id = %s
                """, (new_balance, deposit['user_id']))
                balance_field = 'doge_balance'
            elif currency == 'USDT':
                new_balance = float(user['usdt_balance']) + amount
                cursor.execute("""
                    UPDATE users SET usdt_balance = %s WHERE user_id = %s
                """, (new_balance, deposit['user_id']))
                balance_field = 'usdt_balance'
            else:
                # Para otras monedas, convertir a DOGE y acreditar
                # Por ahora acreditamos como DOGE (puedes agregar tasas de conversión)
                new_balance = float(user['doge_balance']) + amount
                cursor.execute("""
                    UPDATE users SET doge_balance = %s WHERE user_id = %s
                """, (new_balance, deposit['user_id']))
                balance_field = 'doge_balance'

            # Actualizar depósito
            cursor.execute("""
                UPDATE manual_deposits
                SET status = 'approved',
                    admin_notes = %s,
                    processed_at = NOW(),
                    processed_by = %s
                WHERE deposit_id = %s
            """, (admin_notes, session.get('admin_id', 'admin'), deposit_id))

            # Registrar en historial de balance
            cursor.execute("""
                INSERT INTO balance_history
                (user_id, action, currency, amount, balance_before, balance_after, description)
                VALUES (%s, 'deposit', %s, %s, %s, %s, %s)
            """, (
                deposit['user_id'],
                currency,
                amount,
                float(user[balance_field]) if balance_field in user else 0,
                new_balance,
                f'Depósito manual aprobado: {deposit_id}'
            ))

        logger.info(f"✅ Depósito aprobado: {deposit_id} - {amount} {currency} acreditados a {deposit['user_id']}")
        flash(f'Depósito aprobado. {amount} {currency} acreditados al usuario.', 'success')
        return redirect(url_for('manual_deposits.admin_deposits'))

    except Exception as e:
        logger.error(f"❌ Error en approve_deposit: {e}")
        flash('Error al aprobar depósito', 'error')
        return redirect(url_for('manual_deposits.admin_deposits'))


@manual_deposits_bp.route('/admin/deposit/reject', methods=['POST'])
@admin_required
def reject_deposit():
    """Rechazar un depósito"""
    try:
        deposit_id = request.form.get('deposit_id')
        admin_notes = request.form.get('admin_notes', '')

        if not deposit_id:
            flash('ID de depósito requerido', 'error')
            return redirect(url_for('manual_deposits.admin_deposits'))

        with get_cursor() as cursor:
            # Verificar depósito
            cursor.execute("""
                SELECT * FROM manual_deposits WHERE deposit_id = %s
            """, (deposit_id,))
            deposit = cursor.fetchone()

            if not deposit:
                flash('Depósito no encontrado', 'error')
                return redirect(url_for('manual_deposits.admin_deposits'))

            # Verificar que no esté ya procesado
            if deposit['status'] in ['approved', 'rejected']:
                flash('Este depósito ya fue procesado', 'warning')
                return redirect(url_for('manual_deposits.admin_deposits'))

            # Actualizar estado
            cursor.execute("""
                UPDATE manual_deposits
                SET status = 'rejected',
                    admin_notes = %s,
                    processed_at = NOW(),
                    processed_by = %s
                WHERE deposit_id = %s
            """, (admin_notes, session.get('admin_id', 'admin'), deposit_id))

        logger.info(f"❌ Depósito rechazado: {deposit_id}")
        flash('Depósito rechazado', 'success')
        return redirect(url_for('manual_deposits.admin_deposits'))

    except Exception as e:
        logger.error(f"❌ Error en reject_deposit: {e}")
        flash('Error al rechazar depósito', 'error')
        return redirect(url_for('manual_deposits.admin_deposits'))


@manual_deposits_bp.route('/api/admin/deposits/stats', methods=['GET'])
@admin_required
def get_deposit_stats():
    """Obtener estadísticas de depósitos para el admin"""
    try:
        with get_cursor() as cursor:
            # Total por estado
            cursor.execute("""
                SELECT status, COUNT(*) as count, SUM(amount) as total
                FROM manual_deposits
                GROUP BY status
            """)
            stats_by_status = cursor.fetchall()

            # Depósitos hoy
            cursor.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                FROM manual_deposits
                WHERE DATE(created_at) = CURDATE()
            """)
            today = cursor.fetchone()

            # Pendientes
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM manual_deposits
                WHERE status = 'pending'
            """)
            pending = cursor.fetchone()

        return jsonify({
            'success': True,
            'stats': {
                'by_status': stats_by_status,
                'today': {
                    'count': today['count'],
                    'total': float(today['total'])
                },
                'pending': pending['count']
            }
        })

    except Exception as e:
        logger.error(f"❌ Error en get_deposit_stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# REGISTRO DEL BLUEPRINT
# ============================================
def register_manual_deposits(app):
    """Registrar el blueprint y crear tabla"""
    init_deposits_table()
    app.register_blueprint(manual_deposits_bp)
    logger.info("✅ Manual Deposits system registered")
