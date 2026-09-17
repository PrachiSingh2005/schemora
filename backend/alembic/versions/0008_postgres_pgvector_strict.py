"""Enforce PostgreSQL pgvector extension, columns, and index

Revision ID: 0008_postgres_pgvector_strict
Revises: 0007_pgvector_knowledge_chunks
Create Date: 2026-09-17 23:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

revision: str = '0008_postgres_pgvector_strict'
down_revision: Union[str, None] = '0007_pgvector_knowledge_chunks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # 1. Enable pgvector extension
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # 2. Add extra columns to knowledge_chunks if missing
        cols_chunks = [
            ("section", sa.String(length=64)),
            ("scheme_name", sa.String(length=256)),
            ("jurisdiction", sa.String(length=64)),
            ("state", sa.String(length=64)),
            ("category", sa.String(length=128)),
            ("source_id", sa.String(length=128)),
            ("source_name", sa.String(length=128)),
            ("official_info_url", sa.Text()),
            ("official_app_url", sa.Text()),
            ("official_scheme_url", sa.Text()),
            ("official_portal_url", sa.Text()),
            ("last_verified_at", sa.String(length=64)),
            ("scheme_version", sa.String(length=64)),
            ("is_indexed", sa.Boolean(create_constraint=False, name="is_indexed_bool")),
        ]
        for col_name, col_type in cols_chunks:
            try:
                op.add_column('knowledge_chunks', sa.Column(col_name, col_type, nullable=True))
            except Exception:
                pass

        # 3. Add embedding_vec Vector(768)
        if Vector is not None:
            try:
                op.add_column('knowledge_chunks', sa.Column('embedding_vec', Vector(768), nullable=True))
            except Exception:
                pass
        else:
            op.execute("ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(768);")

        # 4. Create indexes
        try:
            op.create_index(op.f('ix_knowledge_chunks_section'), 'knowledge_chunks', ['section'], unique=False)
        except Exception:
            pass

        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
            "ON knowledge_chunks USING hnsw (embedding_vec vector_cosine_ops);"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw;")
