"""
Alembic environment configuration for PM Notification Analyzer.

Supports both SQLite (local dev) and PostgreSQL (BTP production).
The database URL is resolved in this order:
    1. ALEMBIC_DATABASE_URL env var
    2. DATABASE_URL env var
    3. VCAP_SERVICES (BTP Cloud Foundry)
    4. alembic.ini sqlalchemy.url (SQLite default)
"""

import os
import sys
import json
import logging
from logging.config import fileConfig

from alembic import context

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger('alembic.env')

# No SQLAlchemy MetaData - we use raw SQL migrations
target_metadata = None


def get_url() -> str:
    """Resolve database URL from environment."""
    # Explicit Alembic URL
    url = os.environ.get('ALEMBIC_DATABASE_URL')
    if url:
        return url

    # General database URL
    url = os.environ.get('DATABASE_URL')
    if url:
        return url

    # BTP VCAP_SERVICES
    vcap = os.environ.get('VCAP_SERVICES')
    if vcap:
        try:
            services = json.loads(vcap)
            pg_services = services.get('postgresql-db', []) or services.get('postgresql', [])
            if pg_services:
                uri = pg_services[0].get('credentials', {}).get('uri', '')
                if uri:
                    return uri
        except (json.JSONDecodeError, KeyError):
            pass

    # SQLite from DATABASE_PATH
    db_path = os.environ.get('DATABASE_PATH')
    if db_path:
        return f"sqlite:///{db_path}"

    # Default from alembic.ini
    return config.get_main_option("sqlalchemy.url", "sqlite:///data/sap_pm.db")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode - generates SQL script."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode - connects to database."""
    from sqlalchemy import engine_from_config, pool

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == 'sqlite'
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,  # Required for SQLite ALTER TABLE
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
