import React from 'react';
import { percent, pretty } from '../../utils/riskUtils.js';

export default function PsychologyPanel({ assessment }) {
  if (!assessment) return null;
  const detected=new Set(assessment.detected_psychological_techniques||[]);
  return <section className="card"><div className="eyebrow">MANIPULATION INTELLIGENCE</div><h3>Psychology signals</h3>
    {detected.size===0?<p className="muted">No manipulation techniques detected in the supplied conversation.</p>:<div className="technique-list">{[...detected].map((name)=><span className="technique-pill" key={name}>{pretty(name)}</span>)}</div>}
    <div className="bars">{Object.entries(assessment.component_scores||{}).filter(([key])=>key==='psychology').map(([key,value])=><div className="bar-row" key={key}><div><span>Psychology evidence score</span><strong>{value==null?'Unavailable':`${Number(value).toFixed(1)} / 100`}</strong></div><progress max="100" value={value||0}/></div>)}</div>
    <p className="fine-print">Manipulation risk is an evidence index, not a probability. {assessment.scenario_psychology_alignment!=null&&`Scenario/psychology alignment: ${percent(assessment.scenario_psychology_alignment,0)}.`}</p>
  </section>;
}
