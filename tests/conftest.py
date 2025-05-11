"""Test configuration and fixtures."""

import os
import sys
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from src.db.models import Base
from src.db.session import get_db_session

# Use an in-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test engine and session factory
test_engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def setup_test_db():
    """Create all tables in the test database."""
    Base.metadata.create_all(bind=test_engine)


def teardown_test_db():
    """Drop all tables from the test database."""
    Base.metadata.drop_all(bind=test_engine)


class BaseTestCase(unittest.TestCase):
    """Base test case with database setup and teardown."""

    @classmethod
    def setUpClass(cls):
        """Set up test database once for the test case."""
        setup_test_db()

    @classmethod
    def tearDownClass(cls):
        """Tear down test database after all tests."""
        teardown_test_db()

    def setUp(self):
        """Set up a new database session for each test."""
        self.db = TestSessionLocal()

    def tearDown(self):
        """Close the database session after each test."""
        self.db.close()
