"""Small in-process API latency/load smoke; not a production capacity test."""
import json
import statistics
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app

PAYMENT={'transaction':{'transaction_id':'T003072','sender_id':'A0610','receiver_id':'A0201',
 'amount':2076.99,'timestamp':'2026-01-01T00:16:24+00:00','device_id':'D0610','payment_type':'upi',
 'first_time_recipient':True,'payment_reason':'other'},'context':{'payment_reason':'other',
 'contacted_by_unknown_person':True,'urgent_payment_requested':True},
 'message':'Your bank account is at risk. Send a small payment now and keep it secret.'}

def main(count=30):
 latencies=[]; statuses={}
 with TestClient(app) as client:
  for _ in range(count):
   started=time.perf_counter()
   response=client.post('/api/v1/analyze-payment',json=PAYMENT)
   latencies.append((time.perf_counter()-started)*1000)
   statuses[str(response.status_code)]=statuses.get(str(response.status_code),0)+1
 latencies.sort()
 def percentile(p): return round(latencies[min(len(latencies)-1,int((len(latencies)-1)*p))],3)
 result={'notice':'Single-process TestClient smoke only; not a production throughput or concurrent-load guarantee.',
   'requests':count,'statuses':statuses,'latency_ms':{'mean':round(statistics.mean(latencies),3),
     'p50':percentile(.50),'p95':percentile(.95),'max':round(max(latencies),3)}}
 out=ROOT/'evaluation/day7_api_stress.json'
 out.write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result,indent=2))
if __name__=='__main__': main()
