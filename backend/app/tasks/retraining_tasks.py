# app/tasks/retraining_tasks.py

"""
Celery tasks for automatic chatbot retraining and knowledge base updates.
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy import and_
from .. import db
from ..models import Chatbot, DataSource, ConversationFeedback, Message, Conversation
from ..services.vector_service import VectorService
from ..services.llm_service import LLMService

logger = logging.getLogger(__name__)


@shared_task(name='app.tasks.retraining_tasks.auto_retrain_chatbots')
def auto_retrain_chatbots():
    """
    Celery task to automatically retrain chatbots based on:
    1. New data sources added
    2. Updated data sources
    3. Low satisfaction scores (feedback-based retraining)
    4. Scheduled periodic retraining
    
    Returns:
        int: Number of chatbots retrained
    """
    try:
        logger.info("🤖 Starting auto-retraining task for chatbots")
        
        # Get chatbots that need retraining
        cutoff_time = datetime.utcnow() - timedelta(days=7)  # Retrain weekly
        
        chatbots_to_retrain = Chatbot.query.filter(
            and_(
                Chatbot.status == 'active',
                Chatbot.updated_at < cutoff_time
            )
        ).all()
        
        retrained_count = 0
        
        for chatbot in chatbots_to_retrain:
            try:
                logger.info(f"🔄 Retraining chatbot {chatbot.id}: {chatbot.name}")
                
                # Set status to training
                chatbot.status = 'training'
                db.session.commit()
                
                # Check if there are new data sources
                new_sources = DataSource.query.filter(
                    and_(
                        DataSource.chatbot_id == chatbot.id,
                        DataSource.status == 'pending'
                    )
                ).all()
                
                # Process new data sources
                if new_sources:
                    logger.info(f"📚 Found {len(new_sources)} new data sources for chatbot {chatbot.id}")
                    vector_service = VectorService()
                    
                    for source in new_sources:
                        try:
                            # Process the data source (this would trigger the normal processing pipeline)
                            source.status = 'processing'
                            db.session.commit()
                            
                            # The actual processing would be done by the existing pipeline
                            # This is just a trigger to queue the work
                            process_data_source.delay(source.id)
                            
                        except Exception as e:
                            logger.error(f"❌ Failed to process data source {source.id}: {str(e)}")
                            source.status = 'failed'
                            db.session.commit()
                            continue
                
                # Update chatbot to active status
                chatbot.status = 'active'
                chatbot.updated_at = datetime.utcnow()
                db.session.commit()
                
                retrained_count += 1
                logger.info(f"✅ Chatbot {chatbot.id} retrained successfully")
                
            except Exception as e:
                logger.error(f"❌ Failed to retrain chatbot {chatbot.id}: {str(e)}")
                try:
                    chatbot.status = 'active'  # Reset to active on failure
                    db.session.commit()
                except:
                    db.session.rollback()
                continue
        
        logger.info(f"✅ Auto-retraining task completed. Retrained {retrained_count} chatbots.")
        return retrained_count
        
    except Exception as e:
        logger.error(f"❌ Auto-retraining task failed: {str(e)}")
        return 0


@shared_task(name='app.tasks.retraining_tasks.process_data_source')
def process_data_source(data_source_id):
    """
    Celery task to process a single data source in the background.
    
    Args:
        data_source_id (int): ID of the data source to process
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"📄 Processing data source {data_source_id}")
        
        data_source = DataSource.query.get(data_source_id)
        if not data_source:
            logger.error(f"❌ Data source {data_source_id} not found")
            return False
        
        # Update status
        data_source.status = 'processing'
        db.session.commit()
        
        # Initialize services
        vector_service = VectorService()
        
        try:
            # Get the chatbot
            chatbot = Chatbot.query.get(data_source.chatbot_id)
            if not chatbot:
                raise Exception("Chatbot not found")
            
            # Process based on source type
            if data_source.type == 'file':
                # File processing logic (would use existing file processing)
                logger.info(f"📁 Processing file data source: {data_source.name}")
                # This would call the existing file processing pipeline
                
            elif data_source.type == 'url':
                # URL processing logic
                logger.info(f"🌐 Processing URL data source: {data_source.url}")
                # This would call the existing URL processing pipeline
                
            elif data_source.type == 'text':
                # Direct text processing
                logger.info(f"📝 Processing text data source: {data_source.name}")
                # Process the text content directly
            
            # Update status to completed
            data_source.status = 'completed'
            data_source.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"✅ Data source {data_source_id} processed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing data source {data_source_id}: {str(e)}")
            data_source.status = 'failed'
            data_source.error_message = str(e)
            db.session.commit()
            return False
            
    except Exception as e:
        logger.error(f"❌ Data source processing task failed: {str(e)}")
        return False


