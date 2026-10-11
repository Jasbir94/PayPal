import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../src/services/api.js';
import { buildCaseReport } from '../src/services/reports.js';

const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch});
const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});

test('scenario comparison creates an attempt, analyzes it, then loads analyst evidence',async()=>{
  const calls=[];
  globalThis.fetch=async(url,options={})=>{
    calls.push({url,options});
    if(calls.length===1)return json({payment_attempt_id:'attempt-123'});
    if(calls.length===2)return json({context_required:false,payment:{state:'WARNING'}});
    return json({payment:{state:'WARNING'},attempt:{assessment:{app_scam_risk:72}}});
  };
  const result=await api.runScenario({sender_alias:'U101',recipient_alias:'R203',amount:3500,
    payment_reason:'government',context:{claimed_authority:true},messages:[{speaker:'other',text:'Pay now'}]});
  assert.equal(result.payment_attempt_id,'attempt-123');
  assert.equal(result.context_required,false);
  assert.equal(result.analyst.attempt.assessment.app_scam_risk,72);
  assert.equal(calls[0].url,'/api/v1/simulated-payments');
  assert.equal(calls[1].url,'/api/v1/simulated-payments/attempt-123/analyze');
  assert.equal(calls[2].url,'/api/v1/simulated-payments/attempt-123/analyst');
  assert.equal(JSON.parse(calls[1].options.body).messages[0].text,'Pay now');
});

test('transaction history maps to the existing analytics route',async()=>{
  globalThis.fetch=async(url)=>{assert.equal(url,'/api/v1/simulated-payments/analytics?limit=1000');return json({recent_attempts:[{payment_attempt_id:'one'}]})};
  assert.deepEqual(await api.transactions(),[{payment_attempt_id:'one'}]);
});

test('system diagnostics reports live readiness, models, and scenario availability',async()=>{
  globalThis.fetch=async(url)=>{
    if(url==='/health')return json({status:'healthy'});
    if(url==='/ready')return json({status:'ready'});
    if(url==='/api/v1/model-info')return json({components:{graph:{available:true}}});
    if(url==='/api/v1/simulated-payments/scenarios')return json({scenarios:[{id:'normal'}]});
    if(url==='/api/v1/chat/health')return json({available:true,language_model:'not configured'});
    throw new Error(`Unexpected request: ${url}`);
  };
  const result=await api.systemDiagnostics();
  assert.equal(result.health.value.status,'healthy');
  assert.equal(result.ready.value.status,'ready');
  assert.equal(result.models.value.components.graph.available,true);
  assert.equal(result.scenarioCatalog.value.scenarios.length,1);
  assert.equal(result.chat.value.available,true);
});

test('chat API preserves backend-selected session and action contracts',async()=>{
  const calls=[];
  globalThis.fetch=async(url,options={})=>{calls.push({url,options});return json({session_id:'chat-1',interaction_type:'NEEDS_CONTEXT'})};
  const start=await api.chatStart('Send INR 3500 to a new recipient','demo-token','chat-start-key-01');
  await api.chatMessage(start.session_id,'Yes','demo-token','chat-message-key-01');
  await api.chatAction(start.session_id,'cancel','demo-token');
  assert.equal(calls[0].url,'/api/v1/chat/sessions');
  assert.equal(calls[0].options.headers.Authorization,'Bearer demo-token');
  assert.equal(JSON.parse(calls[0].options.body).message,'Send INR 3500 to a new recipient');
  assert.equal(JSON.parse(calls[0].options.body).idempotency_key,'chat-start-key-01');
  assert.equal(JSON.parse(calls[1].options.body).idempotency_key,'chat-message-key-01');
  assert.equal(calls[1].url,'/api/v1/chat/sessions/chat-1/messages');
  assert.equal(calls[2].url,'/api/v1/chat/sessions/chat-1/actions/cancel');
});

test('wallet API binds balance and transaction reads to a bearer session',async()=>{
  const calls=[];
  globalThis.fetch=async(url,options={})=>{calls.push({url,options});return json({available_balance:7000,transactions:[]})};
  await api.bankingBalance('profile-token');
  await api.bankingTransactions('profile-token','direction=DEBIT&period=week');
  assert.equal(calls[0].url,'/api/v1/banking/balance');
  assert.equal(calls[0].options.headers.Authorization,'Bearer profile-token');
  assert.equal(calls[1].url,'/api/v1/banking/transactions?direction=DEBIT&period=week');
  assert.equal(calls[1].options.headers.Authorization,'Bearer profile-token');
});

test('API errors remain visible to customer and research pages',async()=>{
  globalThis.fetch=async()=>json({detail:'Safety analysis unavailable.'},503);
  await assert.rejects(api.accounts(),/Safety analysis unavailable/);
});

test('case report preserves actual assessment values and synthetic-data limits',()=>{
  const report=buildCaseReport({
    payment:{payment_attempt_id:'attempt-42',amount:3500,currency:'INR',simulated_status:'NOT_EXECUTED'},
    attempt:{assessment:{app_scam_risk:58.2,risk_level:'MEDIUM',decision:'ALLOW_WITH_WARNING',
      confidence:0.72,model_versions:{fusion:'demo-v1'},top_reasons:[{code:'CTX_URGENT_REQUEST'}],
      protective_evidence:['KNOWN_RECIPIENT_LONG_TERM'],missing_evidence:['call_verification']},context:{urgent_payment_requested:true}},
    network:{available:true,nodes:[],edges:[]},
  });
  assert.equal(report.assessment.risk_index,58.2);
  assert.equal(report.assessment.confidence,0.72);
  assert.deepEqual(report.evidence.protective,['KNOWN_RECIPIENT_LONG_TERM']);
  assert.equal(report.recipient_network.available,true);
  assert.match(report.limitations[0],/synthetic/);
});
