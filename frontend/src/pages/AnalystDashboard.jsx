import React, { useCallback, useEffect, useState } from 'react';
import RiskOverview from '../components/analyst/RiskOverview.jsx';
import RiskBreakdown from '../components/analyst/RiskBreakdown.jsx';
import PsychologyPanel from '../components/analyst/PsychologyPanel.jsx';
import EvidencePanel from '../components/analyst/EvidencePanel.jsx';
import RecipientNetwork from '../components/analyst/RecipientNetwork.jsx';
import { api } from '../services/api.js';
import { currency, percent, pretty, score, transactionOnlyLabel } from '../utils/riskUtils.js';

export default function AnalystDashboard(){
  const [analytics,setAnalytics]=useState(null),[selected,setSelected]=useState(null),[network,setNetwork]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
  const loadAttempt=useCallback(async(id)=>{if(!id)return;setSelected(null);setNetwork(null);try{const [detail,graph]=await Promise.all([api.analyst(id),api.network(id)]);setSelected({...detail.attempt,payment:detail.payment});setNetwork(graph);setError('')}catch(e){setError(e.message)}},[]);
  const refresh=useCallback(async()=>{setLoading(true);try{const data=await api.analytics();setAnalytics(data);if(!selected){const recent=data.recent_attempts||[];const id=localStorage.getItem('app-shield-last-attempt');const found=recent.find(x=>x.payment_attempt_id===id)||recent[0];if(found)await loadAttempt(found.payment_attempt_id)}}catch(e){setError(e.message)}finally{setLoading(false)}},[loadAttempt,selected]);
  useEffect(()=>{refresh()},[]);
  const assessment=selected?.assessment,contextual=selected?.contextual_result,passive=selected?.passive;
  return <div className="app-shell analyst-shell"><header className="topbar"><a className="wordmark" href="/"><span className="brand-mini">A</span><span>APP Shield <small>ANALYST</small></span></a><div className="topbar-right"><span className="simulation-badge"><i/> SIMULATED DATA</span><a href="/" className="nav-link">← Payment simulator</a><button className="reset-button" onClick={refresh} disabled={loading}>Refresh</button></div></header>
    <main className="analyst-container"><div className="privacy-strip"><span aria-hidden="true">◇</span> Analyst / demo view · Synthetic account and payment data only · Not a production fraud operations console.</div>
      {error&&<div className="error-banner" role="alert"><strong>Analyst data unavailable</strong><span>{error}</span></div>}
      <div className="analyst-heading"><div><div className="eyebrow">PRE-PAYMENT INTELLIGENCE</div><h1>Analyst dashboard</h1><p>Inspect the signals that shaped the pre-payment decision.</p></div><a className="button button-secondary" href="/demo">Open demo library</a></div>
      <section className="metric-grid analytics-grid" aria-label="Simulated intervention analytics">
        <Metric label="Payments analyzed" value={analytics?.payments_analyzed??'—'} />
        <Metric label="Warnings shown" value={analytics?.warnings_shown??'—'} />
        <Metric label="Cancelled after warning" value={analytics?.cancelled_after_warning??'—'} />
        <Metric label="Continued after warning" value={(analytics?.continued_after_warning||0)+(analytics?.verified_and_continued||0)} />
      </section>
      <div className="analyst-columns">
        <aside className="card attempts-card"><div className="section-heading"><div><div className="eyebrow">SIMULATED DATA</div><h3>Recent attempts</h3></div><span className="count-pill">{analytics?.recent_attempts?.length||0}</span></div>
          {loading&&!analytics?<p className="muted">Loading attempts…</p>:!analytics?.recent_attempts?.length?<p className="muted">No attempts yet. Run a payment demo to populate this list.</p>:<div className="attempt-list">{analytics.recent_attempts.map(row=><button key={row.payment_attempt_id} className={`attempt-row ${selected?.payment_attempt_id===row.payment_attempt_id?'attempt-selected':''}`} onClick={()=>loadAttempt(row.payment_attempt_id)}>
            <span className="attempt-row-top"><strong>{currency(row.amount)}</strong><span className={`status-chip status-${String(row.risk_level).toLowerCase()}`}>{pretty(row.risk_level)}</span></span><span className="attempt-row-bottom">{row.recipient} · {pretty(row.scenario)}</span><small>{row.payment_attempt_id.slice(0,13)}…</small>
          </button>)}</div>}
          <div className="distribution"><h4>Risk distribution</h4>{['LOW','MEDIUM','HIGH','CRITICAL'].map(level=><div className="distribution-row" key={level}><span>{pretty(level)}</span><strong>{analytics?.risk_distribution?.[level]||0}</strong></div>)}</div>
        </aside>
        <div className="analyst-main">
          {selected?<><RiskOverview assessment={assessment}/>
            <div className="card comparison-card"><div className="eyebrow">WHY CONTEXT MATTERS</div><h3>Transaction signals and full APP Shield</h3><div className="comparison-grid"><div><small>Transaction-only risk</small><strong>{score(passive?.transaction_details?.score)}</strong><span>Transaction model and rules</span></div><div><small>Passive payment + recipient + graph</small><strong>{transactionOnlyLabel(passive)}</strong><span>Before contextual follow-up</span></div><div><small>Full APP Shield score</small><strong>{score(assessment?.app_scam_risk)}</strong><span>Context, scenario, psychology and fusion</span></div></div><p className="fine-print">Scores are evidence indices. Confidence and risk are separate; neither is shown in the normal payment flow.</p></div>
            <RiskBreakdown assessment={assessment}/>
            <div className="analyst-two-col"><PsychologyPanel assessment={assessment}/><section className="card scenario-card-panel"><div className="eyebrow">NARRATIVE CLASSIFICATION</div><h3>Scenario assessment</h3><div className="scenario-name">{pretty(contextual?.scenario?.type||assessment?.likely_scam_scenario)}</div><div className="compare-values"><span>Scenario classifier confidence</span><strong>{contextual?.scenario?.confidence!=null?percent(contextual.scenario.confidence):'Unavailable'}</strong></div><p className="fine-print">Classifier confidence describes the scenario label. It is not the payment fraud risk or a calibrated probability.</p>{contextual?.scenario?.top_scenarios?.map(item=><div className="alternative" key={item.scenario}><span>{pretty(item.scenario)}</span><strong>{percent(item.score)}</strong></div>)}</section></div>
            <EvidencePanel assessment={assessment} passive={passive} context={selected.context}/>
            <div className="analyst-two-col"><RecipientNetwork data={network}/><section className="card subsystem-card"><div className="eyebrow">EVIDENCE AVAILABILITY</div><h3>Subsystem status</h3><Availability label="Transaction intelligence" data={contextual?.transaction_risk}/><Availability label="Recipient intelligence" data={contextual?.recipient_risk}/><Availability label="Graph intelligence" data={contextual?.graph_risk}/><Availability label="Context intelligence" data={contextual?.context_risk}/><Availability label="Scenario intelligence" data={contextual?.scenario_risk}/><Availability label="Psychology intelligence" data={contextual?.psychology}/><details className="analyst-details"><summary>Model versions</summary><pre>{JSON.stringify(assessment?.model_versions||{},null,2)}</pre></details></section></div>
          </>:<section className="card empty-state">{loading?'Loading the latest simulated attempt…':'Select an analyzed attempt or run the payment simulator.'}</section>}
        </div>
      </div>
    </main><footer className="app-footer"><span>All statistics describe demo interactions only.</span><a href="/">Return to payment simulator</a></footer>
  </div>;
}

function Metric({label,value}){return <article className="metric-card"><small>{label}</small><strong>{value}</strong><span>SIMULATED DATA</span></article>}
function Availability({label,data}){const available=data!=null&&(data.available===undefined||data.available===true);return <div className="availability-row"><span className={`availability-dot ${available?'is-available':''}`} aria-hidden="true"/><div><strong>{label}</strong><small>{available?'Evidence available':'Unavailable — missing evidence is not a low-risk signal'}</small></div></div>}
