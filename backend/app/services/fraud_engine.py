"""Final APP scam assessment orchestrating existing point-in-time engines."""
from time import perf_counter
import logging
import os
import json
from backend.app.config.risk_config import (clamp_score, risk_level, FUSION_MODEL_VERSION,
    CONFIDENCE_FAMILY_PENALTY, CONFIDENCE_AGREEMENT_FLOOR, CONFIDENCE_AGREEMENT_WEIGHT)
from backend.app.fusion.evidence import canonicalize
from backend.app.fusion.grouping import group_signals
from backend.app.fusion.cross_layer_rules import score_cross_layer
from backend.app.fusion.protective_evidence import assess_protective_evidence, apply_protective_evidence
from backend.app.fusion.explanation import rank_reasons
from backend.app.fusion.decision_policy import recommend
from backend.app.fusion.calibration import FusionCalibrator
from backend.app.intervention.intervention_service import build_intervention
from backend.app.security.privacy import pseudonymize

LOGGER = logging.getLogger(__name__)
LOGGER.disabled = False
LOGGER.setLevel(logging.WARNING if os.getenv('APP_ENV','development').lower()=='demo' else logging.INFO)
if not LOGGER.handlers:
    _json_handler = logging.StreamHandler()
    _json_handler.setFormatter(logging.Formatter('%(message)s'))
    LOGGER.addHandler(_json_handler)
    LOGGER.propagate = False

