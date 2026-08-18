"""drop reset_tokens table

Revision ID: 5c1e9a4d7b2f
Revises: 9b4d2e7a8f3c
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c1e9a4d7b2f'
down_revision: Union[str, None] = '9b4d2e7a8f3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('reset_tokens')


def downgrade() -> None:
    op.create_table('reset_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('is_used', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reset_tokens_id'), 'reset_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_reset_tokens_token'), 'reset_tokens', ['token'], unique=True)