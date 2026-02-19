"""
ban_routes.py - Flask Routes for Ban Management System
Provides admin interface and API endpoints for ban management
"""

import json
import logging
from functools import wraps
from flask import request, jsonify, render_template, session, redirect, url_for

logger = logging.getLogger(__name__)


def register_ban_routes(app):
    """Register all ban-related routes with the Flask app"""
    
    # Import ban system functions
    from ban_system import (
        get_user_ban_status, is_user_banned, get_ban_logs,
        ban_user_manual, unban_user_manual, update_ban_reason,
        auto_ban_check, record_device_info,
        get_ban_statistics, get_banned_users_list, get_user_ban_details,
        get_antifraud_config, update_antifraud_config, initialize_ban_system
    )
    
    # Admin authentication decorator
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('admin_logged_in'):
                return jsonify({'success': False, 'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    # ============================================
    # ADMIN ROUTES
    # ============================================
    
    @app.route('/admin/ban-user', methods=['POST'])
    @admin_required
    def ban_system_ban_user():
        """Ban a user manually via ban system"""
        try:
            data = request.get_json() or request.form.to_dict()
            user_id = data.get('user_id')
            reason = data.get('reason', 'Banned by administrator')
            admin_id = session.get('admin_id', 'admin')
            
            if not user_id:
                return jsonify({'success': False, 'error': 'User ID required'}), 400
            
            result = ban_user_manual(user_id, reason, admin_id)
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error in ban_system_ban_user: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/admin/unban-user', methods=['POST'])
    @admin_required
    def ban_system_unban_user():
        """Unban a user manually via ban system"""
        try:
            data = request.get_json() or request.form.to_dict()
            user_id = data.get('user_id')
            reason = data.get('reason', 'Unbanned by administrator')
            admin_id = session.get('admin_id', 'admin')
            
            if not user_id:
                return jsonify({'success': False, 'error': 'User ID required'}), 400
            
            result = unban_user_manual(user_id, reason, admin_id)
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error in ban_system_unban_user: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/admin/users/<user_id>/update-ban-reason', methods=['POST'])
    @admin_required
    def ban_system_update_reason(user_id):
        """Update ban reason for a user"""
        try:
            data = request.get_json() or request.form.to_dict()
            new_reason = data.get('reason')
            admin_id = session.get('admin_id', 'admin')
            
            if not new_reason:
                return jsonify({'success': False, 'error': 'Reason required'}), 400
            
            result = update_ban_reason(user_id, new_reason, admin_id)
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error updating ban reason: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/admin/banned-users')
    @admin_required
    def ban_system_banned_users():
        """View all banned users"""
        try:
            page = request.args.get('page', 1, type=int)
            limit = 50
            offset = (page - 1) * limit
            ban_type = request.args.get('type')
            
            users = get_banned_users_list(limit, offset, ban_type)
            stats = get_ban_statistics()
            
            return render_template('admin_banned_users.html',
                                 users=users,
                                 stats=stats,
                                 page=page,
                                 ban_type=ban_type)
        except Exception as e:
            logger.error(f"Error loading banned users: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/admin/user-ban-details/<user_id>')
    @admin_required
    def ban_system_user_details(user_id):
        """View detailed ban information for a user"""
        try:
            details = get_user_ban_details(user_id)
            if not details:
                return jsonify({'error': 'User not found'}), 404
            
            return render_template('admin_user_ban_details.html', details=details)
        except Exception as e:
            logger.error(f"Error loading ban details: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/admin/ban-logs')
    @admin_required
    def ban_system_logs():
        """View ban event logs"""
        try:
            page = request.args.get('page', 1, type=int)
            limit = 50
            offset = (page - 1) * limit
            user_id = request.args.get('user_id')
            
            logs = get_ban_logs(user_id, limit, offset)
            
            return render_template('admin_ban_logs.html',
                                 logs=logs,
                                 page=page,
                                 user_id=user_id)
        except Exception as e:
            logger.error(f"Error loading ban logs: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/admin/antifraud-config', methods=['GET', 'POST'])
    @admin_required
    def ban_system_antifraud_config():
        """View/update antifraud configuration"""
        try:
            if request.method == 'POST':
                data = request.get_json() or request.form.to_dict()
                
                # Process boolean values
                config_updates = {}
                for key in ['antifraud_enabled', 'auto_ban_enabled', 'ban_related_accounts']:
                    if key in data:
                        config_updates[key] = 'true' if data[key] in ['true', True, '1', 1] else 'false'
                
                for key in ['max_accounts_per_ip', 'max_accounts_per_device']:
                    if key in data:
                        config_updates[key] = str(int(data[key]))
                
                if config_updates:
                    update_antifraud_config(config_updates)
                
                return jsonify({'success': True, 'message': 'Configuration updated'})
            
            config = get_antifraud_config()
            return jsonify({'success': True, 'config': config})
            
        except Exception as e:
            logger.error(f"Error with antifraud config: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Note: API endpoints are defined in app.py
    # Only admin page routes are registered here
    
    @app.route('/admin/init-ban-system', methods=['POST'])
    @admin_required
    def ban_system_init():
        """Initialize the ban system (create tables, add columns)"""
        try:
            result = initialize_ban_system()
            if result:
                return jsonify({'success': True, 'message': 'Ban system initialized successfully'})
            else:
                return jsonify({'success': False, 'error': 'Failed to initialize ban system'}), 500
        except Exception as e:
            logger.error(f"Error initializing ban system: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    logger.info("Ban routes registered successfully")
