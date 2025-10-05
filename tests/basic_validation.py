"""
Test runner script for basic system validation
"""
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../app'))

def test_flask_app_creation():
    """Test basic Flask app creation"""
    try:
        from app.main import create_app
        app = create_app({'TESTING': True})
        return True, "Flask app created successfully"
    except Exception as e:
        return False, f"Failed to create Flask app: {str(e)}"

def test_database_models():
    """Test database models import"""
    try:
        from app.core.models.user import User
        from app.core.models.campaign import Campaign
        from app.core.models.template import Template
        from app.core.models.message import Message
        return True, "All database models imported successfully"
    except Exception as e:
        return False, f"Failed to import models: {str(e)}"

def test_api_blueprints():
    """Test API blueprint imports"""
    try:
        from app.api.webhooks import webhooks_bp
        from app.api.v1.users import users_bp
        from app.api.v1.campaigns import campaigns_bp
        return True, "API blueprints imported successfully"
    except Exception as e:
        return False, f"Failed to import API blueprints: {str(e)}"

def test_ui_routes():
    """Test UI routes import"""
    try:
        from app.ui_routes import ui
        return True, "UI routes imported successfully"
    except Exception as e:
        return False, f"Failed to import UI routes: {str(e)}"

def run_basic_validation():
    """Run basic system validation tests"""
    tests = [
        ("Flask App Creation", test_flask_app_creation),
        ("Database Models", test_database_models),
        ("API Blueprints", test_api_blueprints),
        ("UI Routes", test_ui_routes)
    ]
    
    print("🔍 Running Event Stream Engine Basic Validation Tests\n")
    print("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Testing {test_name}... ", end="")
        try:
            success, message = test_func()
            if success:
                print(f"✅ PASS")
                passed += 1
            else:
                print(f"❌ FAIL: {message}")
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All basic validation tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = run_basic_validation()
    sys.exit(0 if success else 1)