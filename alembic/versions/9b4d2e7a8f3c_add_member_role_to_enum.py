"""add member role to enum

Revision ID: 9b4d2e7a8f3c
Revises: 3a7f9c2e5d1b
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b4d2e7a8f3c'
down_revision: Union[str, None] = '3a7f9c2e5d1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE roleenum ADD VALUE 'member'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE; member is unused, so leaving it is harmless.
    pass