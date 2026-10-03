import React from 'react';

export default function DemoScenarios({ scenarios, selected, onSelect, onLoad, loading }) {
  return <section className="scenario-section" aria-labelledby="scenario-title">
    <div className="section-heading"><div><div className="eyebrow">TRY THE SIMULATOR</div><h2 id="scenario-title">Demo scenarios</h2></div><span className="count-pill">{scenarios.length} ready</span></div>
    <div className="scenario-grid">{scenarios.map((scenario)=><button key={scenario.id} className={`scenario-card ${selected===scenario.id?'scenario-selected':''}`} onClick={()=>onSelect(scenario.id)}>
      <span className="scenario-dot" aria-hidden="true">{scenario.difficulty==='easy'?'○':scenario.difficulty==='flagship'?'✦':'◇'}</span><strong>{scenario.title}</strong><small>{scenario.description}</small>
    </button>)}</div>
    <button className="button button-secondary scenario-load" disabled={!selected||loading} onClick={onLoad}>{loading?'Loading demo…':'Load selected scenario'}</button>
  </section>;
}
