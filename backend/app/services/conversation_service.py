# app/services/conversation_service.py

import re
from datetime import datetime
from typing import Dict
from flask import current_app
from .. import db
from ..models.conversation import Conversation


class ConversationService:
    """Service for handling conversation flow, greetings, farewells, and ending detection"""

    def __init__(self):
        # Greeting patterns (case insensitive)
        self.greeting_patterns = [
            r'\b(hi|hello|hey|good morning|good afternoon|good evening|greetings|howdy)\b',
            r'\b(hola|bonjour|guten tag|ciao|namaste)\b',  # Multi-language greetings
            r'^(hi|hello|hey)[\s\W]*$',  # Simple greetings
        ]

        # Farewell/ending patterns (case insensitive).
        # IMPORTANT: bare words like "end" must NOT match in phrases like
        # "at the end", "to the end of the story", "ending of the movie" —
        # they are content words, not farewell signals. The patterns below
        # are anchored or qualified to avoid false positives.
        self.farewell_patterns = [
            # Explicit goodbyes
            r'\b(bye|goodbye|see you|farewell|take care|have a good day|have a nice day)\b',
            # Gratitude + closure phrases (must be the closing of a turn)
            r'\b(thanks for (?:your )?help|thanks[, ]+this was helpful|thank you for (?:your )?help|appreciate (?:it|the help)|cheers)\b',
            # Strong closure phrases
            r'\b(that\'s all|that is all|nothing else|no more questions|i\'m done|im done|i\'m good|i\'m all set|all set|that\'s it|that solved it|got it,? thanks|perfect,? thanks)\b',
            # "done" / "finish" / "stop" / "quit" / "close" only as a STANDALONE
            # word (the whole message is essentially that word). This is the
            # safe form that won't match "at the end" / "the ending".
            r'^(done|finish|finished|stop|quit|exit|close|closed|end|ended)\s*[.!?]?\s*$',
            # Multi-language farewells
            r'\b(adios|au revoir|auf wiedersehen|arrivederci|sayonara|alvida|khoda hafez)\b',
            # "bye" / "thanks" as the whole message
            r'^(bye|goodbye|thanks|thank you|cheers|farewell)[\s\W]*$',
        ]

        # Greeting responses
        self.greeting_responses = [
            "Hello! I'm here to help you. What can I assist you with today?",
            "Hi there! How can I help you?",
            "Hello! Welcome! What would you like to know?",
            "Hi! I'm ready to assist you. What questions do you have?",
            "Hello! Great to see you. How can I be of service?",
        ]

        # Farewell responses
        self.farewell_responses = [
            "Thank you for chatting with me! Have a wonderful day!",
            "You're welcome! Feel free to come back anytime if you have more questions.",
            "Goodbye! It was great helping you today.",
            "Take care! Don't hesitate to reach out if you need assistance in the future.",
            "Thank you! Have a great day and feel free to return anytime!",
        ]

    def is_greeting(self, message: str) -> bool:
        """Check if message is ONLY a greeting (not a greeting + actual question).

        A message like 'Hi' or 'Hello!' is a greeting.
        A message like 'Hi explain about yourself' or 'Hello, what products do you offer?'
        is NOT a greeting — it contains a greeting word but has real content.
        """
        message_lower = message.lower().strip()
        words = message_lower.split()

        # Very short messages (1-3 words) that match a greeting pattern are greetings
        if len(words) <= 3:
            for pattern in self.greeting_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return True
        return False

    def is_farewell(self, message: str) -> bool:
        """Check if message is a farewell/ending message"""
        message_lower = message.lower().strip()
        for pattern in self.farewell_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return True
        return False

    def get_greeting_response(self, chatbot_config: Dict) -> str:
        """Get appropriate greeting response"""
        # Check if chatbot has custom greeting
        custom_greeting = chatbot_config.get('prompts', {}).get('greeting')
        if custom_greeting:
            return custom_greeting

        # Use default greeting based on personality
        personality = chatbot_config.get('personality', {})
        role = personality.get('role', 'Assistant')

        if 'support' in role.lower():
            return f"Hello! I'm your {role}. How can I help you today?"
        elif 'sales' in role.lower():
            return f"Hi there! I'm {role}. What can I show you today?"
        else:
            return f"Hello! I'm {role}. How can I assist you?"

    def get_farewell_response(self, chatbot_config: Dict) -> str:
        """Get appropriate farewell response"""
        # Check if chatbot has custom farewell
        custom_farewell = chatbot_config.get('prompts', {}).get('farewell')
        if custom_farewell:
            return custom_farewell

        # Use default farewell
        import random
        return random.choice(self.farewell_responses)

    def should_restrict_to_knowledge_base(self, message: str, chatbot_config: Dict) -> bool:
        """Determine if message should be restricted to knowledge base based on mode"""
        # Get mode from chatbot config (default to 'strict' for backward compatibility)
        mode = chatbot_config.get('mode', 'strict')

        # Check mode setting
        if mode == 'permissive':
            # Permissive mode: Allow everything (greetings, farewells, general knowledge, KB content)
            return False
        else:  # strict mode
            # Strict mode: Only allow greetings and farewells, everything else must be from KB
            if self.is_greeting(message) or self.is_farewell(message):
                return False  # Allow greetings/farewells without KB restriction
            else:
                return True   # All other messages must be from knowledge base

    def detect_conversation_ending(self, message: str, conversation_id: int) -> bool:
        """Detect if conversation should end and mark it accordingly"""
        try:
            if self.is_farewell(message):
                # Mark conversation as ended
                conversation = Conversation.query.get(conversation_id)
                if conversation and not conversation.conversation_ended:
                    conversation.conversation_ended = True
                    conversation.ended_at = datetime.utcnow()
                    db.session.commit()

                    current_app.logger.info(f"🔚 Conversation {conversation_id} marked as ended")
                    return True

            return False

        except Exception as e:
            current_app.logger.error(f"Error detecting conversation ending: {str(e)}")
            return False

    def add_satisfaction_rating(self, conversation_id: int, rating: int, feedback: str = None) -> bool:
        """Add satisfaction rating to ended conversation"""
        try:
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                return False

            # Validate rating
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                return False

            conversation.satisfaction_rating = rating
            conversation.satisfaction_feedback = feedback
            db.session.commit()

            current_app.logger.info(f"⭐ Added satisfaction rating {rating}/5 to conversation {conversation_id}")

            # Send notification about rating
            try:
                from ..services.notification_service import NotificationService
                notification_service = NotificationService()

                notification_service.send_feedback_notification(
                    tenant_id=conversation.chatbot.tenant_id,
                    chatbot_id=conversation.chatbot_id,
                    conversation_id=conversation_id,
                    feedback_type='satisfaction_rating',
                    rating=rating
                )
            except Exception as e:
                current_app.logger.error(f"Failed to send satisfaction rating notification: {str(e)}")

            return True

        except Exception as e:
            current_app.logger.error(f"Error adding satisfaction rating: {str(e)}")
            return False

    def get_conversation_stats(self, tenant_id: int) -> Dict:
        """Get conversation statistics including satisfaction ratings"""
        try:
            from sqlalchemy import func

            # Get total conversations
            total_conversations = Conversation.query.filter_by(tenant_id=tenant_id).count()

            # Get ended conversations
            ended_conversations = Conversation.query.filter_by(
                tenant_id=tenant_id,
                conversation_ended=True
            ).count()

            # Get satisfaction ratings
            ratings_query = db.session.query(
                func.avg(Conversation.satisfaction_rating).label('avg_rating'),
                func.count(Conversation.satisfaction_rating).label('rating_count')
            ).filter(
                Conversation.tenant_id == tenant_id,
                Conversation.satisfaction_rating.isnot(None)
            ).first()

            avg_rating = float(ratings_query.avg_rating) if ratings_query.avg_rating else 0.0
            rating_count = ratings_query.rating_count or 0

            # Get rating distribution
            rating_distribution = {}
            for i in range(1, 6):
                count = Conversation.query.filter_by(
                    tenant_id=tenant_id,
                    satisfaction_rating=i
                ).count()
                rating_distribution[str(i)] = count

            return {
                'total_conversations': total_conversations,
                'ended_conversations': ended_conversations,
                'rated_conversations': rating_count,
                'average_satisfaction': round(avg_rating, 2),
                'rating_distribution': rating_distribution,
                'completion_rate': round((ended_conversations / total_conversations * 100), 2) if total_conversations > 0 else 0
            }

        except Exception as e:
            current_app.logger.error(f"Error getting conversation stats: {str(e)}")
            return {
                'total_conversations': 0,
                'ended_conversations': 0,
                'rated_conversations': 0,
                'average_satisfaction': 0.0,
                'rating_distribution': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0},
                'completion_rate': 0.0
            }

    def should_show_rating_prompt(self, conversation_id: int) -> bool:
        """Check if conversation just ended and should show rating prompt"""
        try:
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                return False

            # Show rating if conversation just ended and hasn't been rated yet
            return (conversation.conversation_ended
                    and conversation.satisfaction_rating is None)

        except Exception as e:
            current_app.logger.error(f"Error checking rating prompt: {str(e)}")
            return False
