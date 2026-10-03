export const percent = (value, digits = 0) => value == null ? 'Unavailable' : `${(Number(value) * 100).toFixed(digits)}%`;
export const score = (value) => value == null ? 'Unavailable' : `${Number(value).toFixed(1)} / 100`;
export const pretty = (value) => String(value || 'unknown').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
export const currency = (value) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value || 0);

export function userReasons(assessment) {
  const reasons = assessment?.top_reasons || [];
  return reasons.slice(0, 4).map((reason) => reason.message || reason.label || reason.code).filter(Boolean);
}

export function transactionOnlyLabel(passive) {
  if (!passive) return 'Not available';
  return `${passive.risk_level} · ${Number(passive.preliminary_risk).toFixed(1)}/100`;
}
