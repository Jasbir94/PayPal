"""Check portable tables and SQLite storage without external services."""
from sqlalchemy.orm import Session
from backend.app.database.db import create_database_engine
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
