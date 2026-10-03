"""Queue only uncertain high-impact cases; high risk alone is insufficient."""


def review_reason(assessment: dict, passive: dict | None = None,
                  degraded: bool = False) -> str | None:
    if degraded:
        return 'Risk analysis was degraded or an evidence subsystem was unavailable.'
    risk=float(assessment.get('app_scam_risk',0) or 0)
    confidence=float(assessment.get('confidence',0) or 0)
    groups=assessment.get('component_scores') or {}
    recipient=float(groups.get('recipient') or 0)
    manipulation=float(groups.get('context') or 0)
    scenario_conf=float(assessment.get('scenario_confidence',0) or 0)
    if risk>=55 and confidence<.60:
        return 'High-impact risk with low model confidence.'
    if recipient>=75 and manipulation<=20:
        return 'Critical recipient evidence conflicts with limited manipulation evidence.'
    if manipulation>=70 and recipient<=15 and confidence<.70:
        return 'Strong manipulation evidence conflicts with a comparatively clean recipient profile.'
    if assessment.get('likely_scam_scenario') in ('normal_or_unknown','unknown') and risk>=50:
        return 'Elevated risk has no sufficiently supported scenario label.'
    if scenario_conf<.40 and risk>=55:
        return 'Elevated risk with uncertain scenario classification.'
    return None
