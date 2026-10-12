"""SQL-backed demo wallets, account sessions, and atomic simulated ledger."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import secrets
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import (CheckConstraint, Column, DateTime, ForeignKey, Index, Integer,
    MetaData, String, Table, UniqueConstraint, bindparam, text)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from backend.app.database.db import create_database_engine, normalize_database_url
from backend.app.services.demo_banking_service import InsufficientBalance, _cents, _rupees

_IST = ZoneInfo('Asia/Kolkata')
_METADATA = MetaData()
_WALLETS = Table('app_shield_wallets', _METADATA,
    Column('account_id', String(80), primary_key=True),
    Column('sender_alias', String(32), nullable=False, unique=True),
    Column('display_name', String(160), nullable=False),
    Column('opening_balance_cents', Integer, nullable=False),
    Column('balance_cents', Integer, nullable=False),
    Column('held_cents', Integer, nullable=False, server_default='0'),
    CheckConstraint('opening_balance_cents >= 0'),
    CheckConstraint('balance_cents >= 0'),
    CheckConstraint('held_cents >= 0'))
_ALIASES = Table('app_shield_account_aliases', _METADATA,
    Column('alias', String(32), primary_key=True),
    Column('account_id', String(80), nullable=False),
    Column('display_name', String(160), nullable=False),
    Column('kind', String(32), nullable=False))
_SESSIONS = Table('app_shield_demo_sessions', _METADATA,
    Column('token_hash', String(64), primary_key=True),
    Column('account_id', String(80), ForeignKey('app_shield_wallets.account_id'), nullable=False),
    Column('expires_at', DateTime(timezone=True), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False))
_PAYMENTS = Table('app_shield_payments', _METADATA,
    Column('transaction_id', String(80), primary_key=True),
    Column('idempotency_key', String(160), nullable=False, unique=True),
    Column('sender_account_id', String(80), ForeignKey('app_shield_wallets.account_id'), nullable=False),
    Column('recipient_account_id', String(80)),
    Column('recipient_alias', String(32), nullable=False),
    Column('recipient_name', String(160), nullable=False),
    Column('amount_cents', Integer, nullable=False),
    Column('purpose', String(500)),
    Column('status', String(24), nullable=False),
    Column('settlement_type', String(32), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    CheckConstraint('amount_cents > 0'),
    CheckConstraint("status IN ('COMPLETED')"),
    CheckConstraint("settlement_type IN ('INTERNAL_TRANSFER','EXTERNAL_SIMULATED')"))
_LEDGER = Table('app_shield_ledger_entries', _METADATA,
    Column('entry_id', Integer, primary_key=True, autoincrement=True),
    Column('transaction_id', String(80), ForeignKey('app_shield_payments.transaction_id'), nullable=False),
    Column('account_id', String(80), ForeignKey('app_shield_wallets.account_id'), nullable=False),
    Column('direction', String(8), nullable=False),
    Column('amount_cents', Integer, nullable=False),
    Column('balance_after_cents', Integer, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    UniqueConstraint('transaction_id', 'account_id', 'direction'),
    CheckConstraint("direction IN ('DEBIT','CREDIT')"),
    CheckConstraint('amount_cents > 0'),
    CheckConstraint('balance_after_cents >= 0'))
Index('ix_demo_sessions_expires', _SESSIONS.c.expires_at)
Index('ix_demo_payments_sender_created', _PAYMENTS.c.sender_account_id, _PAYMENTS.c.created_at)
Index('ix_demo_ledger_account_created', _LEDGER.c.account_id, _LEDGER.c.created_at)


def _as_utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _iso(value):
    return _as_utc(value).isoformat()


class SQLDemoBankingService:
    """Banking service using PostgreSQL in deployment and SQLite in tests."""

    SESSION_TTL_HOURS = 12

    def __init__(self, senders, recipients, *, database_url=None, engine: Engine | None = None):
        database_url = normalize_database_url(database_url or os.getenv('DATABASE_URL', 'sqlite:///./app_shield.db'))
        if engine is None:
            engine = create_database_engine(database_url)
        self.engine = engine
        _METADATA.create_all(self.engine)
        self._initialize(senders, recipients)

    @contextmanager
    def _transaction(self, *, immediate=False):
        with self.engine.connect() as connection:
            transaction = connection.begin()
            try:
                if immediate and self.engine.dialect.name == 'sqlite':
                    connection.exec_driver_sql('BEGIN IMMEDIATE')
                yield connection
                transaction.commit()
            except Exception:
                transaction.rollback()
                raise

    def _initialize(self, senders, recipients):
        by_account = {item['account_id'] for item in senders}
        with self._transaction(immediate=True) as connection:
            for sender in senders:
                env_key = 'APP_SHIELD_DEMO_BALANCE_' + sender['alias']
                default = 10000 if sender['alias'] == 'U101' else 2000 if sender['alias'] == 'U102' else 10000
                opening = _cents(os.getenv(env_key, str(default)))
                connection.execute(text('''INSERT INTO app_shield_wallets
                    (account_id,sender_alias,display_name,opening_balance_cents,balance_cents,held_cents)
                    VALUES (:account_id,:sender_alias,:display_name,:opening,:opening,0)
                    ON CONFLICT (account_id) DO NOTHING'''), {'account_id':sender['account_id'],
                    'sender_alias':sender['alias'],'display_name':sender['display_name'],'opening':opening})
                connection.execute(text('''INSERT INTO app_shield_account_aliases(alias,account_id,display_name,kind)
                    VALUES (:alias,:account_id,:display_name,'sender')
                    ON CONFLICT (alias) DO NOTHING'''), {'alias':sender['alias'],
                    'account_id':sender['account_id'],'display_name':sender['display_name']})
            for recipient in recipients:
                connection.execute(text('''INSERT INTO app_shield_account_aliases(alias,account_id,display_name,kind)
                    VALUES (:alias,:account_id,:display_name,:kind)
                    ON CONFLICT (alias) DO NOTHING'''), {'alias':recipient['alias'],
                    'account_id':recipient['account_id'],'display_name':recipient['display_name'],
                    'kind':'internal_recipient' if recipient['account_id'] in by_account else 'external_recipient'})

    def profiles(self):
        with self._transaction() as connection:
            rows = connection.execute(text('''SELECT a.alias,a.display_name
                FROM app_shield_account_aliases a JOIN app_shield_wallets w ON w.account_id=a.account_id
                WHERE a.kind='sender' ORDER BY a.alias''')).mappings().all()
        return [{'alias':row['alias'],'display_name':row['display_name']} for row in rows]

    def create_demo_session(self, account_alias):
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(hours=self.SESSION_TTL_HOURS)
        with self._transaction(immediate=True) as connection:
            row = connection.execute(text('''SELECT account_id,display_name FROM app_shield_account_aliases
                WHERE alias=:alias AND kind='sender' '''), {'alias':account_alias}).mappings().first()
            if row is None:
                raise HTTPException(404, 'Choose an available simulated account.')
            connection.execute(text('''INSERT INTO app_shield_demo_sessions(token_hash,account_id,expires_at,created_at)
                VALUES (:token_hash,:account_id,:expires_at,:created_at)'''), {'token_hash':sha256(token.encode()).hexdigest(),
                'account_id':row['account_id'],'expires_at':expiry,'created_at':now})
        return {'access_token':token,'token_type':'Bearer','account':{'alias':account_alias,
            'account_id':row['account_id'],'display_name':row['display_name']},
            'expires_at':expiry.isoformat(),'environment':'SIMULATED DEMO ACCOUNT'}

    def resolve_token(self, token):
        if not token:
            raise HTTPException(401, 'Open a simulated account session to continue.')
        digest = sha256(token.encode()).hexdigest()
        with self._transaction() as connection:
            row = connection.execute(text('''SELECT w.account_id,a.alias,a.display_name,s.expires_at
                FROM app_shield_demo_sessions s JOIN app_shield_wallets w ON w.account_id=s.account_id
                JOIN app_shield_account_aliases a ON a.account_id=w.account_id AND a.kind='sender'
                WHERE s.token_hash=:token_hash ORDER BY a.alias LIMIT 1'''),
                {'token_hash':digest}).mappings().first()
        if row is None or _as_utc(row['expires_at']) <= datetime.now(timezone.utc):
            raise HTTPException(401, 'This simulated account session expired. Choose an account again.')
        return {'account_id':row['account_id'],'account_alias':row['alias'],'display_name':row['display_name']}

    def account_for_alias(self, alias):
        with self._transaction() as connection:
            row = connection.execute(text('''SELECT account_id,display_name,kind
                FROM app_shield_account_aliases WHERE alias=:alias'''), {'alias':alias}).mappings().first()
        if row is None:
            raise HTTPException(404, "I couldn't find this recipient. Please check the details.")
        return dict(row)

    def balance(self, account_id):
        with self._transaction() as connection:
            row = connection.execute(text('''SELECT balance_cents,held_cents FROM app_shield_wallets
                WHERE account_id=:account_id'''), {'account_id':account_id}).mappings().first()
        if row is None:
            raise HTTPException(404, 'This simulated account is not available.')
        return {'available_balance':_rupees(row['balance_cents']-row['held_cents']),
            'held_balance':_rupees(row['held_cents']),'currency':'INR',
            'as_of':datetime.now(timezone.utc).isoformat()}

    def require_sufficient_balance(self, account_id, amount):
        balance = self.balance(account_id)
        if _cents(amount) > _cents(balance['available_balance']):
            raise InsufficientBalance
        return balance

    def settle(self, *, transaction_id, idempotency_key, sender_account_id, recipient_alias,
               amount, purpose=None):
        amount_cents = _cents(amount)
        if amount_cents <= 0:
            raise HTTPException(422, 'Enter an amount greater than zero.')
        now = datetime.now(timezone.utc)
        try:
            with self._transaction(immediate=True) as connection:
                old = connection.execute(text('SELECT * FROM app_shield_payments WHERE idempotency_key=:key'),
                    {'key':idempotency_key}).mappings().first()
                if old is not None:
                    if old['transaction_id'] != transaction_id:
                        raise HTTPException(409, 'This payment request was already completed.')
                    return self._receipt(connection, old)
                recipient = connection.execute(text('''SELECT account_id,display_name,kind
                    FROM app_shield_account_aliases WHERE alias=:alias'''), {'alias':recipient_alias}).mappings().first()
                if recipient is None:
                    raise HTTPException(404, "I couldn't find this recipient. Please check the details.")
                if recipient['account_id'] == sender_account_id:
                    raise HTTPException(422, 'Choose a different recipient for this transfer.')
                internal = recipient['kind'] in ('sender','internal_recipient')
                account_ids = sorted({sender_account_id, recipient['account_id']} if internal else {sender_account_id})
                lock_query = text('SELECT * FROM app_shield_wallets WHERE account_id IN :account_ids ORDER BY account_id' +
                    ('' if self.engine.dialect.name == 'sqlite' else ' FOR UPDATE')).bindparams(
                        bindparam('account_ids', expanding=True))
                wallets = {row['account_id']:row for row in connection.execute(
                    lock_query, {'account_ids':account_ids}).mappings().all()}
                sender = wallets.get(sender_account_id)
                recipient_wallet = wallets.get(recipient['account_id']) if internal else None
                if sender is None:
                    raise HTTPException(403, 'This session cannot debit the selected account.')
                if internal and recipient_wallet is None:
                    raise HTTPException(409, 'The internal recipient wallet is unavailable. No payment was made.')
                if sender['balance_cents'] - sender['held_cents'] < amount_cents:
                    raise InsufficientBalance
                sender_after = sender['balance_cents'] - amount_cents
                connection.execute(text('''UPDATE app_shield_wallets SET balance_cents=:balance
                    WHERE account_id=:account_id'''), {'balance':sender_after,'account_id':sender_account_id})
                recipient_after = None
                settlement_type = 'EXTERNAL_SIMULATED'
                recipient_account_id = None
                if internal:
                    recipient_account_id = recipient['account_id']
                    recipient_after = recipient_wallet['balance_cents'] + amount_cents
                    connection.execute(text('''UPDATE app_shield_wallets SET balance_cents=:balance
                        WHERE account_id=:account_id'''), {'balance':recipient_after,'account_id':recipient_account_id})
                    settlement_type = 'INTERNAL_TRANSFER'
                connection.execute(text('''INSERT INTO app_shield_payments(transaction_id,idempotency_key,sender_account_id,
                    recipient_account_id,recipient_alias,recipient_name,amount_cents,purpose,status,settlement_type,created_at)
                    VALUES (:transaction_id,:idempotency_key,:sender_account_id,:recipient_account_id,
                    :recipient_alias,:recipient_name,:amount_cents,:purpose,'COMPLETED',:settlement_type,:created_at)'''),
                    {'transaction_id':transaction_id,'idempotency_key':idempotency_key,
                    'sender_account_id':sender_account_id,'recipient_account_id':recipient_account_id,
                    'recipient_alias':recipient_alias,'recipient_name':recipient['display_name'],
                    'amount_cents':amount_cents,'purpose':purpose,'settlement_type':settlement_type,'created_at':now})
                entries = [{'account_id':sender_account_id,'direction':'DEBIT','balance':sender_after}]
                if internal:
                    entries.append({'account_id':recipient_account_id,'direction':'CREDIT','balance':recipient_after})
                for entry in entries:
                    connection.execute(text('''INSERT INTO app_shield_ledger_entries(transaction_id,account_id,direction,
                        amount_cents,balance_after_cents,created_at)
                        VALUES (:transaction_id,:account_id,:direction,:amount,:balance,:created_at)'''),
                        {'transaction_id':transaction_id,'account_id':entry['account_id'],
                        'direction':entry['direction'],'amount':amount_cents,'balance':entry['balance'],'created_at':now})
                payment = connection.execute(text('SELECT * FROM app_shield_payments WHERE transaction_id=:id'),
                    {'id':transaction_id}).mappings().first()
                return self._receipt(connection, payment)
        except InsufficientBalance:
            raise HTTPException(409, 'Your available balance is not enough for this payment. No payment was made.')
        except IntegrityError:
            with self._transaction() as connection:
                old = connection.execute(text('SELECT * FROM app_shield_payments WHERE idempotency_key=:key'),
                    {'key':idempotency_key}).mappings().first()
                if old is not None and old['transaction_id'] == transaction_id:
                    return self._receipt(connection, old)
            raise HTTPException(409, 'This payment request was already completed.')

    def _receipt(self, connection, payment):
        entries = connection.execute(text('''SELECT direction,account_id,balance_after_cents
            FROM app_shield_ledger_entries WHERE transaction_id=:transaction_id'''),
            {'transaction_id':payment['transaction_id']}).mappings().all()
        sender_entry = next((row for row in entries if row['direction'] == 'DEBIT'), None)
        recipient_entry = next((row for row in entries if row['direction'] == 'CREDIT'), None)
        return {'transaction_id':payment['transaction_id'],'amount':_rupees(payment['amount_cents']),
            'sender_account_id':payment['sender_account_id'],'recipient_account_id':payment['recipient_account_id'],
            'recipient_alias':payment['recipient_alias'],'recipient':payment['recipient_name'],
            'status':payment['status'],'settlement_type':payment['settlement_type'],
            'created_at':_iso(payment['created_at']),'purpose':payment['purpose'],
            'sender_balance_after':_rupees(sender_entry['balance_after_cents']) if sender_entry else None,
            'recipient_balance_after':_rupees(recipient_entry['balance_after_cents']) if recipient_entry else None}

    def transactions(self, account_id, *, limit=5, direction=None, payee=None,
                     start=None, end=None, largest=False):
        with self._transaction() as connection:
            rows = connection.execute(text('''SELECT p.*,e.direction,e.balance_after_cents
                FROM app_shield_ledger_entries e JOIN app_shield_payments p ON p.transaction_id=e.transaction_id
                WHERE e.account_id=:account_id ORDER BY p.created_at DESC,p.transaction_id DESC'''),
                {'account_id':account_id}).mappings().all()
        filtered = []
        query = (payee or '').casefold().strip()
        for row in rows:
            created = _as_utc(row['created_at']).astimezone(_IST)
            if direction and row['direction'].casefold() != direction.casefold():
                continue
            if query and query not in row['recipient_name'].casefold() and query not in (row['recipient_alias'] or '').casefold():
                continue
            if start and created < start:
                continue
            if end and created >= end:
                continue
            filtered.append(self._transaction_view(row, account_id))
        if largest:
            filtered.sort(key=lambda row:(-row['amount'],row['created_at']))
        total = sum(item['amount'] for item in filtered)
        return {'transactions':filtered[:max(1,min(int(limit),100))],'total_count':len(filtered),
            'total_amount':round(total,2),'currency':'INR'}

    def _transaction_view(self, row, account_id):
        debit = row['direction'] == 'DEBIT'
        counterparty = row['recipient_name'] if debit else self._sender_name(row['sender_account_id'])
        return {'transaction_id':row['transaction_id'],'amount':_rupees(row['amount_cents']),
            'direction':'DEBIT' if debit else 'CREDIT','counterparty':counterparty,
            'sender':self._sender_name(row['sender_account_id']),'recipient':row['recipient_name'],
            'created_at':_iso(row['created_at']),'status':row['status'],'purpose':row['purpose'],
            'settlement_type':row['settlement_type'],'balance_after':_rupees(row['balance_after_cents'])}

    def _sender_name(self, account_id):
        with self._transaction() as connection:
            row = connection.execute(text('SELECT display_name FROM app_shield_wallets WHERE account_id=:id'),
                {'id':account_id}).mappings().first()
        return row['display_name'] if row else 'External account'

    def transaction(self, account_id, transaction_id):
        with self._transaction() as connection:
            row = connection.execute(text('''SELECT p.*,e.direction,e.balance_after_cents
                FROM app_shield_ledger_entries e JOIN app_shield_payments p ON p.transaction_id=e.transaction_id
                WHERE e.account_id=:account_id AND p.transaction_id=:transaction_id'''),
                {'account_id':account_id,'transaction_id':transaction_id}).mappings().first()
        if row is None:
            raise HTTPException(404, 'Transaction not found for this simulated account.')
        return self._transaction_view(row, account_id)