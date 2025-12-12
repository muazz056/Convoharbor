# app/services/history_service.py

from app import db
from app.models import Conversation, Message
from sqlalchemy import desc
from datetime import datetime, timedelta
from flask import current_app
from app.models import ConversationFeedback

def get_or_create_conversation(session_id: str | None, user_id: str | None) -> Conversation:
    """
    Retrieves an existing conversation by session_id or creates a new one.
    If a conversation is found, its `updated_at` timestamp is touched.
    If a new session_id is needed, it's generated automatically by the model.

    Args:
        session_id: The existing session ID, if any.
        user_id: The optional client-provided user identifier.

    Returns:
        The active Conversation object.
    """
    conversation = None
    if session_id:
        conversation = Conversation.query.filter_by(session_id=session_id).first()

    if conversation:
        # Session exists, keep it alive by updating the timestamp
        conversation.updated_at = datetime.utcnow()
        db.session.commit()
        current_app.logger.info(f"Continuing conversation for session_id: {session_id}")
    else:
        # No session found or no session_id provided, create a new one
        conversation = Conversation(user_id=user_id)
        db.session.add(conversation)
        db.session.commit() # Commit to get the generated session_id
        current_app.logger.info(f"Started new conversation with session_id: {conversation.session_id}")
        
    return conversation

CONCLUDING_PHRASES_TO_REMOVE = [
    "Is there anything else I can help you with regarding this topic?",
    "Is there anything else I can assist you with today?",
    "I hope that was helpful!"
]

def get_recent_history(conversation, limit=5):
    """
    Get recent conversation history formatted for context.
    Added limit parameter for performance optimization.
    """
    try:
        # Optimized query with limit for faster performance - FIXED: Use created_at not timestamp
        recent_messages = Message.query.filter_by(
            conversation_id=conversation.id
        ).order_by(Message.created_at.desc()).limit(limit * 2).all()  # Get limit*2 to have pairs
        
        if not recent_messages:
            return ""

        # Build conversation context (most recent first, then reverse)
        history_parts = []
        for message in reversed(recent_messages[-limit*2:]):  # Take most recent limit*2 messages
            if message.role == 'user':
                history_parts.append(f"User: {message.content}")
            elif message.role == 'assistant':
                history_parts.append(f"Assistant: {message.content}")
        
        return "\n".join(history_parts[-limit*2:])  # Limit total lines
        
    except Exception as e:
        current_app.logger.error(f"Error getting recent history: {e}")
        return ""

def save_message_pair(conversation: Conversation, user_query: str, assistant_answer: str) -> int:
    """
    Saves the user query and the assistant's answer to the database.
    """
    user_message = Message(conversation=conversation, role='user', content=user_query)
    assistant_message = Message(conversation=conversation, role='assistant', content=assistant_answer)
    
    db.session.add(user_message)
    db.session.add(assistant_message)
    # The conversation's `updated_at` is automatically touched by the onupdate trigger.
    db.session.commit()
    
    return assistant_message.id

def calculate_expiration_date(conversation: Conversation) -> str:
    """
    Calculates the 30-day expiration date based on the last update time.
    """
    thirty_days_from_update = conversation.updated_at + timedelta(days=30)
    return thirty_days_from_update.isoformat() + "Z" # ISO 8601 format with Zulu time

def save_conversation_feedback(session_id: str, rating: int, tags: list | None, comment: str | None, user_id: str | None) -> tuple[bool, str]:
    """
    Saves overall feedback for an entire conversation.

    Args:
        session_id: The ID of the conversation to apply feedback to.
        rating: An integer rating (e.g., 1-5).
        tags: A list of tags categorizing the experience.
        comment: Free-form text comment.
        user_id: The optional client-provided user identifier.

    Returns:
        A tuple of (success_boolean, message_string).
    """
    # 1. Find the conversation by its public session_id
    conversation = Conversation.query.filter_by(session_id=session_id).first()
    if not conversation:
        return False, "Conversation with the specified session_id not found."
        
    # 2. Check if feedback already exists for this conversation
    if conversation.feedback:
        return False, "Feedback has already been submitted for this conversation."

    # 3. Create and save the new feedback entry
    new_feedback = ConversationFeedback(
        conversation_id=conversation.id,
        overall_rating=rating,
        tags=tags,
        comment=comment,
        submitted_by_user_id=user_id
    )
    
    db.session.add(new_feedback)
    db.session.commit()
    
    current_app.logger.info(f"CONVERSATION_FEEDBACK_RECORDED: session_id={session_id}, rating={rating}")
    
    return True, "Conversation feedback recorded successfully."

def get_history_by_session_id(session_id: str) -> dict | None:
    """
    Fetches the complete message history for a given session_id.

    Args:
        session_id: The public ID of the conversation.

    Returns:
        A dictionary containing conversation metadata and all messages, or None if not found.
    """
    conversation = Conversation.query.filter_by(session_id=session_id).first()
    
    if not conversation:
        return None

    # Fetch all messages in chronological order
    messages = conversation.messages.order_by(Message.created_at.asc()).all()
    
    # Serialize the messages into a clean format
    message_list = [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat() + "Z",
            "rating": msg.rating
        } 
        for msg in messages
    ]

    return {
        "session_id": conversation.session_id,
        "user_id": conversation.user_id,
        "created_at": conversation.created_at.isoformat() + "Z",
        "updated_at": conversation.updated_at.isoformat() + "Z",
        "message_count": len(message_list),
        "messages": message_list
    }


def get_sessions_by_user_id(user_id: str) -> list[dict]:
    """
    Fetches a list of all conversation sessions associated with a given user_id.

    Args:
        user_id: The client-provided user identifier.

    Returns:
        A list of dictionaries, where each dictionary is a summary of a conversation.
    """
    # Fetch all conversations for the user, most recent first
    conversations = Conversation.query.filter_by(user_id=user_id).order_by(Conversation.updated_at.desc()).all()
    
    # Serialize the conversations into a summary format
    session_list = [
        {
            "session_id": conv.session_id,
            "created_at": conv.created_at.isoformat() + "Z",
            "last_updated_at": conv.updated_at.isoformat() + "Z",
            "message_count": conv.messages.count(),
            # You could generate a title for the conversation here with an LLM call if desired
            "title": f"Conversation from {conv.created_at.strftime('%Y-%m-%d %H:%M')}"
        }
        for conv in conversations
    ]
    
    return session_list

def get_recent_sessions(user_id: str = None, limit: int = 20) -> list:
    """
    Get recent conversation sessions with metadata.
    
    Args:
        user_id: Filter by user ID (optional)
        limit: Maximum number of sessions to return
        
    Returns:
        List of session dictionaries with metadata
    """
    try:
        # Build query
        query = Conversation.query
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        # Get recent conversations
        conversations = query.order_by(Conversation.updated_at.desc()).limit(limit).all()
        
        sessions = []
        for conv in conversations:
            # Count messages for this conversation
            message_count = Message.query.filter_by(conversation_id=conv.id).count()
            
            # Get last message time
            last_message = Message.query.filter_by(
                conversation_id=conv.id
            ).order_by(Message.created_at.desc()).first()
            
            last_activity = last_message.created_at if last_message else conv.created_at
            
            sessions.append({
                "session_id": conv.session_id,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "message_count": message_count,
                "last_activity": last_activity.isoformat(),
                "user_id": conv.user_id
            })
        
        return sessions
        
    except Exception as e:
        current_app.logger.error(f"Error getting recent sessions: {e}")
        return []