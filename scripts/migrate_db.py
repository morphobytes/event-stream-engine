#!/usr/bin/env python3
"""
Database migration script for Event Stream Engine
This script handles database initialization and migrations
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, '/app')

from flask_migrate import upgrade, migrate, stamp, init
from app.main import create_app, db

def run_migrations():
    """Run database migrations with proper error handling"""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("🔄 Starting database migration process...")
            
            # Check if migrations directory exists
            migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
            
            if not os.path.exists(migrations_dir):
                print("📁 Migrations directory not found, initializing...")
                init()
                print("✅ Migration repository initialized")
            
            # Check if there are any migrations to run
            try:
                print("📤 Applying database migrations...")
                upgrade()
                print("✅ Database migrations completed successfully!")
                return True
                
            except Exception as e:
                print(f"⚠️  Migration upgrade failed: {e}")
                print("🔄 Attempting to create initial migration...")
                
                # Try to create and run initial migration
                migrate(message="Initial migration - Event Stream Engine")
                upgrade()
                print("✅ Initial migration created and applied successfully!")
                return True
                
        except Exception as e:
            print(f"❌ Database migration failed: {e}")
            print("\nTroubleshooting steps:")
            print("1. Ensure database is running and accessible")
            print("2. Check DATABASE_URL environment variable")
            print("3. Verify database user has sufficient permissions")
            return False

def create_sample_data():
    """Create sample data for development/testing"""
    
    app = create_app()
    
    with app.app_context():
        try:
            from app.core.data_model import User, ConsentState
            
            # Check if sample data already exists
            existing_users = User.query.count()
            if existing_users > 0:
                print(f"ℹ️  Sample data already exists ({existing_users} users found)")
                return
            
            print("📝 Creating sample development data...")
            
            # Create sample users
            sample_users = [
                User(
                    phone_number="+1234567890",
                    consent_state=ConsentState.OPT_IN,
                    attributes={
                        "first_name": "John",
                        "last_name": "Doe", 
                        "customer_segment": "premium",
                        "timezone": "America/New_York"
                    }
                ),
                User(
                    phone_number="+1234567891",
                    consent_state=ConsentState.OPT_IN,
                    attributes={
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "customer_segment": "standard", 
                        "timezone": "America/Los_Angeles"
                    }
                ),
                User(
                    phone_number="+1234567892",
                    consent_state=ConsentState.OPT_OUT,
                    attributes={
                        "first_name": "Bob",
                        "last_name": "Johnson",
                        "customer_segment": "basic",
                        "timezone": "America/Chicago"
                    }
                )
            ]
            
            for user in sample_users:
                db.session.add(user)
            
            db.session.commit()
            print(f"✅ Created {len(sample_users)} sample users")
            
        except Exception as e:
            db.session.rollback()
            print(f"⚠️  Sample data creation failed: {e}")

def main():
    """Main migration script entry point"""
    
    print("🚀 Event Stream Engine - Database Setup")
    print("=" * 50)
    
    # Run migrations
    if run_migrations():
        print("\n📊 Database migration completed successfully!")
        
        # Create sample data for development
        if os.getenv('FLASK_ENV') == 'development':
            print("\n🔧 Development environment detected, creating sample data...")
            create_sample_data()
        
        print("\n🎉 Database setup completed!")
        print("\nNext steps:")
        print("1. Start the web service: docker compose up web")
        print("2. Access the application: http://localhost:8000")
        print("3. Check health: curl http://localhost:8000/health")
        
    else:
        print("\n❌ Database setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()