const API_ROOT = '/api/v1/simulated-payments';

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
  analyst: (id) => request(`/${encodeURIComponent(id)}/analyst`),
  network: (id) => request(`/${encodeURIComponent(id)}/network`),
};
