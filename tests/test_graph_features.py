import pandas as pd
from backend.app.graph.graph_builder import TransactionGraphBuilder
from backend.app.graph.graph_features import calculate_graph_features, flow_timing, bounded_cycles

def builder(rows, ids, intel=None):
    accounts = pd.DataFrame([{'account_id': a,'created_at':'2026-01-01T00:00:00Z'} for a in ids])
    return TransactionGraphBuilder(pd.DataFrame(rows,columns=['transaction_id','sender_id','receiver_id','amount','timestamp']),accounts,intel)

def test_fifo_rapid_outflow_and_parallel_amounts():
    rows = [
        {'transaction_id':'i1','sender_id':'A','receiver_id':'X','amount':100,'timestamp':'2026-01-02T10:00:00Z'},
        {'transaction_id':'i2','sender_id':'B','receiver_id':'X','amount':100,'timestamp':'2026-01-02T10:05:00Z'},
        {'transaction_id':'o1','sender_id':'X','receiver_id':'C','amount':150,'timestamp':'2026-01-02T10:10:00Z'},
        {'transaction_id':'o2','sender_id':'X','receiver_id':'D','amount':50,'timestamp':'2026-01-02T11:00:00Z'},
    ]
    b=builder(rows,['A','B','C','D','X'])
    g=b.build_graph_until('2026-01-02T12:00:00Z')
    f=calculate_graph_features(g,'X')
    assert f['unique_incoming_senders']==2
    assert f['unique_outgoing_receivers']==2
    assert f['rapid_outflow_ratio']==.75
    assert f['matched_outflow_ratio']==1
    assert f['median_fund_holding_time']==10.0

def test_cycles_bounded_and_pagerank_supporting_feature():
    rows=[
      {'transaction_id':'1','sender_id':'A','receiver_id':'B','amount':10,'timestamp':'2026-01-02T10:00:00Z'},
      {'transaction_id':'2','sender_id':'B','receiver_id':'C','amount':10,'timestamp':'2026-01-02T10:01:00Z'},
      {'transaction_id':'3','sender_id':'C','receiver_id':'A','amount':10,'timestamp':'2026-01-02T10:02:00Z'}]
    g=builder(rows,['A','B','C']).build_graph_until('2026-01-02T12:00:00Z')
    f=calculate_graph_features(g,'A')
    assert f['cycle_count'] >= 1
    assert f['pagerank'] > 0
    assert bounded_cycles(g.graph['simple'],'A')[1] is False
