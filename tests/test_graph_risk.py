import pandas as pd
from backend.app.graph.graph_builder import TransactionGraphBuilder
from backend.app.services.graph_service import GraphService

def make_graph(rows, ids, known=()):
    accounts=pd.DataFrame([{'account_id':a,'created_at':'2026-01-01T00:00:00Z'} for a in ids])
    tx=pd.DataFrame(rows,columns=['transaction_id','sender_id','receiver_id','amount','timestamp'])
    intel=pd.DataFrame([{'account_id':a,'kind':'known_mule','observed_at':'2026-01-01T00:00:00Z'} for a in known],columns=['account_id','kind','observed_at'])
    return GraphService(TransactionGraphBuilder(tx,accounts,intel))

def test_normal_personal_account_is_low():
    ids=['A','B','C']
    rows=[{'transaction_id':'1','sender_id':'A','receiver_id':'B','amount':100,'timestamp':'2026-01-02T10:00:00Z'}]
    assert make_graph(rows,ids).score_graph_risk('B','2026-01-02T12:00:00Z')['score'] == 0

def test_merchant_fan_in_is_not_critical_without_layering():
    ids=['M']+[f'C{i}' for i in range(30)]
    rows=[{'transaction_id':str(i),'sender_id':f'C{i}','receiver_id':'M','amount':1000,'timestamp':f'2026-01-02T10:{i:02d}:00Z'} for i in range(30)]
    result=make_graph(rows,ids).score_graph_risk('M','2026-01-02T12:00:00Z')
    assert result['features']['unique_incoming_senders']==30
    assert result['score'] < 80
    assert 'high_fan_in' in result['reasons']

def test_collector_fan_in_rapid_flow_and_young_account():
    ids=['X']+[f'V{i}' for i in range(25)]+['O']
    rows=[{'transaction_id':f'i{i}','sender_id':f'V{i}','receiver_id':'X','amount':1000,'timestamp':f'2026-01-02T10:{i:02d}:00Z'} for i in range(25)]
    rows.append({'transaction_id':'out','sender_id':'X','receiver_id':'O','amount':23500,'timestamp':'2026-01-02T10:29:00Z'})
    result=make_graph(rows,ids).score_graph_risk('X','2026-01-02T10:30:00Z')
    assert result['features']['rapid_outflow_ratio']==.94
    assert result['score']>=80
    assert {'high_fan_in','rapid_pass_through','collector_pass_through_combination'} <= set(result['reasons'])

def test_known_mule_neighbor_increases_score_without_auto_100():
    rows=[{'transaction_id':'1','sender_id':'X','receiver_id':'K','amount':1000,'timestamp':'2026-01-02T10:00:00Z'}]
    base=make_graph(rows,['X','K']).score_graph_risk('X','2026-01-02T12:00:00Z')['score']
    result=make_graph(rows,['X','K'],known=['K']).score_graph_risk('X','2026-01-02T12:00:00Z')
    assert result['features']['known_mule_neighbors']==1
    assert result['score']>base and result['score']<100


def test_layered_chain_marks_pass_through_depth():
    ids=['V','M1','M2','M3']
    rows=[
      {'transaction_id':'1','sender_id':'V','receiver_id':'M1','amount':11000,'timestamp':'2026-01-02T10:00:00Z'},
      {'transaction_id':'2','sender_id':'M1','receiver_id':'M2','amount':10500,'timestamp':'2026-01-02T10:02:00Z'},
      {'transaction_id':'3','sender_id':'M2','receiver_id':'M3','amount':900,'timestamp':'2026-01-02T10:04:00Z'}]
    result=make_graph(rows,ids).score_graph_risk('M1','2026-01-02T10:10:00Z')
    assert result['features']['suspicious_path_depth'] >= 2
    assert 'suspicious_layering_pattern' in result['reasons']


def test_cycle_plus_rapid_flow_adds_layering_reason():
    ids=['A','B','C']
    rows=[
      {'transaction_id':'1','sender_id':'C','receiver_id':'A','amount':11000,'timestamp':'2026-01-02T10:00:00Z'},
      {'transaction_id':'2','sender_id':'A','receiver_id':'B','amount':10500,'timestamp':'2026-01-02T10:02:00Z'},
      {'transaction_id':'3','sender_id':'B','receiver_id':'C','amount':10000,'timestamp':'2026-01-02T10:04:00Z'}]
    result=make_graph(rows,ids).score_graph_risk('A','2026-01-02T10:10:00Z')
    assert result['features']['cycle_count'] >= 1
    assert 'cycle_rapid_flow_combination' in result['reasons']


def test_established_fast_settling_merchant_is_capped_without_direct_mule_evidence():
    ids=['M']+[f'C{i}' for i in range(25)]+['S']
    rows=[{'transaction_id':f'i{i}','sender_id':f'C{i}','receiver_id':'M','amount':1000,'timestamp':f'2026-01-02T10:{i:02d}:00Z'} for i in range(25)]
    rows.append({'transaction_id':'settlement','sender_id':'M','receiver_id':'S','amount':23500,'timestamp':'2026-01-02T10:29:00Z'})
    accounts=pd.DataFrame([{'account_id':a,'created_at':'2023-01-01T00:00:00Z'} for a in ids])
    tx=pd.DataFrame(rows,columns=['transaction_id','sender_id','receiver_id','amount','timestamp'])
    result=GraphService(TransactionGraphBuilder(tx,accounts)).score_graph_risk('M','2026-01-02T10:30:00Z')
    assert result['features']['rapid_outflow_ratio']==.94
    assert result['score']<=65
    assert 'established_account_network_guard' in result['reasons']
