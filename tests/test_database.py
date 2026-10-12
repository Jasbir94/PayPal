"""Check portable tables and SQLite storage without external services."""
from sqlalchemy.orm import Session
from backend.app.database.db import create_database_engine, normalize_database_url
from backend.app.database.models import Base, AccountRecord
from datetime import datetime, timezone

def test_sqlite_account_storage():
    engine = create_database_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(AccountRecord(account_id='A1', created_at=datetime.now(timezone.utc)))
        session.commit()
        assert session.get(AccountRecord, 'A1').fraud_report_count == 0
    engine.dispose()


def test_database_url_normalizes_duplicated_env_prefix_and_postgres_scheme():
    normalized = normalize_database_url('DATABASE_URL="postgres://user:pass@host/db?sslmode=require"')
    assert normalized == 'postgresql+psycopg://user:pass@host/db?sslmode=require'


def test_database_url_keeps_existing_psycopg_url():
    url = 'postgresql+psycopg://user:pass@host/db?sslmode=require'
    assert normalize_database_url(url) == url
