"""Database connection and session configuration.

This module sets up the SQLAlchemy engine and the session_local factory based on DATABASE_URL.
It also provides a context manager for database sessions to ensure proper cleanup.
"""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

database_url = os.getenv("DATABASE_URL", "sqlite:///./data.db")

connect_args = {}
if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(database_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db_session():
    """Context manager for database sessions.

    Ensures that sessions are properly closed and rolled back on exceptions.

    Yields:
        Session: SQLAlchemy Session object.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