class FraudEngine:
    def __init__(self, risk_service, calibrator=None):
        self.risk_service = risk_service
        if calibrator is not None:
            self.calibrator = calibrator
        else:
            try:
                self.calibrator = FusionCalibrator.load()
            except Exception as error:  # a missing/incompatible artifact keeps manual scoring available
                LOGGER.warning('Fusion calibration artifact unavailable; using manual grouped scoring (%s)',
                               type(error).__name__)
                self.calibrator = FusionCalibrator()

    def analyze_payment(self, transaction, context, message=None, contextual_result=None):
        started = perf_counter()
        context_obj = context
        result = contextual_result or self.risk_service.score_contextual(transaction, context_obj, message)
        tx, recipient = result['transaction_risk'], result['recipient_risk']
        graph = result.get('graph_risk')
        ctx, scenario, psych = result['context_risk'], result['scenario'], result['psychology']
        overlap = result['psychology_overlap_adjustment']
        context_data = context_obj.model_dump(mode='json')
        tx_data, rec_data = tx.get('evidence', {}), recipient.get('evidence', {})
        try:
            past = self.risk_service.repository.sender_history(
                transaction['sender_id'], __import__('pandas').Timestamp(transaction['timestamp']).tz_convert('UTC'),
                transaction['transaction_id'])
            tx_data = dict(tx_data)
            tx_data['prior_payments_to_recipient'] = int(past.receiver_id.eq(transaction['receiver_id']).sum())
        except (AttributeError, KeyError, ValueError):
            tx_data = dict(tx_data)
        transaction_signal = {'score': tx['score'], 'confidence': .90 if tx_data.get('baseline_available') else .55,
                              'available': True, 'evidence': tx_data}
        recipient_signal = {'score': recipient['score'], 'confidence': .88 if rec_data.get('history_count', 0) else .55,
                            'available': True, 'evidence': rec_data}
        graph_signal = {'score': graph['score'], 'confidence': .90 if graph.get('model_available') else .65,
                        'available': True, 'evidence': graph.get('features', {})} if graph else {
                            'score': None, 'confidence': 0.0, 'available': False, 'evidence': {}}
        context_available = bool(ctx.get('context_available'))
        context_signal = {'score': ctx['score'], 'confidence': .88 if context_available else .0,
                          'available': context_available, 'evidence': context_data}
        scenario_supported = scenario['type'] != 'normal_or_unknown' and scenario['confidence'] >= .4 and result['scenario_risk']['score'] > 0
        scenario_signal = {'score': result['scenario_risk']['score'],
                           'confidence': min(.85, max(.35, scenario['confidence'])) if scenario_supported else .25,
                           'available': context_available or scenario['evidence'].get('message_available', False),
                           'evidence': result['scenario_risk'].get('evidence', {})}
        message_available = bool(psych.get('message_available'))
        psychology_signal = {'score': overlap['adjusted_psychology_risk'],
                             'confidence': .82 if psych.get('model_available') else .65,
                             'available': message_available, 'evidence': psych.get('evidence', {})}
        groups, raw_score, weights = group_signals(transaction_signal, recipient_signal, graph_signal,
                                                   context_signal, scenario_signal, psychology_signal,
                                                   result['scenario_psychology_alignment'])
        cross = score_cross_layer(transaction_signal, recipient_signal, graph_signal, context_signal, scenario, psych)
        protective = assess_protective_evidence(transaction_signal, recipient_signal, context_signal)
        raw_score = clamp_score(raw_score + cross['bonus'])
        raw_score = apply_protective_evidence(raw_score, protective)
        features = {
            'user_side_score': groups['user_side']['score'] or 0,
            'recipient_side_score': groups['recipient_side']['score'] or 0,
            'manipulation_side_score': groups['manipulation_side']['score'] or 0,
            'transaction_risk': tx['score'], 'recipient_risk': recipient['score'],
            'graph_risk': graph['score'] if graph else 0,
            'context_risk': ctx['score'], 'scenario_risk': result['scenario_risk']['score'],
            'psychology_risk': overlap['adjusted_psychology_risk'],
            'scenario_psychology_alignment': result['scenario_psychology_alignment'],
            'cross_layer_bonus': cross['bonus'], 'protective_reduction': protective['reduction'],
            'available_family_count': sum(v['available'] for v in groups.values()),
            'graph_available': int(graph_signal['available']),
            'context_available': int(context_signal['available']),
            'scenario_available': int(scenario_signal['available']),
            'psychology_available': int(psychology_signal['available']),
            'amount_ratio_baseline': min(float(tx_data.get('amount_ratio', 1)), 20),
            'new_recipient_baseline': int(bool(tx_data.get('first_time_recipient'))),
        }
        probability = self.calibrator.predict(features)
        score = clamp_score(100 * probability) if probability is not None else raw_score
        available_count = sum(v['available'] for v in groups.values())
        avail_conf = [v['confidence'] for v in groups.values() if v['available']]
        agreement = max(0.0, 1 - (max([v['score'] for v in groups.values() if v['available']] or [0]) -
                                  min([v['score'] for v in groups.values() if v['available']] or [0])) / 100)
        confidence = max(0.0, min(1.0, (sum(avail_conf) / len(avail_conf) if avail_conf else 0) *
                                 (1 - CONFIDENCE_FAMILY_PENALTY * (3 - available_count)) *
                                 (CONFIDENCE_AGREEMENT_FLOOR + CONFIDENCE_AGREEMENT_WEIGHT * agreement)))
        neutral = {'within_expected_transaction_pattern', 'no_recipient_rule_signals',
                   'no_reported_context_risk_signals', 'insufficient_context_information',
                   'normal_or_unknown_scenario', 'scenario_lacks_supporting_context',
                   'psychology_message_unavailable', 'no_context_psychology_overlap',
                   'no_graph_rule_signals', 'text_classifier_evidence', 'text_context_disagreement'}
        reasons = [code for code in tx['reasons'] + recipient['reasons'] + (graph['reasons'] if graph else []) +
                   ctx['reasons'] + scenario['reason_codes'] + psych['reason_codes'] + cross['patterns']
                   if code not in neutral]
        if result['scenario_risk']['score'] > 0:
            reasons.append(scenario['type'])
        canonical = canonicalize(reasons)
        top = rank_reasons(canonical, cross, protective, groups)
        missing = []
        if not graph: missing.append('graph_risk')
        if not context_available: missing.append('structured_context')
        if not message_available: missing.append('message_text')
        if not tx_data.get('baseline_available'): missing.append('sender_baseline')
        decision = recommend(score, confidence, available_count,
            reason_codes=[item['id'] for item in canonical], context=context_data,
            recipient_score=recipient['score'])
        intervention = build_intervention(decision, scenario['type'],
            {'scenario':result['scenario_risk']['score']}, context_data.get('payment_reason','other'))
        versions = {'transaction': 'day2-rule+logistic-v1', 'recipient': 'day2-rule+logistic-v1',
                    'graph': 'day5-temporal-graph-v1' if graph else 'unavailable',
                    'scenario': 'day3-rules+optional-text-v1', 'psychology': 'day4-rules+optional-text-v1',
                    'fusion': self.calibrator.version if probability is not None else 'manual-grouped-v1'}
        latency_ms = (perf_counter() - started) * 1000
        component_latency = {'transaction': tx.get('timing_ms'),
            'recipient': recipient.get('timing_ms', {}).get('total'),
            'graph': graph.get('timing_ms', {}).get('total') if graph else None,
            'context': ctx.get('timing_ms'), 'scenario': scenario.get('timing_ms'),
            'psychology': psych.get('timing_ms'), 'full_engine': round(latency_ms, 3)}
        LOGGER.info(json.dumps({'event':'payment_risk_assessment', 'transaction_ref': pseudonymize(transaction['transaction_id']),
                     'risk_level': risk_level(score), 'decision': decision, 'model_versions': versions,
                     'latency_ms': round(latency_ms, 3), 'component_latency_ms':component_latency,
                     'reason_codes': [x['id'] for x in canonical]}, separators=(',',':')))
        return {'transaction_id': transaction['transaction_id'], 'app_scam_risk': score,
                'calibrated_probability': probability, 'confidence': round(confidence, 4),
                'risk_level': risk_level(score), 'likely_scam_scenario': scenario['type'],
                'user_side_risk': groups['user_side'], 'recipient_network_risk': groups['recipient_side'],
                'manipulation_risk': groups['manipulation_side'],
                'detected_psychological_techniques': psych['detected_techniques'], 'decision': decision,
                'intervention': intervention,
                'top_reasons': top, 'protective_evidence': protective['items'],
                'normalized_evidence': canonical, 'missing_evidence': missing,
                'scenario_psychology_alignment': result['scenario_psychology_alignment'],
                'model_versions': versions, 'component_scores': {'transaction': tx['score'],
                'recipient': recipient['score'], 'graph': graph['score'] if graph else None,
                'context': ctx['score'] if context_available else None, 'scenario': result['scenario_risk']['score'],
                'psychology': overlap['adjusted_psychology_risk'] if message_available else None,
                'cross_layer_bonus': cross['bonus'], 'protective_reduction': protective['reduction']},
                'component_latency_ms':component_latency,
                'reason_codes': [x['id'] for x in canonical], 'latency_ms': round(latency_ms, 3)}
