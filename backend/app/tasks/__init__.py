# app/tasks/__init__.py

# Task modules for Celery background processing

# Import all task modules to ensure they are registered with Celery
from . import notification_tasks
from . import analytics_tasks
from . import retraining_tasks

__all__ = ['notification_tasks', 'analytics_tasks', 'retraining_tasks']