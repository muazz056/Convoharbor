import os
from celery import Celery
from flask import Flask


def make_celery(app: Flask) -> Celery:
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    celery = Celery(
        app.import_name,
        backend=redis_url,
        broker=redis_url,
        include=[
            'app.tasks.notification_tasks',
            'app.tasks.analytics_tasks',
            'app.tasks.retraining_tasks',
            'app.tasks.email_tasks',
            'app.tasks.cleanup_tasks'
        ]
    )

    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,
        task_soft_time_limit=25 * 60,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        result_expires=3600,
        task_routes={
            'app.tasks.notification_tasks.*': {'queue': 'notifications'},
            'app.tasks.analytics_tasks.*': {'queue': 'analytics'},
            'app.tasks.retraining_tasks.*': {'queue': 'retraining'},
            'app.tasks.email_tasks.*': {'queue': 'email'},
            'app.tasks.cleanup_tasks.*': {'queue': 'cleanup'},
        },
        beat_schedule={
            'send-weekly-reports': {
                'task': 'app.tasks.notification_tasks.send_weekly_reports',
                'schedule': 604800.0,
            },
            'cleanup-old-notifications': {
                'task': 'app.tasks.notification_tasks.cleanup_old_notifications',
                'schedule': 86400.0,
            },
            'check-usage-alerts': {
                'task': 'app.tasks.analytics_tasks.check_usage_alerts',
                'schedule': 3600.0,
            },
            'auto-retrain-chatbots': {
                'task': 'app.tasks.retraining_tasks.auto_retrain_chatbots',
                'schedule': 86400.0,
            },
            'feedback-based-retraining': {
                'task': 'app.tasks.retraining_tasks.feedback_based_retraining',
                'schedule': 43200.0,
            },
            'cleanup-old-embeddings': {
                'task': 'app.tasks.retraining_tasks.cleanup_old_embeddings',
                'schedule': 604800.0,
            },
            'expire-jit-accesses': {
                'task': 'app.tasks.retraining_tasks.expire_jit_accesses',
                'schedule': 300.0,
            },
            'cleanup-expired-cloudinary-files': {
                'task': 'app.tasks.cleanup_tasks.cleanup_expired_cloudinary_files',
                'schedule': 86400.0,
            },
            'cleanup-expired-sessions': {
                'task': 'app.tasks.cleanup_tasks.cleanup_expired_sessions',
                'schedule': 3600.0,
            },
        },
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


def init_celery(app: Flask) -> Celery:
    celery = make_celery(app)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
