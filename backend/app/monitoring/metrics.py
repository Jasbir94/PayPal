"""Aggregate prediction metrics; never return per-payment content."""
from collections import Counter
import numpy as np


def prediction_summary(snapshots: list[dict]) -> dict:
    scored=[row for row in snapshots if isinstance(row.get('risk'),(int,float))]
    risks=np.asarray([float(row['risk']) for row in scored],dtype=float)
    confidence=np.asarray([float(row.get('confidence') or 0) for row in scored],dtype=float)
    buckets=Counter('LOW' if x<30 else 'MEDIUM' if x<60 else 'HIGH' if x<80 else 'CRITICAL' for x in risks)
    return {'prediction_count':len(scored),
        'average_risk':round(float(risks.mean()),3) if len(risks) else None,
        'median_risk':round(float(np.median(risks)),3) if len(risks) else None,
        'average_confidence':round(float(confidence.mean()),4) if len(confidence) else None,
        'risk_distribution':dict(buckets),
        'decision_distribution':dict(Counter(row.get('decision','UNKNOWN') for row in scored)),
        'scenario_distribution':dict(Counter(row.get('scenario','unknown') or 'unknown' for row in scored)),
        'label':'SYNTHETIC / RESEARCH AGGREGATES'}


def shadow_summary(predictions: list[dict]) -> dict:
    """Summarize challenger behavior without presenting unlabelled agreement as accuracy."""
    grouped={}
    for row in predictions:
        grouped.setdefault(row.get('model_version','unknown'),[]).append(row)
    versions={}
    for version,rows in grouped.items():
        risks=np.asarray([float(row['risk']) for row in rows],dtype=float)
        versions[version]={'count':len(rows),'mean_risk':round(float(risks.mean()),3),
            'risk_distribution':dict(Counter('LOW' if x<30 else 'MEDIUM' if x<60 else 'HIGH' if x<80 else 'CRITICAL' for x in risks)),
            'decision_distribution':dict(Counter(row.get('decision','UNKNOWN') for row in rows))}
    return {'prediction_count':len(predictions),'models':versions,
        'accuracy_status':'NOT_EVALUABLE_WITHOUT_MATURE_TRUSTED_LABELS',
        'label':'SHADOW RESEARCH AGGREGATES'}
