from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

import os
import sys
from dotenv import load_dotenv

# Add project root to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Import models for autogenerate support - import all to register with Base.metadata
from models.base import Base
from models.enums import RoleEnum  # noqa: F401 - import to register enum
from models.user import User  # noqa: F401 - import to register with Base.metadata
from models.token import Token  # noqa: F401 - import to register with Base.metadata
from models.api_key import APIKey  # noqa: F401 - import to register with Base.metadata
from models.reset_token import ResetToken  # noqa: F401 - import to register with Base.metadata

# this is the Alembic Config object
config = context.config

# Set database URL from environment
config.set_main_option('sqlalchemy.url', os.environ.get('DATABASE_URL', 'postgresql://agentespacio:agentespacio@db:5432/agentespacio_db'))

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
