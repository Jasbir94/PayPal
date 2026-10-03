import React from 'react';

export default function EvidencePanel({ assessment, passive, context }) {
  if (!assessment) return null;
  const reasons=assessment.top_reasons||[];
  return <section className="card"><div className="eyebrow">WHY THE ENGINE RESPONDED</div><h3>Evidence and safeguards</h3>
    <div className="evidence-columns"><div><h4>Supporting evidence</h4>{reasons.length?<ul className="evidence-list">{reasons.slice(0,6).map((item,i)=><li key={`${item.code||item.id}-${i}`}><span className="evidence-mark">+</span><span>{item.description||item.message||item.label||item.code}</span></li>)}</ul>:<p className="muted">No elevated reason codes.</p>}</div>
    <div><h4>Risk-reducing evidence</h4>{assessment.protective_evidence?.length?<ul className="evidence-list">{assessment.protective_evidence.map((item,i)=><li key={`${item}-${i}`}><span className="evidence-mark protect">−</span><span>{String(item).replaceAll('_',' ')}</span></li>)}</ul>:<p className="muted">No affirmative protective evidence was available.</p>}</div></div>
    <div className="missing-evidence"><strong>Missing or unavailable</strong><p>{assessment.missing_evidence?.length?assessment.missing_evidence.map(x=>x.replaceAll('_',' ')).join(' · '):'No required inputs were marked missing.'}</p></div>
    {context&&<details className="analyst-details"><summary>Structured context used</summary><pre>{JSON.stringify(context,null,2)}</pre></details>}
    {passive&&<details className="analyst-details"><summary>Passive transaction + recipient assessment</summary><div className="compare-values"><span>Transaction-only / recipient</span><strong>{passive.risk_level} · {Number(passive.preliminary_risk).toFixed(1)}/100</strong></div></details>}
  </section>;
}
