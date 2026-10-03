"""Temporary grouped fusion to limit duplicate recipient/network evidence."""
from backend.app.config.risk_config import clamp_score

def combine_recipient_graph(recipient_risk, graph_risk):
    return clamp_score(.7 * max(recipient_risk, graph_risk) + .3 * min(recipient_risk, graph_risk))

def combine_grouped_risk(contextual, graph_risk=None):
    user = contextual['transaction_risk']['score']
    recipient = contextual['recipient_risk']['score']
    recipient_side = combine_recipient_graph(recipient, graph_risk) if graph_risk is not None else recipient
    manipulation_parts = [
        contextual['context_risk']['score'], contextual['scenario_risk']['score']]
    if contextual['psychology']['message_available']:
        manipulation_parts.append(contextual['psychology_overlap_adjustment']['adjusted_psychology_risk'])
    strongest = max(manipulation_parts)
    complement = sum(sorted(manipulation_parts, reverse=True)[1:]) / (len(manipulation_parts) - 1)
    manipulation = clamp_score(.7 * strongest + .3 * complement)
    groups = {'user_side': user, 'recipient_side': recipient_side, 'manipulation_side': manipulation}
    # No structured context or message is unknown evidence, not zero-risk evidence.
    if not contextual['context_risk']['context_available'] and not contextual['psychology']['message_available']:
        overall = (.25 * user + .35 * recipient_side) / .60
        policy = 'missing_manipulation_group_weights_renormalized'
    else:
        overall = .25 * user + .35 * recipient_side + .40 * manipulation
        policy = 'temporary_grouped_weights'
    return {'grouped_scores': groups, 'overall_risk': clamp_score(overall), 'fusion_policy': policy}
