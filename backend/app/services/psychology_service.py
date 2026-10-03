"""Independent manipulation detection and transparent, temporary evidence scoring."""
from backend.app.config.psychology_config import (
    DEFAULT_THRESHOLD, BENIGN_SCORE_CAP, STRONG_RULE_THRESHOLD,
    RISK_STRONGEST_WEIGHT, RISK_ADDITIONAL_TECHNIQUE_POINTS, RISK_COUNT_BONUS_CAP,
    HIGH_RISK_COMBINATIONS, ML_ONLY_RISK_CAP, SCENARIO_TECHNIQUES,
    CONTEXT_OVERLAP_FIELDS, MAX_OVERLAP_DISCOUNT)
from backend.app.config.risk_config import clamp_score
from backend.app.models.psychology_model import PsychologyModel
from backend.app.rules.psychology_rules import detect_psychology_rules
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.schemas.context import PaymentContext
from backend.app.schemas.psychology import ManipulationScores
from time import perf_counter
from backend.app.security.text_normalization import normalize_text_view
from types import SimpleNamespace

def calculate_psychology_risk(scores: dict, thresholds: dict | None = None,
                             rule_scores: dict | None = None) -> dict:
    scores = ManipulationScores(scores).root
    thresholds = thresholds or dict.fromkeys(get_psychology_labels(), DEFAULT_THRESHOLD)
    thresholds = ManipulationScores(thresholds).root
    if rule_scores is not None:
        rule_scores = ManipulationScores(rule_scores).root
    active = [label for label in get_psychology_labels() if scores[label] >= thresholds[label] and scores[label] > 0]
    if not active:
        return {'psychology_risk': 0.0, 'detected_techniques': [], 'reason_codes': ['no_manipulation_detected']}
    strongest = max(scores[label] for label in active)
    score = RISK_STRONGEST_WEIGHT * strongest + min(
        RISK_COUNT_BONUS_CAP, RISK_ADDITIONAL_TECHNIQUE_POINTS * (len(active) - 1))
    combinations = [(code, bonus) for code, (labels, bonus) in HIGH_RISK_COMBINATIONS.items()
                    if set(labels).issubset(active) and (rule_scores is None or
                       all(rule_scores[label] >= STRONG_RULE_THRESHOLD for label in labels))]
    codes = ['manipulation_evidence_detected']
    if combinations:
        code, bonus = max(combinations, key=lambda item: item[1])
        score += bonus
        codes.append(code)
    if rule_scores is not None and not any(rule_scores[label] >= STRONG_RULE_THRESHOLD for label in active):
        score = min(score, ML_ONLY_RISK_CAP)
        codes.append('ml_only_risk_capped')
    return {'psychology_risk': clamp_score(score), 'detected_techniques': active, 'reason_codes': codes}

def scenario_psychology_alignment(scenario: str, psychology: dict) -> float:
    expected = SCENARIO_TECHNIQUES.get(scenario, ())
    active = set(psychology['detected_techniques'])
    return round(sum(psychology['scores'][label] for label in expected if label in active) / len(expected), 6) if expected else 0.0

def adjust_context_overlap(psychology: dict, context: PaymentContext) -> dict:
    active = psychology['detected_techniques']
    overlapping = [label for label in active if any(
        getattr(context, field) is True for field in CONTEXT_OVERLAP_FIELDS.get(label, ()))]
    total = sum(psychology['scores'][label] for label in active)
    fraction = sum(psychology['scores'][label] for label in overlapping) / total if total else 0.0
    factor = 1 - MAX_OVERLAP_DISCOUNT * fraction
    return {'adjusted_psychology_risk': clamp_score(psychology['psychology_risk'] * factor),
            'discount_factor': round(factor, 6), 'overlapping_techniques': overlapping,
            'reason_code': 'context_psychology_overlap_discounted' if overlapping else 'no_context_psychology_overlap'}

class PsychologyService:
    def __init__(self, model: PsychologyModel | None = None):
        self.model = model

    def analyze(self, message: str | None, *, normalize: bool = True) -> dict:
        started=perf_counter()
        if normalize:
            text_view = normalize_text_view(message)
            normalized_message = text_view.normalized_text
        else:
            normalized_message = message or ''
            text_view = SimpleNamespace(transformations=())
        rules = detect_psychology_rules(normalized_message)
        raw = self.model.predict_manipulation(normalized_message) if self.model else None
        thresholds = dict(self.model.thresholds) if self.model else dict.fromkeys(get_psychology_labels(), DEFAULT_THRESHOLD)
        scores = {label: max(rules['scores'][label], raw[label] if raw else 0.0)
                  for label in get_psychology_labels()}
        for label in rules['suppressed_techniques']:
            scores[label] = min(scores[label], BENIGN_SCORE_CAP)
        available = bool(message and message.strip())
        if not available:
            scores = dict.fromkeys(get_psychology_labels(), 0.0)
        result = calculate_psychology_risk(scores, thresholds, rules['scores'])
        codes = list(rules['reasons']) + result['reason_codes']
        codes += [label + '_model_evidence' for label in result['detected_techniques']
                  if raw and raw[label] >= thresholds[label] and rules['scores'][label] < thresholds[label]]
        if not self.model:
            codes.append('psychology_model_unavailable_rules_only')
        if not available:
            codes.append('psychology_message_unavailable')
        return {**result, 'scores': scores, 'rule_scores': rules['scores'],
                'ml_probabilities': raw, 'thresholds': thresholds,
                'reason_codes': list(dict.fromkeys(codes)),
                'evidence': {'rule_patterns': rules['evidence'],
                             'benign_suppressed_techniques': rules['suppressed_techniques'],
                             'combination_requires_strong_rule_support': True},
                'model_available': self.model is not None, 'message_available': available,
                'scores_kind': 'hybrid_evidence_not_calibrated_probabilities',
                'normalization_applied': bool(text_view.transformations),
                'normalization_transformations': list(text_view.transformations),
                'timing_ms':round((perf_counter()-started)*1000,3)}
