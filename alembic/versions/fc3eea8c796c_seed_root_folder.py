"""seed root folder

Revision ID: fc3eea8c796c
Revises: e5f71f68e903
Create Date: 2026-06-01 22:36:44.523165

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc3eea8c796c'
down_revision: Union[str, None] = 'e5f71f68e903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUID for the root folder so it is predictable across environments
ROOT_FOLDER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    now = datetime.now(timezone.utc).isoformat()

    op.execute(f"""
        INSERT INTO folders (id, name, parent_id, path, is_root, created_at, updated_at, created_by_id)
        VALUES ('{ROOT_FOLDER_ID}', 'My Drive', NULL, '/', true, '{now}', '{now}', NULL)
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute(f"DELETE FROM folders WHERE id = '{ROOT_FOLDER_ID}'")
