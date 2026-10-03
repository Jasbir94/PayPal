"""Scenario, technique, and feature-availability rates over aggregate snapshots."""
from collections import Counter


def scenario_summary(snapshots: list[dict]) -> dict:
    count=max(1,len(snapshots)); scenarios=Counter(x.get('scenario','unknown') or 'unknown' for x in snapshots)
    techniques=Counter(tech for row in snapshots for tech in row.get('detected_techniques',[]))
    features=[row.get('features') or {} for row in snapshots]
    return {'sample_count':len(snapshots),
        'scenario_rates':{key:round(value/count,4) for key,value in scenarios.items()},
        'psychology_detection_rates':{key:round(value/count,4) for key,value in techniques.items()},
        'new_recipient_rate':round(sum(x.get('new_recipient_baseline',0) for x in features)/count,4) if snapshots else None,
        'unknown_contact_rate':round(sum(x.get('unknown_contact',0) for x in features)/count,4) if snapshots else None,
        'graph_missing_rate':round(sum(x.get('graph_missing',0) for x in features)/count,4) if snapshots else None,
        'context_missing_rate':round(sum(x.get('context_missing',0) for x in features)/count,4) if snapshots else None}
