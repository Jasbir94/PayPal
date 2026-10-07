"""Research-only endpoints for delayed labels, audit, review, and monitoring."""
from fastapi import APIRouter, HTTPException, Request
import csv
from backend.app.feedback.schemas import FraudLabelRequest, UserActionRequest
from backend.app.review.schemas import ReviewOutcomeRequest
from backend.app.monitoring.metrics import prediction_summary,shadow_summary
from backend.app.monitoring.drift import compare_windows
from backend.app.monitoring.calibration import calibration_report
from backend.app.monitoring.scenario_monitor import scenario_summary
from backend.app.monitoring.health import data_quality_summary

feedback_router=APIRouter(prefix='/api/v1/feedback',tags=['research feedback'])
review_router=APIRouter(prefix='/api/v1/reviews',tags=['analyst review'])
monitor_router=APIRouter(prefix='/api/v1/monitoring',tags=['monitoring'])
research_router=APIRouter(prefix='/api/v1/research',tags=['research artifacts'])


def _feedback(request:Request):
    service=getattr(request.app.state,'feedback_service',None)
    if service is None:raise HTTPException(503,'Research feedback storage is unavailable.')
    return service


def _attempt(request:Request,attempt_id:str):
    simulator=getattr(request.app.state,'payment_simulator',None)
    if simulator is None:raise HTTPException(503,'Payment simulation is unavailable.')
    try:return simulator.get(attempt_id)
    except HTTPException:raise


@feedback_router.post('/{attempt_id}/user-action',status_code=201)
def record_user_action(attempt_id:str,payload:UserActionRequest,request:Request):
    service=_feedback(request)
    try:_attempt(request,attempt_id)
    except HTTPException:
        if not service.repository.has_attempt(attempt_id):raise
    return service.record_action(attempt_id,payload.action.value,{'detail_recorded':bool(payload.detail)})


@feedback_router.post('/{attempt_id}/label',status_code=201)
def record_delayed_label(attempt_id:str,payload:FraudLabelRequest,request:Request):
    service=_feedback(request)
    try:
        return service.record_label(attempt_id,payload.label.value,payload.source.value,payload.confidence,
            payload.label_timestamp.isoformat() if payload.label_timestamp else None,payload.note)
    except KeyError as error:
        raise HTTPException(404,'A prediction snapshot must exist before a label can be recorded.') from error


@feedback_router.get('/{attempt_id}')
def get_feedback(attempt_id:str,request:Request):
    repository=_feedback(request).repository
    if not repository.has_attempt(attempt_id):raise HTTPException(404,'Payment feedback not found.')
    return repository.get_feedback(attempt_id)


@feedback_router.get('/audit/verify')
def verify_audit_chain(request:Request):
    return _feedback(request).repository.verify_audit_chain()


@review_router.get('')
def list_review_queue(request:Request,status:str='OPEN'):
    repository=_feedback(request).repository
    reviews=repository.list_reviews(status if status in ('OPEN','CLOSED') else None)
    result=[]
    for review in reviews:
        snapshot=repository.get_snapshot(review['attempt_id']) or {}
        result.append({**review,'prediction':{
            'risk':snapshot.get('risk'),'confidence':snapshot.get('confidence'),
            'scenario':snapshot.get('scenario'),'decision':snapshot.get('decision'),
            'model_versions':snapshot.get('model_versions')}})
    return {'count':len(result),'reviews':result,'label':'LOCAL ANALYST DEMO DATA'}


@review_router.post('/{attempt_id}')
def complete_review(attempt_id:str,payload:ReviewOutcomeRequest,request:Request):
    repository=_feedback(request).repository
    result=repository.complete_review(attempt_id,payload.outcome,payload.note)
    if result is None:raise HTTPException(404,'Review item not found.')
    if result['status']!='CLOSED':raise HTTPException(409,'Review item has already been completed.')
    return result


@monitor_router.get('/summary')
def monitor_summary(request:Request):
    repository=_feedback(request).repository
    snapshots=sorted(repository.list_snapshots(),key=lambda x:x['prediction_timestamp'])
    split=len(snapshots)//2
    labels=repository.list_labeled_predictions()
    return {'label':'SYNTHETIC / RESEARCH MONITORING',
        'overall':prediction_summary(snapshots),'recent_window':prediction_summary(snapshots[split:]),
        'drift':compare_windows(snapshots[:split],snapshots[split:]),
        'scenario_and_feature_rates':scenario_summary(snapshots),
        'calibration':calibration_report(labels),
        'shadow':shadow_summary(repository.list_shadow_predictions()),
        'data_quality':data_quality_summary(snapshots),
        'feedback_counts':repository.aggregate_counts(),
        'automatic_retraining':'DISABLED'}


@research_router.get('/failures')
def failure_replays():
    """Return measured message-level adversarial errors; absent fields stay unavailable."""
    from backend.app.config.risk_config import PROJECT_ROOT
    path=PROJECT_ROOT/'reports'/'final_adversarial_results.csv'
    if not path.is_file():
        raise HTTPException(503,'The frozen adversarial evaluation report is unavailable.')
    with path.open('r',encoding='utf-8',newline='') as handle:
        rows=list(csv.DictReader(handle))
    failures=[]
    for row in rows:
        bucket=row.get('failure_bucket','')
        if bucket not in ('false_positive','false_negative'):
            continue
        expected=int(row['label'])
        predicted=int(row['hardened_prediction'])
        failures.append({'case_id':row.get('case_id'),'case_category':row.get('category'),
            'expected_label':'SCAM' if expected else 'BENIGN',
            'prediction':'SCAM' if predicted else 'BENIGN','risk':None,'confidence':None,
            'evidence':[],'failure_category':'MESSAGE_CLASSIFICATION',
            'failure_bucket':bucket})
    return {'label':'FROZEN SYNTHETIC ADVERSARIAL TEXT EVALUATION',
        'source':'reports/final_adversarial_results.csv',
        'note':'The source artifact has message-level predictions only; payment risk, confidence, and feature evidence are unavailable.',
        'count':len(failures),'false_positives':sum(x['failure_bucket']=='false_positive' for x in failures),
        'false_negatives':sum(x['failure_bucket']=='false_negative' for x in failures),
        'cases':failures[:100]}
