"""
Database abstraction layer supporting both SQLite (local dev) and PostgreSQL (BTP production).

Usage:
    - Local development: Uses SQLite by default (DATABASE_PATH env var)
    - BTP production: Reads PostgreSQL credentials from VCAP_SERVICES
    - Override: Set DATABASE_URL env var to a PostgreSQL connection string

The module provides a unified interface via get_db() / close_db() that
works transparently with both backends. Row access by column name is
supported in both modes.
"""

import os
import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional, Any

from flask import g

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_default_db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'sap_pm.db'
)

DATABASE_PATH = os.environ.get('DATABASE_PATH', _default_db_path)

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'schema.sql'
)

SCHEMA_PG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'schema_pg.sql'
)


def _detect_database_type() -> str:
    """Detect which database backend to use based on environment."""
    # Explicit override
    if os.environ.get('DATABASE_TYPE'):
        return os.environ['DATABASE_TYPE'].lower()

    # PostgreSQL URL present
    if os.environ.get('DATABASE_URL'):
        return 'postgresql'

    # BTP Cloud Foundry environment
    if os.environ.get('VCAP_SERVICES'):
        import json
        try:
            services = json.loads(os.environ['VCAP_SERVICES'])
            if services.get('postgresql-db') or services.get('postgresql'):
                return 'postgresql'
        except (json.JSONDecodeError, KeyError):
            pass

    return 'sqlite'


DATABASE_TYPE = _detect_database_type()


# ---------------------------------------------------------------------------
# PostgreSQL connection pool (lazy-initialized)
# ---------------------------------------------------------------------------

_pg_pool = None


def _get_pg_connection_string() -> str:
    """Build PostgreSQL connection string from environment."""
    # Direct URL takes priority
    if os.environ.get('DATABASE_URL'):
        return os.environ['DATABASE_URL']

    # BTP VCAP_SERVICES
    if os.environ.get('VCAP_SERVICES'):
        import json
        try:
            services = json.loads(os.environ['VCAP_SERVICES'])
            pg_services = services.get('postgresql-db', []) or services.get('postgresql', [])
            if pg_services:
                creds = pg_services[0].get('credentials', {})
                uri = creds.get('uri', '')
                if uri:
                    return uri
                # Build from individual fields
                host = creds.get('hostname', 'localhost')
                port = creds.get('port', 5432)
                dbname = creds.get('dbname', 'pm_analyzer')
                user = creds.get('username', '')
                password = creds.get('password', '')
                return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback to individual env vars
    host = os.environ.get('PG_HOST', 'localhost')
    port = os.environ.get('PG_PORT', '5432')
    dbname = os.environ.get('PG_DATABASE', 'pm_analyzer')
    user = os.environ.get('PG_USER', 'pm_analyzer')
    password = os.environ.get('PG_PASSWORD', '')
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def _get_pg_pool():
    """Get or create the PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is None:
        from psycopg2 import pool as pg_pool
        conn_string = _get_pg_connection_string()
        logger.info("Creating PostgreSQL connection pool")
        _pg_pool = pg_pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=int(os.environ.get('PG_POOL_MAX', '10')),
            dsn=conn_string
        )
    return _pg_pool


# ---------------------------------------------------------------------------
# DictRow wrapper for PostgreSQL (matches sqlite3.Row interface)
# ---------------------------------------------------------------------------

class PgDictCursor:
    """Wraps a psycopg2 cursor to return dict-like rows (matching sqlite3.Row)."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        # Convert ? placeholders to %s for PostgreSQL
        pg_query = query.replace('?', '%s')
        self._cursor.execute(pg_query, params)
        return self

    def executemany(self, query, params_list):
        pg_query = query.replace('?', '%s')
        self._cursor.executemany(pg_query, params_list)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return DictRow(row, self._cursor.description)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [DictRow(row, self._cursor.description) for row in rows]

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size)
        return [DictRow(row, self._cursor.description) for row in rows]

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return getattr(self._cursor, 'lastrowid', None)

    def close(self):
        self._cursor.close()


