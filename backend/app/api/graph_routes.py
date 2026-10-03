"""Point-in-time graph-risk lookup for an account."""
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import AwareDatetime
from typing import Annotated
router = APIRouter(prefix="/api/v1/accounts", tags=["graph risk"])
@router.get("/{account_id}/graph-risk")
def account_graph_risk(account_id: str, request: Request, at: Annotated[AwareDatetime | None, Query()] = None) -> dict:
    service = getattr(request.app.state, "graph_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Graph service unavailable")
    if at is None:
        at = service.builder.transactions.timestamp.max() + pd.Timedelta(nanoseconds=1)
    try:
        result = service.score_graph_risk(account_id, at)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"account_id": account_id, "graph_risk": result["score"], "risk_level": result["risk_level"], **result}
