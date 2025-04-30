"""Database connection and session configuration.

This module sets up the SQLAlchemy engine and the session_local factory based on DATABASE_URL.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

database_url = os.getenv("DATABASE_URL", "sqlite:///./data.db")

connect_args = {}
if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(database_url, connect_args=connect_args)

session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
