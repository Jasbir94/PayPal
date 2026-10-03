import React from 'react';
import { score } from '../../utils/riskUtils.js';

const rows=[['User side',a=>a.user_side_risk],['Recipient side',a=>a.recipient_network_risk],['Manipulation side',a=>a.manipulation_risk]];
export default function RiskBreakdown({ assessment }) {
  if (!assessment) return null;
  return <section className="card"><div className="section-heading"><div><div className="eyebrow">FUSION GROUPS</div><h3>Risk breakdown</h3></div></div>
    <div className="bars">{rows.map(([label,get])=>{const part=get(assessment);return <div className="bar-row" key={label}><div><span>{label}</span><strong>{score(part.score)}</strong></div><progress max="100" value={part.score||0} aria-label={`${label} score`} /><small>{part.available?'Evidence available':'Evidence unavailable'}</small></div>})}</div>
    <div className="subsystem-grid">{Object.entries(assessment.component_scores||{}).map(([name,value])=><div className="subsystem" key={name}><span>{name.replaceAll('_',' ')}</span><strong>{score(value)}</strong></div>)}</div>
  </section>;
}
