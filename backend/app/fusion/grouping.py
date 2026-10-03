"""Combine related model evidence while discounting shared inputs."""
from backend.app.config.risk_config import FUSION_WEIGHTS, clamp_score

def _weighted_available(parts):
    usable = [(float(score), float(conf), float(weight)) for score, conf, weight, available in parts
              if available and score is not None]
    if not usable:
        return {'score': None, 'confidence': 0.0, 'available': False}
    total = sum(weight for _, _, weight in usable)
    score = sum(s * w for s, _, w in usable) / total
    confidence = sum(c * w for _, c, w in usable) / total
    return {'score': clamp_score(score), 'confidence': round(max(0, min(1, confidence)), 4), 'available': True}

def group_signals(transaction, recipient, graph, context, scenario_risk, psychology, alignment=0.0):
    user = _weighted_available([(transaction['score'], transaction['confidence'], 1, transaction['available'])])
    # Recipient and graph scores overlap on fan-in and account velocity. A 0.65/0.35
    # max/min blend captures corroboration without counting the same fact twice.
    network_parts = [x for x in (recipient, graph) if x['available']]
    if len(network_parts) == 2:
        hi, lo = sorted((network_parts[0]['score'], network_parts[1]['score']), reverse=True)
        recipient_side = {'score': clamp_score(.65 * hi + .35 * lo),
                          'confidence': round(.65 * max(recipient['confidence'], graph['confidence']) +
                                              .35 * min(recipient['confidence'], graph['confidence']), 4),
                          'available': True}
    elif network_parts:
        recipient_side = network_parts[0].copy()
    else:
        recipient_side = {'score': None, 'confidence': 0.0, 'available': False}
    # Scenario risk is already grounded in structured context; confidence is not
    # risk. Alignment is only a small corroborating factor when both exist.
    manip = _weighted_available([
        (context['score'], context['confidence'], .40, context['available']),
        (scenario_risk['score'], scenario_risk['confidence'], .25, scenario_risk['available']),
        (psychology['score'], psychology['confidence'], .35, psychology['available']),
    ])
    if manip['available'] and alignment > 0:
        manip['score'] = clamp_score(manip['score'] + min(5.0, 5.0 * float(alignment)))
    families = {'user_side': user, 'recipient_side': recipient_side, 'manipulation_side': manip}
    weights = dict(FUSION_WEIGHTS)
    active = {name: family for name, family in families.items() if family['available']}
    denom = sum(weights[name] for name in active)
    score = sum(weights[name] * active[name]['score'] for name in active) / denom if denom else 0.0
    return families, clamp_score(score), weights
