"""Held-out diagnostics, false cases, reliability and the simple baseline."""
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (precision_score, recall_score, f1_score, confusion_matrix,
    roc_auc_score, average_precision_score, brier_score_loss)
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from time import perf_counter
from backend.app.config.risk_config import PROJECT_ROOT, MODEL_DIR
from ml.fusion.build_dataset import FEATURES, OUT

REPORT = PROJECT_ROOT / 'data' / 'processed' / 'day6' / 'evaluation.json'
GROUPS = {
 'transaction':['transaction_risk','transaction_confidence','amount_ratio_baseline','new_recipient_baseline'],
 'recipient':['recipient_risk','recipient_confidence'],
 'graph':['graph_risk','graph_confidence','graph_available'],
 'context':['context_risk','context_confidence','context_available'],
 'scenario':['scenario_risk','scenario_confidence','scenario_available'],
 'psychology':['psychology_risk','psychology_confidence','psychology_available'],
}

def metrics(y, probability, threshold):
    y=np.asarray(y,dtype=int); pred=np.asarray(probability)>=threshold
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return {'precision':float(precision_score(y,pred,zero_division=0)),
            'recall':float(recall_score(y,pred,zero_division=0)),
            'f1':float(f1_score(y,pred,zero_division=0)),
            'false_positive_rate':float(fp/max(1,fp+tn)), 'false_negative_rate':float(fn/max(1,fn+tp)),
            'roc_auc':float(roc_auc_score(y,probability)) if len(np.unique(y))>1 else None,
            'average_precision':float(average_precision_score(y,probability)) if len(np.unique(y))>1 else None,
            'brier':float(brier_score_loss(y,probability)), 'confusion':{'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}}

def calibrate_variant(train, val, test, features):
    model=LogisticRegression(max_iter=2000,class_weight='balanced',random_state=42)
    model.fit(train[features],train.is_fraud.astype(int))
    raw_val=model.predict_proba(val[features])[:,1]; raw_test=model.predict_proba(test[features])[:,1]
    yv=val.is_fraud.to_numpy(dtype=int)
    platt=LogisticRegression(C=1e6,random_state=42).fit(raw_val.reshape(-1,1),yv)
    iso=IsotonicRegression(out_of_bounds='clip').fit(raw_val,yv)
    choices={'platt':(platt.predict_proba(raw_val.reshape(-1,1))[:,1],platt.predict_proba(raw_test.reshape(-1,1))[:,1]),
             'isotonic':(iso.predict(raw_val),iso.predict(raw_test))}
    selected=min(choices,key=lambda key:brier_score_loss(yv,choices[key][0]))
    pv,pt=choices[selected]
    thresholds=np.arange(.05,.91,.025)
    def f1_at(cut): return f1_score(yv,pv>=cut,zero_division=0)
    threshold=float(max(thresholds,key=lambda cut:(f1_at(cut),precision_score(yv,pv>=cut,zero_division=0))))
    return pt,threshold,selected

def evaluate():
    data=pd.read_csv(OUT).sort_values('timestamp'); n=len(data); a,b=int(n*.6),int(n*.8)
    train,val,test=data.iloc[:a],data.iloc[a:b],data.iloc[b:]
    meta=json.loads((MODEL_DIR/'fusion_metadata.json').read_text(encoding='utf-8'))
    threshold=float(meta['selected_threshold']['threshold']); y=test.is_fraud.to_numpy(dtype=int)
    artifact=joblib.load(MODEL_DIR/'fusion_model.pkl'); model=artifact['estimator']
    cal=joblib.load(MODEL_DIR/'calibration_model.pkl'); method=cal['method']; estimator=cal[method]
    start=perf_counter(); raw=model.predict_proba(test[FEATURES])[:,1]; inference_ms=(perf_counter()-start)*1000/max(1,len(test))
    probabilities=estimator.predict_proba(raw.reshape(-1,1))[:,1] if method=='platt' else estimator.predict(raw)
    manual=(.25*test.transaction_risk+.30*test.recipient_risk)/.55/100
    base_features=['amount_ratio_baseline','new_recipient_baseline']
    baseline,baseline_threshold,baseline_cal=calibrate_variant(train,val,test,base_features)
    val_manual=(.25*val.transaction_risk+.30*val.recipient_risk)/.55/100
    manual_threshold=float(max(np.arange(.05,.91,.025),key=lambda cut:f1_score(
        val.is_fraud.to_numpy(dtype=int),val_manual>=cut,zero_division=0)))
    variants={'learned_fusion':metrics(y,probabilities,threshold),
              'manual_transaction_recipient':metrics(y,manual,manual_threshold),
              'amount_plus_new_recipient_baseline':metrics(y,baseline,baseline_threshold)}
    variants['manual_transaction_recipient']['threshold_selected_on_validation']=manual_threshold
    variants['amount_plus_new_recipient_baseline']['threshold_selected_on_validation']=baseline_threshold
    variants['amount_plus_new_recipient_baseline']['calibrator']=baseline_cal
    ablations={}
    for module,removed in GROUPS.items():
        keep=[feature for feature in FEATURES if feature not in removed]
        score,cut,cal_method=calibrate_variant(train,val,test,keep)
        ablations[f'without_{module}']=metrics(y,score,cut)
        ablations[f'without_{module}']['threshold_selected_on_validation']=cut
        ablations[f'without_{module}']['calibrator']=cal_method
    modules=['transaction_risk','recipient_risk','graph_risk','context_risk','scenario_risk','psychology_risk']
    distributions={}
    for column in modules:
        distributions[column]={}
        available_column={'graph_risk':'graph_available','context_risk':'context_available',
                          'scenario_risk':'scenario_available','psychology_risk':'psychology_available'}.get(column)
        for label,name in ((0,'legitimate'),(1,'fraudulent')):
            subset=data.loc[data.is_fraud==label]
            if available_column:
                values=subset.loc[subset[available_column]==1,column].dropna()
                count_available=int((subset[available_column]==1).sum())
            else:
                values=subset[column].dropna(); count_available=int(len(values))
            distributions[column][name]={'available_count':count_available,'missing_count':int(len(subset)-count_available),
                'mean':float(values.mean()) if len(values) else None,
                'median':float(values.median()) if len(values) else None,
                'p90':float(values.quantile(.9)) if len(values) else None}
    bins=[]
    frac,mean=calibration_curve(y,probabilities,n_bins=10,strategy='quantile')
    bins=[{'mean_predicted':float(p),'observed_rate':float(o)} for p,o in zip(mean,frac)]
    test_eval=test.copy(); test_eval['probability']=probabilities; test_eval['predicted']=probabilities>=threshold
    fp=test_eval[(test_eval.predicted)&(test_eval.is_fraud==0)].sort_values('probability',ascending=False).head(20)
    fn=test_eval[(~test_eval.predicted)&(test_eval.is_fraud==1)].sort_values('probability').head(20)
    def examples(frame):
        return frame[['transaction_id','timestamp','probability','transaction_risk','recipient_risk',
                      'amount_ratio_baseline','new_recipient_baseline','is_fraud']].to_dict('records')
    result={'dataset':'synthetic, point-in-time transaction and recipient service outputs',
        'n_rows':len(data),'split':{'train':len(train),'validation':len(val),'test':len(test)},
        'test_positive_count':int(y.sum()),'selected_calibrator':method,'threshold':threshold,
        'models':variants,'ablations':ablations,'score_distributions':distributions,
        'ablation_coverage':{name:int(data[name].sum()) for name in ('graph_available','context_available','scenario_available','psychology_available')},
        'reliability_curve':bins,'inference_ms_per_row':inference_ms,
        'false_positives':examples(fp),'false_negatives':examples(fn),
        'limitations':'The transaction labels and fraud profiles are synthetic. There is no transaction-level join for context, text or graph evidence; their scores are missing (not zero-risk) in the fusion dataset. Metrics describe only the transaction/recipient baseline and must not be generalized to real payments.'}
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2)); return result

if __name__=='__main__': evaluate()
