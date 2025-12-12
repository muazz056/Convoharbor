#!/usr/bin/env python
"""
Script to run auto-retraining tasks manually.
This runs tasks synchronously for easy testing and maintenance.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.tasks.retraining_tasks import (
    auto_retrain_chatbots,
    feedback_based_retraining,
    cleanup_old_embeddings
)


def show_chatbot_stats():
    """Show current chatbot statistics"""
    print("\n" + "="*70)
    print("📊 Current Database Statistics")
    print("="*70)
    
    try:
        from app.models import Chatbot, DataSource, ConversationFeedback, Conversation
        from app import db
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # Count total chatbots
        total_chatbots = Chatbot.query.count()
        active_chatbots = Chatbot.query.filter_by(status='active').count()
        
        # Count old chatbots (7+ days without update)
        cutoff = datetime.utcnow() - timedelta(days=7)
        old_chatbots = Chatbot.query.filter(
            Chatbot.status == 'active',
            Chatbot.updated_at < cutoff
        ).count()
        
        # Count pending data sources
        pending_sources = DataSource.query.filter_by(status='pending').count()
        
        # Get average satisfaction
        avg_rating = db.session.query(
            func.avg(ConversationFeedback.rating)
        ).filter(
            ConversationFeedback.created_at >= cutoff,
            ConversationFeedback.rating.isnot(None)
        ).scalar() or 0.0
        
        print(f"📊 Total Chatbots: {total_chatbots}")
        print(f"   ├─ Active: {active_chatbots}")
        print(f"   └─ Need Retraining (7+ days old): {old_chatbots}")
        print(f"\n📚 Data Sources:")
        print(f"   └─ Pending Processing: {pending_sources}")
        print(f"\n⭐ Average Satisfaction (last 7 days): {avg_rating:.2f}/5.0")
        
        # Low satisfaction chatbots
        low_satisfaction = db.session.query(
            Conversation.chatbot_id,
            func.avg(ConversationFeedback.rating).label('avg_rating'),
            func.count(ConversationFeedback.id).label('count')
        ).join(
            Conversation, ConversationFeedback.conversation_id == Conversation.id
        ).filter(
            ConversationFeedback.created_at >= cutoff,
            ConversationFeedback.rating.isnot(None)
        ).group_by(
            Conversation.chatbot_id
        ).having(
            func.avg(ConversationFeedback.rating) < 3.0,
            func.count(ConversationFeedback.id) >= 5
        ).all()
        
        if low_satisfaction:
            print(f"\n⚠️  Chatbots with Low Satisfaction:")
            for chatbot_id, rating, count in low_satisfaction:
                chatbot = Chatbot.query.get(chatbot_id)
                name = chatbot.name if chatbot else f"ID {chatbot_id}"
                print(f"   • {name}: {rating:.2f}/5.0 ({count} ratings)")
        
        print()
        
    except Exception as e:
        print(f"⚠️  Could not retrieve statistics: {e}")


def run_auto_retrain():
    """Run automatic chatbot retraining"""
    print("\n" + "="*70)
    print("TASK 1: Auto-Retrain Chatbots")
    print("="*70)
    print("📋 This task finds chatbots that haven't been updated in 7+ days")
    print("   and queues them for retraining.\n")
    
    try:
        result = auto_retrain_chatbots()
        print(f"✅ SUCCESS: Retrained {result} chatbot(s)")
        if result == 0:
            print("   ℹ️  No chatbots needed retraining (all are recently updated)")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_feedback_based():
    """Run feedback-based retraining"""
    print("\n" + "="*70)
    print("TASK 2: Feedback-Based Retraining")
    print("="*70)
    print("📋 This task analyzes feedback from the last 7 days and finds")
    print("   chatbots with low satisfaction scores (<3 stars).\n")
    
    try:
        result = feedback_based_retraining()
        print(f"✅ SUCCESS: Queued {result} chatbot(s) for retraining")
        if result == 0:
            print("   ℹ️  No chatbots with low satisfaction (all performing well!)")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_cleanup():
    """Run embedding cleanup"""
    print("\n" + "="*70)
    print("TASK 3: Cleanup Old Embeddings")
    print("="*70)
    print("📋 This task removes orphaned vector embeddings for deleted")
    print("   data sources to free up storage.\n")
    
    try:
        result = cleanup_old_embeddings()
        print(f"✅ SUCCESS: Cleaned up {result} embedding(s)")
        if result == 0:
            print("   ℹ️  No old embeddings to clean (database is clean!)")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tasks"""
    print("🔄 Auto-Retraining System - Manual Run")
    print("="*70)
    print("This script runs the auto-retraining tasks WITHOUT Celery/Redis.")
    print("Tasks will run synchronously (immediately) in this process.")
    print("="*70)
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        # Show current stats
        show_chatbot_stats()
        
        # Run tasks
        results = {
            "Auto-Retrain Chatbots": run_auto_retrain(),
            "Feedback-Based Retraining": run_feedback_based(),
            "Cleanup Old Embeddings": run_cleanup(),
        }
        
        # Summary
        print("\n" + "="*70)
        print("📊 Task Summary")
        print("="*70)
        
        all_passed = True
        for task_name, result in results.items():
            status = "✅ SUCCESS" if result else "❌ FAILED"
            print(f"{status} - {task_name}")
            if not result:
                all_passed = False
        
        print("="*70)
        
        if all_passed:
            print("\n✅ All tasks completed successfully!")
            print("\n📝 Notes:")
            print("   • These tasks ran synchronously (immediately)")
            print("   • In production, they run in background via Celery")
            return 0
        else:
            print("\n❌ Some tasks failed. Check the errors above.")
            return 1


if __name__ == '__main__':
    sys.exit(main())
