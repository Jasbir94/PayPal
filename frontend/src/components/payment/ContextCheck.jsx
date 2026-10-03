import React from 'react';

const channels=[['phone','Phone'],['whatsapp','WhatsApp'],['sms','SMS'],['telegram','Telegram'],['email','Email'],['social_media','Social media'],['other','Other']];

export default function ContextCheck({ value, setValue, message, setMessage, onSubmit, onCancel, busy, questions=[] }) {
  const asked=value.contacted_by_unknown_person===true;
  const update=(key,next)=>setValue((current)=>({...current,[key]:next}));
  return <section className="card context-card">
    <div className="eyebrow">A QUICK CONTEXT CHECK</div><h2>A couple of details can help us assess this payment</h2>
    <p className="muted">We only ask follow-up questions when the payment context suggests they may help.</p>
    {questions.map((question)=><div className="question" key={question.id}>
      <label>{question.label}</label>
      <div className="segmented"><button type="button" aria-pressed={value[question.id]===true} onClick={()=>update(question.id,true)}>Yes</button><button type="button" aria-pressed={value[question.id]===false} onClick={()=>update(question.id,false)}>No</button></div>
    </div>)}
    {asked&&<div className="context-followups">
      <div className="field"><label htmlFor="channel">How did they contact you?</label><select id="channel" value={value.contact_channel||''} onChange={(e)=>update('contact_channel',e.target.value||null)}><option value="">Choose if known</option>{channels.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></div>
      <div className="question"><label>Did they claim to represent an organization or authority?</label><div className="segmented"><button type="button" aria-pressed={value.claimed_authority===true} onClick={()=>update('claimed_authority',true)}>Yes</button><button type="button" aria-pressed={value.claimed_authority===false} onClick={()=>update('claimed_authority',false)}>No</button></div></div>
      {value.claimed_authority===true&&<div className="field"><label htmlFor="authority">Who did they claim to represent?</label><select id="authority" value={value.authority_type||'other'} onChange={(e)=>update('authority_type',e.target.value)}><option value="government">Government agency</option><option value="police">Police</option><option value="bank">Bank</option><option value="rbi">RBI</option><option value="tax_department">Tax department</option><option value="court">Court</option><option value="company_support">Company support</option><option value="employer">Employer</option><option value="other">Other</option></select></div>}
      <div className="question"><label>Did they ask you to act urgently or threaten a consequence?</label><div className="segmented"><button type="button" aria-pressed={value.urgent_payment_requested===true} onClick={()=>{update('urgent_payment_requested',true);update('threatened_consequences',true)}}>Yes</button><button type="button" aria-pressed={value.urgent_payment_requested===false} onClick={()=>{update('urgent_payment_requested',false);update('threatened_consequences',false)}}>No</button></div></div>
      <div className="question"><label>Did they ask you to keep the payment secret?</label><div className="segmented"><button type="button" aria-pressed={value.requested_secrecy===true} onClick={()=>update('requested_secrecy',true)}>Yes</button><button type="button" aria-pressed={value.requested_secrecy===false} onClick={()=>update('requested_secrecy',false)}>No</button></div></div>
      <div className="field"><label htmlFor="message">Payment-related message <span className="optional">Optional</span></label><textarea id="message" rows="5" maxLength="4000" value={message} onChange={(e)=>setMessage(e.target.value)} placeholder="Paste the message that influenced this payment, if useful." /><small>Do not enter passwords, PINs, OTPs, CVVs, or card credentials.</small></div>
    </div>}
    <div className="form-actions"><button className="button button-quiet" onClick={onCancel} disabled={busy}>Cancel payment</button><button className="button button-primary" onClick={onSubmit} disabled={busy}>{busy?'Checking…':'Continue safety check'}</button></div>
  </section>;
}
