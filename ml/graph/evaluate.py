"""Recipient/graph comparisons, account and full-pipeline ablations."""
import json
from time import perf_counter
import numpy as np
import pandas as pd
from backend.app.database.repository import DataRepository
from backend.app.graph.data import load_graph_builder
from backend.app.models.graph_model import GraphModel
from backend.app.models.recipient_model import RecipientModel
from backend.app.models.transaction_model import TransactionModel
from backend.app.services.recipient_service import RecipientService
from backend.app.services.transaction_service import TransactionService
from backend.app.services.risk_service import RiskService
from backend.app.services.graph_service import GraphService
from backend.app.services.scenario_service import ScenarioService
from backend.app.models.scenario_model import ScenarioModel
from backend.app.services.psychology_service import PsychologyService
from backend.app.models.psychology_model import PsychologyModel
from backend.app.services.grouped_risk import combine_recipient_graph, combine_grouped_risk
from backend.app.features.recipient_features import calculate_recipient_features
from backend.app.schemas.context import PaymentContext
from backend.app.config.graph_config import GRAPH_FEATURE_PATH, GRAPH_REPORT_DIR, GRAPH_ML_FEATURES
from ml.graph.metrics import binary_metrics, validation_threshold

def evaluate():
    data = pd.read_csv(GRAPH_FEATURE_PATH)
    repository = DataRepository.load()
    builder = load_graph_builder(repository)
    graph_model = GraphModel()
    graph_service = GraphService(builder, graph_model)
    recipient_model = RecipientModel()
    recipient_service = RecipientService(recipient_model, repository)
    risks, recipient_probabilities, graph_scores, recipient_scores = [], [], [], []
    for row in data.itertuples():
        stamp = pd.Timestamp(row.at)
        history = builder.transactions[
            (builder.transactions.timestamp < stamp) &
            (builder.transactions.timestamp >= stamp - pd.Timedelta(hours=24)) &
            (builder.transactions.sender_id.eq(row.account_id) | builder.transactions.receiver_id.eq(row.account_id))]
        # Reuse Day 2 aggregation; both models see the same historical transfer set.
        features = calculate_recipient_features(repository.account(row.account_id, stamp), history, stamp)
        result = recipient_service.score_features(features)
        recipient_probabilities.append(recipient_model.probability(features))
        recipient_scores.append(result['score'])
        graph_scores.append(graph_service.score_graph_risk(row.account_id, stamp)['score'])
    graph_probabilities = graph_model.pipeline.predict_proba(data[GRAPH_ML_FEATURES])[:, 1]
    recipient_probabilities = np.asarray(recipient_probabilities)
    combined = .7 * np.maximum(graph_probabilities, recipient_probabilities) + .3 * np.minimum(graph_probabilities, recipient_probabilities)
    validation, test = data.split.eq('validation').to_numpy(), data.split.eq('test').to_numpy()
    y = data.is_known_mule.to_numpy()
    comparisons = {}
    for name, probability in [('recipient_only', recipient_probabilities), ('graph_only', graph_probabilities),
                              ('recipient_plus_graph', combined)]:
        threshold = graph_model.threshold if name == 'graph_only' else validation_threshold(y[validation], probability[validation])[0]
        comparisons[name] = binary_metrics(y[test], probability[test], threshold)
    # Deployed score ablation uses synthetic suspicious-network truth, distinct from sparse known labels.
    truth = data.is_suspicious.to_numpy()
    combined_scores = np.array([combine_recipient_graph(a, b) for a, b in zip(recipient_scores, graph_scores)])
    deployed = {name: binary_metrics(truth[test], np.asarray(scores)[test] / 100, .60)
                for name, scores in [('recipient_only', recipient_scores), ('graph_only', graph_scores),
                                     ('recipient_plus_graph', combined_scores)]}
    full_service = RiskService(repository, TransactionService(TransactionModel()), recipient_service,
        ScenarioService(ScenarioModel()), PsychologyService(PsychologyModel()))
    examples, timings = [], []
    for row in data[data.split.eq('test')].itertuples():
        sender = 'A0001'
        if sender == row.account_id:
            sender = 'A0000'
        payment = dict(transaction_id=f'ABL-{row.account_id}', sender_id=sender,
            receiver_id=row.account_id, amount=3500, timestamp=row.at, device_id='D0001', payment_type='bank_transfer',
            first_time_recipient=False, payment_reason='other')
        context = PaymentContext(payment_reason='shopping', contacted_by_unknown_person=False,
            claimed_authority=False, authority_type='none', threatened_consequences=False,
            urgent_payment_requested=False, promised_profit=False, requested_secrecy=False)
        message = 'I am making an ordinary purchase payment; there is no urgency or promised reward.'
        started = perf_counter()
        contextual = full_service.score_contextual(payment, context, message)
        graph = graph_service.score_graph_risk(row.account_id, row.at)
        without = combine_grouped_risk(contextual)
        with_graph = combine_grouped_risk(contextual, graph['score'])
        timings.append((perf_counter() - started) * 1000)
        suspicious = bool(row.is_suspicious)  # evaluation target, read only after scoring
        examples.append({'account_id': row.account_id, 'is_suspicious': int(suspicious),
                         'without_graph': without['overall_risk'], 'with_graph': with_graph['overall_risk']})
    actual = [row['is_suspicious'] for row in examples]
    ablation = {name: binary_metrics(actual, [row[name] / 100 for row in examples], .60)
                for name in ('without_graph', 'with_graph')}
    report = {'target': 'is_known_mule', 'comparisons': comparisons,
        'deployed_score_target': 'is_suspicious', 'deployed_score_comparison': deployed,
        'full_ablation': ablation, 'full_ablation_examples': examples,
        'full_ablation_note': 'All test accounts receive the same neutral structured context and message, independent of target labels. The synthetic overlay topology was generated using synthetic suspicious-profile membership, so this controlled benchmark is still not independent real-world validation.',
        'hard_negative_results': [
            {'account_id': row.account_id, 'role': row.role, 'graph_score': graph_scores[index],
             'recipient_score': recipient_scores[index]}
            for index, row in enumerate(data.itertuples()) if row.split == 'test' and row.role not in ('mule', 'personal')],
        'api_core_latency_ms': {'median': float(np.median(timings)), 'p95': float(np.quantile(timings, .95))},
        'limitations': graph_model.metadata['limitations']}
    GRAPH_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (GRAPH_REPORT_DIR / 'evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('comparisons', 'deployed_score_comparison', 'full_ablation', 'api_core_latency_ms')}, indent=2))
    return report

if __name__ == '__main__':
    evaluate()
