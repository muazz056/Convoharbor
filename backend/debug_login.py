#!/usr/bin/env python3
"""
Script to debug login issues.
"""

import os
from werkzeug.security import check_password_hash

def debug_login():
    """Debug login for super admin."""
    
    # Set the Neon database URL
    neon_url = "postgresql://neondb_owner:npg_as0ANyUEtZ3z@ep-rapid-haze-a1axw89e-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    os.environ['DATABASE_URL'] = neon_url
    
    from app import create_app, db
    from app.models import User
    
    app = create_app()
    app.config['SQLALCHEMY_DATABASE_URI'] = neon_url
    
    with app.app_context():
        print("🔍 Debugging super admin login...")
        
        # Test database connection first
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            print("✅ Database connection successful!")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return
        
        # Find the user
        user = User.query.filter_by(email='muazijazadmin@gmail.com').first()
        if not user:
            print("❌ User not found in database!")
            return
        
        print(f"✅ User found:")
        print(f"   📧 Email: {user.email}")
        print(f"   👤 Role: {user.role}")
        print(f"   📊 Status: {user.status}")
        print(f"   ✉️ Email confirmed: {user.email_confirmed}")
        print(f"   🆔 User ID: {user.id}")
        print(f"   🏢 Tenant ID: {user.tenant_id}")
        
        # Test password
        test_password = 'Muazijaz1234@'
        password_valid = check_password_hash(user.password_hash, test_password)
        print(f"   🔑 Password test: {'✅ Valid' if password_valid else '❌ Invalid'}")
        
        # Test auth service
        try:
            authenticated_user = app.auth_service.authenticate_user(user.email, test_password)
            if authenticated_user:
                print("✅ Auth service authentication: SUCCESS")
            else:
                print("❌ Auth service authentication: FAILED")
                
                # Check specific conditions
                if not user.email_confirmed:
                    print("   🚫 Reason: Email not confirmed")
                if user.status == 'pending':
                    print("   🚫 Reason: User status is pending")
                if user.status != 'active':
                    print(f"   🚫 Reason: User status is '{user.status}', should be 'active'")
                    
        except Exception as e:
            print(f"❌ Auth service error: {e}")

if __name__ == '__main__':
    debug_login()
