import React, { useEffect, useMemo, useState } from 'react';
import DemoScenarios from '../components/payment/DemoScenarios.jsx';
import ContextCheck from '../components/payment/ContextCheck.jsx';
import ScamWarning from '../components/intervention/ScamWarning.jsx';
import TopNav from '../components/common/TopNav.jsx';
import AppFooter from '../components/common/AppFooter.jsx';
import { api } from '../services/api.js';
import { currency, pretty } from '../utils/riskUtils.js';

const reasons=[['family','Family'],['friend','Friend'],['shopping','Shopping'],['investment','Investment'],['job','Job'],['government','Government'],['bank_support','Bank / Support'],['loan','Loan'],['refund','Refund'],['marketplace','Marketplace'],['emergency','Emergency'],['other','Other']];
const freshId=()=>globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}`;
const emptyContext=()=>({contacted_by_unknown_person:null,contact_channel:null,claimed_authority:null,authority_type:'other',urgent_payment_requested:null,threatened_consequences:null,requested_secrecy:null,fund_transfer_requested:null,asked_to_pay_fee:null,promised_profit:null,guaranteed_returns_promised:null,asked_to_install_remote_access:null});

export default function PaymentPage({ libraryOnly=false, initialAttemptId=null }) {
  const [catalog,setCatalog]=useState(null),[scenarios,setScenarios]=useState([]),[form,setForm]=useState({sender_alias:'U101',recipient_alias:'R201',amount:'3500',payment_reason:'friend',payment_type:'upi',note:''});
  const [selectedScenario,setSelectedScenario]=useState('government_impersonation'),[scenarioMessages,setScenarioMessages]=useState([]),[demoContext,setDemoContext]=useState(null),[demoNote,setDemoNote]=useState('');
  const [attempt,setAttempt]=useState(null),[attemptId,setAttemptId]=useState(null),[questions,setQuestions]=useState([]),[userContext,setUserContext]=useState(emptyContext),[message,setMessage]=useState('');
  const [page,setPage]=useState('form'),[busy,setBusy]=useState(false),[ack,setAck]=useState(false),[error,setError]=useState(''),[loadingCatalog,setLoadingCatalog]=useState(true);
  const sender=useMemo(()=>catalog?.senders?.find(x=>x.alias===form.sender_alias),[catalog,form.sender_alias]);
  const recipient=useMemo(()=>catalog?.recipients?.find(x=>x.alias===form.recipient_alias),[catalog,form.recipient_alias]);
  useEffect(()=>{let active=true;Promise.all([api.accounts(),api.scenarios()]).then(([a,s])=>{if(!active)return;setCatalog(a);setScenarios(s.scenarios||[]);}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoadingCatalog(false)});if(initialAttemptId){api.attempt(initialAttemptId).then(value=>{if(!active)return;setAttempt(value);setAttemptId(initialAttemptId);setQuestions(value.context_questions||[]);setForm(current=>({...current,sender_alias:value.sender.alias,recipient_alias:value.recipient.alias,amount:String(value.amount),payment_reason:value.payment_reason,note:value.note||''}));const restoredPage=value.state==='CONTEXT_REQUIRED'?'context':value.state==='READY'?'ready':['SIMULATED_COMPLETED','CANCELLED','SIMULATED_HELD'].includes(value.state)?'outcome':['DRAFT','REVIEW'].includes(value.state)?'review':value.state==='ANALYZING'?'loading':value.state==='ERROR'?'error':'result';setPage(restoredPage);}).catch(e=>{if(active){setError(e.message);setPage('error')}})}return()=>{active=false}},[initialAttemptId]);
  const setField=(key,value)=>setForm(current=>({...current,[key]:value}));

  async function loadScenario(id=selectedScenario){
    setBusy(true);setError('');
    try{const s=await api.scenario(id);setSelectedScenario(id);setForm({sender_alias:s.sender_alias,recipient_alias:s.recipient_alias,amount:String(s.amount),payment_reason:s.payment_reason,payment_type:'upi',note:''});setScenarioMessages(s.messages||[]);setDemoContext(s.context||null);setDemoNote(s.difficulty==='flagship'?'Why this case is difficult: the amount is within a normal range, the sender uses a known device, and the pressure appears in the payment story. APP Shield combines the payment context with recipient and manipulation evidence.':'');resetFlow();if(libraryOnly)history.replaceState(null,'','/send');}
    catch(e){setError(e.message)}finally{setBusy(false)}
  }
  function resetFlow(){setAttempt(null);setAttemptId(null);setQuestions([]);setUserContext(emptyContext());setMessage('');setPage('form');setAck(false);setError('');}
  function resetDemo(){resetFlow();setForm({sender_alias:'U101',recipient_alias:'R201',amount:'3500',payment_reason:'friend',payment_type:'upi',note:''});setScenarioMessages([]);setDemoContext(null);setDemoNote('');setSelectedScenario('government_impersonation');history.replaceState(null,'','/send');}

  async function beginAnalysis(context=demoContext||emptyContext(),messages=scenarioMessages){
    setBusy(true);setError('');setPage('loading');
    try{
      let id=attemptId;
      if(!id){const created=await api.createAttempt({...form,amount:Number(form.amount),idempotency_key:freshId()});id=created.payment_attempt_id;setAttemptId(id);localStorage.setItem('app-shield-last-attempt',id);}
      history.replaceState(null,'',`/payment/${encodeURIComponent(id)}/review`);
      const result=await api.analyze(id,{context:{...context,payment_reason:form.payment_reason},messages});
      setAttempt(result.payment);setQuestions(result.context_questions||[]);const next=result.context_required?'context':result.payment.state==='SIMULATED_COMPLETED'?'outcome':'result';setPage(next);history.replaceState(null,'',`/payment/${encodeURIComponent(id)}/${next==='context'?'context':next==='outcome'?'result':'intervention'}`);
    }catch(e){setError(e.message);setPage('error')}finally{setBusy(false)}
  }
  async function submitContext(){
    const context={...userContext,payment_reason:form.payment_reason,user_message:null};
    const msgs=message.trim()?[{speaker:'other',text:message.trim()}]:[];
    await beginAnalysis(context,msgs);
  }
  async function action(call,next){setBusy(true);setError('');try{const result=await call();setAttempt(result);const pageName=next(result);setPage(pageName);if(attemptId)history.replaceState(null,'',`/payment/${encodeURIComponent(attemptId)}/${pageName==='outcome'?'result':pageName}`)}catch(e){setError(e.message)}finally{setBusy(false)}}
  async function cancelAttempt(){if(!attemptId){resetFlow();return}await action(()=>api.cancel(attemptId),()=> 'outcome')}
  async function continueAttempt(){await action(()=>api.continuePayment(attemptId,ack),()=> 'outcome')}
  async function verifyAttempt(){await action(()=>api.verify(attemptId,'verified_independently'),()=> 'result')}
  const routeToResult=()=>attempt?.state==='SIMULATED_HELD'?'result':attempt?.state==='VERIFICATION_REQUIRED'?'result':attempt?.state==='READY'?'ready':attempt?.state==='SIMULATED_COMPLETED'||attempt?.state==='CANCELLED'?'outcome':'result';

  function renderForm(){return <>
    <div className="payment-intro"><div className="brand-mark">S</div><div className="intro-copy"><div className="eyebrow">SHIELDPAY · POWERED BY APP SHIELD</div><h1>Send money with confidence.</h1><p>Review your payment, then get a safety check before anything is completed.</p></div><button className="button button-secondary flagship-button" onClick={()=>loadScenario('government_impersonation')} disabled={busy}>✦ Try flagship demo</button></div>
    {demoNote&&<div className="demo-note"><strong>Flagship scenario · why it’s difficult</strong><p>{demoNote}</p></div>}
    <section className="card payment-form"><div className="section-heading"><div><div className="eyebrow">NEW SIMULATED PAYMENT</div><h2>Who are you paying?</h2></div><span className="step-pill">Step 1 of 2</span></div>
      <div className="field-grid"><div className="field"><label htmlFor="sender">From</label><select id="sender" value={form.sender_alias} onChange={e=>setField('sender_alias',e.target.value)} disabled={!catalog}>{(catalog?.senders||[]).map(x=><option key={x.alias} value={x.alias}>{x.display_name} · {x.alias}</option>)}</select></div>
      <div className="field"><label htmlFor="recipient">To</label><select id="recipient" value={form.recipient_alias} onChange={e=>setField('recipient_alias',e.target.value)} disabled={!catalog}>{(catalog?.recipients||[]).map(x=><option key={x.alias} value={x.alias}>{x.display_name} · {x.alias}</option>)}</select></div>
      <div className="field"><label htmlFor="amount">Amount</label><div className="money-input"><span>₹</span><input id="amount" type="number" min="1" max="10000000" step="1" required value={form.amount} onChange={e=>setField('amount',e.target.value)} /></div></div>
      <div className="field"><label htmlFor="purpose">What is this payment for?</label><select id="purpose" value={form.payment_reason} onChange={e=>setField('payment_reason',e.target.value)}>{reasons.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></div>
      <div className="field field-full"><label htmlFor="payment-note">Note <span className="optional">Optional</span></label><input id="payment-note" type="text" maxLength="240" value={form.note} onChange={e=>setField('note',e.target.value)} placeholder="Add a note for this payment" /></div></div>
      <div className="payment-protection"><span aria-hidden="true">◇</span><div><strong>Safety check before payment</strong><small>APP Shield checks transaction, recipient, context and manipulation signals. Nothing is transferred from this demo.</small></div></div>
      <div className="form-actions"><span className="fine-print">Your payment remains simulated until you confirm.</span><button className="button button-primary" onClick={()=>setPage('review')} disabled={loadingCatalog||busy||!Number(form.amount)}>{loadingCatalog?'Loading demo accounts…':'Review payment'} <span aria-hidden="true">→</span></button></div>
    </section>
    <DemoScenarios scenarios={scenarios} selected={selectedScenario} onSelect={setSelectedScenario} onLoad={()=>loadScenario()} loading={busy}/>
  </>}

  function renderReview(){return <section className="card review-card"><div className="eyebrow">PAYMENT REVIEW</div><h1>Check the details</h1><div className="review-amount">{currency(form.amount)}</div><p className="review-destination">to <strong>{recipient?.display_name}</strong> <span>{form.recipient_alias}</span></p><dl className="review-list"><div><dt>From</dt><dd>{sender?.display_name}</dd></div><div><dt>Note</dt><dd>{form.note||'—'}</dd></div><div><dt>Payment method</dt><dd>ShieldPay Balance</dd></div><div><dt>Environment</dt><dd>Demo · no transfer</dd></div></dl><div className="form-actions"><button className="button button-quiet" onClick={()=>setPage('form')}>Go back</button><button className="button button-primary" onClick={()=>beginAnalysis()} disabled={busy}>Review &amp; send <span aria-hidden="true">→</span></button></div><p className="fine-print center">APP Shield checks the payment before simulated completion.</p></section>}

  function renderContext(){return <ContextCheck value={userContext} setValue={setUserContext} message={message} setMessage={setMessage} onSubmit={submitContext} onCancel={cancelAttempt} busy={busy} questions={questions}/>}

  function renderPaymentResult(){
    if(!attempt)return null;
    if(['WARNING','VERIFICATION_REQUIRED','SIMULATED_HELD'].includes(attempt.state))return <ScamWarning payment={attempt} checked={ack} onCheck={setAck} onCancel={cancelAttempt} onContinue={continueAttempt} onVerify={verifyAttempt} busy={busy}/>;
    if(attempt.state==='READY')return <section className="card ready-card"><div className="success-icon" aria-hidden="true">✓</div><div className="eyebrow">PAYMENT READY</div><h1>Ready for your confirmation</h1><div className="review-amount">{currency(attempt.amount)}</div><p className="review-destination">to <strong>{attempt.recipient.display_name}</strong> <span>{attempt.recipient.alias}</span></p><p className="muted">The safety check is complete. Confirm only if these details are correct.</p><div className="form-actions"><button className="button button-quiet" onClick={cancelAttempt} disabled={busy}>Cancel</button><button className="button button-primary" onClick={continueAttempt} disabled={busy}>{busy?'Confirming…':'Confirm simulated payment'}</button></div></section>;
    return <section className={`card outcome-card ${attempt.state==='SIMULATED_COMPLETED'?'outcome-success':''}`}><div className="eyebrow">SIMULATED PAYMENT RECEIPT</div><div className="receipt-brand">ShieldPay <small>POWERED BY APP SHIELD</small></div><div className="outcome-icon" aria-hidden="true">{attempt.state==='SIMULATED_COMPLETED'?'✓':'—'}</div><h1>{attempt.state==='SIMULATED_COMPLETED'?'Payment completed in simulation':attempt.state==='CANCELLED'?'Payment cancelled':'Payment paused in simulation'}</h1><p>{attempt.state==='SIMULATED_COMPLETED'?'The demo recorded this payment as simulated. No real money moved.':attempt.state==='CANCELLED'?'You chose to cancel. Good call checking first. No simulated money was sent.':attempt.state==='SIMULATED_HELD'?'This attempt remains held by the demo policy. No payment was made.':'This attempt remains paused for review. No payment was made.'}</p><div className="receipt-amount">{currency(attempt.amount)}</div><p>Sent to <strong>{attempt.recipient.display_name}</strong></p><dl className="receipt-list"><div><dt>Transaction ID</dt><dd className="receipt-id">{attempt.payment_attempt_id}</dd></div><div><dt>Date</dt><dd>{attempt.created_at?new Date(attempt.created_at).toLocaleString():'Unavailable'}</dd></div><div><dt>Status</dt><dd>{pretty(attempt.state)}</dd></div><div><dt>Note</dt><dd>{attempt.note||'—'}</dd></div><div><dt>APP Shield</dt><dd>Payment analyzed before completion</dd></div></dl><div className="form-actions"><a className="button button-quiet" href="/transactions">Transaction history</a><button className="button button-primary" onClick={resetDemo}>Start another payment</button>{attemptId&&<a className="button button-secondary" href="/analyst">Analyst view</a>}</div></section>
  }

  return <div className="app-shell shieldpay-shell">
    <TopNav active={libraryOnly?'demo':'send'} onReset={resetDemo}/>
    <main className="page-container">
      <div className="demo-banner"><span aria-hidden="true">ⓘ</span><span>Demo environment — no real money is transferred. Never enter passwords, PINs, OTPs, CVVs or card details.</span></div>
      {error&&<div className="error-banner" role="alert"><strong>Safety analysis unavailable</strong><span>{error} This payment has not been executed.</span><button onClick={()=>setError('')} aria-label="Dismiss error">×</button></div>}
      {page==='form'&&renderForm()}
      {page==='review'&&renderReview()}
      {page==='context'&&renderContext()}
      {page==='loading'&&<section className="card loading-card" role="status"><span className="loader"/><div><strong>Checking this payment before it continues</strong><p>APP Shield is reviewing available payment and context signals.</p></div></section>}
      {page==='result'&&renderPaymentResult()}
      {page==='ready'&&renderPaymentResult()}
      {page==='outcome'&&renderPaymentResult()}
      {page==='error'&&<section className="card empty-state"><h2>Safety analysis unavailable</h2><p>The payment was not executed. You can retry the safety check or cancel this attempt.</p><div className="form-actions"><button className="button button-quiet" onClick={cancelAttempt}>Cancel payment</button><button className="button button-primary" onClick={()=>attemptId?beginAnalysis(userContext,scenarioMessages):beginAnalysis()}>Retry analysis</button></div></section>}
    </main>
    <AppFooter/>
  </div>;
}
