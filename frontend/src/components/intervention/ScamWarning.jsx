import React from 'react';

export default function ScamWarning({ payment, checked, onCheck, onCancel, onContinue, onVerify, busy }) {
  const intervention = payment?.intervention || {};
  const decision = payment?.decision;
  const severe = decision === 'STEP_UP_VERIFICATION' || decision === 'BLOCK_AND_ESCALATE';
  const blocked = payment?.state === 'SIMULATED_HELD';
  return <section className={`intervention ${severe ? 'intervention-strong' : 'intervention-review'}`} aria-labelledby="warning-title">
    <div className="intervention-icon" aria-hidden="true">{blocked ? 'Ⅱ' : severe ? '!' : '✓'}</div>
    <div className="eyebrow">{blocked ? 'SIMULATED TEMPORARY HOLD' : severe ? 'STRONG WARNING' : 'PLEASE VERIFY'}</div>
    <h2 id="warning-title">{intervention.title || 'Verify this payment before continuing'}</h2>
    <p>{intervention.message || 'We detected unusual circumstances around this payment.'}</p>
    <div className="recommended"><strong>Recommended next step</strong><span>{intervention.recommended_action}</span></div>
    {payment.top_reasons?.length > 0 && <div className="reason-list"><strong>Why we’re asking</strong><ul>{payment.top_reasons.slice(0, 4).map((reason, i) => <li key={`${i}-${reason}`}>{reason}</li>)}</ul></div>}
    {payment.state === 'VERIFICATION_REQUIRED' && <div className="verification-note"><strong>Additional verification required</strong><span>Choose a demo action to verify independently. APP Shield will never ask for an OTP, PIN, password or card security code.</span>
      <button className="button button-primary" onClick={onVerify} disabled={busy}>I verified independently</button>
    </div>}
    <div className="warning-actions">
      <button className="button button-quiet" onClick={onCancel} disabled={busy}>Cancel payment</button>
      {!blocked && payment.state !== 'VERIFICATION_REQUIRED' && <label className="acknowledge"><input type="checkbox" checked={checked} onChange={(event) => onCheck(event.target.checked)} /> I understand and want to continue in this simulation</label>}
      {payment.state !== 'VERIFICATION_REQUIRED' && !blocked && <button className="button button-danger" onClick={onContinue} disabled={busy || !checked}>Continue anyway</button>}
    </div>
    {blocked && <p className="hold-note">This demo hold cannot continue. You can close this simulated attempt.</p>}
  </section>;
}
