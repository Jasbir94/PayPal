"""Preliminary fusion of two modules, not a final APP fraud probability."""
import pandas as pd
from backend.app.config.risk_config import TRANSACTION_WEIGHT, RECIPIENT_WEIGHT, clamp_score, risk_level
from backend.app.database.repository import DataRepository
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService
from backend.app.services.context_service import ContextService
from backend.app.services.scenario_service import ScenarioService, calculate_scenario_risk
from backend.app.schemas.context import PaymentContext
from backend.app.config.context_config import EXTENDED_WEIGHTS, PRESERVE_DAY2_WITHOUT_CONTEXT
from backend.app.config.psychology_config import DAY4_WEIGHTS
from backend.app.services.psychology_service import PsychologyService, scenario_psychology_alignment, adjust_context_overlap
from backend.app.services.graph_service import GraphService
from backend.app.services.grouped_risk import combine_grouped_risk


def combine_risk(transaction: dict, recipient: dict) -> dict:
    score = clamp_score(TRANSACTION_WEIGHT * transaction['score'] + RECIPIENT_WEIGHT * recipient['score'])
    reasons = list(dict.fromkeys(transaction['reasons'] + recipient['reasons']))
    return {'transaction_risk': transaction['score'], 'recipient_risk': recipient['score'],
            'preliminary_risk': score, 'risk_level': risk_level(score), 'reasons': reasons,
            'transaction_details': transaction, 'recipient_details': recipient}


class RiskService:
    def __init__(self, repository: DataRepository, transaction: TransactionService,
                 recipient: RecipientService, scenario: ScenarioService | None = None,
                 psychology: PsychologyService | None = None, graph: GraphService | None = None):
        self.repository, self.transaction, self.recipient = repository, transaction, recipient
        self.context = ContextService()
        self.scenario = scenario or ScenarioService()
        self.psychology = psychology or PsychologyService()
        self.graph = graph

    def score(self, payment: dict) -> dict:
        stamp = pd.Timestamp(payment['timestamp']).tz_convert('UTC')
        if stamp < self.repository.start:
            raise ValueError('Scoring before the synthetic observation window is unsupported')
        profile = self.repository.account(payment['sender_id'], stamp)
        self.repository.account(payment['receiver_id'], stamp)
        history = self.repository.sender_history(payment['sender_id'], stamp, payment['transaction_id'])
        transaction = self.transaction.score_transaction(payment, history, profile)
        recipient = self.recipient.score_recipient(payment['receiver_id'], stamp, payment['transaction_id'])
        return combine_risk(transaction, recipient)


    def score_contextual(self, payment: dict, context: PaymentContext, message: str | None = None) -> dict:
        preliminary = self.score(payment)
        transaction, recipient = preliminary['transaction_details'], preliminary['recipient_details']
        new_recipient = bool(transaction['evidence']['first_time_recipient'])
        context_result = self.context.calculate_context_risk(context, new_recipient)
        scenario = self.scenario.predict_scenario(message, context)
        scenario_risk = calculate_scenario_risk(scenario['type'], scenario['confidence'], context, new_recipient)
        score = clamp_score(EXTENDED_WEIGHTS['transaction'] * transaction['score'] +
            EXTENDED_WEIGHTS['recipient'] * recipient['score'] +
            EXTENDED_WEIGHTS['context'] * context_result['score'] +
            EXTENDED_WEIGHTS['scenario'] * scenario_risk['score'])
        retained_without_context = PRESERVE_DAY2_WITHOUT_CONTEXT and not context_result['context_available']
        if retained_without_context:
            score = max(score, preliminary['preliminary_risk'])
        codes = list(dict.fromkeys(transaction['reasons'] + recipient['reasons'] +
                                  context_result['reasons'] + scenario['reason_codes'] + scenario_risk['reasons']))
        if retained_without_context:
            codes.append('day2_risk_retained_missing_context')
        psychology = self.psychology.analyze(message or context.user_message)
        overlap = adjust_context_overlap(psychology, context)
        extended = score
        if psychology['message_available']:
            extended = clamp_score(DAY4_WEIGHTS['transaction'] * transaction['score'] +
                DAY4_WEIGHTS['recipient'] * recipient['score'] +
                DAY4_WEIGHTS['context'] * context_result['score'] +
                DAY4_WEIGHTS['scenario'] * scenario_risk['score'] +
                DAY4_WEIGHTS['psychology'] * overlap['adjusted_psychology_risk'])
            if retained_without_context:
                extended = max(extended, preliminary['preliminary_risk'])
        else:
            codes.append('day3_risk_retained_missing_psychology_message')
        codes = list(dict.fromkeys(codes + psychology['reason_codes'] + [overlap['reason_code']]))
        graph = self.graph.score_graph_risk(payment['receiver_id'], payment['timestamp'], payment.get('transaction_id')) if self.graph else None
        if graph:
            codes = list(dict.fromkeys(codes + graph['reasons']))
        groups = combine_grouped_risk({'transaction_risk': transaction, 'recipient_risk': recipient, 'context_risk': context_result, 'scenario_risk': scenario_risk, 'psychology': psychology, 'psychology_overlap_adjustment': overlap}, graph['score'] if graph else None)
        return {'transaction_risk': transaction, 'recipient_risk': recipient, 'context_risk': context_result,
                'scenario': scenario, 'scenario_risk': scenario_risk, 'extended_preliminary_risk': score,
                'psychology': psychology, 'scenario_psychology_alignment': scenario_psychology_alignment(scenario['type'], psychology),
                'psychology_overlap_adjustment': overlap, 'extended_risk': extended,
                'risk_level': risk_level(score), 'extended_risk_level': risk_level(extended), 'graph_risk': graph, 'reason_codes': codes, **groups, 'overall_risk_level': risk_level(groups['overall_risk'])}
