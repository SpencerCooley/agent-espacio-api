"""rename user role to editor

Revision ID: 3a7f9c2e5d1b
Revises: 2f1e68eb5daf
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a7f9c2e5d1b'
down_revision: Union[str, None] = '2f1e68eb5daf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE roleenum RENAME VALUE 'user' TO 'editor'")


def downgrade() -> None:
    op.execute("ALTER TYPE roleenum RENAME VALUE 'editor' TO 'user'")