"""Freeze immutable, hashed Day 10 train/validation/test and robustness inputs."""
import hashlib
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from backend.app.config.risk_config import PROJECT_ROOT
from ml.fusion.build_dataset import OUT


DEST=PROJECT_ROOT/'data'/'benchmark'/'final_benchmark_v1'


def _write_json(path,data):
    text=json.dumps(data,indent=2,ensure_ascii=False,sort_keys=True)+'\n'
    path.write_text(text,encoding='utf-8')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def freeze():
    if DEST.exists() and any(DEST.iterdir()):
        raise FileExistsError(f'Frozen benchmark already exists: {DEST}')
    DEST.mkdir(parents=True,exist_ok=True)
    data=pd.read_csv(OUT).sort_values('timestamp',kind='mergesort').reset_index(drop=True)
    n=len(data);train=data.iloc[:int(.60*n)];validation=data.iloc[int(.60*n):int(.80*n)];test=data.iloc[int(.80*n):]
    hashes={}
    for name,frame in [('train',train),('validation',validation),('test',test)]:
        hashes[f'{name}.json']=_write_json(DEST/f'{name}.json',frame.to_dict('records'))
    adversarial=json.loads((PROJECT_ROOT/'data/adversarial/benchmark.json').read_text(encoding='utf-8'))['cases']
    adv=[row for row in adversarial if row.get('split')=='holdout']
    hard=[row for row in adv if row.get('label')=='legitimate']
    hashes['adversarial_test.json']=_write_json(DEST/'adversarial_test.json',adv)
    hashes['hard_negative_test.json']=_write_json(DEST/'hard_negative_test.json',hard)
    source_corpora=_source_profiles()
    metadata={'dataset_version':'app_shield_final_v1','frozen_at':datetime.now(timezone.utc).isoformat(),
        'source':'existing synthetic fusion dataset plus existing authored Day 7 adversarial corpus',
        'synthetic_generation_version':'day1-transactions-v1/day7-adversarial-v1',
        'sample_counts':{'train':len(train),'validation':len(validation),'test':len(test),
            'adversarial_test':len(adv),'hard_negative_test':len(hard)},
        'class_distribution':{'train':train.is_fraud.value_counts().to_dict(),
            'validation':validation.is_fraud.value_counts().to_dict(),'test':test.is_fraud.value_counts().to_dict()},
        'scam_categories':sorted(source_corpora['synthetic_transactions']['fraud_type_counts']),
        'language_distribution':'See category counts in adversarial_corpus_profile below; authored synthetic transforms, not broad language population data.',
        'source_corpora':source_corpora,
        'sha256':hashes,'test_policy':'Frozen copies of already generated synthetic inputs; do not tune on the test split. Existing reports have previously examined the source dataset.'}
    _write_json(DEST/'metadata.json',metadata)
    return metadata


def _source_profiles():
    transactions=pd.read_csv(PROJECT_ROOT/'data/synthetic/transactions.csv')
    adversarial=json.loads((PROJECT_ROOT/'data/adversarial/benchmark.json').read_text(encoding='utf-8'))['cases']
    fraud=transactions[transactions.is_fraud==1]
    return {'synthetic_transactions':{'rows':len(transactions),'fraud_rows':len(fraud),
            'fraud_type_counts':fraud.fraud_type.value_counts().sort_index().to_dict()},
        'adversarial_corpus':{'rows':len(adversarial),
            'variant_counts':pd.Series([row['category'] for row in adversarial]).value_counts().sort_index().to_dict(),
            'language_notice':'One transformation per authored message; Hinglish wrapper is limited and no combined obfuscated-Hinglish subset exists.'}}


def refresh_metadata():
    path=DEST/'metadata.json';metadata=json.loads(path.read_text(encoding='utf-8'))
    metadata['source_corpora']=_source_profiles()
    metadata['scam_categories']=sorted(metadata['source_corpora']['synthetic_transactions']['fraud_type_counts'])
    metadata['language_distribution']='See source_corpora.adversarial_corpus.variant_counts; authored synthetic transforms, not broad language population data.'
    path.write_text(json.dumps(metadata,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    return metadata


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh-metadata',action='store_true')
    args=parser.parse_args();result=refresh_metadata() if args.refresh_metadata else freeze()
    print(json.dumps(result,indent=2,ensure_ascii=False))
