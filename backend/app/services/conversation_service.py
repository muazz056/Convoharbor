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
            # "no/nah/thanks/thank you" as closing — covers "no thanks", "nah thanks", "no thank you" etc.
            # Also handles "no thanks for the information/help/etc."
            r'^(no|nah|nope|noo)[\s,]+(thanks|thank you|thank|ty|bye|goodbye|more|further|questions)[\s\S]*$',
            # "no thanks for..." — explicit gratitude + closure
            r'^(no|nah|nope|noo)[\s,]+thanks[\s,]+for[\s\S]*$',
            # "okay/ok/cool/alright/sure" + optional "thanks/thank you/bye" as closing
            r'^(okay|ok|cool|alright|sure|fine|gotcha|understood)[\s,]*(thanks|thank you|thank|ty|bye|goodbye)?[\s\S]*$',
            # "thanks/thank you" + optional "bye/goodbye" as closing
            r'^(thanks|thank you|thank|ty|cheers)[\s,]*(okay|ok|cool|alright|sure|bye|goodbye)?[\s\S]*$',
            # Satisfaction signals that indicate conversation can end
            r'\b(got it|perfect|great|awesome|helpful|nice|cool|sweet|alright|excellent|wonderful|fantastic|amazing|brilliant|superb|outstanding)\b',
            # Appreciation phrases
            r'\b(appreciate it|that helps|that\'s helpful|very helpful|exactly what i needed|exactly what i wanted|you\'ve been helpful|thanks a lot|thanks so much|many thanks|tysm|ty)\b',
            # "done" / "finish" / "stop" / "quit" / "close" only as a STANDALONE
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

    def _has_follow_up_question(self, last_assistant_message: str) -> bool:
        """Check if the last assistant message contains a follow-up question.

        If the chatbot asked 'Do you want more information?' and the user
        says 'okay', that's answering the question — NOT a farewell.
        """
        if not last_assistant_message:
            return False
        text = last_assistant_message.lower().strip()
        follow_up_patterns = [
            r'\bdo you want\b',
            r'\bwould you like\b',
            r'\bwant more\b',
            r'\bmore information\b',
            r'\bhelp you with\b',
            r'\banything else\b',
            r'\bcan i help\b',
            r'\bshall i\b',
            r'\bshould i\b',
            r'\bdo you need\b',
            r'\bis there anything\b',
            r'\bwould that help\b',
            r'\bneed more\b',
            r'\bclarify\b',
            r'\bexplain further\b',
            r'\bmore details\b',
            r'\?$',  # ends with question mark
        ]
        for p in follow_up_patterns:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    def _is_last_message_informational(self, last_assistant_message: str) -> bool:
        """Check if the assistant's last message was informational/concluding
        (NOT a follow-up question). This helps determine if short user messages
        like 'okay', 'great', 'cool' are farewells.

        Informational = assistant gave an answer, explanation, or statement.
        NOT informational = assistant asked a follow-up question.
        """
        if not last_assistant_message:
            return False
        text = last_assistant_message.lower().strip()

        # If the last assistant message ends with a question mark, it's
        # probably asking something — NOT informational
        if text.endswith('?'):
            return False

        # Check for explicit follow-up question patterns
        follow_up_patterns = [
            r'\bdo you want\b',
            r'\bwould you like\b',
            r'\bwant more\b',
            r'\bmore information\b',
            r'\bhelp you with\b',
            r'\banything else\b',
            r'\bcan i help\b',
            r'\bshall i\b',
            r'\bshould i\b',
            r'\bdo you need\b',
            r'\bis there anything\b',
            r'\bwould that help\b',
            r'\bneed more\b',
            r'\bclarify\b',
            r'\bexplain further\b',
            r'\bmore details\b',
        ]
        for p in follow_up_patterns:
            if re.search(p, text, re.IGNORECASE):
                return False

        # If none of the above matched, the message is informational/concluding
        return True

    def is_smart_farewell(self, message: str, last_assistant_message: str = None) -> bool:
        """Smart farewell detection with intelligent context analysis.

        Logic:
        - Chatbot: "Here's the answer..." → User: "okay" = farewell ✅
        - Chatbot: "Here's the answer..." → User: "great" = farewell ✅
        - Chatbot: "Do you want more info?" → User: "okay" = answering, NOT farewell ❌
        - Chatbot: "Do you want more info?" → User: "okay thanks" = farewell ✅ (strong signal)
        - Chatbot: "Do you want more info?" → User: "bye" = farewell ✅ (strong signal)
        - No last message → User: "okay" = farewell ✅ (can't be answering anything)
        """
        if not self.is_farewell(message):
            return False

        msg = message.lower().strip()

        # Strong farewell signals in the user message always mean farewell,
        # regardless of what the assistant asked. These are explicit closings.
        strong_farewell_patterns = [
            r'\b(bye|goodbye|see you|farewell|take care|have a good day|have a nice day)\b',
            r'\b(thanks|thank you|thank|ty|cheers)\b',
            r'\b(done|finished|nothing else|no more questions|i\'m done|im done|i\'m all set|all set|that\'s it|that\'s all)\b',
            r'\b(got it,?\s*thanks|perfect,?\s*thanks|great,?\s*thanks)\b',
            r'^(no|nah|nope)[\s,]+(thanks|thank you|thank|ty|bye|goodbye|more|further|questions)?[\s\S]*$',
            r'^(okay|ok|cool|alright|sure|fine|gotcha|understood)[\s,]*(thanks|thank you|thank|ty|bye|goodbye)?[\s\S]*$',
            r'^(thanks|thank you|thank|ty|cheers)[\s,]*(okay|ok|cool|alright|sure|bye|goodbye)?[\s\S]*$',
        ]
        for p in strong_farewell_patterns:
            if re.search(p, msg, re.IGNORECASE):
                return True

        # For weaker signals (just "okay", "alright", "great", "cool", etc.),
        # use intelligent context analysis:
        if not last_assistant_message:
            # No prior message — short acknowledgment = farewell
            return True

        if self._has_follow_up_question(last_assistant_message):
            # Assistant asked a follow-up question — user is probably answering
            return False

        if self._is_last_message_informational(last_assistant_message):
            # Assistant gave an informational response — short acknowledgment = farewell
            # e.g., assistant: "The answer is 42." → user: "okay" = farewell
            return True

        # Default: treat as farewell (the message matched a farewell pattern
        # and the assistant didn't ask a follow-up question)
        return True

    def get_greeting_response(self, chatbot_config: Dict) -> str:
        """Get appropriate greeting response"""
        custom_greeting = chatbot_config.get('prompts', {}).get('greeting')
        if custom_greeting:
            return custom_greeting
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
        custom_farewell = chatbot_config.get('prompts', {}).get('farewell')
        if custom_farewell:
            return custom_farewell
        import random
        return random.choice(self.farewell_responses)

    def should_restrict_to_knowledge_base(self, message: str, chatbot_config: Dict) -> bool:
        """Determine if message should be restricted to knowledge base based on mode"""
        mode = chatbot_config.get('mode', 'strict')
        if mode == 'permissive':
            return False
        else:
            if self.is_greeting(message) or self.is_farewell(message):
                return False
            else:
                return True

    def detect_conversation_ending(self, message: str, conversation_id: int, last_assistant_message: str = None) -> bool:
        """Detect if conversation should end and mark it accordingly."""
        try:
            if self.is_smart_farewell(message, last_assistant_message):
                conversation = Conversation.query.get(conversation_id)
                if conversation and not conversation.conversation_ended:
                    conversation.conversation_ended = True
                    conversation.ended_at = datetime.utcnow()
                    db.session.commit()
                    current_app.logger.info(f"Conversation {conversation_id} marked as ended")
                    return True
            return False
        except Exception as e:
            current_app.logger.error(f"Error detecting conversation ending: {str(e)}")
            return False

    def add_satisfaction_rating(self, conversation_id: int, rating: int, feedback: str = None) -> bool:
        """Add satisfaction rating — always APPENDS a new ConversationFeedback record"""
        try:
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                return False
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                return False
            # Keep conversation's latest rating (used for unique-conversation math)
            conversation.satisfaction_rating = rating
            conversation.satisfaction_feedback = feedback
            # Also APPEND a new ConversationFeedback record (so every submission is preserved)
            from ..models.conversation import ConversationFeedback
            feedback_record = ConversationFeedback(
                conversation_id=conversation_id,
                rating=rating,
                feedback_type='rating',
                feedback_text=feedback,
                user_id=conversation.user_id
            )
            db.session.add(feedback_record)
            db.session.commit()
            current_app.logger.info(f"Appended satisfaction rating {rating}/5 to conversation {conversation_id} (feedback #{feedback_record.id})")
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
        """Get conversation statistics including satisfaction ratings from ConversationFeedback"""
        try:
            from sqlalchemy import func
            from ..models.conversation import ConversationFeedback
            total_conversations = Conversation.query.filter_by(tenant_id=tenant_id).count()
            ended_conversations = Conversation.query.filter_by(
                tenant_id=tenant_id, conversation_ended=True
            ).count()
            # Query from ConversationFeedback (all submissions, unique conversations)
            ratings_query = db.session.query(
                func.avg(ConversationFeedback.rating).label('avg_rating'),
                func.count(func.distinct(ConversationFeedback.conversation_id)).label('rating_count')
            ).join(Conversation, ConversationFeedback.conversation_id == Conversation.id).filter(
                Conversation.tenant_id == tenant_id,
                Conversation.status != 'deleted',
                ConversationFeedback.feedback_type == 'rating'
            ).first()
            avg_rating = float(ratings_query.avg_rating) if ratings_query.avg_rating else 0.0
            rating_count = ratings_query.rating_count or 0
            rating_distribution = {}
            for i in range(1, 6):
                count = db.session.query(
                    func.count(func.distinct(ConversationFeedback.conversation_id))
                ).join(Conversation, ConversationFeedback.conversation_id == Conversation.id).filter(
                    Conversation.tenant_id == tenant_id,
                    Conversation.status != 'deleted',
                    ConversationFeedback.feedback_type == 'rating',
                    ConversationFeedback.rating == i
                ).scalar() or 0
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
                'total_conversations': 0, 'ended_conversations': 0,
                'rated_conversations': 0, 'average_satisfaction': 0.0,
                'rating_distribution': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0},
                'completion_rate': 0.0
            }

    def should_show_rating_prompt(self, conversation_id: int) -> bool:
        """Check if conversation just ended and should show rating prompt"""
        try:
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                return False
            return (conversation.conversation_ended and conversation.satisfaction_rating is None)
        except Exception as e:
            current_app.logger.error(f"Error checking rating prompt: {str(e)}")
            return False