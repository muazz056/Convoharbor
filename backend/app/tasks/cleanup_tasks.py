from celery import shared_task
from flask import current_app


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def cleanup_expired_cloudinary_files(self):
    try:
        from ..services.cloudinary_service import CloudinaryService
        service = CloudinaryService()
        deleted = service.cleanup_temp_files()
        return {"cleaned_up": deleted}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=3600)
def cleanup_expired_sessions(self):
    try:
        redis_service = current_app.redis_service
        if redis_service:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = redis_service.client.scan(cursor, "session:*", count=100)
                if keys:
                    for key in keys:
                        ttl = redis_service.client.ttl(key)
                        if ttl < 0:
                            redis_service.client.delete(key)
                            deleted += 1
                if cursor == 0:
                    break
            return {"expired_sessions_removed": deleted}
        return {"expired_sessions_removed": 0}
    except Exception as exc:
        raise self.retry(exc=exc)
