"""Business rules for delayed labels and prediction-time snapshots."""
from datetime import datetime, timezone
from backend.app.feedback.repository import FeedbackRepository


class FeedbackService:
    def __init__(self, repository: FeedbackRepository | None = None):
        self.repository = repository or FeedbackRepository()

    def record_prediction(self, attempt: dict, passive: dict, assessment: dict, contextual: dict) -> dict:
        tx=passive.get('transaction_details') or {}
        rec=passive.get('recipient_details') or {}
        graph=passive.get('graph_risk') or {}
        component=assessment.get('component_scores') or {}
        psychology=assessment.get('detected_psychological_techniques') or []
        evidence=tx.get('evidence') or {}
        rec_evidence=rec.get('evidence') or {}
        graph_features=graph.get('features') or {}
        context_evidence=(contextual.get('context_risk') or {}).get('evidence') or {}
        features={
            'transaction_risk':float(component.get('transaction',tx.get('score',0)) or 0),
            'transaction_confidence':.90 if evidence.get('baseline_available') else .55,
            'recipient_risk':float(component.get('recipient',rec.get('score',0)) or 0),
            'recipient_confidence':.88 if rec_evidence.get('history_count',0) else .55,
            'graph_risk':float(component.get('graph') or 0),
            'graph_confidence':.90 if graph.get('model_available') else .65,
            'graph_available':int(bool(graph)),
            'context_risk':float(component.get('context') or 0),
            'context_confidence':.88 if contextual.get('context_risk',{}).get('context_available') else 0,
            'context_available':int(bool(contextual.get('context_risk',{}).get('context_available'))),
            'scenario_risk':float(component.get('scenario') or 0),
            'scenario_confidence':float(contextual.get('scenario',{}).get('confidence',0) or 0),
            'scenario_available':int(bool(contextual.get('scenario',{}).get('evidence',{}).get('message_available') or contextual.get('context_risk',{}).get('context_available'))),
            'psychology_risk':float(component.get('psychology') or 0),
            'psychology_confidence':.82 if psychology else .65,
            'psychology_available':int(bool(contextual.get('psychology',{}).get('message_available'))),
            'amount_ratio_baseline':min(float(evidence.get('amount_ratio',1) or 1),20),
            'new_recipient_baseline':int(bool(evidence.get('first_time_recipient'))),
            'recipient_account_age_days':float(rec_evidence.get('account_age_days',0) or 0),
            'recipient_fan_in_24h':float(rec_evidence.get('unique_senders_24h',0) or 0),
            'recipient_outflow_ratio':float(rec_evidence.get('outgoing_ratio',0) or 0),
            'unknown_contact':int(bool(context_evidence.get('unknown_contact_evidence') or context_evidence.get('contacted_by_unknown_person'))),
            'urgency_detected':int('urgency' in psychology),
            'authority_detected':int('authority' in psychology),
            'fear_detected':int('fear' in psychology),
            'secrecy_detected':int('secrecy' in psychology),
            'graph_missing':int(not bool(graph)),
            'context_missing':int(not bool(contextual.get('context_risk',{}).get('context_available'))),
        }
        now=datetime.now(timezone.utc).isoformat()
        snapshot={'payment_attempt_id':attempt['payment_attempt_id'],'prediction_timestamp':now,
            'risk':assessment['app_scam_risk'],'calibrated_probability':assessment.get('calibrated_probability'),
            'confidence':assessment['confidence'],'scenario':assessment['likely_scam_scenario'],
            'scenario_confidence':contextual.get('scenario',{}).get('confidence'),
            'decision':assessment['decision'],'intervention':assessment.get('intervention'),
            'group_scores':{'user_side':assessment['user_side_risk'].get('score'),
                'recipient_side':assessment['recipient_network_risk'].get('score'),
                'manipulation_side':assessment['manipulation_risk'].get('score')},
            'model_versions':assessment.get('model_versions',{}),'reason_codes':assessment.get('reason_codes',[]),
            'detected_techniques':psychology,'features':features,
            'user_action_at_prediction':None,'fraud_label_at_prediction':'UNKNOWN'}
        saved=self.repository.record_snapshot(snapshot)
        version=','.join(sorted(set(saved.get('model_versions',{}).values())))
        self.repository.append_audit(attempt['payment_attempt_id'],'FULL_ANALYSIS_COMPLETED',
            {'risk':saved['risk'],'decision':saved['decision'],'snapshot_sha256':self.repository.get_feedback(attempt['payment_attempt_id'])['prediction_snapshot_sha256']},version,now)
        return saved

    def record_action(self, attempt_id: str, action: str, detail: dict | None = None):
        return self.repository.add_action(attempt_id,action,detail)

    def record_label(self, attempt_id: str, label: str, source: str, confidence: float,
                     label_timestamp: str | None = None, note: str | None = None):
        if self.repository.get_snapshot(attempt_id) is None:
            raise KeyError('A prediction snapshot is required before a delayed fraud label can be recorded.')
        return self.repository.add_label(attempt_id,label,source,confidence,label_timestamp,note)
