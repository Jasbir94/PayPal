"""SQLAlchemy engine factory supporting SQLite and PostgreSQL URLs."""
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

def normalize_database_url(url: str | None) -> str:
    database_url = (url or '').strip()
    while database_url.startswith('DATABASE_URL='):
        database_url = database_url[len('DATABASE_URL='):].strip()
    if len(database_url) >= 2 and database_url[0] == database_url[-1] and database_url[0] in ('"', "'"):
        database_url = database_url[1:-1].strip()
    if database_url.startswith('postgres://'):
        return 'postgresql+psycopg://' + database_url[len('postgres://'):]
    if database_url.startswith('postgresql://'):
        return 'postgresql+psycopg://' + database_url[len('postgresql://'):]
    return database_url


def create_database_engine(url: str | None = None) -> Engine:
    database_url = normalize_database_url(url or os.getenv('DATABASE_URL', 'sqlite:///./app_shield.db'))
    options = {'check_same_thread': False} if database_url.startswith('sqlite:') else {}
    pool = StaticPool if database_url in ('sqlite://', 'sqlite:///:memory:') else None
    return create_engine(database_url, connect_args=options, pool_pre_ping=True, poolclass=pool)
