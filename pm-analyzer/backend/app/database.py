import sqlite3
import os
import logging
from flask import g

logger = logging.getLogger(__name__)

# Allow database path override via environment variable
_default_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'sap_pm.db')
DATABASE_PATH = os.environ.get('DATABASE_PATH', _default_db_path)
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'schema.sql')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row # Access columns by name
    return db

def close_db(e=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database with the schema."""
    if not os.path.exists(os.path.dirname(DATABASE_PATH)):
        os.makedirs(os.path.dirname(DATABASE_PATH))

    with sqlite3.connect(DATABASE_PATH) as db:
        with open(SCHEMA_PATH, mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
    logger.info(f"Database initialized at {DATABASE_PATH}")
