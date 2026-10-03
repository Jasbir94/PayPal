"""Run every bundled demo through the actual simulator and fraud engine."""
from datetime import datetime,timezone
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app

EXPECTATIONS={
 'normal_friend':'No severe action for the normal friend-payment scenario.',
 'large_purchase':'A high amount is assessed with recipient and context evidence; never complete on its own.',
 'merchant':'An established merchant is not blocked on fan-in or volume alone.',
 'government_impersonation':'Government-authority and manipulation evidence is assessed before simulated completion.',
 'bank_impersonation':'Bank-authority and transfer-request evidence is assessed before simulated completion.',
 'investment_scam':'Investment, promised-return and pressure evidence is assessed.',
 'fake_job':'Job-fee and recruiter context are assessed.',
 'tech_support':'Remote-access and payment-request evidence are assessed.',
 'family_emergency':'Emergency context is assessed without trusting the story by itself.',
 'small_investment':'The small payment is analyzed with investment and reward/urgency context.',
 'mule_network':'Recipient/graph availability is reported for analyst inspection without disclosing training labels.',
 'hinglish_impersonation':'The Hinglish message is evaluated by actual scenario and psychology services.',
 'missing_context':'The flow asks for context or explicitly records the absent evidence before completion.'}

def assess(sid,final,detail,context_required):
    if sid=='missing_context':
        return context_required or bool({'structured_context','message_text'} & set(detail['assessment']['missing_evidence'])) if detail.get('assessment') else context_required
    assessment=detail['assessment'];ctx=detail['contextual_result'];scenario=ctx['scenario']['type'];tech=set(assessment['detected_psychological_techniques'])
    if sid in ('normal_friend','large_purchase','merchant'):
        return assessment['decision']!='BLOCK_AND_ESCALATE' and assessment['decision']!='STEP_UP_VERIFICATION'
    if sid=='government_impersonation':return (scenario=='government_impersonation' or len(tech&{'authority','fear','urgency','secrecy','emotional_pressure'})>=2 or ctx['scenario_risk']['score']>0) and assessment['app_scam_risk']>detail['passive']['transaction_details']['score']
    if sid=='bank_impersonation':return scenario=='bank_impersonation' or ('authority' in tech and ctx['context_risk']['score']>0)
    if sid=='investment_scam':return scenario=='investment_scam' or (ctx['context_risk']['score']>0 and ('reward' in tech or 'urgency' in tech))
    if sid=='fake_job':return scenario=='fake_job_scam' or ctx['context_risk']['score']>0
    if sid=='tech_support':return ctx['context_risk']['score']>0 and ctx['context_risk']['evidence'].get('remote_access_request',0)>0
    if sid=='family_emergency':return ctx['context_risk']['score']>0 or bool(tech&{'fear','urgency','emotional_pressure'})
    if sid=='small_investment':return scenario=='investment_scam' or ctx['context_risk']['score']>0 or bool(tech&{'reward','scarcity','urgency'})
    if sid=='mule_network':return detail['passive']['graph_risk'] is not None and assessment['recipient_network_risk']['available']
    if sid=='hinglish_impersonation':return scenario in ('bank_impersonation','government_impersonation') or len(tech&{'authority','fear','urgency','secrecy','emotional_pressure'})>=2
    return False

def main():
    rows=[]
    with TestClient(app) as client:
      scenarios=client.get('/api/v1/simulated-payments/scenarios').json()['scenarios']
      for summary in scenarios:
        item=client.get('/api/v1/simulated-payments/scenarios/'+summary['id']).json()
        created=client.post('/api/v1/simulated-payments',json={
           'sender_alias':item['sender_alias'],'recipient_alias':item['recipient_alias'],
           'amount':item['amount'],'payment_reason':item['payment_reason'],'payment_type':'upi',
           'idempotency_key':'day8-validation-'+item['scenario_id']+'-'+str(time.time_ns())})
        if created.status_code!=200: raise RuntimeError(created.text)
        aid=created.json()['payment_attempt_id']
        context={'payment_reason':item['payment_reason'],**item.get('context',{})}
        started=time.perf_counter()
        result=client.post(f'/api/v1/simulated-payments/{aid}/analyze',json={'context':context,'messages':item.get('messages',[])})
        payload=result.json()
        context_required=payload.get('context_required',False)
        if result.status_code!=200: raise RuntimeError(f"{item['scenario_id']}: {result.text}")
        if context_required and item['scenario_id']!='missing_context':
            context['contacted_by_unknown_person']=False
            result=client.post(f'/api/v1/simulated-payments/{aid}/analyze',json={'context':context,'messages':item.get('messages',[])})
            if result.status_code!=200: raise RuntimeError(f"{item['scenario_id']} context step: {result.text}")
            payload=result.json()
        public=payload['payment']
        detail=client.get(f'/api/v1/simulated-payments/{aid}/analyst').json()['attempt']
        passive=detail['passive'] or {}
        assessment=detail['assessment']
        passed=assess(item['scenario_id'],payload,detail,context_required)
        rows.append({'scenario_id':item['scenario_id'],'title':item['title'],'expected_general_behavior':EXPECTATIONS[item['scenario_id']],
          'passive_risk':passive.get('preliminary_risk'),'passive_risk_level':passive.get('risk_level'),
          'transaction_only_risk':(passive.get('transaction_details') or {}).get('score'),
          'passive_graph_risk':(passive.get('graph_risk') or {}).get('score'),
          'full_risk':assessment.get('app_scam_risk') if assessment else None,
          'confidence':assessment.get('confidence') if assessment else None,
          'scenario':detail['contextual_result']['scenario']['type'] if detail.get('contextual_result') else None,
          'scenario_confidence':detail['contextual_result']['scenario']['confidence'] if detail.get('contextual_result') else None,
          'psychological_techniques':assessment.get('detected_psychological_techniques',[]) if assessment else [],
          'decision':assessment.get('decision') if assessment else 'CONTEXT_REQUIRED',
          'intervention':assessment.get('intervention') if assessment else None,
          'context_required_first':context_required,'final_state':public['state'],'pass':bool(passed),
          'latency_ms':detail['latency_ms']})
    report={'title':'APP Shield Day 8 actual demo scenario validation','generated_at':datetime.now(timezone.utc).isoformat(),
      'environment':'synthetic, in-process FastAPI simulator; no external payment processing',
      'passed':sum(row['pass'] for row in rows),'failed':sum(not row['pass'] for row in rows),
      'scenario_count':len(rows),'criteria_notice':'Pass/fail checks broad expected behaviors listed per case; they are not hidden fraud labels or calibrated performance metrics.',
      'scenarios':rows}
    out=ROOT/'evaluation/day8_scenario_validation.json';out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='scenarios'},indent=2))
    for row in rows:print(row['scenario_id'],row['pass'],row['scenario'],row['decision'],row['full_risk'],row['psychological_techniques'])
if __name__=='__main__':main()
