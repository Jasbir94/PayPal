"""Text-only analysis works when payment artifacts are unavailable."""
from fastapi import APIRouter, Request
from backend.app.schemas.psychology import PsychologyRequest, PsychologyResult
router = APIRouter(prefix='/api/v1/analyze', tags=['psychology'])
@router.post('/psychology', response_model=PsychologyResult)
def analyze_psychology(payload: PsychologyRequest, request: Request) -> dict:
    return request.app.state.psychology_service.analyze(payload.message)
