"""Exercise 20 simulated payment conversations against a running APP Shield API."""
import json
import os
import statistics
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Support both `python -m scripts.conversation_reliability_audit` and direct
# Windows invocation via `python scripts\conversation_reliability_audit.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.rag.knowledge_store import HybridRetriever

BASE=os.getenv('APP_SHIELD_URL','http://127.0.0.1:8000').rstrip('/')
TOKEN=None
CASES=[
 ('known recipient','Send INR 1200 to my saved recipient for dinner','Friend or family','confirm','R201'),
 ('new legitimate recipient','Send INR 850 to a new recipient for a book purchase','I found the seller for this book','cancel','R203'),
 ('urgent family emergency','Send INR 20000 to my saved recipient for a hospital emergency','My brother asked me','cancel','R201'),
 ('government impersonation','Send INR 3500 to a new recipient for government verification. An officer says my account will be blocked; pay now.','Not sure','cancel','R203'),
 ('fake bank verification','Send INR 4200 to a new recipient for bank verification. The caller says transfer now to protect my account.','Not sure','cancel','R203'),
 ('fake job registration fee','Send INR 1800 to a new recipient for a recruiter registration fee.','Not sure','cancel','R203'),
 ('investment scam','Send INR 9000 to a new recipient for guaranteed investment returns today.','Not sure','cancel','R203'),
 ('suspicious recipient network','Send INR 2200 to R205 for a purchase','Not sure','cancel','R205'),
 ('missing information','I need to send money','3500','cancel','R201'),
 ('user changes their mind','Send INR 1200 to my saved recipient','I changed my mind','cancel','R201'),
 ('small known payment','Send INR 500 to my saved recipient','Friend or family','confirm','R201'),
 ('established merchant','Send INR 2400 to R202 for shopping','No one contacted me','confirm','R202'),
 ('legitimate large purchase','Send INR 80000 to R202 for a laptop purchase','I initiated this purchase','cancel','R202'),
 ('legitimate family emergency','Send INR 20000 to my saved recipient. My brother has a hospital emergency; I know him and want to help.','Friend or family','confirm','R201'),
 ('secret authority request','Send INR 3100 to a new recipient. A government officer asks me to keep this secret and pay immediately.','Not sure','cancel','R203'),
 ('uncertain contact','Send INR 3500 to a new recipient','Not sure','cancel','R203'),
 ('Hinglish bank impersonation','Send INR 3100 to R204 for bank verification. Bank caller bolta hai abhi transfer karo, kisi ko mat batana.','Not sure','cancel','R204'),
 ('remote support pressure','Send INR 2600 to R204. Tech support says install remote access and send a test payment.','Not sure','cancel','R204'),
 ('refund pressure','Send INR 5000 to a new recipient. Caller says I got an extra refund and must return it immediately.','Not sure','cancel','R203'),
 ('ordinary merchant','Send INR 3200 to R202 for a normal store purchase, no one contacted me.','No one contacted me','confirm','R202'),
]

