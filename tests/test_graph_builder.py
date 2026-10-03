import pandas as pd
import pytest
from backend.app.graph.graph_builder import TransactionGraphBuilder

@pytest.fixture
def tiny():
    accounts = pd.DataFrame([
        {'account_id': a, 'created_at': '2026-01-01T00:00:00Z'}
        for a in ['A','B','C']])
    tx = pd.DataFrame([
        {'transaction_id':'one','sender_id':'A','receiver_id':'B','amount':10,'timestamp':'2026-01-02T10:00:00Z'},
        {'transaction_id':'two','sender_id':'A','receiver_id':'B','amount':20,'timestamp':'2026-01-02T10:30:00Z'},
        {'transaction_id':'at','sender_id':'C','receiver_id':'B','amount':40,'timestamp':'2026-01-02T12:00:00Z'},
        {'transaction_id':'future','sender_id':'B','receiver_id':'C','amount':50,'timestamp':'2026-01-02T14:00:00Z'},
    ])
    return TransactionGraphBuilder(tx, accounts)

def test_multidigraph_preserves_parallel_transfers_and_past_only(tiny):
    graph = tiny.build_graph_until('2026-01-02T12:00:00Z')
    assert graph.number_of_edges('A','B') == 2
    assert {edge['transaction_id'] for edge in graph['A']['B'].values()} == {'one','two'}
    assert not graph.has_edge('C','B')
    assert not graph.has_edge('B','C')
    assert tiny.build_graph_until('2026-01-02T12:00:00Z') is graph
    assert tiny.build_count == 1

def test_timezone_required(tiny):
    with pytest.raises(ValueError):
        tiny.build_graph_until('2026-01-02T12:00:00')


def test_absent_current_transaction_id_reuses_snapshot(tiny):
    first=tiny.build_graph_until('2026-01-02T12:00:00Z','new-payment-id')
    second=tiny.build_graph_until('2026-01-02T12:00:00Z','another-new-id')
    assert first is second
    assert tiny.build_count==1
