"""Maturity-gated calibration checks using trusted labels and calibrated outputs only."""
from collections import defaultdict
from backend.app.feedback.label_policy import training_eligibility,LABEL_MATURITY_DAYS


def calibration_report(rows: list[dict], now=None, maturity_days: int = LABEL_MATURITY_DAYS,
                       min_samples: int = 30, bins: int = 10) -> dict:
    from sklearn.metrics import brier_score_loss
    included=[];excluded=0
    for row in rows:
        snapshot=row['snapshot']
        ok,_=training_eligibility(row['fraud_label'],row['label_source'],row['label_confidence'],
            snapshot['prediction_timestamp'],now=now,maturity_days=maturity_days)
        probability=snapshot.get('calibrated_probability')
        if not ok or probability is None:
            excluded+=1;continue
        included.append((float(probability),int(row['fraud_label'] in ('CONFIRMED_SCAM','CONFIRMED_MULE'))))
    report={'labelled_rows':len(rows),'eligible_mature_calibrated_rows':len(included),'excluded_rows':excluded,
        'maturity_days':maturity_days,'status':'INSUFFICIENT_MATURE_LABELS' if len(included)<min_samples else 'MEASURED',
        'brier_score':None,'buckets':[],'alerts':[],
        'notice':'Only trusted, final, sufficiently mature labels are used. Evidence-index risk is not treated as probability.'}
    if len(included)<min_samples:return report
    from sklearn.calibration import calibration_curve
    probability=[x[0] for x in included];target=[x[1] for x in included]
    report['brier_score']=float(brier_score_loss(target,probability))
    observed,predicted=calibration_curve(target,probability,n_bins=bins,strategy='quantile')
    report['buckets']=[{'mean_predicted':float(p),'observed_rate':float(o)} for p,o in zip(predicted,observed)]
    gaps=[abs(x['mean_predicted']-x['observed_rate']) for x in report['buckets']]
    if gaps and max(gaps)>=.15:report['alerts'].append('CALIBRATION_DRIFT')
    return report
