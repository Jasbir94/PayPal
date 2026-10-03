"""Reproduce measured Day 9–10 reports without retraining or mutating active models."""
import json
import shutil
import html
from pathlib import Path
from backend.app.config.risk_config import PROJECT_ROOT
from scripts.run_final_evaluation import main as evaluate
from evaluation.flagship_experiments import run as run_demos
from evaluation.day7_adversarial import main as run_adversarial
from scripts.freeze_final_benchmark import DEST,freeze


def main():
    if not DEST.exists():freeze()
    run_adversarial()
    evaluate()
    report=run_demos(PROJECT_ROOT/'reports'/'demo_scenario_results.json')
    reports=PROJECT_ROOT/'reports'
    shutil.copyfile(reports/'scenario_performance.csv',reports/'final_scenario_performance.csv')
    shutil.copyfile(reports/'hard_negative_performance.csv',reports/'final_hard_negative_results.csv')
    adversarial=json.loads((PROJECT_ROOT/'evaluation/day7_adversarial_evaluation.json').read_text(encoding='utf-8'))
    rows=[]
    for item in adversarial['results']:
        rows.append({'case_id':item['case_id'],'category':item['category'],'label':item['label'],
            'baseline_prediction':item['baseline_prediction'],'hardened_prediction':item['hardened_prediction'],
            'failure_bucket':item['failure_bucket']})
    import pandas as pd
    pd.DataFrame(rows).to_csv(reports/'final_adversarial_results.csv',index=False)
    grouped=[]
    for category in ('base','hinglish','leet','split','indirect','misspelling','paraphrase'):
        sample=[row for row in adversarial['results'] if row['category']==category]
        if not sample:continue
        tp=sum(x['label']==1 and x['hardened_prediction']==1 for x in sample)
        fp=sum(x['label']==0 and x['hardened_prediction']==1 for x in sample)
        fn=sum(x['label']==1 and x['hardened_prediction']==0 for x in sample)
        tn=sum(x['label']==0 and x['hardened_prediction']==0 for x in sample)
        grouped.append({'transformation':category,'cases':len(sample),'scam_recall':tp/max(1,tp+fn),
            'message_false_positive_rate':fp/max(1,fp+tn),'scope':'Authored synthetic message-level subset; not payment-level or representative language evaluation.'})
    grouped.append({'transformation':'obfuscated_hinglish_combination','cases':0,'scam_recall':None,
        'message_false_positive_rate':None,'scope':'NOT_EVALUABLE: the generator applies one transformation at a time and does not create a combined obfuscated-Hinglish holdout.'})
    pd.DataFrame(grouped).to_csv(reports/'final_language_robustness.csv',index=False)
    (reports/'final_message_hard_negative.json').write_text(json.dumps({'scope':'Synthetic text-only negative messages',
        'legitimate_messages':adversarial['hardened_normalized_text']['tn']+adversarial['hardened_normalized_text']['fp'],
        'false_positives':adversarial['hardened_normalized_text']['fp'],
        'false_positive_rate':adversarial['hardened_normalized_text']['false_positive_rate'],
        'notice':'Probe threshold 25 on authored message templates; this does not estimate payment-level hard-negative FPR.'},indent=2),encoding='utf-8')
    _write_metric_chart(pd.read_csv(reports/'final_model_comparison.csv'),reports/'figures'/'baseline_ablation.svg')
    print(json.dumps({'model_rows':len(pd.read_csv(reports/'final_model_comparison.csv')),
        'demo_cases':len(report['cases']),'adversarial_cases':len(rows)},indent=2))


def _write_metric_chart(frame,path):
    measured=frame[frame.status=='MEASURED'].copy();path.parent.mkdir(parents=True,exist_ok=True)
    width,height=1000,500;left,top=310,80;row_height=48;scale=520
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="32" y="36" font-size="22" font-family="Arial" font-weight="700">Synthetic temporal holdout: PR-AUC and recall</text>',
        '<text x="32" y="59" font-size="13" font-family="Arial" fill="#555">400 test rows, 33 positive labels; bars run from 0 to 1</text>']
    for index,row in measured.reset_index(drop=True).iterrows():
        y=top+index*row_height;name=html.escape(row['model'])
        parts.append(f'<text x="{left-12}" y="{y+16}" text-anchor="end" font-size="12" font-family="Arial">{name}</text>')
        for offset,key,color,label in ((0,'pr_auc','#2563eb','PR-AUC'),(18,'recall','#16a34a','Recall')):
            value=float(row[key]);bar=scale*value
            parts.append(f'<rect x="{left}" y="{y+offset}" width="{bar:.1f}" height="13" rx="3" fill="{color}"/>')
            parts.append(f'<text x="{left+bar+6:.1f}" y="{y+offset+11}" font-size="11" font-family="Arial">{value:.3f}</text>')
    legend_y=height-28
    parts.extend([f'<rect x="{left}" y="{legend_y-10}" width="14" height="14" fill="#2563eb"/><text x="{left+20}" y="{legend_y+2}" font-size="12" font-family="Arial">PR-AUC</text>',
        f'<rect x="{left+100}" y="{legend_y-10}" width="14" height="14" fill="#16a34a"/><text x="{left+120}" y="{legend_y+2}" font-size="12" font-family="Arial">Recall</text>','</svg>'])
    path.write_text('\n'.join(parts),encoding='utf-8')


if __name__=='__main__':main()
