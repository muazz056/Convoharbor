import os
from dotenv import load_dotenv

# Load environment variables BEFORE any app imports to ensure Config class
# attributes are evaluated with .env vars already loaded
load_dotenv()

from app import create_app, db
from flask_migrate import Migrate

# Get the configuration name from environment variables or use default
config_name = os.getenv('FLASK_ENV', 'default')
app = create_app(config_name)

# This hook allows us to use the 'flask shell' command to get a pre-configured
# shell with the 'app' and 'db' objects ready to use.
@app.shell_context_processor
def make_shell_context():
    return dict(app=app, db=db)

if __name__ == '__main__':
    # Use port 5001 to avoid conflicts with Apple's AirTunes on port 5000
    # Use WebSocket server instead of regular Flask server
    from app.services.websocket_service import websocket_service
    use_reloader = os.getenv('FLASK_RELOAD', 'true').lower() in ['true', '1', 't']
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', 5001))
    websocket_service.socketio.run(app, host=host, port=port, debug=True, use_reloader=use_reloader)