export function buildCaseReport({payment,attempt,network}) {
  const assessment=attempt?.assessment;
  if (!payment || !assessment) throw new Error('Analyze a payment before exporting its report.');
  return {
    report_type:'APP_SHIELD_SYNTHETIC_PAYMENT_ANALYSIS',
    source:'Current APP Shield local synthetic demo assessment',
    generated_at:new Date().toISOString(),
    payment:{
      payment_attempt_id:payment.payment_attempt_id,
      created_at:payment.created_at,
      sender:payment.sender,
      recipient:payment.recipient,
      amount:payment.amount,
      currency:payment.currency,
      purpose:payment.payment_reason,
      simulated_status:payment.simulated_status,
    },
    assessment:{
      risk_index:assessment.app_scam_risk,
      risk_level:assessment.risk_level,
      decision:assessment.decision,
      confidence:assessment.confidence,
      score_semantics:'Evidence index; not a calibrated probability. Confidence describes evidence certainty, not fraud probability.',
      model_versions:assessment.model_versions,
    },
    evidence:{
      reasons:assessment.top_reasons||[],
      protective:assessment.protective_evidence||[],
      unavailable:assessment.missing_evidence||[],
      context:attempt.context,
      conversation:attempt.conversation_evidence,
    },
    recipient_network:network||{available:false,reason:'Network response was not available for this case.'},
    limitations:[
      'This report contains synthetic demonstration data and is not a real payment decision.',
      'A user cancellation or simulated action is not a confirmed fraud label.',
      'Unavailable evidence is not evidence of safety.',
    ],
  };
}

export function downloadCaseReport(report) {
  const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');
  link.href=url;
  link.download=`app-shield-${report.payment.payment_attempt_id}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
