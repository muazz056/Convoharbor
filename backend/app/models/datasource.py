# app/models/datasource.py

from datetime import datetime
from .. import db


class DataSource(db.Model):
    """
    Represents a data source (uploaded file or crawled URL) for a chatbot
    """
    __tablename__ = 'data_sources'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    chatbot_id = db.Column(db.Integer, db.ForeignKey('chatbots.id'), nullable=True)  # Optional association
    source_type = db.Column(db.String(20), nullable=False)  # 'upload', 'crawl', 'api'
    source_name = db.Column(db.String(500), nullable=False)  # filename or URL
    source_url = db.Column(db.Text)  # S3 URL for uploads, original URL for crawls
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    meta_data = db.Column(db.JSON, default=dict)  # file size, type, processing results, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<DataSource {self.source_name}>'
