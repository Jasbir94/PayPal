"""Calm, evidence-matched message templates; no thresholds or rule details."""
GENERIC={
 'title':'Verify this payment before continuing',
 'message':'We detected unusual circumstances around this payment. Please verify the recipient independently before continuing.',
 'recommended_action':'Contact the person or organization using a trusted contact method you found yourself.',
}
TEMPLATES={
 'government_impersonation':{
  'title':'Verify this official request independently',
  'message':'Someone claiming to represent a government or law-enforcement office appears to be requesting this payment. Government agencies should not ask you to move money to a “safe account” to avoid an investigation.',
  'recommended_action':'Pause and contact the agency using contact details from its official website or a document you already trust.'},
 'bank_impersonation':{
  'title':'Check this bank request through a trusted channel',
  'message':'This request has indicators associated with bank impersonation. Your bank should not ask you to transfer funds to protect or verify your account.',
  'recommended_action':'Do not use the caller’s number or link. Contact your bank using the number on your card or official app.'},
 'investment_scam':{
  'title':'Check the investment before sending money',
  'message':'This payment has indicators commonly associated with investment scams, such as promised returns or pressure to act quickly.',
  'recommended_action':'Verify the provider and recipient independently. Guaranteed returns are a warning sign.'},
 'fake_job_scam':{
  'title':'Verify the employer before paying a fee',
  'message':'This payment appears connected to a job opportunity that may request an upfront fee.',
  'recommended_action':'Contact the employer through a separately verified channel before paying registration, training or onboarding fees.'},
 'tech_support_scam':{
  'title':'Verify this technical-support request independently',
  'message':'This payment is connected to a request from someone claiming to provide technical support. Be cautious if they asked you to install remote access and transfer money to secure an account.',
  'recommended_action':'End the remote session and contact the company using support details from its official website or app.'},
}
