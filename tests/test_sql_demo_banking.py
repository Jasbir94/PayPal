from sqlalchemy import create_engine, text

from backend.app.services.sql_demo_banking_service import SQLDemoBankingService


def make_bank(monkeypatch):
    monkeypatch.setenv('APP_SHIELD_DEMO_BALANCE_A', '10000')
    monkeypatch.setenv('APP_SHIELD_DEMO_BALANCE_B', '2000')
    engine = create_engine('sqlite://')
    service = SQLDemoBankingService(
        [{'alias':'A','account_id':'account-a','display_name':'Account A'},
         {'alias':'B','account_id':'account-b','display_name':'Account B'}],
        [{'alias':'RB','account_id':'account-b','display_name':'Account B'},
         {'alias':'RE','account_id':'external-1','display_name':'External recipient'}],
        engine=engine)
    return service, engine


def test_sql_banking_session_and_atomic_internal_transfer(monkeypatch):
    bank, engine = make_bank(monkeypatch)
    try:
        session = bank.create_demo_session('A')
        assert bank.resolve_token(session['access_token'])['account_id'] == 'account-a'
        receipt = bank.settle(transaction_id='tx-1', idempotency_key='idem-1',
            sender_account_id='account-a', recipient_alias='RB', amount=3000, purpose='family')
        assert receipt['settlement_type'] == 'INTERNAL_TRANSFER'
        assert receipt['sender_balance_after'] == 7000
        assert receipt['recipient_balance_after'] == 5000
        assert bank.balance('account-a')['available_balance'] == 7000
        assert bank.transactions('account-a', direction='DEBIT')['total_count'] == 1
        with bank._transaction() as connection:
            assert connection.execute(text('SELECT COUNT(*) FROM app_shield_ledger_entries')).scalar_one() == 2
    finally:
        engine.dispose()


def test_sql_banking_external_payment_is_not_credited(monkeypatch):
    bank, engine = make_bank(monkeypatch)
    try:
        receipt = bank.settle(transaction_id='tx-external', idempotency_key='idem-external',
            sender_account_id='account-a', recipient_alias='RE', amount=100)
        assert receipt['settlement_type'] == 'EXTERNAL_SIMULATED'
        assert receipt['recipient_account_id'] is None
        assert receipt['recipient_balance_after'] is None
        assert bank.balance('account-a')['available_balance'] == 9900
    finally:
        engine.dispose()


def test_sql_banking_replay_returns_original_receipt(monkeypatch):
    bank, engine = make_bank(monkeypatch)
    try:
        arguments = {'transaction_id':'tx-replay','idempotency_key':'idem-replay',
            'sender_account_id':'account-a','recipient_alias':'RB','amount':500}
        first = bank.settle(**arguments)
        second = bank.settle(**arguments)
        assert first == second
        with bank._transaction() as connection:
            assert connection.execute(text('SELECT COUNT(*) FROM app_shield_payments')).scalar_one() == 1
            assert connection.execute(text('SELECT COUNT(*) FROM app_shield_ledger_entries')).scalar_one() == 2
    finally:
        engine.dispose()