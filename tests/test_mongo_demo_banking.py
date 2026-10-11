import sys
from types import SimpleNamespace

import pytest


class FakeCollection:
    def __init__(self):
        self.rows = []
        self.indexes = []

    def create_index(self, fields, **kwargs):
        self.indexes.append((fields, kwargs))

    def update_one(self, query, update, upsert=False):
        row = next((item for item in self.rows if all(item.get(key) == value for key, value in query.items())), None)
        if row is None and upsert:
            self.rows.append(dict(update['$setOnInsert']))

    def find(self, query, projection=None):
        rows = [row.copy() for row in self.rows if all(row.get(key) == value for key, value in query.items())]
        return FakeCursor(rows)


class FakeCursor(list):
    def sort(self, key, direction=1):
        return FakeCursor(sorted(self, key=lambda row: row.get(key), reverse=direction < 0))


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


class FakeClient:
    def __init__(self):
        self.admin = SimpleNamespace(command=lambda command: {'ok': 1})
        self.databases = {}

    def __getitem__(self, name):
        return self.databases.setdefault(name, FakeDatabase())


def test_mongo_initializes_isolated_appshield_database_and_indexes(monkeypatch):
    monkeypatch.setenv('APP_SHIELD_DEMO_BALANCE_A', '10000')
    fake_client = FakeClient()
    monkeypatch.setitem(sys.modules, 'pymongo', SimpleNamespace(MongoClient=lambda *args, **kwargs: fake_client))
    from backend.app.services.mongo_demo_banking_service import MongoDemoBankingService

    service = MongoDemoBankingService(
        [{'alias': 'A', 'account_id': 'account-a', 'display_name': 'Account A'}],
        [{'alias': 'RB', 'account_id': 'account-b', 'display_name': 'Account B'}],
        uri='mongodb://unused', database_name='appshield', client=fake_client)

    assert service.db is fake_client.databases['appshield']
    assert service.profiles() == [{'alias': 'A', 'display_name': 'Account A'}]
    assert service.wallets.rows[0]['balance_cents'] == 1_000_000
    assert any(fields == [('transaction_id', 1), ('account_id', 1), ('direction', 1)] and options['unique']
               for fields, options in service.ledger.indexes)
    assert service.payments.indexes == [('transaction_id', {'unique': True}),
        ('idempotency_key', {'unique': True}), ([('sender_account_id', 1), ('created_at', -1)], {})]


def test_mongo_rejects_diary_database_to_prevent_cross_app_data_use():
    from backend.app.services.mongo_demo_banking_service import MongoDemoBankingService

    with pytest.raises(ValueError, match='dedicated APP Shield database'):
        MongoDemoBankingService([], [], uri='mongodb://placeholder', database_name='deardiary', client=object())
