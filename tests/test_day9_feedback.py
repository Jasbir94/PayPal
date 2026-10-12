from datetime import datetime,timedelta,timezone
import pytest
from backend.app.feedback.repository import FeedbackRepository,SnapshotConflict
from backend.app.feedback.label_policy import training_eligibility
from backend.app.feedback.models import LabelSource


def test_snapshot_is_immutable_and_audit_chain_verifies():
    repository=FeedbackRepository(':memory:')
    snapshot={'payment_attempt_id':'attempt-1','prediction_timestamp':datetime.now(timezone.utc).isoformat(),'risk':42}
    repository.record_snapshot(snapshot)
    with pytest.raises(SnapshotConflict):repository.record_snapshot({**snapshot,'risk':43})
    repository.append_audit('attempt-1','TEST_EVENT',{'safe':True})
    assert repository.verify_audit_chain()['valid'] is True


def test_user_behavior_and_untrusted_labels_never_become_training_truth():
    timestamp=datetime.now(timezone.utc)-timedelta(days=30)
    for label,source,confidence in [('UNKNOWN',LabelSource.USER_REPORT.value,1),
            ('CONFIRMED_SCAM',LabelSource.USER_REPORT.value,1),
            ('CONFIRMED_SCAM',LabelSource.ANALYST_CONFIRMED.value,.8)]:
        assert not training_eligibility(label,source,confidence,timestamp)[0]


def test_only_mature_high_confidence_trusted_final_label_is_trainable():
    timestamp=datetime.now(timezone.utc)-timedelta(days=8)
    eligible,reason=training_eligibility('CONFIRMED_SCAM',LabelSource.ANALYST_CONFIRMED.value,.95,timestamp)
    assert eligible and reason=='eligible'
    assert not training_eligibility('CONFIRMED_MULE',LabelSource.SYNTHETIC_GROUND_TRUTH.value,.95,
        datetime.now(timezone.utc)-timedelta(days=2))[0]


def test_shadow_records_are_persistent_and_summarized_as_unlabeled():
    from backend.app.monitoring.metrics import shadow_summary
    repository=FeedbackRepository(':memory:')
    repository.add_shadow_prediction('attempt-1',{'model_version':'candidate-v1','risk':61,'decision':'WARN'})
    result=shadow_summary(repository.list_shadow_predictions())
    assert result['prediction_count']==1
    assert result['accuracy_status']=='NOT_EVALUABLE_WITHOUT_MATURE_TRUSTED_LABELS'


def test_default_feedback_repository_is_transient_without_database_url(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('APP_SHIELD_FEEDBACK_DB', raising=False)
    repository=FeedbackRepository()
    assert repository.path == ':memory:'
    assert repository.aggregate_counts()['user_actions'] == 0
