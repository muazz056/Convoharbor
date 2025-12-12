# app/celery_app.py

import os
from celery import Celery
from flask import Flask


def make_celery(app: Flask) -> Celery:
    """Create and configure Celery instance"""
    
    # Get Redis URL from environment
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    celery = Celery(
        app.import_name,
        backend=redis_url,
        broker=redis_url,
        include=[
            'app.tasks.notification_tasks',
            'app.tasks.analytics_tasks',
            'app.tasks.retraining_tasks'
        ]
    )
    
    # Configure Celery
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        task_soft_time_limit=25 * 60,  # 25 minutes
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        result_expires=3600,  # 1 hour
        
        # Task routing
        task_routes={
            'app.tasks.notification_tasks.*': {'queue': 'notifications'},
            'app.tasks.analytics_tasks.*': {'queue': 'analytics'},
            'app.tasks.retraining_tasks.*': {'queue': 'retraining'},
        },
        
        # Beat schedule for periodic tasks
        beat_schedule={
            'send-weekly-reports': {
                'task': 'app.tasks.notification_tasks.send_weekly_reports',
                'schedule': 604800.0,  # 7 days in seconds
            },
            'cleanup-old-notifications': {
                'task': 'app.tasks.notification_tasks.cleanup_old_notifications',
                'schedule': 86400.0,  # 1 day in seconds
            },
            'check-usage-alerts': {
                'task': 'app.tasks.analytics_tasks.check_usage_alerts',
                'schedule': 3600.0,  # 1 hour in seconds
            },
            # Auto-retraining tasks
            'auto-retrain-chatbots': {
                'task': 'app.tasks.retraining_tasks.auto_retrain_chatbots',
                'schedule': 86400.0,  # 1 day in seconds (daily check)
            },
            'feedback-based-retraining': {
                'task': 'app.tasks.retraining_tasks.feedback_based_retraining',
                'schedule': 43200.0,  # 12 hours in seconds (twice daily)
            },
            'cleanup-old-embeddings': {
                'task': 'app.tasks.retraining_tasks.cleanup_old_embeddings',
                'schedule': 604800.0,  # 7 days in seconds (weekly cleanup)
            },
            # Security tasks
            'expire-jit-accesses': {
                'task': 'app.tasks.retraining_tasks.expire_jit_accesses',
                'schedule': 300.0,  # 5 minutes in seconds (frequent checks)
            },
        },
    )
    
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery


def init_celery(app: Flask) -> Celery:
    """Initialize Celery with Flask app"""
    celery = make_celery(app)
    
    # Update task base classes
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery
