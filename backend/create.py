#!/usr/bin/env python3
"""
Script to create a hardcoded super admin user.
Run this once to create the initial super admin account.
"""

import os
import sys
from flask import Flask
from app import create_app, db
from app.models import User, Tenant

def create_super_admin():
    """Create a hardcoded super admin user."""
    # Set the DATABASE_URL environment variable for PostgreSQL Neon
    # Replace this with your actual Neon database connection string
    neon_db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
    
    if not neon_db_url or 'sqlite' in neon_db_url:
        print("⚠️ WARNING: No PostgreSQL DATABASE_URL found!")
        print("Please set your Neon database URL as an environment variable:")
        print("export DATABASE_URL='postgresql://neondb_owner:npg_as0ANyUEtZ3z@ep-rapid-haze-a1axw89e-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'")
        print("")
        print("Or set NEON_DATABASE_URL environment variable")
        print("Current DATABASE_URL:", os.environ.get('DATABASE_URL', 'Not set'))
        print("")
        
        # Ask user if they want to continue with SQLite for testing
        response = input("Continue with SQLite for testing? (y/N): ").lower()
        if response != 'y':
            print("❌ Exiting. Please set your PostgreSQL connection string.")
            return
    
    app = create_app()
    
    # Override database URL if we have Neon URL
    if neon_db_url and 'postgresql' in neon_db_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = neon_db_url
        print(f"🔗 Using PostgreSQL Neon database")
    
    with app.app_context():
        # Ensure we're using the correct database
        print("🔗 Using database:", app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured'))
        # Check if super admin already exists
        existing_admin = User.query.filter_by(email='muazijazadmin@gmail.com').first()
        if existing_admin:
            print("❌ Super admin already exists!")
            print(f"   Email: {existing_admin.email}")
            print(f"   Role: {existing_admin.role}")
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
        
        # Create super admin user with all confirmations bypassed
        print("👑 Creating super admin...")
        
        # Create user directly without email confirmation requirements
        from werkzeug.security import generate_password_hash
        from datetime import datetime
        
        now = datetime.utcnow()
        
        super_admin = User(
            tenant_id=default_tenant.id,
            email='muazijazadmin@gmail.com',
            password_hash=generate_password_hash('Muazijaz1234@'),
            role='super_admin',
            first_name='Muazi',
            last_name='Jaz',
            status='active',  # Set to active immediately
            email_confirmed=True,  # Bypass email confirmation
            email_confirmed_at=now,  # Set confirmation timestamp
            created_at=now,
            updated_at=now
        )
        
        db.session.add(super_admin)
        db.session.commit()
        
        print("✅ Super admin created successfully!")
        print(f"   📧 Email: muazijazadmin@gmail.com")
        print(f"   🔑 Password: Muazijaz1234@")
        print(f"   👤 Role: super_admin")
        print("")
        print("🚨 IMPORTANT: Change the password after first login!")
        print("🔐 This account has full system access.")

if __name__ == '__main__':
    create_super_admin()
