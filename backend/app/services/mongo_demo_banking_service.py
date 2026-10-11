"""MongoDB-backed demo wallet and payment ledger.

MongoDB is selected only when APP_SHIELD_MONGO_URI is configured. A dedicated
APP_SHIELD_MONGO_DATABASE is used so demo payments cannot enter another app's DB.
Settlement uses a MongoDB transaction: deploy to Atlas or another replica set.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import secrets
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from backend.app.services.demo_banking_service import InsufficientBalance, _cents, _rupees

_IST = ZoneInfo('Asia/Kolkata')


class MongoDemoBankingService:
    """MongoDB equivalent of ``DemoBankingService`` with atomic settlements."""

    SESSION_TTL_HOURS = 12

    def __init__(self, senders, recipients, *, uri=None, database_name=None, client=None):
        uri = uri or os.getenv('APP_SHIELD_MONGO_URI')
        database_name = database_name or os.getenv('APP_SHIELD_MONGO_DATABASE', 'appshield')
        if not uri:
            raise ValueError('APP_SHIELD_MONGO_URI is required for MongoDB banking storage.')
        if database_name.casefold() == 'deardiary':
            raise ValueError('APP_SHIELD_MONGO_DATABASE must be a dedicated APP Shield database.')

        from pymongo import MongoClient

        self.client = client or MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
        self.db = self.client[database_name]
        # Fail startup instead of silently switching to volatile/local storage.
        self.client.admin.command('ping')
        self.wallets = self.db['wallets']
        self.aliases = self.db['account_aliases']
        self.sessions = self.db['demo_sessions']
        self.payments = self.db['payments']
        self.ledger = self.db['ledger_entries']
        self._ensure_indexes()
        self._initialize(senders, recipients)

    def _ensure_indexes(self):
        self.wallets.create_index('account_id', unique=True)
        self.wallets.create_index('sender_alias', unique=True)
        self.aliases.create_index('alias', unique=True)
        self.sessions.create_index('token_hash', unique=True)
        self.sessions.create_index('expires_at', expireAfterSeconds=0)
        self.payments.create_index('transaction_id', unique=True)
        self.payments.create_index('idempotency_key', unique=True)
        self.payments.create_index([('sender_account_id', 1), ('created_at', -1)])
        self.ledger.create_index([('transaction_id', 1), ('account_id', 1), ('direction', 1)], unique=True)
        self.ledger.create_index([('account_id', 1), ('created_at', -1)])

    def _initialize(self, senders, recipients):
        sender_by_alias = {item['alias']: item for item in senders}
        by_account = {item['account_id']: item for item in senders}
        for sender in senders:
            env_key = 'APP_SHIELD_DEMO_BALANCE_' + sender['alias']
            default = 10000 if sender['alias'] == 'U101' else 2000 if sender['alias'] == 'U102' else 10000
            opening = _cents(os.getenv(env_key, str(default)))
            self.wallets.update_one({'account_id': sender['account_id']}, {'$setOnInsert': {
                'account_id': sender['account_id'], 'sender_alias': sender['alias'],
                'display_name': sender['display_name'], 'opening_balance_cents': opening,
                'balance_cents': opening, 'held_cents': 0,
            }}, upsert=True)
            self.aliases.update_one({'alias': sender['alias']}, {'$setOnInsert': {
                'alias': sender['alias'], 'account_id': sender['account_id'],
                'display_name': sender['display_name'], 'kind': 'sender',
            }}, upsert=True)
        for recipient in recipients:
            internal = recipient['account_id'] in by_account
            self.aliases.update_one({'alias': recipient['alias']}, {'$setOnInsert': {
                'alias': recipient['alias'], 'account_id': recipient['account_id'],
                'display_name': recipient['display_name'],
                'kind': 'internal_recipient' if internal else 'external_recipient',
            }}, upsert=True)

    def profiles(self):
        return [{'alias': row['alias'], 'display_name': row['display_name']} for row in
                self.aliases.find({'kind': 'sender'}, {'_id': 0, 'alias': 1, 'display_name': 1}).sort('alias', 1)]

    def create_demo_session(self, account_alias):
        row = self.aliases.find_one({'alias': account_alias, 'kind': 'sender'})
        if row is None:
            raise HTTPException(404, 'Choose an available simulated account.')
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(hours=self.SESSION_TTL_HOURS)
        self.sessions.insert_one({'token_hash': sha256(token.encode()).hexdigest(),
            'account_id': row['account_id'], 'expires_at': expiry, 'created_at': now})
        return {'access_token': token, 'token_type': 'Bearer', 'account': {
            'alias': account_alias, 'account_id': row['account_id'], 'display_name': row['display_name']},
            'expires_at': expiry.isoformat(), 'environment': 'SIMULATED DEMO ACCOUNT'}

    def resolve_token(self, token):
        if not token:
            raise HTTPException(401, 'Open a simulated account session to continue.')
        now = datetime.now(timezone.utc)
        session = self.sessions.find_one({'token_hash': sha256(token.encode()).hexdigest(), 'expires_at': {'$gt': now}})
        if session is None:
            raise HTTPException(401, 'This simulated account session expired. Choose an account again.')
        alias = self.aliases.find_one({'account_id': session['account_id'], 'kind': 'sender'})
        wallet = self.wallets.find_one({'account_id': session['account_id']})
        if alias is None or wallet is None:
            raise HTTPException(401, 'This simulated account session expired. Choose an account again.')
        return {'account_id': session['account_id'], 'account_alias': alias['alias'],
                'display_name': wallet['display_name']}

    def account_for_alias(self, alias):
        row = self.aliases.find_one({'alias': alias}, {'_id': 0})
        if row is None:
            raise HTTPException(404, "I couldn't find this recipient. Please check the details.")
        return row

    def balance(self, account_id):
        wallet = self.wallets.find_one({'account_id': account_id})
        if wallet is None:
            raise HTTPException(404, 'This simulated account is not available.')
        return {'available_balance': _rupees(wallet['balance_cents'] - wallet.get('held_cents', 0)),
                'held_balance': _rupees(wallet.get('held_cents', 0)), 'currency': 'INR',
                'as_of': datetime.now(timezone.utc).isoformat()}

    def require_sufficient_balance(self, account_id, amount):
        balance = self.balance(account_id)
        if _cents(amount) > _cents(balance['available_balance']):
            raise InsufficientBalance
        return balance

    def settle(self, *, transaction_id, idempotency_key, sender_account_id, recipient_alias,
               amount, purpose=None):
        from pymongo.errors import DuplicateKeyError

        amount_cents = _cents(amount)
        if amount_cents <= 0:
            raise HTTPException(422, 'Enter an amount greater than zero.')
        old = self.payments.find_one({'idempotency_key': idempotency_key})
        if old is not None:
            if old['transaction_id'] != transaction_id:
                raise HTTPException(409, 'This payment request was already completed.')
            return self._receipt(old)

        now = datetime.now(timezone.utc)
        try:
            with self.client.start_session() as session:
                def commit_payment(tx_session):
                    sender = self.wallets.find_one({'account_id': sender_account_id}, session=tx_session)
                    recipient = self.aliases.find_one({'alias': recipient_alias}, session=tx_session)
                    if sender is None:
                        raise HTTPException(403, 'This session cannot debit the selected account.')
                    if recipient is None:
                        raise HTTPException(404, "I couldn't find this recipient. Please check the details.")
                    if recipient['account_id'] == sender_account_id:
                        raise HTTPException(422, 'Choose a different recipient for this transfer.')
                    sender_after = sender['balance_cents'] - amount_cents
                    if sender_after < sender.get('held_cents', 0):
                        raise InsufficientBalance
                    internal = recipient['kind'] in ('sender', 'internal_recipient')
                    recipient_wallet = self.wallets.find_one({'account_id': recipient['account_id']}, session=tx_session) if internal else None
                    if internal and recipient_wallet is None:
                        raise HTTPException(409, 'The internal recipient wallet is unavailable. No payment was made.')
                    self.payments.insert_one({'transaction_id': transaction_id,
                        'idempotency_key': idempotency_key, 'sender_account_id': sender_account_id,
                        'recipient_account_id': recipient['account_id'] if internal else None,
                        'recipient_alias': recipient_alias, 'recipient_name': recipient['display_name'],
                        'amount_cents': amount_cents, 'purpose': purpose, 'status': 'COMPLETED',
                        'settlement_type': 'INTERNAL_TRANSFER' if internal else 'EXTERNAL_SIMULATED',
                        'created_at': now}, session=tx_session)
                    debit = self.wallets.update_one({'account_id': sender_account_id,
                        'balance_cents': {'$gte': amount_cents + sender.get('held_cents', 0)}},
                        {'$inc': {'balance_cents': -amount_cents}}, session=tx_session)
                    if debit.modified_count != 1:
                        raise InsufficientBalance
                    sender_after = sender['balance_cents'] - amount_cents
                    self.ledger.insert_one({'transaction_id': transaction_id,
                        'account_id': sender_account_id, 'direction': 'DEBIT',
                        'amount_cents': amount_cents, 'balance_after_cents': sender_after, 'created_at': now},
                        session=tx_session)
                    recipient_after = None
                    if internal:
                        recipient_after = recipient_wallet['balance_cents'] + amount_cents
                        self.wallets.update_one({'account_id': recipient['account_id']},
                            {'$inc': {'balance_cents': amount_cents}}, session=tx_session)
                        self.ledger.insert_one({'transaction_id': transaction_id,
                            'account_id': recipient['account_id'], 'direction': 'CREDIT',
                            'amount_cents': amount_cents, 'balance_after_cents': recipient_after,
                            'created_at': now}, session=tx_session)
                    return {'transaction_id': transaction_id, 'amount': _rupees(amount_cents),
                        'sender_account_id': sender_account_id,
                        'recipient_account_id': recipient['account_id'] if internal else None,
                        'recipient_alias': recipient_alias, 'recipient': recipient['display_name'],
                        'status': 'COMPLETED',
                        'settlement_type': 'INTERNAL_TRANSFER' if internal else 'EXTERNAL_SIMULATED',
                        'created_at': now.isoformat(), 'purpose': purpose,
                        'sender_balance_after': _rupees(sender_after),
                        'recipient_balance_after': _rupees(recipient_after) if recipient_after is not None else None}

                return session.with_transaction(commit_payment)
        except InsufficientBalance:
            raise HTTPException(409, 'Your available balance is not enough for this payment. No payment was made.')
        except DuplicateKeyError:
            # A concurrent replay may have won the unique idempotency key race.
            old = self.payments.find_one({'idempotency_key': idempotency_key})
            if old is not None and old['transaction_id'] == transaction_id:
                return self._receipt(old)
            raise HTTPException(409, 'This payment request was already completed.')

    def _receipt(self, payment):
        entries = list(self.ledger.find({'transaction_id': payment['transaction_id']},
            {'_id': 0, 'direction': 1, 'account_id': 1, 'balance_after_cents': 1}))
        debit = next((row for row in entries if row['direction'] == 'DEBIT'), None)
        credit = next((row for row in entries if row['direction'] == 'CREDIT'), None)
        created = payment['created_at']
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return {'transaction_id': payment['transaction_id'], 'amount': _rupees(payment['amount_cents']),
            'sender_account_id': payment['sender_account_id'], 'recipient_account_id': payment['recipient_account_id'],
            'recipient_alias': payment['recipient_alias'], 'recipient': payment['recipient_name'],
            'status': payment['status'], 'settlement_type': payment['settlement_type'],
            'created_at': created.isoformat(), 'purpose': payment.get('purpose'),
            'sender_balance_after': _rupees(debit['balance_after_cents']) if debit else None,
            'recipient_balance_after': _rupees(credit['balance_after_cents']) if credit else None}

    def transactions(self, account_id, *, limit=5, direction=None, payee=None,
                     start=None, end=None, largest=False):
        entries = list(self.ledger.find({'account_id': account_id}).sort('created_at', -1))
        tx_ids = list({entry['transaction_id'] for entry in entries})
        payments = {row['transaction_id']: row for row in self.payments.find({'transaction_id': {'$in': tx_ids}})} if tx_ids else {}
        filtered = []
        query = (payee or '').casefold().strip()
        for entry in entries:
            row = payments.get(entry['transaction_id'])
            if row is None:
                continue
            created = row['created_at']
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            local_created = created.astimezone(_IST)
            if direction and entry['direction'].casefold() != direction.casefold():
                continue
            if query and query not in row['recipient_name'].casefold() and query not in row['recipient_alias'].casefold():
                continue
            if start and local_created < start:
                continue
            if end and local_created >= end:
                continue
            view = {**row, 'direction': entry['direction'], 'balance_after_cents': entry['balance_after_cents']}
            filtered.append(self._transaction_view(view, account_id))
        if largest:
            filtered.sort(key=lambda row: (-row['amount'], row['created_at']))
        return {'transactions': filtered[:max(1, min(int(limit), 100))], 'total_count': len(filtered),
            'total_amount': round(sum(item['amount'] for item in filtered), 2), 'currency': 'INR'}

    def _transaction_view(self, row, account_id):
        debit = row['direction'] == 'DEBIT'
        created = row['created_at']
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return {'transaction_id': row['transaction_id'], 'amount': _rupees(row['amount_cents']),
            'direction': row['direction'],
            'counterparty': row['recipient_name'] if debit else self._sender_name(row['sender_account_id']),
            'sender': self._sender_name(row['sender_account_id']), 'recipient': row['recipient_name'],
            'created_at': created.isoformat(), 'status': row['status'], 'purpose': row.get('purpose'),
            'settlement_type': row['settlement_type'], 'balance_after': _rupees(row['balance_after_cents'])}

    def _sender_name(self, account_id):
        row = self.wallets.find_one({'account_id': account_id}, {'display_name': 1})
        return row['display_name'] if row else 'External account'

    def transaction(self, account_id, transaction_id):
        entry = self.ledger.find_one({'account_id': account_id, 'transaction_id': transaction_id})
        row = self.payments.find_one({'transaction_id': transaction_id})
        if entry is None or row is None:
            raise HTTPException(404, 'Transaction not found for this simulated account.')
        return self._transaction_view({**row, 'direction': entry['direction'],
            'balance_after_cents': entry['balance_after_cents']}, account_id)