class DictRow:
    """Row wrapper providing dict-like access by column name, matching sqlite3.Row."""

    __slots__ = ('_data', '_columns')

    def __init__(self, row_tuple, description):
        self._columns = [desc[0] for desc in description] if description else []
        self._data = dict(zip(self._columns, row_tuple))

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._data.values())

    def __len__(self):
        return len(self._data)

    def keys(self):
        return self._columns

    def values(self):
        return list(self._data.values())

    def items(self):
        return list(self._data.items())

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __repr__(self):
        return f"DictRow({self._data})"


# ---------------------------------------------------------------------------
# PostgreSQL connection wrapper (mimics sqlite3.Connection interface)
# ---------------------------------------------------------------------------

class PgConnectionWrapper:
    """Wraps a psycopg2 connection to match the sqlite3.Connection interface."""

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._closed = False

    def execute(self, query, params=None):
        cursor = PgDictCursor(self._conn.cursor())
        cursor.execute(query, params)
        return cursor

    def executemany(self, query, params_list):
        cursor = PgDictCursor(self._conn.cursor())
        cursor.executemany(query, params_list)
        return cursor

    def cursor(self):
        return PgDictCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._closed:
            self._pool.putconn(self._conn)
            self._closed = True

    @property
    def row_factory(self):
        return None

    @row_factory.setter
    def row_factory(self, value):
        # Ignored for PostgreSQL - DictRow handles this
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_db():
    """
    Get a database connection for the current request context.

    Returns a connection that supports:
        - conn.execute(sql, params) -> cursor with dict-like rows
        - conn.commit()
        - row["column_name"] access

    Works transparently with both SQLite and PostgreSQL.
    """
    db = getattr(g, '_database', None)
    if db is None:
        if DATABASE_TYPE == 'postgresql':
            pool = _get_pg_pool()
            raw_conn = pool.getconn()
            raw_conn.autocommit = False
            db = g._database = PgConnectionWrapper(raw_conn, pool)
            logger.debug("Opened PostgreSQL connection from pool")
        else:
            db = g._database = sqlite3.connect(DATABASE_PATH)
            db.row_factory = sqlite3.Row
            logger.debug(f"Opened SQLite connection: {DATABASE_PATH}")
    return db


def close_db(e=None):
    """Close the database connection for the current request context."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        g._database = None


def get_standalone_connection():
    """
    Get a database connection outside of Flask request context.

    Used by background jobs, security modules, and CLI scripts.
    Caller is responsible for closing the connection.
    """
    if DATABASE_TYPE == 'postgresql':
        pool = _get_pg_pool()
        raw_conn = pool.getconn()
        raw_conn.autocommit = False
        return PgConnectionWrapper(raw_conn, pool)
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


@contextmanager
def get_db_connection():
    """
    Context manager for database connections outside Flask request context.

    Usage:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM QMEL")
            rows = cursor.fetchall()
            conn.commit()
    """
    conn = get_standalone_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database with the schema."""
    if DATABASE_TYPE == 'postgresql':
        schema_file = SCHEMA_PG_PATH
        if not os.path.exists(schema_file):
            logger.warning(f"PostgreSQL schema not found at {schema_file}, using SQLite schema")
            schema_file = SCHEMA_PATH

        pool = _get_pg_pool()
        conn = pool.getconn()
        try:
            with open(schema_file, mode='r') as f:
                conn.cursor().execute(f.read())
            conn.commit()
            logger.info("PostgreSQL database initialized")
        finally:
            pool.putconn(conn)
    else:
        if not os.path.exists(os.path.dirname(DATABASE_PATH)):
            os.makedirs(os.path.dirname(DATABASE_PATH))

        with sqlite3.connect(DATABASE_PATH) as db:
            with open(SCHEMA_PATH, mode='r') as f:
                db.cursor().executescript(f.read())
            db.commit()
        logger.info(f"SQLite database initialized at {DATABASE_PATH}")


def close_pool():
    """Close the connection pool (call on app shutdown)."""
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.closeall()
        _pg_pool = None
        logger.info("PostgreSQL connection pool closed")


def get_database_info() -> dict:
    """Return information about the current database configuration."""
    return {
        'type': DATABASE_TYPE,
        'path': DATABASE_PATH if DATABASE_TYPE == 'sqlite' else None,
        'host': os.environ.get('PG_HOST', 'from VCAP_SERVICES') if DATABASE_TYPE == 'postgresql' else None,
        'pool_max': int(os.environ.get('PG_POOL_MAX', '10')) if DATABASE_TYPE == 'postgresql' else None,
    }
