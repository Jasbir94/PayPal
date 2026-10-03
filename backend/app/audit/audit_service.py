"""Small typed wrapper around the hash-chained feedback repository audit log."""
from backend.app.audit.audit_models import AuditEventType
from backend.app.feedback.repository import FeedbackRepository


class AuditService:
    def __init__(self, repository: FeedbackRepository):
        self.repository=repository

    def record(self, attempt_id: str, event_type: AuditEventType | str,
               payload: dict | None = None, model_version: str | None = None):
        return self.repository.append_audit(attempt_id,str(event_type),payload,model_version)

    def verify_chain(self):
        return self.repository.verify_audit_chain()
