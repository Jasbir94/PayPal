"""Check Day 5 graph and grouped contextual routes on the running local API."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from backend.app.config.graph_config import GRAPH_REPORT_DIR

def get(path):
    with urlopen('http://127.0.0.1:8000' + path, timeout=30) as response:
        return json.load(response)

def post(path, payload):
    body=json.dumps(payload).encode('utf-8')
    request=Request('http://127.0.0.1:8000'+path,data=body,headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=30) as response:
        return json.load(response)

def main():
    account='A1006'
    point='2026-01-30T23:31:50+00:00'
    risk=get('/api/v1/accounts/'+account+'/graph-risk?'+urlencode({'at':point}))
    assert risk['account_id']==account and 0<=risk['graph_risk']<=100
    payment={'sender_id':'A0001','receiver_id':account,'amount':85000,
             'timestamp':point,'device_id':'D0001','payment_type':'bank_transfer'}
    context={'payment_reason':'government','contacted_by_unknown_person':True,'claimed_authority':True,
             'authority_type':'police','urgent_payment_requested':True,'threatened_consequences':True,
             'requested_secrecy':True,'fund_transfer_requested':True}
    result=post('/api/v1/risk/contextual',{'transaction':payment,'context':context,
        'message':'I am from Cyber Crime. Transfer immediately or you will be arrested. Do not tell anyone.'})
    assert result['graph_risk'] is not None
    assert set(result['grouped_scores'])=={'user_side','recipient_side','manipulation_side'}
    assert 0<=result['overall_risk']<=100
    GRAPH_REPORT_DIR.mkdir(parents=True,exist_ok=True)
    (GRAPH_REPORT_DIR/'live_api_examples.json').write_text(json.dumps({
        'graph_request':{'account_id':account,'at':point},'graph_response':risk,
        'contextual_request':{'transaction':payment,'context':context,'message':'I am from Cyber Crime. Transfer immediately or you will be arrested. Do not tell anyone.'},
        'contextual_response':result},indent=2),encoding='utf-8')
    print(f"graph={risk['graph_risk']} ({risk['risk_level']}), features={len(risk['features'])}; "
          f"grouped overall={result['overall_risk']} ({result['overall_risk_level']}); "
          f"fusion={result['fusion_policy']}")
if __name__=='__main__':
    main()
