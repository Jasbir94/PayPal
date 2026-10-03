"""SQLAlchemy engine factory supporting SQLite and PostgreSQL URLs."""
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

def create_database_engine(url: str | None = None) -> Engine:
    database_url = url or os.getenv('DATABASE_URL', 'sqlite:///./app_shield.db')
    options = {'check_same_thread': False} if database_url.startswith('sqlite:') else {}
    return create_engine(database_url, connect_args=options, pool_pre_ping=True)
