"""
ban_system.py - Complete Ban Management System for SALLY-E
Handles automatic and manual banning with full audit logging
Compatible with PythonAnywhere db.py (uses get_cursor)
"""

import json
import logging
from datetime import datetime
from db import get_cursor, execute_query

logger = logging.getLogger(__name__)


# ============================================
# CONFIGURATION
# ============================================

def get_antifraud_config():
    """Get antifraud configuration from database"""
    try:
        config = {}
        keys = ['antifraud_enabled', 'max_accounts_per_ip', 'max_accounts_per_device', 
                'auto_ban_enabled', 'ban_related_accounts']
        
        with get_cursor() as cursor:
            for key in keys:
                cursor.execute(
                    "SELECT config_value FROM config WHERE config_key = %s",
                    (key,)
                )
                result = cursor.fetchone()
                
                if result:
                    value = result.get('config_value', '')
                    if key in ['max_accounts_per_ip', 'max_accounts_per_device']:
                        config[key] = int(value) if value and str(value).isdigit() else 3
                    else:
                        config[key] = str(value).lower() == 'true'
                else:
                    # Defaults
                    if key == 'antifraud_enabled':
                        config[key] = True
                    elif key == 'max_accounts_per_ip':
                        config[key] = 3
                    elif key == 'max_accounts_per_device':
                        config[key] = 2
                    elif key == 'auto_ban_enabled':
                        config[key] = True
                    elif key == 'ban_related_accounts':
                        config[key] = False
        
        return config
    except Exception as e:
        logger.error(f"Error getting antifraud config: {e}")
        return {
            'antifraud_enabled': True,
            'max_accounts_per_ip': 3,
            'max_accounts_per_device': 2,
            'auto_ban_enabled': True,
            'ban_related_accounts': False
        }


def update_antifraud_config(config_updates):
    """Update antifraud configuration"""
    try:
        with get_cursor() as cursor:
            for key, value in config_updates.items():
                cursor.execute(
                    """INSERT INTO config (config_key, config_value) 
                       VALUES (%s, %s) 
                       ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)""",
                    (key, str(value))
                )
        return True
    except Exception as e:
        logger.error(f"Error updating antifraud config: {e}")
        return False


# ============================================
# BAN STATUS
# ============================================

