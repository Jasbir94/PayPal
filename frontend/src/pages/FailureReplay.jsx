import React, { useEffect, useState } from 'react';
import TopNav from '../components/common/TopNav.jsx';
import AppFooter from '../components/common/AppFooter.jsx';
import { api } from '../services/api.js';
import { pretty } from '../utils/riskUtils.js';

export default function FailureReplay(){
  const [data,setData]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[filter,setFilter]=useState('all');
  useEffect(()=>{let alive=true;api.failures().then(value=>{if(alive)setData(value)}).catch(e=>{if(alive)setError(e.message)}).finally(()=>{if(alive)setLoading(false)});return()=>{alive=false}},[]);
  const rows=(data?.cases||[]).filter(row=>filter==='all'||row.failure_bucket===filter);
  return <div className="app-shell shieldpay-shell"><TopNav analyst research/><main className="customer-container research-container">
    <div className="demo-banner"><span aria-hidden="true">ⓘ</span><span>{data?.label||'Research workspace · synthetic evaluation data.'}</span></div>
    <div className="research-nav" aria-label="Research navigation"><a className="research-tab" href="/research/comparison">Comparison</a><a className="research-tab active" href="/research/failures">Failure replay</a><a className="research-tab" href="/research/adversarial">Adversarial lab</a></div>
    <div className="page-title-row"><div><div className="eyebrow">RESEARCH · EVALUATION ERRORS</div><h1>Failure replay</h1><p>Inspect measured message-classification errors from the frozen synthetic adversarial evaluation.</p></div></div>
    {error&&<div className="error-banner" role="alert"><strong>Evaluation report unavailable</strong><span>{error}</span></div>}
    {loading?<section className="card loading-card" role="status"><span className="loader"/><div><strong>Loading evaluation failures…</strong></div></section>:data&&<><div className="metric-grid failure-metrics"><Metric label="False positives" value={data.false_positives}/><Metric label="False negatives" value={data.false_negatives}/><Metric label="Error cases loaded" value={data.count}/></div><section className="card failure-card"><div className="section-heading"><div><div className="eyebrow">SOURCE: {data.source}</div><h2>Misclassified cases</h2></div><div className="field filter-field"><label htmlFor="failure-filter">Filter</label><select id="failure-filter" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All errors</option><option value="false_positive">False positives</option><option value="false_negative">False negatives</option></select></div></div><p className="research-note">{data.note}</p>{!rows.length?<div className="table-state">No cases match this filter.</div>:<div className="transaction-table-wrap"><table className="transaction-table"><thead><tr><th>Case</th><th>Variant</th><th>Expected</th><th>Prediction</th><th>Failure type</th><th>Risk / confidence</th></tr></thead><tbody>{rows.map((row,i)=><tr key={`${row.case_id}-${i}`}><td><strong>{row.case_id}</strong></td><td>{pretty(row.case_category)}</td><td>{pretty(row.expected_label)}</td><td>{pretty(row.prediction)}</td><td><span className={`table-status ${row.failure_bucket==='false_negative'?'status-warning':'status-cancelled'}`}>{pretty(row.failure_bucket)}</span></td><td>Unavailable in source</td></tr>)}</tbody></table></div>}</section></>}
  </main><AppFooter/></div>;
}
function Metric({label,value}){return <article className="metric-card"><small>{label}</small><strong>{value??'—'}</strong><span>SYNTHETIC EVALUATION</span></article>}

