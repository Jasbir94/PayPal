"""Versioned model registry with conservative, explicit champion promotion."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
from threading import RLock
from backend.app.config.risk_config import PROJECT_ROOT

REGISTRY_PATH=PROJECT_ROOT/'models'/'registry'/'registry.json'
_LOCK=RLock()


class RegistryError(ValueError):pass


def load_registry(path=REGISTRY_PATH):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_registry(registry,path=REGISTRY_PATH):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(registry,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def register_challenger(version:str,record:dict,path=REGISTRY_PATH):
    with _LOCK:
        registry=load_registry(path);fusion=registry['models']['fusion']
        if version in fusion['versions']:raise RegistryError('Model versions are immutable and cannot be overwritten.')
        if record.get('status')!='CHALLENGER':raise RegistryError('New candidate must be registered with CHALLENGER status.')
        for key in ('artifact_path','calibration_path'):
            if key in record:
                resolved=(PROJECT_ROOT/record[key]).resolve()
                if PROJECT_ROOT.resolve() not in resolved.parents or not resolved.is_file():
                    raise RegistryError(f'{key} must point to an existing project-local artifact.')
        fusion['versions'][version]=record
        registry['updated_at']=datetime.now(timezone.utc).isoformat()
        save_registry(registry,path)
        return registry


def promotion_checks(candidate:dict,champion:dict,policy:dict) -> dict:
    cm=candidate.get('metrics') or {};am=champion.get('metrics') or {};checks={}
    def delta(name,minimum):
        left,right=cm.get(name),am.get(name)
        checks[name]=None if left is None or right is None else float(left)>=float(right)+float(minimum)
    delta('pr_auc',policy['minimum_pr_auc_delta'])
    delta('recall',policy['minimum_recall_delta'])
    fpr=cm.get('false_positive_rate')
    checks['false_positive_rate']=None if fpr is None else float(fpr)<=policy['maximum_false_positive_rate']
    brier,active_brier=cm.get('brier'),am.get('brier')
    checks['brier']=None if brier is None or active_brier is None else float(brier)<=float(active_brier)+policy['maximum_brier_delta']
    regressions=cm.get('scenario_regressions')
    checks['scenario_regressions']=None if regressions is None else len(regressions)==0
    hard_fpr=cm.get('hard_negative_fpr')
    checks['hard_negative_fpr']=None if hard_fpr is None else float(hard_fpr)<=policy['maximum_hard_negative_fpr']
    checks['all_required_metrics_present']=all(value is not None for value in checks.values())
    checks['eligible']=all(value is True for value in checks.values())
    return checks


def promote(version:str,explicitly_approved:bool,comparison:dict|None=None,path=REGISTRY_PATH) -> dict:
    if not explicitly_approved:raise RegistryError('Promotion requires explicit --approve after reviewing the comparison report.')
    if comparison is None:raise RegistryError('A same-holdout champion/challenger comparison is required for promotion.')
    with _LOCK:
        registry=load_registry(path);fusion=registry['models']['fusion']
        candidate=fusion['versions'].get(version)
        if candidate is None or candidate.get('status')!='CHALLENGER':raise RegistryError('Only a registered CHALLENGER can be promoted.')
        active=fusion['versions'][fusion['active_version']]
        if comparison.get('candidate_version')!=version or comparison.get('active_version')!=fusion['active_version']:
            raise RegistryError('Comparison does not match the currently registered champion and challenger.')
        if not comparison.get('same_holdout') or not comparison.get('holdout_fingerprint'):
            raise RegistryError('Promotion requires an identical, fingerprinted temporal holdout.')
        checks=promotion_checks({'metrics':comparison.get('challenger_metrics')},
            {'metrics':comparison.get('active_metrics')},registry['promotion_policy'])
        checks['same_holdout']=True
        checks['eligible']=checks['eligible'] and checks['same_holdout']
        if not checks['eligible']:raise RegistryError('Promotion guardrails failed or evidence is insufficient: '+json.dumps(checks,sort_keys=True))
        candidate['metrics']=comparison['challenger_metrics']
        candidate['promotion_comparison']={'holdout_fingerprint':comparison['holdout_fingerprint'],
            'active_version':comparison['active_version'],'checks':checks}
        active['status']='RETIRED';candidate['status']='ACTIVE'
        candidate['promoted_at']=datetime.now(timezone.utc).isoformat()
        fusion['active_version']=version
        registry['updated_at']=datetime.now(timezone.utc).isoformat()
        save_registry(registry,path)
        return {'active_version':version,'checks':checks,'registry':registry}
