from backend.app.graph.graph_builder import TransactionGraphBuilder
from backend.app.graph.graph_features import calculate_graph_features

def test_future_flow_never_changes_prior_graph_score():
    accounts=[{'account_id':a,'created_at':'2026-01-01T00:00:00Z'} for a in ['V','X','O']]
    tx=[
      {'transaction_id':'in','sender_id':'V','receiver_id':'X','amount':1000,'timestamp':'2026-01-02T11:00:00Z'},
      {'transaction_id':'future','sender_id':'X','receiver_id':'O','amount':950,'timestamp':'2026-01-02T14:00:00Z'}]
    import pandas as pd
    b=TransactionGraphBuilder(pd.DataFrame(tx),pd.DataFrame(accounts))
    before=calculate_graph_features(b.build_graph_until('2026-01-02T12:00:00Z'),'X')
    after=calculate_graph_features(b.build_graph_until('2026-01-02T15:00:00Z'),'X')
    assert before['rapid_outflow_ratio']==0
    assert after['matched_outflow_ratio']==.95