def get_user_ban_status(user_id):
    """Get complete ban status for a user"""
    try:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT user_id, username, first_name, banned, ban_reason, ban_date, 
                          ban_type, account_state, last_ip, device_hash
                   FROM users WHERE user_id = %s""",
                (str(user_id),)
            )
            result = cursor.fetchone()
        
        if not result:
            return None
        
        # Check if user is banned
        is_banned = (
            result.get('banned') == 1 or 
            result.get('account_state') == 'BANNED'
        )
        
        return {
            'user_id': result.get('user_id'),
            'username': result.get('username'),
            'first_name': result.get('first_name'),
            'is_banned': is_banned,
            'ban_reason': result.get('ban_reason'),
            'ban_date': result.get('ban_date'),
            'ban_type': result.get('ban_type'),
            'account_state': result.get('account_state'),
            'last_ip': result.get('last_ip'),
            'device_hash': result.get('device_hash')
        }
    except Exception as e:
        logger.error(f"Error checking ban status: {e}")
        return None


def is_user_banned(user_id):
    """Quick check if user is banned"""
    status = get_user_ban_status(user_id)
    return status.get('is_banned', False) if status else False


# ============================================
# BAN LOGGING
# ============================================

def log_ban_event(user_id, event_type, reason, admin_id=None, related_users=None):
    """Log a ban/unban event"""
    try:
        related_json = json.dumps(related_users) if related_users else None
        
        with get_cursor() as cursor:
            # Check if ban_logs table exists
            cursor.execute("SHOW TABLES LIKE 'ban_logs'")
            if not cursor.fetchone():
                # Create table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ban_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        event_type ENUM('ban', 'unban', 'update_reason') NOT NULL,
                        reason TEXT,
                        admin_id VARCHAR(50),
                        related_users JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_id (user_id),
                        INDEX idx_event_type (event_type),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
            
            cursor.execute(
                """INSERT INTO ban_logs (user_id, event_type, reason, admin_id, related_users)
                   VALUES (%s, %s, %s, %s, %s)""",
                (str(user_id), event_type, reason, admin_id, related_json)
            )
        return True
    except Exception as e:
        logger.error(f"Error logging ban event: {e}")
        return False


def get_ban_logs(user_id=None, limit=50, offset=0):
    """Get ban event logs"""
    try:
        with get_cursor() as cursor:
            # Check if table exists
            cursor.execute("SHOW TABLES LIKE 'ban_logs'")
            if not cursor.fetchone():
                return []
            
            if user_id:
                cursor.execute(
                    """SELECT * FROM ban_logs 
                       WHERE user_id = %s 
                       ORDER BY created_at DESC 
                       LIMIT %s OFFSET %s""",
                    (str(user_id), limit, offset)
                )
            else:
                cursor.execute(
                    """SELECT * FROM ban_logs 
                       ORDER BY created_at DESC 
                       LIMIT %s OFFSET %s""",
                    (limit, offset)
                )
            return cursor.fetchall() or []
    except Exception as e:
        logger.error(f"Error getting ban logs: {e}")
        return []


# ============================================
# DEVICE TRACKING
# ============================================

def record_device_info(user_id, device_hash, user_agent=None, screen_info=None, timezone=None, platform=None):
    """Record device information for a user"""
    try:
        if not device_hash:
            return False
        
        with get_cursor() as cursor:
            # Update user's device_hash
            cursor.execute(
                "UPDATE users SET device_hash = %s WHERE user_id = %s",
                (device_hash, str(user_id))
            )
            
            # Check if user_device_history table exists
            cursor.execute("SHOW TABLES LIKE 'user_device_history'")
            if cursor.fetchone():
                # Record in history if table exists
                screen_json = json.dumps(screen_info) if screen_info else None
                cursor.execute(
                    """INSERT INTO user_device_history 
                       (user_id, device_hash, user_agent, screen_info, timezone, platform)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE 
                       last_seen = CURRENT_TIMESTAMP,
                       user_agent = VALUES(user_agent)""",
                    (str(user_id), device_hash, user_agent, screen_json, timezone, platform)
                )
        
        return True
    except Exception as e:
        logger.error(f"Error recording device info: {e}")
        return False


def get_users_by_device(device_hash):
    """Get all users with the same device hash"""
    try:
        if not device_hash:
            return []
        
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT user_id, username, first_name, banned, ban_reason, created_at
                   FROM users WHERE device_hash = %s""",
                (device_hash,)
            )
            return cursor.fetchall() or []
    except Exception as e:
        logger.error(f"Error getting users by device: {e}")
        return []


def get_users_by_ip_address(ip_address):
    """Get all users who have used this IP address"""
    try:
        if not ip_address:
            return []
        
        with get_cursor() as cursor:
            # Check if user_ips table exists
            cursor.execute("SHOW TABLES LIKE 'user_ips'")
            if cursor.fetchone():
                cursor.execute(
                    """SELECT DISTINCT u.user_id, u.username, u.first_name, u.banned, u.ban_reason, u.created_at
                       FROM users u
                       INNER JOIN user_ips ui ON u.user_id = ui.user_id
                       WHERE ui.ip_address = %s""",
                    (ip_address,)
                )
            else:
                # Fallback to last_ip
                cursor.execute(
                    """SELECT user_id, username, first_name, banned, ban_reason, created_at
                       FROM users WHERE last_ip = %s""",
                    (ip_address,)
                )
            return cursor.fetchall() or []
    except Exception as e:
        logger.error(f"Error getting users by IP: {e}")
        return []


# ============================================
# MANUAL BAN/UNBAN
# ============================================

def ban_user_manual(user_id, reason, admin_id=None):
    """Manually ban a user"""
    try:
        with get_cursor() as cursor:
            cursor.execute(
                """UPDATE users SET 
                   banned = 1,
                   ban_reason = %s,
                   ban_date = NOW(),
                   ban_type = 'manual',
                   account_state = 'BANNED'
                   WHERE user_id = %s""",
                (reason, str(user_id))
            )
            
            if cursor.rowcount == 0:
                return {'success': False, 'error': 'User not found'}
        
        # Log the event
        log_ban_event(user_id, 'ban', reason, admin_id)
        
        logger.info(f"[BAN] User {user_id} manually banned by {admin_id}: {reason}")
        return {'success': True, 'message': f'User {user_id} has been banned'}
    
    except Exception as e:
        logger.error(f"Error banning user {user_id}: {e}")
        return {'success': False, 'error': str(e)}


