import React, { useEffect, useState } from 'react';
import TopNav from '../components/common/TopNav.jsx';
import AppFooter from '../components/common/AppFooter.jsx';
import { api } from '../services/api.js';
import { currency, pretty } from '../utils/riskUtils.js';

const statusText=(row)=>row.state==='SIMULATED_COMPLETED'?'Completed':row.state==='CANCELLED'?'Cancelled':row.state==='SIMULATED_HELD'?'Held':row.state==='WARNING'||row.state==='VERIFICATION_REQUIRED'?'Under review':row.state==='READY'?'Ready':'In progress';
const status=(probe,predicate=()=>true)=>probe?.ok&&predicate(probe.value)?'ready':'unavailable';

export default function Dashboard(){
  const [activity,setActivity]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[diagnostics,setDiagnostics]=useState(null),[checking,setChecking]=useState(false);
  useEffect(()=>{let alive=true;api.transactions().then(data=>{if(alive)setActivity(data.slice(0,5))}).catch(e=>{if(alive)setError(e.message)}).finally(()=>{if(alive)setLoading(false)});refreshHealth(()=>alive);return()=>{alive=false}},[]);
  async function refreshHealth(isAlive=()=>true){setChecking(true);try{const value=await api.systemDiagnostics();if(isAlive())setDiagnostics(value)}finally{if(isAlive())setChecking(false)}}
  const coreReady=status(diagnostics?.health,value=>value.status==='healthy')==='ready'&&status(diagnostics?.ready,value=>value.status==='ready')==='ready';
  const components=diagnostics?.models?.value?.components||{};
  const scenarios=diagnostics?.scenarioCatalog?.value?.scenarios||[];
  return <div className="app-shell shieldpay-shell">
    <TopNav active="home"/>
    <main className="customer-container control-center">
      <div className="demo-banner"><span aria-hidden="true">ⓘ</span><span>APP Shield demo uses synthetic payment data. It does not connect to a bank or transfer real money.</span></div>
      <section className="welcome-row control-welcome"><div><div className="eyebrow">APP SHIELD · SIMPLE MODE</div><h1>Analyze a payment before money moves.</h1><p>Enter a few details, run the safety check, and see the reasons behind the result.</p></div></section>
      <section className="control-center-hero"><div><div className="eyebrow">ONE PAYMENT · ONE CLEAR RESULT</div><h2>Start with a payment</h2><p>APP Shield checks transaction patterns, recipient history, network behavior, payment context and pressure signals through one backend analysis.</p><div className="control-hero-actions"><a className="button button-primary" href="/send">Analyze payment <span aria-hidden="true">→</span></a><a className="button button-secondary" href="/demo">Test a prepared scenario</a></div><small>Demo only · Never enter a password, PIN, OTP, CVV or card details.</small></div><div className="analysis-steps" aria-label="Analysis process"><span><b>1</b>Payment details</span><span><b>2</b>Context check</span><span><b>3</b>Clear recommendation</span></div></section>
      <section className="quick-section control-explore"><div className="section-heading"><div><div className="eyebrow">EXPLORE APP SHIELD</div><h2>Choose what you want to do</h2></div></div><div className="quick-actions control-actions">
        <a href="/demo" className="quick-action"><span className="quick-icon quick-request" aria-hidden="true">◈</span><strong>Test a scam</strong><small>Run prepared scam and legitimate payment cases.</small></a>
        <a href="/analyst" className="quick-action"><span className="quick-icon quick-history" aria-hidden="true">⌕</span><strong>Investigate payment &amp; network</strong><small>Review risk, confidence, reasons, protective evidence and recipient connections.</small></a>
        <a href="/investigate" className="quick-action"><span className="quick-icon quick-people" aria-hidden="true">◎</span><strong>Look up a recipient</strong><small>Open a recipient network directly, without running a payment.</small></a>
        <a href="/research/comparison" className="quick-action"><span className="quick-icon quick-people" aria-hidden="true">⇄</span><strong>Compare analysis</strong><small>See how transaction-only and contextual analysis differ.</small></a>
        <a href="/research/failures" className="quick-action"><span className="quick-icon quick-send" aria-hidden="true">▤</span><strong>Review evaluation failures</strong><small>Inspect measured errors from the frozen synthetic benchmark.</small></a>
      </div></section>
      <div className="dashboard-columns control-dashboard-columns">
        <section className="card activity-card"><div className="section-heading"><div><div className="eyebrow">LOCAL DEMO HISTORY</div><h2>Recent analyses</h2></div><a className="text-link" href="/transactions">See all</a></div>
          {error&&<div className="inline-error" role="status">Recent analyses are unavailable. {error}</div>}
          {loading?<div className="activity-empty" role="status">Loading recent analyses…</div>:!activity.length?<div className="activity-empty"><span className="empty-illustration" aria-hidden="true">◷</span><strong>No analyses yet</strong><span>Your simulated payments will appear here.</span><a href="/demo" className="text-link">Run your first scenario</a></div>:<ul className="activity-list">{activity.map(row=><li key={row.payment_attempt_id}><a href={`/payment/${row.payment_attempt_id}/result`} className="activity-row"><span className="activity-recipient-icon" aria-hidden="true">{row.recipient?.[0]||'S'}</span><span className="activity-main"><strong>{row.recipient}</strong><small>{row.created_at?new Date(row.created_at).toLocaleString():pretty(row.scenario)}</small></span><span className="activity-amount"><strong>{currency(row.amount)}</strong><small className={`activity-status activity-${String(row.state).toLowerCase()}`}>{statusText(row)}</small></span></a></li>)}</ul>}
        </section>
        <section className="card health-card" aria-labelledby="system-health-title"><div className="section-heading"><div><div className="eyebrow">SYSTEM HEALTH</div><h2 id="system-health-title">Demo readiness</h2></div><button className="button button-quiet health-refresh" onClick={()=>refreshHealth()} disabled={checking}>{checking?'Checking…':'Check again'}</button></div>
          {!diagnostics?<p className="health-summary" role="status">{checking?'Checking the backend and available models…':'System status is unavailable.'}</p>:<>
            <p className={`health-summary ${coreReady?'health-summary-ready':'health-summary-unavailable'}`}>{coreReady?'Core payment analysis is ready.':'Core analysis is unavailable; payment checks may fail.'}</p>
            <HealthRow label="Backend API" value={status(diagnostics.health,value=>value.status==='healthy')} detail={diagnostics.health?.ok?'Service responds normally':diagnostics.health?.error}/>
            <HealthRow label="Payment analysis" value={status(diagnostics.ready,value=>value.status==='ready')} detail={diagnostics.ready?.ok?'Transaction and recipient analysis available':diagnostics.ready?.error}/>
            <HealthRow label="Recipient network" value={components.graph?.available?'ready':'fallback'} detail={components.graph?.available?'Graph evidence available':'Graph evidence unavailable; continue with other signals'}/>
            <HealthRow label="Demo scenarios" value={diagnostics.scenarioCatalog?.ok?'ready':'unavailable'} detail={diagnostics.scenarioCatalog?.ok?`${scenarios.length} prepared cases available`:diagnostics.scenarioCatalog?.error}/>
            <HealthRow label="Payment conversation" value={status(diagnostics.chat,value=>value.available)} detail={diagnostics.chat?.value?.language_model||diagnostics.chat?.error}/>
            {(components.scenario_text?.available===false||components.psychology_text?.available===false)&&<p className="health-footnote">A text model is unavailable. The app reports its rules fallback; missing evidence is not treated as proof of safety.</p>}
          </>}
        </section>
      </div>
      <section className="research-callout"><div><div className="eyebrow">ANALYST AND RESEARCH MODES</div><h2>Need more detail?</h2><p>Open a case investigation or review model comparisons and measured failures.</p></div><div className="control-hero-actions"><a className="button button-secondary" href="/analyst">Open analyst mode</a><a className="button button-secondary" href="/research/comparison">Open research mode</a></div></section>
    </main><AppFooter/>
  </div>;
}

function HealthRow({label,value,detail}){const text=value==='ready'?'Ready':value==='fallback'?'Fallback':'Unavailable';return <div className="health-row"><span className={`health-dot health-dot-${value}`} aria-hidden="true"/><div><strong>{label}</strong><small>{detail||text}</small></div><span className={`health-state health-state-${value}`}>{text}</span></div>}