def call(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    headers={'Content-Type':'application/json'} if data else {}
    if TOKEN:headers['Authorization']='Bearer '+TOKEN
    request=Request(BASE+path,data=data,headers=headers)
    started=time.perf_counter()
    try:
        with urlopen(request,timeout=30) as response:
            result=json.loads(response.read().decode())
            return result,(time.perf_counter()-started)*1000
    except (HTTPError,URLError,TimeoutError) as error:
        detail=error.read().decode() if isinstance(error,HTTPError) else str(error)
        raise RuntimeError(f'{path}: {detail}') from error

def percentile(values,p):
    ordered=sorted(values)
    return round(ordered[min(len(ordered)-1,round((len(ordered)-1)*p))],2) if ordered else None

def main():
    global TOKEN
    health,_=call('/ready')
    if health.get('status')!='ready':raise SystemExit(f'Backend is not ready: {health}')
    demo_session,_=call('/api/v1/banking/demo-sessions',{'account_alias':'U101'})
    TOKEN=demo_session['access_token']
    case_rows=[];http_latencies=[];complete_latencies=[];payment_latencies={
        'passive_analysis_ms':[],'full_analysis_ms':[],'end_to_end_analysis_ms':[]};question_counts=[]
    for name,opening,answer,action,recipient in CASES:
        started=time.perf_counter();calls=0;questions=[]
        result,latency=call('/api/v1/chat/sessions',{'message':opening});http_latencies.append(latency);calls+=1
        session=result['session_id'];payment=result.get('payment')
        if result.get('interaction_type')=='COLLECTING_DETAILS' and not payment:
            reply=answer if result['message'].startswith('What amount') else recipient
            result,latency=call(f'/api/v1/chat/sessions/{session}/messages',{'message':reply});http_latencies.append(latency);calls+=1
        if result.get('recipient_options'):
            choice=next((item['value'] for item in result['recipient_options'] if item['value']==recipient),result['recipient_options'][0]['value'])
            result,latency=call(f'/api/v1/chat/sessions/{session}/messages',{'message':choice});http_latencies.append(latency);calls+=1
        while result.get('current_question') and len(questions)<4:
            prompt=result['message'];questions.append(prompt)
            reply=(answer if len(questions)==1 and answer and answer!='I changed my mind'
                   else 'Not sure')
            result,latency=call(f'/api/v1/chat/sessions/{session}/messages',{'message':reply});http_latencies.append(latency);calls+=1
        payment=result.get('payment')
        # The change-of-mind case exercises natural-language cancellation through chat.
        if name=='user changes their mind' and payment and payment['state'] not in ('CANCELLED','SIMULATED_HELD','SIMULATED_COMPLETED','ERROR'):
            result,latency=call(f'/api/v1/chat/sessions/{session}/messages',{'message':answer});http_latencies.append(latency);calls+=1
            payment=result.get('payment')
        if result.get('interaction_type')=='INSUFFICIENT_FUNDS':
            elapsed=(time.perf_counter()-started)*1000;complete_latencies.append(elapsed);question_counts.append(len(questions))
            case_rows.append({'scenario':name,'state':'INSUFFICIENT_FUNDS','decision':'NOT_ANALYZED',
                'risk_level':None,'risk_score':None,'reason_codes':[],'evidence_reasons':[],
                'questions':len(questions),'question_prompts':questions,'question_repeated':False,
                'unresolved_question':bool(result.get('current_question')),
                'explicit_action':None,'before_action_status':'NOT_EXECUTED','simulated_status':'NOT_EXECUTED',
                'api_calls':calls,'flow_ms':round(elapsed,2),'analysis_ms':{}})
            continue
        if not payment:
            raise RuntimeError(f'{name}: no payment assessment after collecting details: {result}')
        before_action=payment['simulated_status']
        if before_action=='SIMULATED_SUCCESS':raise RuntimeError(f'{name}: payment executed before explicit confirmation')
        if action=='confirm' and 'confirm' in result.get('available_actions',[]):
            result,latency=call(f"/api/v1/chat/sessions/{session}/actions/confirm",{});http_latencies.append(latency);calls+=1
        elif action=='cancel' and 'cancel' in result.get('available_actions',[]):
            result,latency=call(f"/api/v1/chat/sessions/{session}/actions/cancel",{});http_latencies.append(latency);calls+=1
        payment=result.get('payment') or payment
        elapsed=(time.perf_counter()-started)*1000;complete_latencies.append(elapsed);question_counts.append(len(questions))
        attempt_id=payment['payment_attempt_id']
        analyst,_=call(f'/api/v1/simulated-payments/{attempt_id}/analyst')
        timing=analyst['attempt'].get('latency_ms') or {}
        for key in payment_latencies:
            if timing.get(key) is not None:payment_latencies[key].append(timing[key])
        assessment=analyst['attempt'].get('assessment') or {}
        case_rows.append({'scenario':name,'state':payment['state'],'decision':payment.get('decision'),
            'risk_level':assessment.get('risk_level'),'risk_score':assessment.get('app_scam_risk'),
            'reason_codes':assessment.get('reason_codes',[]),
            'evidence_reasons':[item.get('id') for item in assessment.get('top_reasons',[])],
            'questions':len(questions),'question_prompts':questions,
            'question_repeated':len(questions)!=len(set(questions)),
            'unresolved_question':bool(result.get('current_question')),
            'explicit_action':payment.get('user_action'),'before_action_status':before_action,
            'simulated_status':payment['simulated_status'],'api_calls':calls,
            'flow_ms':round(elapsed,2),'analysis_ms':timing})
    retriever=HybridRetriever();retrieval_samples=[]
    for _ in range(50):
        started=time.perf_counter();retriever.retrieve('government officer says account blocked and asks for urgent payment',category='government_impersonation')
        retrieval_samples.append((time.perf_counter()-started)*1000)
    summary={'count':len(CASES),'question_count_total':sum(question_counts),
        'maximum_questions_per_flow':max(question_counts,default=0),
        'flows_with_multiple_questions':sum(row['questions']>1 for row in case_rows),
        'unresolved_questions':sum(row['unresolved_question'] for row in case_rows),
        'repeated_questions':sum(row['question_repeated'] for row in case_rows),
        'terminal_outcomes':sum(row['state'] in ('SIMULATED_COMPLETED','CANCELLED','SIMULATED_HELD','ERROR','INSUFFICIENT_FUNDS') for row in case_rows),
        'preconfirmation_executions':sum(row['before_action_status']=='SIMULATED_SUCCESS' for row in case_rows),
        'http_response_ms':{'median':round(statistics.median(http_latencies),2),'p95':percentile(http_latencies,.95),'max':round(max(http_latencies),2)},
        'complete_flow_ms':{'median':round(statistics.median(complete_latencies),2),'p95':percentile(complete_latencies,.95),'max':round(max(complete_latencies),2)},
        'rag_retrieval_ms_50_local_samples':{'median':round(statistics.median(retrieval_samples),3),'p95':percentile(retrieval_samples,.95),'max':round(max(retrieval_samples),3)},
        'payment_analysis_ms':{key:{'median':round(statistics.median(values),2),'p95':percentile(values,.95),
            'max':round(max(values),2)} if values else None for key,values in payment_latencies.items()}}
    print(json.dumps({'summary':summary,'cases':case_rows},indent=2))

if __name__=='__main__':main()
