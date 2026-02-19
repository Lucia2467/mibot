#!/usr/bin/env python3
"""
SALLY-E Admin Panel Fix Installation Script
============================================
This script applies all fixes for the admin user management module.

Run with: python install_fixes.py
"""

import os
import shutil
from datetime import datetime

# Directory where the script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def backup_file(filepath):
    """Create a backup of a file before modifying"""
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{filepath}.backup_{timestamp}"
        shutil.copy2(filepath, backup_path)
        print(f"✅ Backup created: {backup_path}")
        return backup_path
    return None

def install_fixes():
    """Apply all fixes"""
    print("\n" + "="*60)
    print("🔧 SALLY-E Admin Panel Fix Installation")
    print("="*60 + "\n")
    
    # 1. Replace database.py
    print("📁 Step 1: Updating database.py...")
    db_original = os.path.join(BASE_DIR, 'database.py')
    db_fixed = os.path.join(BASE_DIR, 'database_fixed.py')
    
    if os.path.exists(db_fixed):
        backup_file(db_original)
        shutil.copy2(db_fixed, db_original)
        print("✅ database.py updated successfully\n")
    else:
        print("❌ database_fixed.py not found!\n")
    
    # 2. Replace admin_users.html
    print("📁 Step 2: Updating admin_users.html...")
    template_original = os.path.join(BASE_DIR, 'templates', 'admin_users.html')
    template_fixed = os.path.join(BASE_DIR, 'templates', 'admin_users_fixed.html')
    
    if os.path.exists(template_fixed):
        backup_file(template_original)
        shutil.copy2(template_fixed, template_original)
        print("✅ admin_users.html updated successfully\n")
    else:
        print("❌ admin_users_fixed.html not found!\n")
    
    # 3. Patch app.py
    print("📁 Step 3: Patching app.py...")
    app_path = os.path.join(BASE_DIR, 'app.py')
    
    if os.path.exists(app_path):
        backup_file(app_path)
        
        with open(app_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add new imports if not present
        if 'get_banned_users_count' not in content:
            old_import = """from database import (
    get_user, create_user, update_user, get_all_users, get_users_count,
    ban_user, unban_user, update_balance,"""
            
            new_import = """from database import (
    get_user, create_user, update_user, get_all_users, get_users_count,
    get_banned_users_count, search_users, get_all_users_with_referrals,
    get_user_balance_history, get_user_with_referrals,
    ban_user, unban_user, update_balance,"""
            
            content = content.replace(old_import, new_import)
            print("  ✅ Added new imports")
        
        # Fix the admin_users route - change 'users' to 'usuarios'
        # Find and replace the return statement
        old_return = """return render_template('admin_users.html',
                         users=users,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         search=search)"""
        
        new_return = """# Get banned count for stats
    try:
        banned_count = get_banned_users_count()
    except:
        banned_count = sum(1 for u in users if u.get('banned'))
    
    return render_template('admin_users.html',
                         usuarios=users,  # FIXED: renamed to 'usuarios' for template
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         banned_count=banned_count,
                         search=search)"""
        
        if old_return in content:
            content = content.replace(old_return, new_return)
            print("  ✅ Fixed admin_users route variable name")
        else:
            # Try alternative format
            old_return_alt = """return render_template('admin_users.html',
                     users=users,
                     page=page,
                     total_pages=total_pages,
                     total=total,
                     search=search)"""
            if old_return_alt in content:
                content = content.replace(old_return_alt, new_return.replace('                         ', '                     '))
                print("  ✅ Fixed admin_users route variable name (alt format)")
        
        # Add the new API endpoints at the end if not present
        if '/api/admin/user-balance-history/' not in content:
            api_endpoints = '''

# ============== NEW API ENDPOINTS FOR ADMIN USER MANAGEMENT ==============

@app.route('/api/admin/user-balance-history/<user_id>')
@admin_required
def api_admin_user_balance_history(user_id):
    """Get user balance history - NEW API endpoint"""
    try:
        from database import get_user_balance_history
        
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
    """Get user details - NEW API endpoint for real-time data"""
    try:
        from database import get_user_with_referrals
        
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
    """Search users - NEW API endpoint"""
    try:
        from database import search_users
        
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
    """Get users statistics - NEW API endpoint"""
    try:
        from database import get_users_count, get_banned_users_count
        
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
'''
            # Insert before the error handlers or main block
            if '# ============== ERROR HANDLERS ==============' in content:
                content = content.replace(
                    '# ============== ERROR HANDLERS ==============',
                    api_endpoints + '\n# ============== ERROR HANDLERS =============='
                )
                print("  ✅ Added new API endpoints")
            else:
                # Append at the end before if __name__
                if "if __name__ == '__main__':" in content:
                    content = content.replace(
                        "if __name__ == '__main__':",
                        api_endpoints + "\nif __name__ == '__main__':"
                    )
                    print("  ✅ Added new API endpoints (at end)")
        
        # Write the patched content
        with open(app_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ app.py patched successfully\n")
    else:
        print("❌ app.py not found!\n")
    
    print("="*60)
    print("🎉 Installation Complete!")
    print("="*60)
    print("""
Next steps:
1. Restart your Flask application
2. Clear your browser cache
3. Visit /admin/users to test the fixes

If something goes wrong, restore from the backup files created.
    """)

if __name__ == '__main__':
    install_fixes()