def unban_user_manual(user_id, reason=None, admin_id=None):
    """Manually unban a user"""
    try:
        with get_cursor() as cursor:
            cursor.execute(
                """UPDATE users SET 
                   banned = 0,
                   ban_reason = NULL,
                   ban_date = NULL,
                   ban_type = NULL,
                   account_state = 'ACTIVE'
                   WHERE user_id = %s""",
                (str(user_id),)
            )
            
            if cursor.rowcount == 0:
                return {'success': False, 'error': 'User not found'}
        
        # Log the event
        log_ban_event(user_id, 'unban', reason or 'Unbanned by admin', admin_id)
        
        logger.info(f"[UNBAN] User {user_id} unbanned by {admin_id}")
        return {'success': True, 'message': f'User {user_id} has been unbanned'}
    
    except Exception as e:
        logger.error(f"Error unbanning user {user_id}: {e}")
        return {'success': False, 'error': str(e)}


def update_ban_reason(user_id, new_reason, admin_id=None):
    """Update the ban reason for a user"""
    try:
        with get_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET ban_reason = %s WHERE user_id = %s AND banned = 1",
                (new_reason, str(user_id))
            )
            
            if cursor.rowcount == 0:
                return {'success': False, 'error': 'User not found or not banned'}
        
        # Log the event
        log_ban_event(user_id, 'update_reason', new_reason, admin_id)
        
        return {'success': True, 'message': 'Ban reason updated'}
    
    except Exception as e:
        logger.error(f"Error updating ban reason: {e}")
        return {'success': False, 'error': str(e)}


# ============================================
# AUTOMATIC BAN SYSTEM
# ============================================

def check_and_auto_ban(user_id, ip_address=None, device_hash=None):
    """
    Check if user should be auto-banned based on antifraud rules.
    Returns dict with ban status and reason.
    """
    try:
        # Get antifraud config
        config = get_antifraud_config()
        
        if not config.get('antifraud_enabled') or not config.get('auto_ban_enabled'):
            return {'should_ban': False, 'reason': None}
        
        max_ip = config.get('max_accounts_per_ip', 3)
        max_device = config.get('max_accounts_per_device', 2)
        
        related_users = []
        reasons = []
        
        # Check IP-based multi-accounting
        if ip_address:
            ip_users = get_users_by_ip_address(ip_address)
            # Filter out the current user
            ip_users = [u for u in ip_users if str(u.get('user_id')) != str(user_id)]
            
            if len(ip_users) >= max_ip:
                reasons.append(f"Multiple accounts ({len(ip_users) + 1}) from same IP")
                related_users.extend([str(u.get('user_id')) for u in ip_users])
        
        # Check device-based multi-accounting
        if device_hash:
            device_users = get_users_by_device(device_hash)
            # Filter out the current user
            device_users = [u for u in device_users if str(u.get('user_id')) != str(user_id)]
            
            if len(device_users) >= max_device:
                reasons.append(f"Multiple accounts ({len(device_users) + 1}) from same device")
                for u in device_users:
                    uid = str(u.get('user_id'))
                    if uid not in related_users:
                        related_users.append(uid)
        
        if reasons:
            return {
                'should_ban': True,
                'reason': '; '.join(reasons),
                'related_users': related_users
            }
        
        return {'should_ban': False, 'reason': None}
    
    except Exception as e:
        logger.error(f"Error in auto-ban check: {e}")
        return {'should_ban': False, 'reason': None, 'error': str(e)}


