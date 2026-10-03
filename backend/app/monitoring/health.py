"""Data quality and monitor readiness summaries."""
def data_quality_summary(snapshots: list[dict]) -> dict:
    count=len(snapshots)
    required=('risk','confidence','scenario','decision','model_versions')
    missing={key:sum(row.get(key) is None for row in snapshots) for key in required}
    invalid=sum(not 0<=float(row.get('risk',-1))<=100 or not 0<=float(row.get('confidence',-1))<=1
                for row in snapshots)
    return {'prediction_count':count,'missing_required_fields':missing,'invalid_numeric_outputs':invalid,
        'alerts':(['MODEL_OUTPUT_INVALID'] if invalid else [])+
            (['GRAPH_FEATURE_MISSING_RATE_HIGH'] if count and sum((x.get('features') or {}).get('graph_missing',0) for x in snapshots)/count>.5 else [])+
            (['CONTEXT_MISSING_RATE_HIGH'] if count and sum((x.get('features') or {}).get('context_missing',0) for x in snapshots)/count>.8 else []),
        'status':'INSUFFICIENT_MONITORING_DATA' if count<30 else 'MEASURED'}
