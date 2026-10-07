import React from 'react';

const requesters=[['government','Government or authority'],['bank','Bank or payment company'],['employer','Employer or recruiter'],['investment_advisor','Investment advisor'],['seller','Seller'],['friend_family','Friend or family'],['other','Someone else']];

export default function ContextCheck({ value, setValue, message, setMessage, onSubmit, onCancel, busy, questions=[] }) {
  const asked=value.contacted_by_unknown_person===true;
  const update=(key,next)=>setValue((current)=>({...current,[key]:next}));
  const answer=(key,next)=>{update(key,next);if(key==='contacted_by_unknown_person'&&next!==true){update('who_requested_payment',null);update('claimed_authority',null);update('authority_type',null)}};
  return <section className="card context-card">
    <div className="eyebrow">ONE QUICK CHECK BEFORE YOU PAY</div><h2>A couple of details can help us assess this payment</h2>
    <p className="muted">Your answers stay within this simulated safety check. “Not sure” is a useful answer too.</p>
    {questions.map((question)=><div className="question" key={question.id}>
      <label>{question.label}</label>
      <div className="segmented"><button type="button" aria-pressed={value[question.id]===true} onClick={()=>answer(question.id,true)}>Yes</button><button type="button" aria-pressed={value[question.id]===false} onClick={()=>answer(question.id,false)}>No</button><button type="button" aria-pressed={value[question.id]==null} onClick={()=>answer(question.id,null)}>Not sure</button></div>
    </div>)}
    {asked&&<div className="context-followups">
      <div className="field"><label htmlFor="requester">Who asked you to pay?</label><select id="requester" value={value.who_requested_payment||''} onChange={(e)=>{const category=e.target.value;update('who_requested_payment',category||null);update('claimed_authority',category?['government','bank'].includes(category):null);if(category==='government')update('authority_type','government');else if(category==='bank')update('authority_type','bank');else update('authority_type',category?'other':null)}}><option value="">Choose if known</option>{requesters.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></div>
      <div className="field"><label htmlFor="message">Payment-related message <span className="optional">Optional</span></label><textarea id="message" rows="5" maxLength="4000" value={message} onChange={(e)=>setMessage(e.target.value)} placeholder="Paste the message that influenced this payment, if useful." /><small>Do not enter passwords, PINs, OTPs, CVVs, or card credentials.</small></div>
    </div>}
    <div className="form-actions"><button className="button button-quiet" onClick={onCancel} disabled={busy}>Cancel payment</button><button className="button button-primary" onClick={onSubmit} disabled={busy}>{busy?'Checking…':'Continue safety check'}</button></div>
  </section>;
}
