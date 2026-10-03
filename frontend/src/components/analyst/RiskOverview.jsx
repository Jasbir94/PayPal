import React from 'react';
import { pretty, score, percent } from '../../utils/riskUtils.js';

export default function RiskOverview({ assessment }) {
  if (!assessment) return <section className="card empty-state">Run a payment analysis to see the analyst view.</section>;
  const a=assessment;
  return <section className="analyst-overview">
    <div className="risk-hero"><div><div className="eyebrow">FULL APP SHIELD ASSESSMENT · ANALYST / DEMO VIEW</div><h2>{score(a.app_scam_risk)}</h2><p>Evidence-based APP scam risk · {a.risk_level}</p></div><div className="confidence-ring"><strong>{percent(a.confidence*1,0)}</strong><span>Confidence</span></div></div>
    <div className="metric-grid compact"><article className="metric-card"><small>Final decision</small><strong>{pretty(a.decision)}</strong></article><article className="metric-card"><small>Likely scenario</small><strong>{pretty(a.likely_scam_scenario)}</strong><span>Scenario classification, not fraud probability</span></article><article className="metric-card"><small>End-to-end latency</small><strong>{Number(a.latency_ms).toFixed(1)} ms</strong></article></div>
  </section>;
}
