from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from netdecker.config import DB_CONNECTION_STRING, LOGGER
from netdecker.models import register_models
from netdecker.models.base import Base

# Simple module-level database setup
engine = create_engine(DB_CONNECTION_STRING)
Session = sessionmaker(engine)

# Track initialization to avoid redundant calls
_db_initialized = False


def initialize_database() -> bool:
    """Initialize the database. Call this once at application startup."""
    global _db_initialized

    if _db_initialized:
        return True

    try:
        inspector = inspect(engine)
        register_models()

        # Get all table names from models
        model_tables = Base.metadata.tables.keys()
        existing_tables = inspector.get_table_names()

        # Check which tables need to be created
        tables_to_create = set(model_tables) - set(existing_tables)

        if tables_to_create:
            LOGGER.info(f"🏗️ Creating missing database tables: {tables_to_create}")
            Base.metadata.create_all(bind=engine)
            LOGGER.info("✨ Database tables created successfully!")
        else:
            LOGGER.debug(
                f"Database already initialized with {len(model_tables)} tables"
            )

        _db_initialized = True
        return True
    except Exception as e:
        LOGGER.error(f"Error initializing database: {e}")
        return False