def execute_auto_ban(user_id, reason, related_users=None):
    """Execute automatic ban on a user"""
    try:
        with get_cursor() as cursor:
            cursor.execute(
                """UPDATE users SET 
                   banned = 1,
                   ban_reason = %s,
                   ban_date = NOW(),
                   ban_type = 'automatic',
                   account_state = 'BANNED'
                   WHERE user_id = %s""",
                (reason, str(user_id))
            )
        
        # Log the event
        log_ban_event(user_id, 'ban', reason, admin_id='SYSTEM', related_users=related_users)
        
        logger.warning(f"[AUTO-BAN] User {user_id} automatically banned: {reason}")
        
        # Optionally ban related accounts
        config = get_antifraud_config()
        if config.get('ban_related_accounts') and related_users:
            for related_id in related_users:
                try:
                    with get_cursor() as cursor:
                        cursor.execute(
                            """UPDATE users SET 
                               banned = 1,
                               ban_reason = %s,
                               ban_date = NOW(),
                               ban_type = 'automatic',
                               account_state = 'BANNED'
                               WHERE user_id = %s AND banned = 0""",
                            (f"Related to banned account {user_id}", str(related_id))
                        )
                    if cursor.rowcount > 0:
                        log_ban_event(related_id, 'ban', f"Related to banned account {user_id}", 
                                     admin_id='SYSTEM', related_users=[str(user_id)])
                        logger.warning(f"[AUTO-BAN] Related user {related_id} also banned")
                except Exception as e:
                    logger.error(f"Error banning related user {related_id}: {e}")
        
        return {'success': True, 'was_banned': True, 'reason': reason}
    
    except Exception as e:
        logger.error(f"Error executing auto-ban for {user_id}: {e}")
        return {'success': False, 'error': str(e)}


def auto_ban_check(user_id, ip_address=None, device_hash=None):
    """
    Complete auto-ban check and execution.
    Call this when a user accesses the app.
    """
    try:
        # First check if already banned
        status = get_user_ban_status(user_id)
        if status and status.get('is_banned'):
            return {
                'already_banned': True,
                'was_banned': False,
                'reason': status.get('ban_reason')
            }
        
        # Check if should be banned
        check_result = check_and_auto_ban(user_id, ip_address, device_hash)
        
        if check_result.get('should_ban'):
            # Execute the ban
            ban_result = execute_auto_ban(
                user_id, 
                check_result.get('reason'),
                check_result.get('related_users')
            )
            return {
                'already_banned': False,
                'was_banned': ban_result.get('success', False),
                'reason': check_result.get('reason')
            }
        
        return {
            'already_banned': False,
            'was_banned': False,
            'reason': None
        }
    
    except Exception as e:
        logger.error(f"Error checking auto-ban for {user_id}: {e}")
        return {
            'already_banned': False,
            'was_banned': False,
            'error': str(e)
        }


# ============================================
# STATISTICS
# ============================================

def get_ban_statistics():
    """Get ban statistics"""
    try:
        stats = {}
        
        with get_cursor() as cursor:
            # Total banned users
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE banned = 1")
            result = cursor.fetchone()
            stats['total_banned'] = result.get('count', 0) if result else 0
            
            # Automatic bans
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE banned = 1 AND ban_type = 'automatic'")
            result = cursor.fetchone()
            stats['automatic_bans'] = result.get('count', 0) if result else 0
            
            # Manual bans
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE banned = 1 AND ban_type = 'manual'")
            result = cursor.fetchone()
            stats['manual_bans'] = result.get('count', 0) if result else 0
            
            # Bans today
            cursor.execute(
                "SELECT COUNT(*) as count FROM users WHERE banned = 1 AND DATE(ban_date) = CURDATE()"
            )
            result = cursor.fetchone()
            stats['bans_today'] = result.get('count', 0) if result else 0
            
            # Check if ban_logs table exists for unban stats
            cursor.execute("SHOW TABLES LIKE 'ban_logs'")
            if cursor.fetchone():
                cursor.execute(
                    """SELECT COUNT(*) as count FROM ban_logs 
                       WHERE event_type = 'unban' AND DATE(created_at) = CURDATE()"""
                )
                result = cursor.fetchone()
                stats['unbans_today'] = result.get('count', 0) if result else 0
            else:
                stats['unbans_today'] = 0
        
        return stats
    except Exception as e:
        logger.error(f"Error getting ban statistics: {e}")
        return {
            'total_banned': 0,
            'automatic_bans': 0,
            'manual_bans': 0,
            'bans_today': 0,
            'unbans_today': 0
        }


def get_banned_users_list(limit=50, offset=0, ban_type=None):
    """Get list of banned users"""
    try:
        with get_cursor() as cursor:
            if ban_type:
                cursor.execute(
                    """SELECT user_id, username, first_name, ban_reason, ban_date, ban_type, 
                              last_ip, device_hash, created_at
                       FROM users 
                       WHERE banned = 1 AND ban_type = %s
                       ORDER BY ban_date DESC
                       LIMIT %s OFFSET %s""",
                    (ban_type, limit, offset)
                )
            else:
                cursor.execute(
                    """SELECT user_id, username, first_name, ban_reason, ban_date, ban_type,
                              last_ip, device_hash, created_at
                       FROM users 
                       WHERE banned = 1
                       ORDER BY ban_date DESC
                       LIMIT %s OFFSET %s""",
                    (limit, offset)
                )
            return cursor.fetchall() or []
    except Exception as e:
        logger.error(f"Error getting banned users list: {e}")
        return []


