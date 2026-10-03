"""Complement text evidence with structured narrative rules, without equating confidence to risk."""
from backend.app.config.context_config import (TEXT_WEIGHT, CONTEXT_SCENARIO_WEIGHT,
    MODEL_MIN_CONFIDENCE, MODEL_MIN_MARGIN, MIN_SCENARIO_EVIDENCE, MIN_CONTEXT_FOR_SCENARIO_RISK,
    SCENARIO_RISK_CONTEXT_FACTOR, SCENARIO_RISK_CONFIDENCE_FACTOR)
from backend.app.config.risk_config import clamp_score
from backend.app.models.scenario_model import ScenarioModel
from backend.app.schemas.context import PaymentContext
from backend.app.rules.scenario_rules import classify_scenario_rules
from backend.app.rules.context_rules import calculate_context_risk
from backend.app.utils.scenario_labels import get_scenario_labels, validate_scenario_label
from time import perf_counter
from backend.app.security.text_normalization import normalize_text_view
from types import SimpleNamespace


class ScenarioService:
    def __init__(self, model: ScenarioModel | None = None):
        self.model = model

    def predict_scenario(self, text: str | None, structured_context: PaymentContext, *, normalize: bool = True) -> dict:
        started=perf_counter()
        labels = get_scenario_labels()
        rules = classify_scenario_rules(structured_context)
        source_text = text or structured_context.user_message or ''
        text_view = normalize_text_view(source_text) if normalize else SimpleNamespace(
            normalized_text=source_text, transformations=())
        message = text_view.normalized_text.strip()
        text_result = self.model.predict(message) if message and self.model else None
        rule_matches = rules['scenario'] != labels[0]
        if text_result and rule_matches:
            context_weight = CONTEXT_SCENARIO_WEIGHT
            scores = {label: TEXT_WEIGHT * text_result['scores'][label] +
                      context_weight * rules['scores'][label] for label in labels}
            kind = 'structured_and_text_evidence'
        elif text_result:
            scores = text_result['scores'].copy()
            kind = text_result['confidence_kind']
        else:
            scores = rules['scores'].copy()
            kind = 'structured_rule_evidence' if rule_matches else 'insufficient_evidence'
        ranked = sorted(scores, key=scores.get, reverse=True)
        best = ranked[0]
        confidence = scores[best]
        codes = list(rules['reasons_by_label'][best])
        if text_result:
            codes.append('text_classifier_evidence')
            if rule_matches and rules['scenario'] != text_result['scenario']:
                codes.append('text_context_disagreement')
        if message and self.model is None:
            codes.append('text_model_unavailable_rule_fallback')
        margin = scores[ranked[0]] - scores[ranked[1]]
        if not rule_matches and best != labels[0] and (confidence < MODEL_MIN_CONFIDENCE or margin < MODEL_MIN_MARGIN):
            best = labels[0]
            confidence = max(scores[best], 1.0 - scores[ranked[0]])
            scores[best] = confidence
            codes.append('uncertain_text_scenario')
            kind = 'abstention_evidence'
        codes = list(dict.fromkeys(codes)) or ['insufficient_scenario_evidence']
        ranked = sorted(scores, key=scores.get, reverse=True)
        return {'type': best, 'confidence': round(float(confidence), 6), 'confidence_kind': kind,
                'top_scenarios': [{'scenario': label, 'score': round(float(scores[label]), 6)} for label in ranked[:3]],
                'reason_codes': codes, 'evidence': {
                    'structured_scenario': rules['scenario'], 'structured_strength': rules['confidence'],
                    'text_scenario': text_result['scenario'] if text_result else None,
                    'text_support_terms': text_result['support_terms'] if text_result else [],
                    'message_available': bool(message), 'text_model_available': self.model is not None,
                    'normalization_applied': bool(text_view.transformations),
                    'normalization_transformations': list(text_view.transformations)},
                'timing_ms':round((perf_counter()-started)*1000,3)}


def calculate_scenario_risk(predicted_scenario: str, confidence: float, context: PaymentContext,
                            new_recipient: bool = False) -> dict:
    """High narrative confidence needs matching structured evidence to raise risk.

    Normal/unknown always yields zero. Text alone classifies a story, but cannot
    establish structured circumstances. Weights are an illustrative evidence index.
    """
    validate_scenario_label(predicted_scenario)
    context_result = calculate_context_risk(context, new_recipient)
    rules = classify_scenario_rules(context)
    support = rules['scores'][predicted_scenario]
    evidence = {'matching_structured_strength': support, 'context_score': context_result['score']}
    if predicted_scenario == get_scenario_labels()[0]:
        return {'score': 0.0, 'reasons': ['normal_or_unknown_scenario'], 'evidence': evidence}
    if context_result['score'] < MIN_CONTEXT_FOR_SCENARIO_RISK or support < MIN_SCENARIO_EVIDENCE:
        return {'score': 0.0, 'reasons': ['scenario_lacks_supporting_context'], 'evidence': evidence}
    bounded_confidence = max(0.0, min(1.0, confidence))
    score = context_result['score'] * (SCENARIO_RISK_CONTEXT_FACTOR + SCENARIO_RISK_CONFIDENCE_FACTOR * bounded_confidence)
    return {'score': clamp_score(score), 'reasons': [f'{predicted_scenario}_context_supported'], 'evidence': evidence}
