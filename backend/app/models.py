# app/models.py

from . import db
from datetime import datetime
import uuid

def generate_uuid():
    """Generates a URL-safe UUID string for session IDs."""
    return str(uuid.uuid4())

class Conversation(db.Model):
    __tablename__ = 'conversation'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), unique=True, nullable=False, default=generate_uuid, index=True)
    user_id = db.Column(db.String(255), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade="all, delete-orphan")
    
    # --- NEW: Add a relationship to the conversation-level feedback ---
    # `uselist=False` indicates a one-to-one relationship: one conversation has one feedback entry.
    feedback = db.relationship('ConversationFeedback', backref='conversation', uselist=False, cascade="all, delete-orphan")
    # --- END NEW ---

    def __repr__(self):
        return f'<Conversation session_id={self.session_id}>'

class Message(db.Model):
    __tablename__ = 'message'
    # ... (This model remains exactly the same, with the per-message 'rating' column) ...
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    rating = db.Column(db.String(10), nullable=True)


# --- NEW TABLE FOR CONVERSATION-LEVEL FEEDBACK ---
class ConversationFeedback(db.Model):
    __tablename__ = 'conversation_feedback'

    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key to link this feedback to a specific conversation
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), unique=True, nullable=False)
    
    # The overall rating for the entire conversation
    # Using an integer (e.g., 1-5) is more flexible than thumbs-up/down for overall experience.
    overall_rating = db.Column(db.Integer, nullable=False)
    
    # Optional tags to categorize the feedback
    tags = db.Column(db.JSON, nullable=True) # e.g., ["helpful", "slow", "inaccurate"]

    # Also add the message id of the message that the feedback is about
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    
    # Optional free-form text comment
    comment = db.Column(db.Text, nullable=True)
    
    # The user_id of the person who submitted the feedback (can be null for visitors)
    submitted_by_user_id = db.Column(db.String(255), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ConversationFeedback conversation_id={self.conversation_id} rating={self.overall_rating}>'
# --- END NEW TABLE ---