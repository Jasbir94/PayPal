"""Run three real-engine, simulated payment case studies and save observed outputs."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app


CASES=[
    {'name':'government_impersonation','title':'Normal-range government impersonation',
     'sender_alias':'U101','recipient_alias':'R203','amount':3500,'payment_reason':'government',
     'context':{'contacted_by_unknown_person':True,'contact_channel':'whatsapp','claimed_authority':True,
        'authority_type':'government','urgent_payment_requested':True,'threatened_consequences':True,
        'requested_secrecy':True,'fund_transfer_requested':True},
     'messages':[{'speaker':'other','text':'Aaj verification complete karna zaroori hai. Provided account me transfer kar dijiye. Kisi ko mat batana, warna legal action ho sakta hai.'}]},
    {'name':'large_legitimate_purchase','title':'₹80,000 user-initiated established merchant purchase',
     'sender_alias':'U101','recipient_alias':'R202','amount':80000,'payment_reason':'shopping',
     'context':{'contacted_by_unknown_person':False,'contact_channel':'in_person','urgent_payment_requested':False,
        'claimed_authority':False,'requested_secrecy':False,'fund_transfer_requested':False},'messages':[]},
    {'name':'small_initial_investment','title':'₹500 guaranteed-return investment pressure',
     'sender_alias':'U101','recipient_alias':'R203','amount':500,'payment_reason':'investment',
     'context':{'contacted_by_unknown_person':True,'contact_channel':'whatsapp','promised_profit':True,
        'guaranteed_returns_promised':True,'urgent_payment_requested':True},
     'messages':[{'speaker':'other','text':'Start with only ₹500 today. Guaranteed return of ₹1,000; only a few slots remain, transfer now.'}]},
    {'name':'mule_network','title':'Recipient linked to a synthetic pass-through network',
     'sender_alias':'U102','recipient_alias':'R205','amount':2200,'payment_reason':'other',
     'context':{},'messages':[]},
    {'name':'legitimate_family_emergency','title':'Urgent family help to an established contact',
     'sender_alias':'U101','recipient_alias':'R201','amount':20000,'payment_reason':'family',
     'context':{'contacted_by_unknown_person':False,'contact_channel':'phone','urgent_payment_requested':True,
        'relationship_duration_days':3650},
     'messages':[{'speaker':'user','text':'My brother is in hospital. Please send ₹20,000 immediately.'}]},
]


def run(output_path=ROOT/'reports'/'flagship_experiments.json'):
    rows=[]
    with TestClient(app) as client:
        for index,case in enumerate(CASES):
            created=client.post('/api/v1/simulated-payments',json={k:case[k] for k in
                ('sender_alias','recipient_alias','amount','payment_reason')}|{'payment_type':'upi',
                    'idempotency_key':f"day9-case-study-{index}-{time.time_ns()}"})
            created.raise_for_status();attempt=created.json()['payment_attempt_id']
            response=client.post(f'/api/v1/simulated-payments/{attempt}/analyze',json={
                'context':case['context'],'messages':case['messages']})
            response.raise_for_status();payload=response.json()
            # If the simulator requests more context, provide a bounded explicit answer and analyze again.
            if payload.get('context_required'):
                context={**case['context'],'contacted_by_unknown_person':False}
                response=client.post(f'/api/v1/simulated-payments/{attempt}/analyze',json={
                    'context':context,'messages':case['messages']})
                response.raise_for_status();payload=response.json()
            detail=client.get(f'/api/v1/simulated-payments/{attempt}/analyst').json()['attempt']
            assessment=detail.get('assessment') or {};passive=detail.get('passive') or {}
            context=detail.get('contextual_result') or {}
            rows.append({'case':case['name'],'title':case['title'],'amount_inr':case['amount'],
                'transaction_only_risk':(passive.get('transaction_details') or {}).get('score'),
                'recipient_risk':(passive.get('recipient_details') or {}).get('score'),
                'passive_graph_risk':(passive.get('graph_risk') or {}).get('score'),
                'passive_risk':passive.get('preliminary_risk'),
                'passive_graph_risk':(passive.get('graph_risk') or {}).get('score'),
                'passive_risk':passive.get('preliminary_risk'),
                'full_app_shield_risk':assessment.get('app_scam_risk'),
                'confidence':assessment.get('confidence'),'scenario':(context.get('scenario') or {}).get('type'),
                'scenario_confidence':(context.get('scenario') or {}).get('confidence'),
                'component_latency_ms':assessment.get('component_latency_ms',{}),
                'component_latency_ms':assessment.get('component_latency_ms',{}),
                'psychological_techniques':assessment.get('detected_psychological_techniques',[]),
                'decision':assessment.get('decision'),'intervention':assessment.get('intervention'),
                'analysis_state':payload.get('payment',{}).get('state'),
                'interpretation':'Observed synthetic-engine output; not a fraud ground-truth performance label.'})
    report={'title':'APP Shield Day 9 flagship case studies','generated_at':datetime.now(timezone.utc).isoformat(),
        'environment':'Local synthetic simulator; no payment was executed.',
        'cases':rows,'limitations':'These are illustrative runs, not scenario recall or verified outcome measurements.'}
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    Path(output_path).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return report


if __name__=='__main__':
    report=run();print(json.dumps(report,indent=2,ensure_ascii=True))
