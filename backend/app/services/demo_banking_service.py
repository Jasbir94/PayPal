"""SQLite-backed wallets, account-bound demo sessions, and atomic simulated ledger."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import os
from pathlib import Path
import secrets
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_INR = Decimal('0.01')
_IST = ZoneInfo('Asia/Kolkata')


def _cents(value):
    amount = Decimal(str(value)).quantize(_INR, rounding=ROUND_HALF_UP)
    return int(amount * 100)


def _rupees(cents):
    return float(Decimal(int(cents)) / 100)


class InsufficientBalance(Exception):
    pass


class DemoBankingService:
    """Balances are seeded once from demo config and thereafter read from SQLite."""

    SESSION_TTL_HOURS = 12

    def __init__(self, senders, recipients, database_path=None):
        configured = database_path or os.getenv('APP_SHIELD_BANKING_DB')
        if str(configured) == ':memory:':
            self.database_path = ':memory:'
            self._database_target = f'file:app-shield-banking-{uuid4()}?mode=memory&cache=shared'
            self._uri = True
            self._anchor = sqlite3.connect(self._database_target, uri=True, check_same_thread=False)
        else:
            self.database_path = Path(configured) if configured else PROJECT_ROOT / 'data' / 'processed' / 'demo_banking.sqlite3'
            self._database_target = str(self.database_path)
            self._uri = False
            self._anchor = None
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize(senders, recipients)

    def _connect(self):
        connection = sqlite3.connect(self._database_target, timeout=15, isolation_level=None, uri=self._uri)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=15000')
        return connection

    @contextmanager
    def _transaction(self, *, immediate=False):
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE' if immediate else 'BEGIN')
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self, senders, recipients):
        connection = self._connect()
        try:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS wallets (
                    account_id TEXT PRIMARY KEY,
                    sender_alias TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    opening_balance_cents INTEGER NOT NULL CHECK(opening_balance_cents >= 0),
                    balance_cents INTEGER NOT NULL CHECK(balance_cents >= 0),
                    held_cents INTEGER NOT NULL DEFAULT 0 CHECK(held_cents >= 0)
                );
                CREATE TABLE IF NOT EXISTS account_aliases (
                    alias TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('sender','internal_recipient','external_recipient'))
                );
                CREATE TABLE IF NOT EXISTS demo_sessions (
                    token_hash TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES wallets(account_id)
                );
                CREATE TABLE IF NOT EXISTS payments (
                    transaction_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    sender_account_id TEXT NOT NULL,
                    recipient_account_id TEXT,
                    recipient_alias TEXT NOT NULL,
                    recipient_name TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                    purpose TEXT,
                    status TEXT NOT NULL CHECK(status IN ('COMPLETED')),
                    settlement_type TEXT NOT NULL CHECK(settlement_type IN ('INTERNAL_TRANSFER','EXTERNAL_SIMULATED')),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(sender_account_id) REFERENCES wallets(account_id)
                );
                CREATE TABLE IF NOT EXISTS ledger_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('DEBIT','CREDIT')),
                    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                    balance_after_cents INTEGER NOT NULL CHECK(balance_after_cents >= 0),
                    created_at TEXT NOT NULL,
                    UNIQUE(transaction_id, account_id, direction),
                    FOREIGN KEY(transaction_id) REFERENCES payments(transaction_id),
                    FOREIGN KEY(account_id) REFERENCES wallets(account_id)
                );
                CREATE INDEX IF NOT EXISTS ix_ledger_account_created ON ledger_entries(account_id, created_at DESC);
            ''')
            connection.execute('BEGIN IMMEDIATE')
            sender_by_alias = {item['alias']: item for item in senders}
            by_account = {item['account_id']: item for item in senders}
            for sender in senders:
                env_key = 'APP_SHIELD_DEMO_BALANCE_' + sender['alias']
                default = 10000 if sender['alias'] == 'U101' else 2000 if sender['alias'] == 'U102' else 10000
                opening = _cents(os.getenv(env_key, str(default)))
                connection.execute('''INSERT OR IGNORE INTO wallets
                    (account_id,sender_alias,display_name,opening_balance_cents,balance_cents)
                    VALUES (?,?,?,?,?)''', (sender['account_id'],sender['alias'],sender['display_name'],opening,opening))
                connection.execute('''INSERT OR IGNORE INTO account_aliases(alias,account_id,display_name,kind)
                    VALUES (?,?,?,'sender')''', (sender['alias'],sender['account_id'],sender['display_name']))
            for recipient in recipients:
                internal = recipient['account_id'] in by_account
                connection.execute('''INSERT OR IGNORE INTO account_aliases(alias,account_id,display_name,kind)
                    VALUES (?,?,?,?)''', (recipient['alias'],recipient['account_id'],recipient['display_name'],
                    'internal_recipient' if internal else 'external_recipient'))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def profiles(self):
        with self._transaction() as connection:
            rows=connection.execute('''SELECT a.alias,a.display_name,w.account_id
                FROM account_aliases a JOIN wallets w ON w.account_id=a.account_id
                WHERE a.kind='sender' ORDER BY a.alias''').fetchall()
        return [{'alias':row['alias'],'display_name':row['display_name']} for row in rows]

    def create_demo_session(self, account_alias):
        token=secrets.token_urlsafe(32)
        digest=sha256(token.encode()).hexdigest()
        now=datetime.now(timezone.utc)
        with self._transaction(immediate=True) as connection:
            row=connection.execute('''SELECT a.account_id,a.display_name FROM account_aliases a
                WHERE a.alias=? AND a.kind='sender' ''',(account_alias,)).fetchone()
            if row is None:raise HTTPException(404,'Choose an available simulated account.')
            connection.execute('INSERT INTO demo_sessions(token_hash,account_id,expires_at,created_at) VALUES (?,?,?,?)',
                (digest,row['account_id'],(now+timedelta(hours=self.SESSION_TTL_HOURS)).isoformat(),now.isoformat()))
        return {'access_token':token,'token_type':'Bearer','account':{
            'alias':account_alias,'account_id':row['account_id'],'display_name':row['display_name']},
            'expires_at':(now+timedelta(hours=self.SESSION_TTL_HOURS)).isoformat(),
            'environment':'SIMULATED DEMO ACCOUNT'}

    def resolve_token(self, token):
        if not token:raise HTTPException(401,'Open a simulated account session to continue.')
        digest=sha256(token.encode()).hexdigest()
        with self._transaction() as connection:
            row=connection.execute('''SELECT s.account_id,a.alias,a.display_name,s.expires_at
                FROM demo_sessions s JOIN wallets w ON w.account_id=s.account_id
                JOIN account_aliases a ON a.account_id=w.account_id AND a.kind='sender'
                WHERE s.token_hash=? ORDER BY a.alias LIMIT 1''',(digest,)).fetchone()
        if row is None or datetime.fromisoformat(row['expires_at'])<=datetime.now(timezone.utc):
            raise HTTPException(401,'This simulated account session expired. Choose an account again.')
        return {'account_id':row['account_id'],'account_alias':row['alias'],'display_name':row['display_name']}

    def account_for_alias(self, alias):
        with self._transaction() as connection:
            row=connection.execute('SELECT account_id,display_name,kind FROM account_aliases WHERE alias=?',(alias,)).fetchone()
        if row is None:raise HTTPException(404,"I couldn't find this recipient. Please check the details.")
        return dict(row)

    def balance(self, account_id):
        with self._transaction() as connection:
            row=connection.execute('SELECT balance_cents,held_cents FROM wallets WHERE account_id=?',(account_id,)).fetchone()
        if row is None:raise HTTPException(404,'This simulated account is not available.')
        return {'available_balance':_rupees(row['balance_cents']-row['held_cents']),
            'held_balance':_rupees(row['held_cents']),'currency':'INR','as_of':datetime.now(timezone.utc).isoformat()}

    def require_sufficient_balance(self, account_id, amount):
        balance=self.balance(account_id)
        if _cents(amount)>_cents(balance['available_balance']):
            raise InsufficientBalance
        return balance

    def settle(self, *, transaction_id, idempotency_key, sender_account_id, recipient_alias,
               amount, purpose=None):
        amount_cents=_cents(amount)
        if amount_cents<=0:raise HTTPException(422,'Enter an amount greater than zero.')
        created=datetime.now(timezone.utc).isoformat()
        try:
            with self._transaction(immediate=True) as connection:
                old=connection.execute('SELECT * FROM payments WHERE idempotency_key=?',(idempotency_key,)).fetchone()
                if old is not None:
                    if old['transaction_id']!=transaction_id:
                        raise HTTPException(409,'This payment request was already completed.')
                    return self._receipt(connection,old)
                sender=connection.execute('SELECT balance_cents,held_cents FROM wallets WHERE account_id=?',(sender_account_id,)).fetchone()
                recipient=connection.execute('''SELECT a.account_id,a.display_name,a.kind,w.balance_cents
                    FROM account_aliases a LEFT JOIN wallets w ON w.account_id=a.account_id WHERE a.alias=?''',
                    (recipient_alias,)).fetchone()
                if sender is None:raise HTTPException(403,'This session cannot debit the selected account.')
                if recipient is None:raise HTTPException(404,"I couldn't find this recipient. Please check the details.")
                if recipient['account_id']==sender_account_id:
                    raise HTTPException(422,'Choose a different recipient for this transfer.')
                if sender['balance_cents']-sender['held_cents']<amount_cents:raise InsufficientBalance
                internal=recipient['kind']=='sender' or recipient['kind']=='internal_recipient'
                if internal and recipient['balance_cents'] is None:
                    raise HTTPException(409,'The internal recipient wallet is unavailable. No payment was made.')
                sender_after=sender['balance_cents']-amount_cents
                connection.execute('UPDATE wallets SET balance_cents=? WHERE account_id=? AND balance_cents-held_cents>=?',
                    (sender_after,sender_account_id,amount_cents))
                if connection.execute('SELECT changes()').fetchone()[0]!=1:raise InsufficientBalance
                recipient_after=None
                settlement='EXTERNAL_SIMULATED'
                recipient_account_id=None
                if internal:
                    recipient_account_id=recipient['account_id'];recipient_after=recipient['balance_cents']+amount_cents
                    connection.execute('UPDATE wallets SET balance_cents=? WHERE account_id=?',
                        (recipient_after,recipient_account_id))
                    settlement='INTERNAL_TRANSFER'
                connection.execute('''INSERT INTO payments(transaction_id,idempotency_key,sender_account_id,
                    recipient_account_id,recipient_alias,recipient_name,amount_cents,purpose,status,settlement_type,created_at)
                    VALUES (?,?,?,?,?,?,?,?,'COMPLETED',?,?)''',
                    (transaction_id,idempotency_key,sender_account_id,recipient_account_id,recipient_alias,
                     recipient['display_name'],amount_cents,purpose,settlement,created))
                connection.execute('''INSERT INTO ledger_entries(transaction_id,account_id,direction,amount_cents,
                    balance_after_cents,created_at) VALUES (?,?, 'DEBIT',?,?,?)''',
                    (transaction_id,sender_account_id,amount_cents,sender_after,created))
                if internal:
                    connection.execute('''INSERT INTO ledger_entries(transaction_id,account_id,direction,amount_cents,
                        balance_after_cents,created_at) VALUES (?,?, 'CREDIT',?,?,?)''',
                        (transaction_id,recipient_account_id,amount_cents,recipient_after,created))
                payment=connection.execute('SELECT * FROM payments WHERE transaction_id=?',(transaction_id,)).fetchone()
                return self._receipt(connection,payment)
        except InsufficientBalance:
            raise HTTPException(409,'Your available balance is not enough for this payment. No payment was made.')

    def _receipt(self, connection, payment):
        entries=connection.execute('SELECT direction,account_id,balance_after_cents FROM ledger_entries WHERE transaction_id=?',
            (payment['transaction_id'],)).fetchall()
        sender_entry=next((row for row in entries if row['direction']=='DEBIT'),None)
        recipient_entry=next((row for row in entries if row['direction']=='CREDIT'),None)
        return {'transaction_id':payment['transaction_id'],'amount':_rupees(payment['amount_cents']),
            'sender_account_id':payment['sender_account_id'],'recipient_account_id':payment['recipient_account_id'],
            'recipient_alias':payment['recipient_alias'],'recipient':payment['recipient_name'],
            'status':payment['status'],'settlement_type':payment['settlement_type'],
            'created_at':payment['created_at'],'purpose':payment['purpose'],
            'sender_balance_after':_rupees(sender_entry['balance_after_cents']) if sender_entry else None,
            'recipient_balance_after':_rupees(recipient_entry['balance_after_cents']) if recipient_entry else None}

    def transactions(self, account_id, *, limit=5, direction=None, payee=None,
                     start=None, end=None, largest=False):
        with self._transaction() as connection:
            rows=connection.execute('''SELECT p.*,e.direction,e.balance_after_cents
                FROM ledger_entries e JOIN payments p ON p.transaction_id=e.transaction_id
                WHERE e.account_id=? ORDER BY p.created_at DESC,p.transaction_id DESC''',(account_id,)).fetchall()
        filtered=[]
        query=(payee or '').casefold().strip()
        for row in rows:
            created=datetime.fromisoformat(row['created_at']).astimezone(_IST)
            if direction and row['direction'].casefold()!=direction.casefold():continue
            if query and query not in row['recipient_name'].casefold() and query not in (row['recipient_alias'] or '').casefold():continue
            if start and created<start:continue
            if end and created>=end:continue
            item=self._transaction_view(row,account_id)
            filtered.append(item)
        if largest:
            filtered.sort(key=lambda row:(-row['amount'],row['created_at']))
        total=sum(item['amount'] for item in filtered)
        return {'transactions':filtered[:max(1,min(int(limit),100))], 'total_count':len(filtered),
            'total_amount':round(total,2),'currency':'INR'}

    def _transaction_view(self,row,account_id):
        debit=row['direction']=='DEBIT'
        counterparty=(row['recipient_name'] if debit else self._sender_name(row['sender_account_id']))
        return {'transaction_id':row['transaction_id'],'amount':_rupees(row['amount_cents']),
            'direction':'DEBIT' if debit else 'CREDIT','counterparty':counterparty,
            'sender':self._sender_name(row['sender_account_id']),'recipient':row['recipient_name'],
            'created_at':row['created_at'],'status':row['status'],'purpose':row['purpose'],
            'settlement_type':row['settlement_type'],'balance_after':_rupees(row['balance_after_cents'])}

    def _sender_name(self,account_id):
        with self._transaction() as connection:
            row=connection.execute('SELECT display_name FROM wallets WHERE account_id=?',(account_id,)).fetchone()
        return row['display_name'] if row else 'External account'

    def transaction(self, account_id, transaction_id):
        with self._transaction() as connection:
            row=connection.execute('''SELECT p.*,e.direction,e.balance_after_cents
                FROM ledger_entries e JOIN payments p ON p.transaction_id=e.transaction_id
                WHERE e.account_id=? AND p.transaction_id=?''',(account_id,transaction_id)).fetchone()
        if row is None:raise HTTPException(404,'Transaction not found for this simulated account.')
        return self._transaction_view(row,account_id)
