#!/usr/bin/env python
"""
Tests for auto-retraining tasks (NO REDIS REQUIRED).
This runs tasks synchronously for easy testing.
"""

import os
import sys
import pytest
from datetime import datetime, timedelta
from sqlalchemy import func

# Import the tasks
from app.tasks.retraining_tasks import (
    auto_retrain_chatbots,
    feedback_based_retraining,
    cleanup_old_embeddings
)
from app.models import Chatbot, DataSource, ConversationFeedback, Conversation
from app import db, create_app


@pytest.fixture
def app():
    """Create test Flask app"""
    app = create_app()
    return app


def test_auto_retrain(app):
    """Test automatic chatbot retraining"""
    with app.app_context():
        result = auto_retrain_chatbots()
        assert isinstance(result, int)
        assert result >= 0


def test_feedback_based(app):
    """Test feedback-based retraining"""
    with app.app_context():
        result = feedback_based_retraining()
        assert isinstance(result, int)
        assert result >= 0


def test_cleanup(app):
    """Test embedding cleanup"""
    with app.app_context():
        result = cleanup_old_embeddings()
        assert isinstance(result, int)
        assert result >= 0


def test_chatbot_stats(app):
    """Test chatbot statistics"""
    with app.app_context():
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
        
        # Assertions
        assert isinstance(total_chatbots, int)
        assert isinstance(active_chatbots, int)
        assert isinstance(old_chatbots, int)
        assert isinstance(pending_sources, int)
        assert isinstance(avg_rating, float)
        assert avg_rating >= 0 and avg_rating <= 5
        assert isinstance(low_satisfaction, list)
        
        # Relationship assertions
        assert total_chatbots >= active_chatbots
        assert active_chatbots >= old_chatbots
