"""Enable pgvector extension and add embedding_vec column to knowledge_chunks

Revision ID: 0007_pgvector_knowledge_chunks
Revises: 0006_saved_schemes_reminders
Create Date: 2026-09-15 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

revision: str = '0007_pgvector_knowledge_chunks'
down_revision: Union[str, None] = '0006_saved_schemes_reminders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # Enable pgvector extension in PostgreSQL
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Add vector column (768 dimensions for Gemini text-embedding-004)
        if Vector is not None:
            op.add_column('knowledge_chunks', sa.Column('embedding_vec', Vector(768), nullable=True))
        else:
            op.execute("ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(768);")

        # Create HNSW index for fast cosine distance vector queries
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
            "ON knowledge_chunks USING hnsw (embedding_vec vector_cosine_ops);"
        )
    else:
        # SQLite / Dev fallback column
        op.add_column('knowledge_chunks', sa.Column('embedding_vec', sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw;")
    
    op.drop_column('knowledge_chunks', 'embedding_vec')
