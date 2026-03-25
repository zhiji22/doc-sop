"""add agent_memories table

Revision ID: 7d2398f100fb
Revises: 3d72b9115438
Create Date: 2026-03-24 19:22:37.087089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7d2398f100fb'
down_revision: Union[str, Sequence[str], None] = '3d72b9115438'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.agent_memories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id TEXT NOT NULL,
            file_id UUID,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            embedding JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_agent_memories_user ON public.agent_memories(user_id);
        CREATE INDEX IF NOT EXISTS idx_agent_memories_user_file ON public.agent_memories(user_id, file_id);
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS public.agent_memories;")
