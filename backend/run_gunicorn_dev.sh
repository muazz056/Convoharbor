#!/bin/bash

echo "Starting Gunicorn server for development..."

export FLASK_ENV=development

exec gunicorn --worker-class eventlet \
         --workers 5 \
         --bind 0.0.0.0:5001 \
         --timeout 120 \
         --access-logfile logs/access.log \
         --error-logfile logs/error.log \
         --log-level info \
         "run:app"
