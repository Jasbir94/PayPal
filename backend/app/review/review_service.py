"""Persistent analyst review queue with outcomes separate from ground-truth labels."""
from backend.app.feedback.repository import FeedbackRepository
from backend.app.review.review_policy import review_reason


class ReviewService:
    def __init__(self, repository: FeedbackRepository):
        self.repository=repository

    def enqueue_if_needed(self, attempt_id: str, assessment: dict,
                          passive: dict | None = None, degraded: bool = False):
        reason=review_reason(assessment,passive,degraded)
        if not reason:return None
        return self.repository.upsert_review(attempt_id,reason)

    def queue(self, status: str | None = 'OPEN'):
        return self.repository.list_reviews(status)

    def complete(self, attempt_id: str, outcome: str, note: str | None = None):
        return self.repository.complete_review(attempt_id,outcome,note)
