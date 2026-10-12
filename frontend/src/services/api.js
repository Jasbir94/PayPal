const API_BASE = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');
export const resolveApiUrl = (path, apiBase, isProduction) => {
  if (isProduction && !apiBase) {
    throw new Error('Backend API URL is not configured. Set VITE_API_BASE_URL to the Render API origin.');
  }
  return `${apiBase}${path}`;
};
const apiUrl = path => resolveApiUrl(path, API_BASE, import.meta.env?.PROD === true);
const API_ROOT = '/api/v1/simulated-payments';
const requestId = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(apiUrl(`${API_ROOT}${path}`), {
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
  recipientNetwork: (accountId) => request(`/recipients/${encodeURIComponent(accountId)}/network`),
  bankingProfiles: () => fetch(apiUrl('/api/v1/banking/profiles')).then(readResponse),
  bankingDemoSession: (account_alias) => fetch(apiUrl('/api/v1/banking/demo-sessions'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({account_alias})}).then(readResponse),
  bankingSession: (token) => fetch(apiUrl('/api/v1/banking/session'),{headers:{Authorization:`Bearer ${token}`}}).then(readResponse),
  bankingBalance: (token) => fetch(apiUrl('/api/v1/banking/balance'),{headers:{Authorization:`Bearer ${token}`}}).then(readResponse),
  bankingTransactions: (token,query='') => fetch(apiUrl(`/api/v1/banking/transactions${query?`?${query}`:''}`),{headers:{Authorization:`Bearer ${token}`}}).then(readResponse),
  bankingTransaction: (token,id) => fetch(apiUrl(`/api/v1/banking/transactions/${encodeURIComponent(id)}`),{headers:{Authorization:`Bearer ${token}`}}).then(readResponse),
  chatStart: (message,token,idempotencyKey) => fetch(apiUrl('/api/v1/chat/sessions'),{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({message,idempotency_key:idempotencyKey})}).then(readResponse),
  chatSession: (id,token) => fetch(apiUrl(`/api/v1/chat/sessions/${encodeURIComponent(id)}`),{headers:{Authorization:`Bearer ${token}`}}).then(readResponse),
  chatMessage: (id,message,token,idempotencyKey) => fetch(apiUrl(`/api/v1/chat/sessions/${encodeURIComponent(id)}/messages`),{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({message,idempotency_key:idempotencyKey})}).then(readResponse),
  chatAction: (id,action,token) => fetch(apiUrl(`/api/v1/chat/sessions/${encodeURIComponent(id)}/actions/${encodeURIComponent(action)}`),{method:'POST',headers:{Authorization:`Bearer ${token}`}}).then(readResponse),
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
  transactions: async () => (await request('/analytics?limit=1000')).recent_attempts || [],
  monitoring: () => fetch(apiUrl('/api/v1/monitoring/summary')).then(readResponse),
  failures: () => fetch(apiUrl('/api/v1/research/failures')).then(readResponse),
  feedback: (id) => fetch(apiUrl(`/api/v1/feedback/${encodeURIComponent(id)}`)).then(readResponse),
  modelInfo: () => fetch(apiUrl('/api/v1/model-info')).then(readResponse),
  async systemDiagnostics() {
    const probe = (promise) => promise.then(value => ({ ok:true, value }))
      .catch(error => ({ ok:false, error:error.message }));
    const [health,ready,models,scenarioCatalog,chat] = await Promise.all([
      probe(fetch(apiUrl('/health')).then(readResponse)),
      probe(fetch(apiUrl('/ready')).then(readResponse)),
      probe(fetch(apiUrl('/api/v1/model-info')).then(readResponse)),
      probe(request('/scenarios')),
      probe(fetch(apiUrl('/api/v1/chat/health')).then(readResponse)),
    ]);
    return { health,ready,models,scenarioCatalog,chat };
  },
  async runScenario(scenario) {
    const created = await post('', {sender_alias:scenario.sender_alias,
      recipient_alias:scenario.recipient_alias,amount:Number(scenario.amount),
      payment_reason:scenario.payment_reason,payment_type:'upi',note:'',idempotency_key:requestId()});
    let result = await post(`/${encodeURIComponent(created.payment_attempt_id)}/analyze`, {
      context:scenario.context || {},messages:scenario.messages || []});
    if (result.context_required) {
      return {payment_attempt_id:created.payment_attempt_id,payment:result.payment,
        context_required:true,context_questions:result.context_questions};
    }
    return {payment_attempt_id:created.payment_attempt_id,payment:result.payment,context_required:false,
      analyst:await request(`/${encodeURIComponent(created.payment_attempt_id)}/analyst`)};
  },
};

async function readResponse(response) {
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.detail||'The request could not be completed.');
  return data;
}