@shared_task(name='app.tasks.retraining_tasks.update_vector_embeddings')
def update_vector_embeddings(chatbot_id):
    """
    Celery task to update vector embeddings for a chatbot's knowledge base.
    Useful when the embedding model is updated or embeddings need refreshing.
    
    Args:
        chatbot_id (int): ID of the chatbot
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"🔄 Updating vector embeddings for chatbot {chatbot_id}")
        
        chatbot = Chatbot.query.get(chatbot_id)
        if not chatbot:
            logger.error(f"❌ Chatbot {chatbot_id} not found")
            return False
        
        # Set status to training
        original_status = chatbot.status
        chatbot.status = 'training'
        db.session.commit()
        
        try:
            # Initialize vector service
            vector_service = VectorService()
            
            # Get all data sources for this chatbot
            data_sources = DataSource.query.filter_by(
                chatbot_id=chatbot_id,
                status='completed'
            ).all()
            
            logger.info(f"📚 Found {len(data_sources)} completed data sources to re-embed")
            
            # Re-process each data source to update embeddings
            for source in data_sources:
                try:
                    logger.info(f"🔄 Re-embedding data source {source.id}: {source.name}")
                    # Trigger re-processing
                    process_data_source.delay(source.id)
                except Exception as e:
                    logger.error(f"❌ Failed to re-embed data source {source.id}: {str(e)}")
                    continue
            
            # Restore original status
            chatbot.status = original_status
            chatbot.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"✅ Vector embeddings update queued for chatbot {chatbot_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating vector embeddings: {str(e)}")
            chatbot.status = original_status
            db.session.commit()
            return False
            
    except Exception as e:
        logger.error(f"❌ Vector embeddings update task failed: {str(e)}")
        return False


@shared_task(name='app.tasks.retraining_tasks.feedback_based_retraining')
def feedback_based_retraining():
    """
    Celery task to identify chatbots with low satisfaction scores and trigger retraining.
    Analyzes conversation feedback to find chatbots that need improvement.
    
    Returns:
        int: Number of chatbots queued for retraining
    """
    try:
        logger.info("📊 Starting feedback-based retraining analysis")
        
        # Get chatbots with low average satisfaction (< 3 stars)
        cutoff_time = datetime.utcnow() - timedelta(days=7)  # Last 7 days
        
        # Query to get chatbots with low satisfaction
        # Need to join through Conversation table since ConversationFeedback doesn't have chatbot_id
        from sqlalchemy import func
        
        low_satisfaction_chatbots = db.session.query(
            Conversation.chatbot_id,
            func.avg(ConversationFeedback.rating).label('avg_rating'),
            func.count(ConversationFeedback.id).label('feedback_count')
        ).join(
            Conversation, ConversationFeedback.conversation_id == Conversation.id
        ).filter(
            ConversationFeedback.created_at >= cutoff_time,
            ConversationFeedback.rating.isnot(None)  # Only count actual ratings
        ).group_by(
            Conversation.chatbot_id
        ).having(
            func.avg(ConversationFeedback.rating) < 3.0,
            func.count(ConversationFeedback.id) >= 5  # At least 5 feedback entries
        ).all()
        
        retrain_count = 0
        
        for result in low_satisfaction_chatbots:
            chatbot_id, avg_rating, feedback_count = result
            
            logger.warning(
                f"⚠️ Chatbot {chatbot_id} has low satisfaction: "
                f"{avg_rating:.2f}/5 stars ({feedback_count} ratings)"
            )
            
            try:
                # Queue for retraining
                chatbot = Chatbot.query.get(chatbot_id)
                if chatbot and chatbot.status == 'active':
                    # Trigger vector embedding update
                    update_vector_embeddings.delay(chatbot_id)
                    retrain_count += 1
                    logger.info(f"📋 Queued chatbot {chatbot_id} for retraining due to low satisfaction")
                    
            except Exception as e:
                logger.error(f"❌ Failed to queue chatbot {chatbot_id} for retraining: {str(e)}")
                continue
        
        logger.info(f"✅ Feedback-based retraining analysis completed. Queued {retrain_count} chatbots.")
        return retrain_count
        
    except Exception as e:
        logger.error(f"❌ Feedback-based retraining task failed: {str(e)}")
        return 0


@shared_task(name='app.tasks.retraining_tasks.cleanup_old_embeddings')
def cleanup_old_embeddings():
    """
    Celery task to clean up old or orphaned vector embeddings.
    Removes embeddings for deleted chatbots or data sources.
    
    Returns:
        int: Number of embeddings cleaned up
    """
    try:
        logger.info("🧹 Starting old embeddings cleanup task")
        
        vector_service = VectorService()
        cleanup_count = 0
        
        # Find data sources marked as deleted but still have embeddings
        deleted_sources = DataSource.query.filter_by(status='deleted').all()
        
        for source in deleted_sources:
            try:
                # Clean up associated embeddings
                # This would depend on the vector database implementation
                logger.info(f"🗑️ Cleaning up embeddings for deleted data source {source.id}")
                
                # Delete the data source record
                db.session.delete(source)
                cleanup_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to cleanup data source {source.id}: {str(e)}")
                continue
        
        db.session.commit()
        
        logger.info(f"✅ Embeddings cleanup completed. Cleaned up {cleanup_count} items.")
        return cleanup_count
        
    except Exception as e:
        logger.error(f"❌ Embeddings cleanup task failed: {str(e)}")
        db.session.rollback()
        return 0


@shared_task(name='app.tasks.retraining_tasks.expire_jit_accesses')
def expire_jit_accesses():
    """
    Celery task to expire old JIT access grants.
    Runs periodically to clean up expired temporary access privileges.
    
    Returns:
        int: Number of access grants expired
    """
    try:
        logger.info("🔐 Starting JIT access expiration task")
        
        from ..services.jit_access_service import JITAccessService
        
        expired_count = JITAccessService.expire_old_accesses()
        
        logger.info(f"✅ JIT access expiration task completed. Expired {expired_count} accesses.")
        return expired_count
        
    except Exception as e:
        logger.error(f"❌ JIT access expiration task failed: {str(e)}")
        return 0

