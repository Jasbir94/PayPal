"""Illustrative threshold/cost sweep on the same temporal fusion holdout."""
import argparse
import json
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix,precision_score,recall_score
from backend.app.config.risk_config import PROJECT_ROOT
from backend.app.fusion.calibration import FusionCalibrator
from ml.fusion.build_dataset import FEATURES,OUT

DEFAULT_COSTS={'false_negative_cost':8.0,'false_positive_cost':1.0,
    'soft_warning_cost':.10,'context_check_cost':.25,'strong_warning_cost':.50,
    'step_up_verification_cost':1.0,'manual_review_cost':1.5}


def run(input_path=OUT,output_path=PROJECT_ROOT/'reports'/'threshold_analysis.csv',costs=None):
    costs={**DEFAULT_COSTS,**(costs or {})}
    data=pd.read_csv(input_path).sort_values('timestamp',kind='mergesort').reset_index(drop=True)
    test=data.iloc[int(len(data)*.8):].copy();calibrator=FusionCalibrator.load()
    probabilities=np.asarray([calibrator.predict(row) for row in test[FEATURES].to_dict('records')],dtype=float)
    y=test.is_fraud.to_numpy(dtype=int);rows=[]
    for threshold in np.round(np.arange(.10,.901,.05),2):
        labels=probabilities>=threshold
        tn,fp,fn,tp=confusion_matrix(y,labels,labels=[0,1]).ravel()
        tiers={'soft_warning':0,'context_check':0,'strong_warning':0,'step_up_verification':0,'manual_review':0}
        for score in probabilities[labels]:
            if score>=min(.99,threshold+.40):tiers['manual_review']+=1
            elif score>=min(.99,threshold+.30):tiers['step_up_verification']+=1
            elif score>=min(.99,threshold+.20):tiers['strong_warning']+=1
            elif score>=min(.99,threshold+.10):tiers['context_check']+=1
            else:tiers['soft_warning']+=1
        expected=(fn*costs['false_negative_cost']+fp*costs['false_positive_cost']+
            tiers['soft_warning']*costs['soft_warning_cost']+
            tiers['context_check']*costs['context_check_cost']+
            tiers['strong_warning']*costs['strong_warning_cost']+
            tiers['step_up_verification']*costs['step_up_verification_cost']+
            tiers['manual_review']*costs['manual_review_cost'])
        rows.append({'threshold':float(threshold),'precision':float(precision_score(y,labels,zero_division=0)),
            'recall':float(recall_score(y,labels,zero_division=0)),
            'false_positive_rate':float(fp/max(1,fp+tn)),'false_negative_rate':float(fn/max(1,fn+tp)),
            'false_positives':int(fp),'false_negatives':int(fn),**tiers,
            'expected_simulated_cost':float(expected)})
    output_path.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path,index=False)
    config_path=output_path.with_name('cost_analysis_config.json')
    config_path.write_text(json.dumps({'costs':costs,'total_test_rows':len(test),
        'model_version':calibrator.version,'notice':'Illustrative comparison parameters only; not actual provider economics or product policy.'},indent=2),encoding='utf-8')
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name,default in DEFAULT_COSTS.items():parser.add_argument('--'+name.replace('_','-'),type=float,default=default)
    args=parser.parse_args();values=vars(args)
    results=run(costs=values)
    print(json.dumps({'rows':len(results),'min_cost':min(results,key=lambda row:row['expected_simulated_cost'])},indent=2))
