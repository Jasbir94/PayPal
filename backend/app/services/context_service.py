"""Payment context engine wrapping the independently testable rule scorer."""
from backend.app.schemas.context import PaymentContext
from backend.app.rules.context_rules import calculate_context_risk
from time import perf_counter


class ContextService:
    def calculate_context_risk(self, context: PaymentContext, new_recipient: bool = False) -> dict:
        started=perf_counter()
        result=calculate_context_risk(context, new_recipient)
        result['timing_ms']=round((perf_counter()-started)*1000,3)
        return result
