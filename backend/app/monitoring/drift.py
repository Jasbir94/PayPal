"""PSI for numeric features and Jensen–Shannon divergence for categories."""
from collections import Counter
import numpy as np
from scipy.spatial.distance import jensenshannon

MIN_WINDOW_SIZE=30
PSI_ALERT_THRESHOLD=.20
JSD_ALERT_THRESHOLD=.15


def population_stability_index(reference, current, bins=10) -> float | None:
    reference=np.asarray([x for x in reference if x is not None and np.isfinite(float(x))],dtype=float)
    current=np.asarray([x for x in current if x is not None and np.isfinite(float(x))],dtype=float)
    if len(reference)<MIN_WINDOW_SIZE or len(current)<MIN_WINDOW_SIZE:return None
    edges=np.unique(np.quantile(reference,np.linspace(0,1,bins+1)))
    if len(edges)<3:
        center=float(reference[0]); edges=np.asarray([-np.inf,center,np.inf])
    else: edges[0],edges[-1]=-np.inf,np.inf
    a=np.histogram(reference,bins=edges)[0].astype(float)+.5
    b=np.histogram(current,bins=edges)[0].astype(float)+.5
    a/=a.sum();b/=b.sum()
    return float(np.sum((b-a)*np.log(b/a)))


def categorical_jsd(reference, current) -> float | None:
    reference=[str(x or 'unknown') for x in reference]
    current=[str(x or 'unknown') for x in current]
    if len(reference)<MIN_WINDOW_SIZE or len(current)<MIN_WINDOW_SIZE:return None
    keys=sorted(set(reference)|set(current))
    a=np.asarray([Counter(reference)[key] for key in keys],dtype=float)+.5
    b=np.asarray([Counter(current)[key] for key in keys],dtype=float)+.5
    a/=a.sum();b/=b.sum()
    return float(jensenshannon(a,b,base=2)**2)


def compare_windows(reference: list[dict], current: list[dict]) -> dict:
    numeric=('risk','confidence')
    result={'method':'PSI numeric, Jensen-Shannon divergence categorical',
        'reference_count':len(reference),'current_count':len(current),'features':{},
        'notice':'Drift indicates a distribution change to investigate; it does not prove fraud increased.'}
    for feature in numeric:
        value=population_stability_index([x.get(feature) for x in reference],[x.get(feature) for x in current])
        result['features'][feature]={'method':'PSI','value':value,'alert':value is not None and value>=PSI_ALERT_THRESHOLD}
    for feature in ('scenario','decision'):
        value=categorical_jsd([x.get(feature) for x in reference],[x.get(feature) for x in current])
        result['features'][feature]={'method':'Jensen-Shannon divergence','value':value,
            'alert':value is not None and value>=JSD_ALERT_THRESHOLD}
    feature_keys=sorted(set().union(*(set(x.get('features') or {}) for x in reference+current)))
    for key in feature_keys:
        if key in ('transaction_risk','recipient_risk','graph_risk','context_risk','psychology_risk','amount_ratio_baseline','recipient_account_age_days','recipient_fan_in_24h','recipient_outflow_ratio'):
            ref=[(x.get('features') or {}).get(key) for x in reference]
            cur=[(x.get('features') or {}).get(key) for x in current]
            val=population_stability_index(ref,cur)
            result['features'][key]={'method':'PSI','value':val,'alert':val is not None and val>=PSI_ALERT_THRESHOLD}
    result['alert_count']=sum(bool(item['alert']) for item in result['features'].values())
    return result
