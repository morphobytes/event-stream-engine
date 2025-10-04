"""
Event Stream Engine - Flask Application Factory
Main entry point for the Flask application with Celery integration
"""
from flask import Flask
from celery import Celery
import os


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Load configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', '0') == '1'
    
    # Basic health check route
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'event-stream-engine'}, 200
    
    @app.route('/')
    def index():
        return {
            'message': 'Event Stream Engine API',
            'version': '1.0.0',
            'status': 'ready'
        }, 200
    
    # Temporary webhook endpoints for testing connectivity
    @app.route('/webhooks/inbound', methods=['POST'])
    def test_inbound_webhook():
        """Temporary webhook to test Twilio connectivity"""
        from flask import request
        print("🎉 INBOUND WEBHOOK RECEIVED!")
        print("Form data:", dict(request.form))
        print("Headers:", dict(request.headers))
        
        # Return a simple TwiML response
        return '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>✅ Webhook test successful! Your message was received by Event Stream Engine.</Message>
</Response>''', 200, {'Content-Type': 'text/xml'}
    
    @app.route('/webhooks/status', methods=['POST'])
    def test_status_webhook():
        """Temporary webhook to test Twilio status callbacks"""
        from flask import request
        print("📊 STATUS CALLBACK RECEIVED!")
        print("Form data:", dict(request.form))
        
        return {'status': 'received'}, 200
    
    return app


def create_celery(app=None):
    """Create and configure Celery instance"""
    celery = Celery(
        'event-stream-engine',
        broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
    )
    
    if app:
        # Initialize Celery with Flask app context
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    return celery


# Create Flask app instance
app = create_app()

# Create Celery instance
celery_app = create_celery(app)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)