import pandas as pd
from backend.app.database.repository import DataRepository
from backend.app.graph.graph_builder import TransactionGraphBuilder
from backend.app.graph.graph_features import calculate_graph_features


def test_future_transaction_cannot_change_historical_recipient_features():
    accounts=pd.DataFrame([{'account_id':key,'created_at':'2026-01-01T00:00:00Z',
        'average_transaction_amount':1000,'fraud_report_count':0,'outgoing_ratio':0.0}
        for key in ('S','R','O')])
    rows=[{'transaction_id':f'old-{i}','sender_id':'S','receiver_id':'R','amount':100,
        'timestamp':f'2026-01-02T09:{i%60:02d}:00Z','is_fraud':0} for i in range(99)]
    rows.append({'transaction_id':'future','sender_id':'R','receiver_id':'O','amount':500,
        'timestamp':'2026-01-02T11:00:00Z','is_fraud':1})
    transactions=pd.DataFrame(rows)
    for key,value in {'device_id':'d','payment_type':'upi','payment_reason':'other',
        'first_time_recipient':False,'sender_average_amount':1000,'account_age_days':365,
        'unique_senders_24h':0,'incoming_transactions_24h':0,'outgoing_ratio':0.0,
        'fraud_reports':0,'fraud_type':'normal'}.items():transactions[key]=value
    transactions.loc[transactions.transaction_id=='future','fraud_type']='investment_scam'
    transactions['account_age_days']=1
    for key,value in {'is_known_mule':False,'is_suspicious':False,'normal_hour_start':0,
        'normal_hour_end':23,'usual_device':'d','usual_recipients':'[]',
        'average_holding_minutes':500}.items():accounts[key]=value
    repository=DataRepository(transactions,accounts)
    history=repository.recipient_history('R',pd.Timestamp('2026-01-02T10:30:00Z'))
    assert len(history)==99 and 'future' not in set(history.transaction_id)
    # Strictly-before semantics also excludes an event timestamped exactly at prediction time.
    exact=repository.recipient_history('R',pd.Timestamp('2026-01-02T11:00:00Z'))
    assert len(exact)==99 and 'future' not in set(exact.transaction_id)


def test_future_mule_flow_does_not_appear_in_historical_graph_features():
    accounts=pd.DataFrame([{'account_id':key,'created_at':'2026-01-01T00:00:00Z'} for key in ('V','X','O')])
    transactions=pd.DataFrame([
        {'transaction_id':'in','sender_id':'V','receiver_id':'X','amount':1000,'timestamp':'2026-01-02T11:00:00Z'},
        {'transaction_id':'future-out','sender_id':'X','receiver_id':'O','amount':950,'timestamp':'2026-01-02T14:00:00Z'},
    ])
    builder=TransactionGraphBuilder(transactions,accounts)
    past=calculate_graph_features(builder.build_graph_until('2026-01-02T12:00:00Z'),'X')
    assert past['rapid_outflow_ratio']==0
