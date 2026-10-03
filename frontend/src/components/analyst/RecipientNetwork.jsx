import React from 'react';

export default function RecipientNetwork({ data }) {
  if (!data) return <section className="card"><div className="eyebrow">RECIPIENT INTELLIGENCE · ANALYST</div><h3>Recipient network</h3><p className="muted">Select an analyzed attempt to load a two-hop network view.</p></section>;
  if (!data.available) return <section className="card"><div className="eyebrow">RECIPIENT INTELLIGENCE · ANALYST</div><h3>Recipient network</h3><p className="muted">{data.reason||'Graph evidence unavailable.'}</p></section>;
  const width=660,height=310,cx=width/2,cy=height/2,outer=Math.min(112,110+(data.nodes.length>8?10:0));
  const positions=new Map(data.nodes.map((node,index)=>[node.id,index===0?{x:cx,y:cy}:{x:cx+outer*Math.cos((index-1)*Math.PI*2/Math.max(1,data.nodes.length-1)),y:cy+outer*Math.sin((index-1)*Math.PI*2/Math.max(1,data.nodes.length-1))}]));
  return <section className="card network-card"><div className="eyebrow">RECIPIENT INTELLIGENCE · ANALYST / DEMO VIEW</div><h3>Observed recipient network</h3><p className="muted">A capped two-hop view of historical synthetic transfers. Edges reflect observed payment history.</p>
    <svg className="network-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Network showing ${data.nodes.length} accounts and ${data.edges.length} observed transfers`}>
      {data.edges.map((edge,i)=>{const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)return null;return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="network-edge"/>})}
      {data.nodes.map((node,index)=>{const pos=positions.get(node.id);return <g key={node.id}><circle cx={pos.x} cy={pos.y} r={index===0?26:18} className={index===0?'network-center':'network-node'}/><text x={pos.x} y={pos.y+4} textAnchor="middle" className="network-node-text">{index===0?'R':index}</text><text x={pos.x} y={pos.y+(index===0?44:34)} textAnchor="middle" className="network-label">{node.label}</text></g>})}
    </svg><div className="network-legend"><span><i className="legend-current"/>Recipient in this attempt</span><span><i className="legend-history"/>Historical synthetic account</span><span>{data.edges.length} observed transfers</span></div>
  </section>;
}
