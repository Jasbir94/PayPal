"""Evaluate text/psychology evidence on the fixed Day 7 synthetic corpus."""
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.services.psychology_service import PsychologyService
from backend.app.security.text_normalization import normalize_text_view

def summarize(rows):
 tp=sum(r['label']==1 and r['predicted']==1 for r in rows)
 fp=sum(r['label']==0 and r['predicted']==1 for r in rows)
 fn=sum(r['label']==1 and r['predicted']==0 for r in rows)
 tn=sum(r['label']==0 and r['predicted']==0 for r in rows)
 precision=tp/(tp+fp) if tp+fp else 0
 recall=tp/(tp+fn) if tp+fn else 0
 return {'n':len(rows),'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':precision,
   'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0,
   'false_positive_rate':fp/(fp+tn) if fp+tn else 0,
   'false_negative_rate':fn/(fn+tp) if fn+tp else 0}

def main():
 corpus=json.loads((ROOT/'data/adversarial/benchmark.json').read_text(encoding='utf-8'))['cases']
 service=PsychologyService()
 results=[]
 start=time.perf_counter()
 for case in corpus:
  label=int(case['label']=='scam')
  raw=service.analyze(case['text'],normalize=False)
  hardened=service.analyze(case['text'],normalize=True)
  # Message evidence index threshold is a declared probe threshold, not a calibrated
  # probability or production decision threshold.
  base_risk=raw['psychology_risk']; normalized_risk=hardened['psychology_risk']
  results.append({**case,'label':label,'baseline_score':base_risk,'hardened_score':normalized_risk,
     'baseline_prediction':int(base_risk>=25),'hardened_prediction':int(normalized_risk>=25),
     'transformations':hardened['normalization_transformations'],
     'failure_bucket':('false_negative' if label and normalized_risk<25 else
                       'false_positive' if not label and normalized_risk>=25 else 'correct')})
 elapsed=(time.perf_counter()-start)*1000
 def method(name):
  return summarize([{**r,'predicted':r[f'{name}_prediction']} for r in results])
 groups={}
 for field in ('difficulty','category','split','label'):
  groups[field]={}
  for key in sorted({str(r[field]) for r in results}):
   subset=[r for r in results if str(r[field])==key]
   groups[field][key]={'n':len(subset),'baseline':summarize([{**r,'predicted':r['baseline_prediction']} for r in subset]),
       'hardened':summarize([{**r,'predicted':r['hardened_prediction']} for r in subset])}
 latencies=[r['hardened_score'] for r in results]
 report={'title':'Day 7 synthetic message robustness evaluation','notice':corpus and 'Authored synthetic templates; message-level labels only. Scores are evidence indices, not probabilities. The threshold 25 is a probe threshold, not a policy recommendation.',
  'corpus_cases':len(results),'source_templates':50,'model':'PsychologyService rules-only unless model explicitly loaded; production model availability must be reported separately.',
  'threshold':25,'baseline_raw_text':method('baseline'),'hardened_normalized_text':method('hardened'),
  'by_group':groups,'latency_ms':{'total':round(elapsed,2),'mean_pair_ms':round(elapsed/len(results),3)},
  'failure_taxonomy':{'false_negatives':[r['case_id'] for r in results if r['failure_bucket']=='false_negative'],
                      'false_positives':[r['case_id'] for r in results if r['failure_bucket']=='false_positive'],
                      'false_negatives_by_category':{key:sum(r['failure_bucket']=='false_negative' and r['category']==key for r in results)
                          for key in sorted({r['category'] for r in results})}},
  'limitations':['No linked transaction/recipient labels; this is not payment-level fraud evaluation.',
    'Corpus is generated from 50 authored templates and has an artificial 50/50 class balance.',
    'Template families are split by source template: indices 0-19 development/validation and 20-24 holdout per class.',
    'Rule scores are deterministic evidence indices and must not be presented as calibrated probabilities.',
    'Hinglish coverage is limited to code-switched wrappers, not a broad linguistic benchmark.'],
  'results':results}
 out=ROOT/'evaluation/day7_adversarial_evaluation.json'
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k not in ('results','failure_taxonomy')},indent=2))
if __name__=='__main__': main()
