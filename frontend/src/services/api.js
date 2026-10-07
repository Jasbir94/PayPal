const API_ROOT = '/api/v1/simulated-payments';
const requestId = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${API_ROOT}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'The safety check could not be completed.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Safety analysis timed out. No payment was executed.');
    if (error instanceof TypeError) throw new Error('We could not reach APP Shield. No payment was executed.');
    throw error;
  } finally { clearTimeout(timeout); }
}

const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) });

export const api = {
  accounts: () => request('/accounts'),
  scenarios: () => request('/scenarios'),
  scenario: (id) => request(`/scenarios/${encodeURIComponent(id)}`),
  createAttempt: (body) => post('', body),
  analyze: (id, body = {}) => post(`/${encodeURIComponent(id)}/analyze`, body),
  continuePayment: (id, acknowledged_warning = false) => post(`/${encodeURIComponent(id)}/continue`, { acknowledged_warning }),
  verify: (id, action) => post(`/${encodeURIComponent(id)}/verify`, { action }),
  cancel: (id) => post(`/${encodeURIComponent(id)}/cancel`, {}),
  attempt: (id) => request(`/${encodeURIComponent(id)}`),
  analytics: () => request('/analytics'),
  analystAnalytics: () => request('/analyst/analytics'),
  analyst: (id) => request(`/${encodeURIComponent(id)}/analyst`),
  network: (id) => request(`/${encodeURIComponent(id)}/network`),
  ablation: (id) => post(`/${encodeURIComponent(id)}/ablation`, {}),
  transactions: async () => (await request('/analytics')).recent_attempts || [],
  monitoring: () => fetch('/api/v1/monitoring/summary').then(readResponse),
  failures: () => fetch('/api/v1/research/failures').then(readResponse),
  feedback: (id) => fetch(`/api/v1/feedback/${encodeURIComponent(id)}`).then(readResponse),
  modelInfo: () => fetch('/api/v1/model-info').then(readResponse),
  async runScenario(scenario) {
    const created = await post('', {sender_alias:scenario.sender_alias,
      recipient_alias:scenario.recipient_alias,amount:Number(scenario.amount),
      payment_reason:scenario.payment_reason,payment_type:'upi',note:'',idempotency_key:requestId()});
    let result = await post(`/${encodeURIComponent(created.payment_attempt_id)}/analyze`, {
      context:scenario.context || {},messages:scenario.messages || []});
    if (result.context_required) {
      return {payment:result.payment,context_required:true,context_questions:result.context_questions};
    }
    return {payment:result.payment,context_required:false,
      analyst:await request(`/${encodeURIComponent(created.payment_attempt_id)}/analyst`)};
  },
};

async function readResponse(response) {
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.detail||'The request could not be completed.');
  return data;
}
