#!/bin/bash

# This script starts the Flask application using the Gunicorn server.
# It's configured for development with auto-reloading.

echo "Starting Gunicorn server for development..."

# Set the environment to development
export FLASK_ENV=development

# Gunicorn command explained:
# --bind 0.0.0.0:5000   : Bind to all network interfaces on port 5000.
#                        This allows access from other devices on your network.
# --workers 1          : Use a single worker process. The --reload flag works best with one worker.
# --log-level debug    : Print detailed logs for easier debugging.
# --reload             : The key feature. Gunicorn will watch for file changes and
#                        automatically restart the worker, clearing any caches.
# "run:app"            : The WSGI application entry point. Gunicorn looks for a variable
#                        named 'app' inside the 'run.py' module.

exec gunicorn --bind 0.0.0.0:3000 --workers 1 --log-level debug --reload "run:app"
