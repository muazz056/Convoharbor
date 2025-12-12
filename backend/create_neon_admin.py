#!/usr/bin/env python3
"""
Script to create super admin directly in Neon PostgreSQL database.
"""

import os
import sys
from datetime import datetime
from werkzeug.security import generate_password_hash

def create_neon_super_admin():
    """Create super admin directly in Neon database."""
    
    # Set the Neon database URL
    neon_url = "postgresql://neondb_owner:npg_as0ANyUEtZ3z@ep-rapid-haze-a1axw89e-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    os.environ['DATABASE_URL'] = neon_url
    
    print("🔗 Connecting to Neon PostgreSQL database...")
    
    # Import Flask app after setting environment
    from app import create_app, db
    from app.models import User, Tenant
    
    app = create_app()
    app.config['SQLALCHEMY_DATABASE_URI'] = neon_url
    
    with app.app_context():
        print(f"🔗 Using database: {app.config.get('SQLALCHEMY_DATABASE_URI')[:50]}...")
        
        try:
            # Test database connection
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            print("✅ Database connection successful!")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return
        
        # Check if super admin already exists
        existing_admin = User.query.filter_by(email='muazijazadmin@gmail.com').first()
        if existing_admin:
            print("✅ Super admin already exists!")
            print(f"   📧 Email: {existing_admin.email}")
            print(f"   👤 Role: {existing_admin.role}")
            print(f"   📊 Status: {existing_admin.status}")
            print(f"   ✉️ Email confirmed: {existing_admin.email_confirmed}")
            
            # Update status if needed
            if existing_admin.status != 'active' or not existing_admin.email_confirmed:
                print("🔧 Updating super admin status...")
                existing_admin.status = 'active'
                existing_admin.email_confirmed = True
                existing_admin.email_confirmed_at = datetime.utcnow()
                db.session.commit()
                print("✅ Super admin status updated!")
            
            return
        
        # Get or create default tenant
        default_tenant = Tenant.query.first()
        if not default_tenant:
            print("📝 Creating default tenant...")
            default_tenant = Tenant(
                name="ConvoPilot System",
                domain="system.convopilot.com",
                type="convopilot"
            )
            db.session.add(default_tenant)
            db.session.commit()
            print("✅ Default tenant created!")
        
        # Create super admin
        print("👑 Creating super admin...")
        
        now = datetime.utcnow()
        
        super_admin = User(
            tenant_id=default_tenant.id,
            email='muazijazadmin@gmail.com',
            password_hash=generate_password_hash('Muazijaz1234@'),
            role='super_admin',
            first_name='Muazi',
            last_name='Jaz',
            status='active',
            email_confirmed=True,
            email_confirmed_at=now,
            created_at=now,
            updated_at=now
        )
        
        db.session.add(super_admin)
        db.session.commit()
        
        print("✅ Super admin created successfully!")
        print(f"   📧 Email: muazijazadmin@gmail.com")
        print(f"   🔑 Password: Muazijaz1234@")
        print(f"   👤 Role: super_admin")
        print(f"   📊 Status: active")
        print(f"   ✉️ Email confirmed: True")
        print("")
        print("🎉 You can now login with these credentials!")
        print("🔐 This account has full system access including Top K configuration.")

if __name__ == '__main__':
    create_neon_super_admin()
