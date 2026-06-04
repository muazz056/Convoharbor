import os
from datetime import datetime
from .. import db

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    Vector = None
    PGVECTOR_AVAILABLE = False

VECTOR_DIMENSION = int(os.environ.get('VECTOR_DIMENSION', '3072'))


def _vector_col(dim):
    if PGVECTOR_AVAILABLE:
        return db.Column(Vector(dim), nullable=True)
    return db.Column(db.JSON, nullable=True)


class DocumentEmbedding(db.Model):
    __tablename__ = 'document_embeddings'

    id = db.Column(db.Integer, primary_key=True)
    vector_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    doc_id = db.Column(db.String(36), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False, default=0)
    page_content = db.Column(db.Text, nullable=False)
    meta_data = db.Column(db.JSON, default=dict)
    source = db.Column(db.String(500), nullable=False, index=True)
    chatbot_id = db.Column(db.Integer, db.ForeignKey('chatbots.id'), nullable=True, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    provider = db.Column(db.String(20), nullable=False, default='openai')
    embedding_openai = _vector_col(VECTOR_DIMENSION)
    embedding_gemini = _vector_col(VECTOR_DIMENSION)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<DocumentEmbedding {self.vector_id}>'
