"""Leakage-conscious, chronological baseline and ablation evaluation."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.calibration import calibration_curve
from backend.app.config.risk_config import PROJECT_ROOT
from backend.app.fusion.calibration import FusionCalibrator
from ml.fusion.build_dataset import FEATURES,OUT

REPORTS=PROJECT_ROOT/'reports'
VARIANTS={
 'Amount ratio threshold':('threshold',['amount_ratio_baseline'],None),
 'Transaction Rules':('rules',['amount_ratio_baseline','new_recipient_baseline'],None),
 'Transaction Rules':('rules',['amount_ratio_baseline','new_recipient_baseline'],None),
 'Amount ratio + new recipient':('logistic',['amount_ratio_baseline','new_recipient_baseline'],None),
 'Transaction ML':('logistic',['transaction_risk','transaction_confidence','amount_ratio_baseline','new_recipient_baseline'],None),
 'Transaction + Recipient':('logistic',['transaction_risk','transaction_confidence','recipient_risk','recipient_confidence','amount_ratio_baseline','new_recipient_baseline'],None),
 'Transaction + Recipient + Graph':('logistic',['transaction_risk','transaction_confidence','recipient_risk','recipient_confidence','amount_ratio_baseline','new_recipient_baseline','graph_risk','graph_confidence','graph_available'],'graph_available'),
 'Transaction + Recipient + Context':('logistic',['transaction_risk','transaction_confidence','recipient_risk','recipient_confidence','amount_ratio_baseline','new_recipient_baseline','context_risk','context_confidence','context_available'],'context_available'),
 'Transaction + Recipient + Scenario':('logistic',['transaction_risk','transaction_confidence','recipient_risk','recipient_confidence','amount_ratio_baseline','new_recipient_baseline','scenario_risk','scenario_confidence','scenario_available'],'scenario_available'),
 'Transaction + Recipient + Psychology':('logistic',['transaction_risk','transaction_confidence','recipient_risk','recipient_confidence','amount_ratio_baseline','new_recipient_baseline','psychology_risk','psychology_confidence','psychology_available'],'psychology_available'),
 'Full APP Shield registered fusion':('registry',FEATURES,None),
}


def _metrics(y,probability,threshold,recall_at_5=None):
    y=np.asarray(y,dtype=int);p=np.asarray(probability,dtype=float);pred=p>=threshold
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return {'samples':int(len(y)),'positives':int(y.sum()),'threshold':float(threshold),
      'precision':float(precision_score(y,pred,zero_division=0)),
      'recall':float(recall_score(y,pred,zero_division=0)),
      'f1':float(f1_score(y,pred,zero_division=0)),
      'pr_auc':float(average_precision_score(y,p)) if len(np.unique(y))>1 else None,
      'roc_auc':float(roc_auc_score(y,p)) if len(np.unique(y))>1 else None,
      'false_positive_rate':float(fp/max(1,fp+tn)),'false_negative_rate':float(fn/max(1,fn+tp)),
      'brier':float(brier_score_loss(y,p)),
      'test_recall_at_validation_fpr_le_5pct_threshold':recall_at_5,
      'confusion':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}}


def _validation_cut(y,probability):
    thresholds=np.arange(.05,.951,.01)
    return float(max(thresholds,key=lambda cut:(f1_score(y,probability>=cut,zero_division=0),
        precision_score(y,probability>=cut,zero_division=0),-abs(cut-.5))))


def _fpr_cut(y,probability):
    options=[]
    for cut in np.arange(.01,.991,.01):
        pred=probability>=cut;tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
        fpr=fp/max(1,fp+tn);recall=tp/max(1,tp+fn)
        if fpr<=.05:options.append((recall,cut))
    return max(options,default=(0.,1.))[0],max(options,default=(0.,1.))[1]


def _calibrate(train,val,test,features):
    estimator=LogisticRegression(max_iter=2000,class_weight='balanced',random_state=42)
    estimator.fit(train[features],train.is_fraud.astype(int))
    rv=estimator.predict_proba(val[features])[:,1];rt=estimator.predict_proba(test[features])[:,1]
    calibrator=LogisticRegression(C=1e6,random_state=42).fit(rv.reshape(-1,1),val.is_fraud.astype(int))
    return calibrator.predict_proba(rv.reshape(-1,1))[:,1],calibrator.predict_proba(rt.reshape(-1,1))[:,1]


def run(input_path=OUT,output_dir=REPORTS):
    data=pd.read_csv(input_path).sort_values('timestamp',kind='mergesort').reset_index(drop=True)
    if len(data)<100:raise ValueError('Temporal evaluation requires at least 100 chronologically ordered rows.')
    n=len(data);train_end=int(n*.60);validation_end=int(n*.80)
    train,val,test=data.iloc[:train_end].copy(),data.iloc[train_end:validation_end].copy(),data.iloc[validation_end:].copy()
    times=[pd.to_datetime(frame.timestamp,utc=True) for frame in (train,val,test)]
    if not (times[0].max()<times[1].min() and times[1].max()<times[2].min()):
        raise ValueError('Temporal split overlap detected.')
    yv=val.is_fraud.to_numpy(dtype=int);yt=test.is_fraud.to_numpy(dtype=int)
    results={};model_rows=[];predictions={}
    for name,(kind,features,availability) in VARIANTS.items():
        if availability and (not data[availability].astype(bool).any() or
                not train[availability].astype(bool).any() or not val[availability].astype(bool).any() or not test[availability].astype(bool).any()):
            results[name]={'status':'NOT_EVALUABLE','reason':f'No transaction-linked {availability} evidence in the shared temporal dataset.',
                'coverage':int(data[availability].astype(bool).sum()),'samples':len(test)}
            continue
        if kind=='threshold':
            value='amount_ratio_baseline';cuts=np.arange(1,10.01,.1)
            threshold=float(max(cuts,key=lambda cut:(f1_score(yv,val[value]>=cut,zero_division=0),
                precision_score(yv,val[value]>=cut,zero_division=0),-cut)))
            pv=np.clip(val[value].to_numpy(dtype=float)/10,0,1)
            pt=np.clip(test[value].to_numpy(dtype=float)/10,0,1)
        elif kind=='rules':
            def rule_score(frame):
                ratio=frame.amount_ratio_baseline.to_numpy(dtype=float)
                amount=np.select([ratio>=10,ratio>=3,ratio>=1.5],[.75,.50,.25],default=.05)
                new=frame.new_recipient_baseline.to_numpy(dtype=float)*.20
                return np.clip(amount+new,0,1)
            pv,pt=rule_score(val),rule_score(test)
            threshold=_validation_cut(yv,pv)
        elif kind=='rules':
            def rule_score(frame):
                ratio=frame.amount_ratio_baseline.to_numpy(dtype=float)
                amount=np.select([ratio>=10,ratio>=3,ratio>=1.5],[.75,.50,.25],default=.05)
                new=frame.new_recipient_baseline.to_numpy(dtype=float)*.20
                return np.clip(amount+new,0,1)
            pv,pt=rule_score(val),rule_score(test)
            threshold=_validation_cut(yv,pv)
        elif kind=='registry':
            calibrator=FusionCalibrator.load()
            profile={'graph_available':0,'context_available':0,'scenario_available':0,'psychology_available':0}
            if calibrator.modality_profile and calibrator.modality_profile!=profile:
                results[name]={'status':'NOT_EVALUABLE','reason':'Active fusion artifact modality profile does not match this shared holdout.'}
                continue
            pv=np.asarray([calibrator.predict(row) for row in val[FEATURES].to_dict('records')],dtype=float)
            pt=np.asarray([calibrator.predict(row) for row in test[FEATURES].to_dict('records')],dtype=float)
            threshold=float(json.loads((PROJECT_ROOT/'data/processed/day6/evaluation.json').read_text(encoding='utf-8')).get('threshold',.5))
        else:
            pv,pt=_calibrate(train,val,test,features)
            threshold=_validation_cut(yv,pv)
        recall5,cut5=_fpr_cut(yv,pv)
        test_recall5=float(recall_score(yt,pt>=cut5,zero_division=0))
        metric=_metrics(yt,pt,threshold,test_recall5)
        metric.update({'status':'MEASURED','validation_recall_at_fpr_le_5pct':recall5,
            'validation_threshold_at_fpr_le_5pct':cut5,'validation_threshold_selection':'F1, then precision; validation only',
            'features':features,'model_version':calibrator.version if kind=='registry' else 'day9-temporal-logistic-v1'})
        results[name]=metric;predictions[name]=pt.tolist()
        model_rows.append({'model':name,**metric})
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    comparison=pd.DataFrame(model_rows)
    comparison.to_csv(output_dir/'final_model_comparison.csv',index=False)
    # Scenario and named hard-negative ground truth do not have a transaction-linked label source.
    scenario_names=['government_impersonation','bank_impersonation','investment','fake_job','tech_support','romance','marketplace','loan_scam','refund_scam','family_emergency','small_initial_payment']
    pd.DataFrame([{'scenario':x,'status':'NOT_EVALUABLE','support':0,
      'reason':'No transaction-linked scenario ground truth in the temporal holdout.'} for x in scenario_names]).to_csv(output_dir/'scenario_performance.csv',index=False)
    negatives=['normal_friend','large_legitimate_purchase','known_merchant','government_fee','utility_bill',
      'loan_repayment','known_investment_provider','business_supplier','college_fee','hospital_payment',
      'friend_repayment','family_emergency']
    pd.DataFrame([{'case':x,'status':'NOT_EVALUABLE','support':0,
      'reason':'No verified intent-level hard-negative labels in the temporal holdout; Day 8 demo presets are illustrative only.'}
      for x in negatives]).to_csv(output_dir/'hard_negative_performance.csv',index=False)
    reliability=[]
    ece=None
    active=results.get('Full APP Shield registered fusion',{})
    if active.get('status')=='MEASURED':
        frac,mean=calibration_curve(yt,np.asarray(predictions['Full APP Shield registered fusion']),n_bins=10,strategy='quantile')
        reliability=[{'mean_predicted':float(a),'observed_rate':float(b)} for a,b in zip(mean,frac)]
        probabilities=np.asarray(predictions['Full APP Shield registered fusion'])
        edges=np.unique(np.quantile(probabilities,np.linspace(0,1,11)))
        contributions=[]
        for index in range(len(edges)-1):
            mask=(probabilities>=edges[index]) & (probabilities<edges[index+1] if index<len(edges)-2 else probabilities<=edges[index+1])
            if mask.any():contributions.append(float(mask.mean()*abs(probabilities[mask].mean()-yt[mask].mean())))
        ece=float(sum(contributions))
    calibration={'status':'MEASURED_SYNTHETIC' if reliability else 'NOT_EVALUABLE',
        'model_version':active.get('model_version'),'test_samples':len(test) if reliability else 0,
        'test_positives':int(yt.sum()) if reliability else 0,'brier':active.get('brier'),'expected_calibration_error':ece,
        'reliability_bins':reliability,
        'notice':'Calibrated probability belongs to the registered transaction/recipient fusion modality profile; it is not evidence of real-world calibration.'}
    (output_dir/'calibration_report.json').write_text(json.dumps(calibration,indent=2),encoding='utf-8')
    # The same time-ordered corpus supplies older reference and recent test observations.
    from backend.app.monitoring.drift import compare_windows
    reference=train.tail(min(len(train),len(test))).copy()
    current=test.copy()
    reference_rows=[{'risk':float(r.transaction_risk),'confidence':float(r.transaction_confidence),
        'scenario':'unavailable','decision':'unavailable','features':{'transaction_risk':float(r.transaction_risk),
        'recipient_risk':float(r.recipient_risk),'amount_ratio_baseline':float(r.amount_ratio_baseline)}} for r in reference.itertuples()]
    current_rows=[{'risk':float(r.transaction_risk),'confidence':float(r.transaction_confidence),
        'scenario':'unavailable','decision':'unavailable','features':{'transaction_risk':float(r.transaction_risk),
        'recipient_risk':float(r.recipient_risk),'amount_ratio_baseline':float(r.amount_ratio_baseline)}} for r in current.itertuples()]
    drift=compare_windows(reference_rows,current_rows)
    drift.update({'reference_period':{'start':str(times[0].min()),'end':str(times[0].max())},
        'current_period':{'start':str(times[2].min()),'end':str(times[2].max())},
        'notice':'Synthetic input shift only; no current production stream exists and drift is not proof fraud increased.'})
    (output_dir/'drift_report.json').write_text(json.dumps(drift,indent=2),encoding='utf-8')
    report={'title':'APP Shield Day 9 temporal evaluation','generated_at':pd.Timestamp.now(tz='UTC').isoformat(),
        'dataset':'Synthetic point-in-time transaction/recipient fusion rows; chronological 60/20/20 split.',
        'split':{'train':len(train),'validation':len(val),'test':len(test),'train_start':str(times[0].min()),
          'train_end':str(times[0].max()),'validation_start':str(times[1].min()),'validation_end':str(times[1].max()),
          'test_start':str(times[2].min()),'test_end':str(times[2].max()),'time_ordered':True},
        'test_positive_count':int(yt.sum()),'models':results,'calibration':calibration,'drift':drift,
        'outputs':['final_model_comparison.csv','scenario_performance.csv','hard_negative_performance.csv','calibration_report.json','drift_report.json','threshold_analysis.csv'],
        'limitations':'Only transaction and recipient features are linked to payment IDs and time. Graph, context, scenario, psychology, named scenarios and intended hard negatives are excluded from supervised metrics rather than filled with zero or assigned labels. Synthetic results do not establish production accuracy.'}
    (output_dir/'final_evaluation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return report


if __name__=='__main__':
    result=run();print(json.dumps({'split':result['split'],'models':result['models']},indent=2))