def get_user_ban_details(user_id):
    """Get comprehensive ban details for a user"""
    try:
        details = {}
        
        # Get user info
        status = get_user_ban_status(user_id)
        if not status:
            return None
        
        details['user'] = status
        
        # Get ban logs
        details['ban_logs'] = get_ban_logs(user_id, limit=20)
        
        # Get IP history
        with get_cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'user_ips'")
            if cursor.fetchone():
                cursor.execute(
                    """SELECT ip_address, first_seen, last_seen, times_seen
                       FROM user_ips WHERE user_id = %s
                       ORDER BY last_seen DESC LIMIT 10""",
                    (str(user_id),)
                )
                details['ip_history'] = cursor.fetchall() or []
            else:
                details['ip_history'] = []
        
        # Get device history
        with get_cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'user_device_history'")
            if cursor.fetchone():
                cursor.execute(
                    """SELECT device_hash, user_agent, platform, timezone, first_seen, last_seen
                       FROM user_device_history WHERE user_id = %s
                       ORDER BY last_seen DESC LIMIT 10""",
                    (str(user_id),)
                )
                details['device_history'] = cursor.fetchall() or []
            else:
                details['device_history'] = []
        
        # Get related accounts (same IP or device)
        related = []
        if status.get('last_ip'):
            ip_users = get_users_by_ip_address(status.get('last_ip'))
            for u in ip_users:
                if str(u.get('user_id')) != str(user_id):
                    u['relation'] = 'same_ip'
                    related.append(u)
        
        if status.get('device_hash'):
            device_users = get_users_by_device(status.get('device_hash'))
            for u in device_users:
                uid = str(u.get('user_id'))
                if uid != str(user_id) and uid not in [str(r.get('user_id')) for r in related]:
                    u['relation'] = 'same_device'
                    related.append(u)
        
        details['related_accounts'] = related
        
        # Get referrals
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT user_id, username, first_name, banned, created_at
                   FROM users WHERE referred_by = %s LIMIT 10""",
                (str(user_id),)
            )
            details['referrals'] = cursor.fetchall() or []
        
        return details
    except Exception as e:
        logger.error(f"Error getting user ban details: {e}")
        return None


# ============================================
# INITIALIZATION
# ============================================

def initialize_ban_system():
    """Initialize ban system tables and columns"""
    try:
        with get_cursor() as cursor:
            # Add columns to users table if they don't exist
            columns_to_add = [
                ("ban_type", "VARCHAR(20) DEFAULT NULL"),
                ("account_state", "ENUM('ACTIVE', 'SUSPENDED', 'BANNED') DEFAULT 'ACTIVE'"),
                ("device_hash", "VARCHAR(100) DEFAULT NULL")
            ]
            
            for col_name, col_def in columns_to_add:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Added column {col_name} to users table")
                except Exception as e:
                    if "Duplicate column" not in str(e):
                        logger.warning(f"Could not add column {col_name}: {e}")
            
            # Create ban_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ban_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    event_type ENUM('ban', 'unban', 'update_reason') NOT NULL,
                    reason TEXT,
                    admin_id VARCHAR(50),
                    related_users JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_event_type (event_type),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Create user_device_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_device_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    device_hash VARCHAR(100) NOT NULL,
                    user_agent TEXT,
                    screen_info JSON,
                    timezone VARCHAR(50),
                    platform VARCHAR(50),
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_device (user_id, device_hash),
                    INDEX idx_device_hash (device_hash)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Add default config values
            config_defaults = [
                ('antifraud_enabled', 'true'),
                ('max_accounts_per_ip', '3'),
                ('max_accounts_per_device', '2'),
                ('auto_ban_enabled', 'true'),
                ('ban_related_accounts', 'false')
            ]
            
            for key, value in config_defaults:
                cursor.execute(
                    """INSERT IGNORE INTO config (config_key, config_value) VALUES (%s, %s)""",
                    (key, value)
                )
        
        logger.info("✅ Ban system initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing ban system: {e}")
        return False
