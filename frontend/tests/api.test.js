import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../src/services/api.js';

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
  assert.equal(result.context_required,false);
  assert.equal(result.analyst.attempt.assessment.app_scam_risk,72);
  assert.equal(calls[0].url,'/api/v1/simulated-payments');
  assert.equal(calls[1].url,'/api/v1/simulated-payments/attempt-123/analyze');
  assert.equal(calls[2].url,'/api/v1/simulated-payments/attempt-123/analyst');
  assert.equal(JSON.parse(calls[1].options.body).messages[0].text,'Pay now');
});

test('transaction history maps to the existing analytics route',async()=>{
  globalThis.fetch=async(url)=>{assert.equal(url,'/api/v1/simulated-payments/analytics');return json({recent_attempts:[{payment_attempt_id:'one'}]})};
  assert.deepEqual(await api.transactions(),[{payment_attempt_id:'one'}]);
});

test('API errors remain visible to customer and research pages',async()=>{
  globalThis.fetch=async()=>json({detail:'Safety analysis unavailable.'},503);
  await assert.rejects(api.accounts(),/Safety analysis unavailable/);
});
