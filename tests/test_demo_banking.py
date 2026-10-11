from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest
from fastapi import HTTPException

from backend.app.services.demo_banking_service import DemoBankingService, InsufficientBalance


@pytest.fixture
def bank(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_SHIELD_DEMO_BALANCE_A','10000')
    monkeypatch.setenv('APP_SHIELD_DEMO_BALANCE_B','2000')
    return DemoBankingService(
        [{'alias':'A','account_id':'account-a','display_name':'Account A'},
         {'alias':'B','account_id':'account-b','display_name':'Account B'}],
        [{'alias':'RB','account_id':'account-b','display_name':'Account B'},
         {'alias':'RE','account_id':'external-1','display_name':'External recipient'}],
        tmp_path/'bank.sqlite3')


def test_atomic_internal_transfer_records_balanced_debit_and_credit(bank):
    receipt=bank.settle(transaction_id='tx-1',idempotency_key='idem-1',sender_account_id='account-a',
        recipient_alias='RB',amount=3000,purpose='family')
    assert receipt['settlement_type']=='INTERNAL_TRANSFER'
    assert receipt['sender_balance_after']==7000
    assert receipt['recipient_balance_after']==5000
    assert bank.balance('account-a')['available_balance']==7000
    assert bank.balance('account-b')['available_balance']==5000
    debit=bank.transactions('account-a',direction='DEBIT')['transactions'][0]
    credit=bank.transactions('account-b',direction='CREDIT')['transactions'][0]
    assert debit['transaction_id']==credit['transaction_id']=='tx-1'
    assert debit['counterparty']=='Account B' and credit['counterparty']=='Account A'


def test_duplicate_settlement_returns_original_receipt_without_duplicate_ledger(bank):
    one=bank.settle(transaction_id='tx-2',idempotency_key='idem-2',sender_account_id='account-a',
        recipient_alias='RB',amount=500,purpose='friend')
    two=bank.settle(transaction_id='tx-2',idempotency_key='idem-2',sender_account_id='account-a',
        recipient_alias='RB',amount=500,purpose='friend')
    assert one==two
    with bank._transaction() as connection:
        assert connection.execute('SELECT COUNT(*) FROM payments WHERE transaction_id=?',('tx-2',)).fetchone()[0]==1
        assert connection.execute('SELECT COUNT(*) FROM ledger_entries WHERE transaction_id=?',('tx-2',)).fetchone()[0]==2


def test_insufficient_balance_cannot_make_negative_or_create_ledger_rows(bank):
    with pytest.raises(HTTPException,match='not enough'):
        bank.settle(transaction_id='tx-big',idempotency_key='idem-big',sender_account_id='account-a',
            recipient_alias='RB',amount=10001,purpose='other')
    assert bank.balance('account-a')['available_balance']==10000
    with bank._transaction() as connection:
        assert connection.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==0
        assert connection.execute('SELECT COUNT(*) FROM ledger_entries').fetchone()[0]==0


def test_concurrent_transfers_cannot_overdraw_wallet(bank):
    def transfer(suffix):
        try:
            return bank.settle(transaction_id='tx-'+suffix,idempotency_key='idem-'+suffix,
                sender_account_id='account-a',recipient_alias='RB',amount=7000,purpose='other')
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(transfer,('one','two')))
    assert sum(isinstance(item,dict) for item in results)==1
    assert sum(item==409 for item in results)==1
    assert bank.balance('account-a')['available_balance']==3000
    assert bank.balance('account-b')['available_balance']==9000


def test_failed_ledger_write_rolls_back_both_wallet_balances(bank,monkeypatch):
    original=bank._receipt
    def fail(*args,**kwargs):raise sqlite3.IntegrityError('injected receipt failure')
    monkeypatch.setattr(bank,'_receipt',fail)
    with pytest.raises(sqlite3.IntegrityError):
        bank.settle(transaction_id='tx-fail',idempotency_key='idem-fail',sender_account_id='account-a',
            recipient_alias='RB',amount=3000,purpose='other')
    monkeypatch.setattr(bank,'_receipt',original)
    assert bank.balance('account-a')['available_balance']==10000
    assert bank.balance('account-b')['available_balance']==2000
    with bank._transaction() as connection:
        assert connection.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==0
        assert connection.execute('SELECT COUNT(*) FROM ledger_entries').fetchone()[0]==0


def test_external_simulated_recipient_is_not_falsely_credited(bank):
    receipt=bank.settle(transaction_id='tx-external',idempotency_key='idem-external',sender_account_id='account-a',
        recipient_alias='RE',amount=100,purpose='shopping')
    assert receipt['settlement_type']=='EXTERNAL_SIMULATED'
    assert receipt['recipient_account_id'] is None
    assert receipt['recipient_balance_after'] is None
    assert bank.balance('account-a')['available_balance']==9900
    with bank._transaction() as connection:
        assert connection.execute('SELECT COUNT(*) FROM ledger_entries WHERE transaction_id=?',('tx-external',)).fetchone()[0]==1
