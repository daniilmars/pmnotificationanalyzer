"""
Unit tests for the database abstraction layer.
Verifies both SQLite and PostgreSQL wrapper behavior.
"""
import pytest
import os
import tempfile
import sqlite3

# Ensure we're using SQLite for tests
os.environ['DATABASE_TYPE'] = 'sqlite'
os.environ['AUTH_ENABLED'] = 'false'


class TestDatabaseModule:
    """Tests for database module configuration."""

    def test_database_type_detection_sqlite(self):
        """Test that DATABASE_TYPE defaults to sqlite."""
        from app.database import DATABASE_TYPE
        assert DATABASE_TYPE == 'sqlite'

    def test_database_info(self):
        """Test get_database_info returns correct structure."""
        from app.database import get_database_info
        info = get_database_info()
        assert 'type' in info
        assert info['type'] == 'sqlite'
        assert 'path' in info
        assert info['path'] is not None

    def test_schema_paths_exist(self):
        """Test that schema files are accessible."""
        from app.database import SCHEMA_PATH, SCHEMA_PG_PATH
        assert os.path.exists(SCHEMA_PATH)
        assert os.path.exists(SCHEMA_PG_PATH)


class TestSQLiteConnection:
    """Tests for SQLite connection within Flask context."""

    def test_get_db_returns_connection(self, app):
        """Test get_db returns a valid database connection."""
        from app.database import get_db
        with app.app_context():
            db = get_db()
            assert db is not None
            cursor = db.execute("SELECT 1 as test")
            row = cursor.fetchone()
            assert row['test'] == 1

    def test_get_db_returns_same_connection(self, app):
        """Test get_db returns the same connection within a request."""
        from app.database import get_db
        with app.app_context():
            db1 = get_db()
            db2 = get_db()
            assert db1 is db2

    def test_close_db(self, app):
        """Test close_db cleans up connection."""
        from app.database import get_db, close_db
        with app.app_context():
            get_db()
            close_db()
            from flask import g
            assert getattr(g, '_database', None) is None

    def test_init_db(self, app):
        """Test init_db creates tables."""
        from app.database import init_db, get_db
        with app.app_context():
            init_db()
            db = get_db()
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='QMEL'")
            row = cursor.fetchone()
            assert row is not None


class TestStandaloneConnection:
    """Tests for standalone connections (outside Flask context)."""

    def test_standalone_connection(self):
        """Test get_standalone_connection returns a working connection."""
        from app.database import get_standalone_connection
        conn = get_standalone_connection()
        try:
            cursor = conn.execute("SELECT 1 as test")
            row = cursor.fetchone()
            assert row['test'] == 1
        finally:
            conn.close()

    def test_db_connection_context_manager(self):
        """Test get_db_connection context manager."""
        from app.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT 1 as test")
            row = cursor.fetchone()
            assert row['test'] == 1


class TestDictRow:
    """Tests for the DictRow wrapper."""

    def test_dict_row_access_by_name(self):
        """Test DictRow supports access by column name."""
        from app.database import DictRow

        class FakeDesc:
            def __init__(self, name):
                self.name = name
            def __getitem__(self, idx):
                return self.name

        desc = [FakeDesc('col1'), FakeDesc('col2')]
        # DictRow takes a tuple and description
        row = DictRow(('val1', 'val2'), desc)
        assert row['col1'] == 'val1'
        assert row['col2'] == 'val2'

    def test_dict_row_access_by_index(self):
        """Test DictRow supports access by integer index."""
        from app.database import DictRow

        class FakeDesc:
            def __init__(self, name):
                self.name = name
            def __getitem__(self, idx):
                return self.name

        desc = [FakeDesc('col1'), FakeDesc('col2')]
        row = DictRow(('val1', 'val2'), desc)
        assert row[0] == 'val1'
        assert row[1] == 'val2'

    def test_dict_row_keys(self):
        """Test DictRow.keys() returns column names."""
        from app.database import DictRow

        class FakeDesc:
            def __init__(self, name):
                self.name = name
            def __getitem__(self, idx):
                return self.name

        desc = [FakeDesc('a'), FakeDesc('b')]
        row = DictRow(('1', '2'), desc)
        assert row.keys() == ['a', 'b']

    def test_dict_row_contains(self):
        """Test 'in' operator on DictRow."""
        from app.database import DictRow

        class FakeDesc:
            def __init__(self, name):
                self.name = name
            def __getitem__(self, idx):
                return self.name

        desc = [FakeDesc('col1')]
        row = DictRow(('val1',), desc)
        assert 'col1' in row
        assert 'col2' not in row

    def test_dict_row_len(self):
        """Test len() on DictRow."""
        from app.database import DictRow

        class FakeDesc:
            def __init__(self, name):
                self.name = name
            def __getitem__(self, idx):
                return self.name

        desc = [FakeDesc('a'), FakeDesc('b'), FakeDesc('c')]
        row = DictRow(('1', '2', '3'), desc)
        assert len(row) == 3

    def test_dict_row_get(self):
        """Test DictRow.get() with default."""
        from app.database import DictRow

        class FakeDesc:
            def __init__(self, name):
                self.name = name
            def __getitem__(self, idx):
                return self.name

        desc = [FakeDesc('col1')]
        row = DictRow(('val1',), desc)
        assert row.get('col1') == 'val1'
        assert row.get('missing', 'default') == 'default'
