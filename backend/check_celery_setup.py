#!/usr/bin/env python
"""
Script to verify Celery setup and configuration.
Run this to check if all auto-retraining tasks are properly registered.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.celery_app import make_celery


def check_redis_connection():
    """Check if Redis is accessible"""
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        print(f"✅ Redis connection successful: {redis_url}")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print(f"   Make sure Redis is running and REDIS_URL is correct in .env")
        return False


def check_celery_tasks():
    """Check if all Celery tasks are registered"""
    try:
        app = create_app()
        celery = make_celery(app)
        
        # Get all registered tasks
        registered_tasks = list(celery.tasks.keys())
        
        # Expected retraining tasks
        expected_tasks = [
            'app.tasks.retraining_tasks.auto_retrain_chatbots',
            'app.tasks.retraining_tasks.process_data_source',
            'app.tasks.retraining_tasks.update_vector_embeddings',
            'app.tasks.retraining_tasks.feedback_based_retraining',
            'app.tasks.retraining_tasks.cleanup_old_embeddings',
        ]
        
        print("\n📋 Registered Celery Tasks:")
        print("=" * 70)
        
        for task in sorted(registered_tasks):
            if not task.startswith('celery.'):  # Skip built-in Celery tasks
                is_retraining = '✨' if 'retraining' in task else '  '
                print(f"{is_retraining} {task}")
        
        print("\n🔍 Checking Auto-Retraining Tasks:")
        print("=" * 70)
        
        all_found = True
        for task in expected_tasks:
            if task in registered_tasks:
                print(f"✅ {task}")
            else:
                print(f"❌ {task} - NOT FOUND")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error checking Celery tasks: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_beat_schedule():
    """Check if periodic tasks are properly scheduled"""
    try:
        app = create_app()
        celery = make_celery(app)
        
        print("\n⏰ Celery Beat Schedule (Periodic Tasks):")
        print("=" * 70)
        
        beat_schedule = celery.conf.beat_schedule
        
        for name, config in beat_schedule.items():
            task = config['task']
            schedule = config['schedule']
            
            # Convert schedule to human-readable format
            if schedule == 3600.0:
                schedule_str = "Every 1 hour"
            elif schedule == 43200.0:
                schedule_str = "Every 12 hours (twice daily)"
            elif schedule == 86400.0:
                schedule_str = "Every 24 hours (daily)"
            elif schedule == 604800.0:
                schedule_str = "Every 7 days (weekly)"
            else:
                schedule_str = f"Every {schedule} seconds"
            
            emoji = "✨" if "retraining" in task else "📅"
            print(f"{emoji} {name}")
            print(f"   Task: {task}")
            print(f"   Schedule: {schedule_str}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking beat schedule: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_task_routing():
    """Check if task routing is properly configured"""
    try:
        app = create_app()
        celery = make_celery(app)
        
        print("\n🚦 Task Routing Configuration:")
        print("=" * 70)
        
        task_routes = celery.conf.task_routes
        
        for pattern, config in task_routes.items():
            queue = config.get('queue', 'default')
            print(f"📦 Pattern: {pattern}")
            print(f"   → Queue: {queue}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking task routing: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all checks"""
    print("🔍 Celery Auto-Retraining Setup Verification")
    print("=" * 70)
    
    checks = {
        "Redis Connection": check_redis_connection(),
        "Celery Tasks": check_celery_tasks(),
        "Beat Schedule": check_beat_schedule(),
        "Task Routing": check_task_routing(),
    }
    
    print("\n" + "=" * 70)
    print("📊 Summary")
    print("=" * 70)
    
    all_passed = True
    for check_name, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not result:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n✅ All checks passed! Auto-retraining system is ready.")
        print("\n📚 Next steps:")
        print("   1. Start Redis (if not running): redis-server")
        print("   2. Start Celery Worker:")
        print("      celery -A app.celery_app:make_celery worker --loglevel=info --pool=solo -Q retraining,notifications,analytics")
        print("   3. Start Celery Beat:")
        print("      celery -A app.celery_app:make_celery beat --loglevel=info")
        print("\n📖 See CELERY_SETUP.md for detailed instructions.")
        return 0
    else:
        print("\n❌ Some checks failed. Please review the errors above.")
        print("📖 See CELERY_SETUP.md for troubleshooting steps.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

