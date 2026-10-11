"""Repository-local dataset inventory and leakage checks for Stage 1.

This module inspects only checked-in synthetic datasets. It never downloads data
or treats a dataset label as a model input.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from backend.app.config.graph_config import GRAPH_ML_FEATURES
from backend.app.config.risk_config import RECIPIENT_FEATURES, TRANSACTION_FEATURES
from backend.app.features.text_features import normalize_text

TEXT_SPLITS = (
    ('data/synthetic/scam_messages.csv', 'text', 'split', 'template_id'),
    ('data/synthetic/psychology_messages.csv', 'text', 'split', 'source_families'),
    ('data/adversarial/benchmark.json', 'text', 'split', 'source_template'),
)
FROZEN_SPLITS = ('train.json', 'validation.json', 'test.json')
FORBIDDEN_PREDICTORS = {
    'target', 'is_fraud', 'fraud_type', 'is_suspicious', 'is_known_mule',
    'label', 'scenario_label', 'split', 'transaction_id', 'entity_id', 'account_id',
}


def _json_rows(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(value, list):
        return value
    for key in ('cases', 'records', 'transactions'):
        if isinstance(value, dict) and isinstance(value.get(key), list):
            return value[key]
    return []


def _group_values(value) -> list[str]:
    if pd.isna(value):
        return []
    return [part.strip() for part in str(value).split('|') if part.strip()]


def validate_text_partitions(frame: pd.DataFrame, *, text_column: str,
                             split_column: str, group_column: str) -> dict:
    """Reject normalized-message or source-family overlap across partitions."""
    required = {text_column, split_column, group_column}
    if missing := required - set(frame.columns):
        raise ValueError(f'Missing split validation columns: {sorted(missing)}')
    if frame[list(required)].isna().any().any():
        raise ValueError('Text split fields contain missing values')
    normalized = frame[text_column].astype(str).map(normalize_text)
    if normalized.eq('').any():
        raise ValueError('Text corpus contains empty normalized examples')
    overlap = pd.DataFrame({'text': normalized, 'split': frame[split_column]}).groupby('text').split.nunique()
    cross_split_exact = int((overlap > 1).sum())
    groups = frame[[split_column, group_column]].copy()
    groups[group_column] = groups[group_column].map(_group_values)
    groups = groups.explode(group_column).dropna()
    group_overlap = groups.groupby(group_column)[split_column].nunique()
    cross_split_groups = int((group_overlap > 1).sum())
    if cross_split_exact:
        raise ValueError(f'{cross_split_exact} normalized messages cross dataset partitions')
    if cross_split_groups:
        raise ValueError(f'{cross_split_groups} source groups cross dataset partitions')
    duplicates_within_split = int(normalized.duplicated().sum())
    return {'rows': int(len(frame)), 'normalized_duplicate_rows': duplicates_within_split,
            'cross_split_normalized_messages': cross_split_exact,
            'source_groups': int(groups[group_column].nunique()),
            'cross_split_source_groups': cross_split_groups,
            'split_counts': {str(k): int(v) for k, v in frame[split_column].value_counts().items()}}


def verify_frozen_benchmark(root: Path) -> dict:
    """Verify split counts, canonical hashes and chronological boundaries.

    Canonical LF hashing makes the metadata stable across Windows CRLF and Unix
    LF checkouts without rewriting the frozen artifacts.
    """
    directory = root / 'data/benchmark/final_benchmark_v1'
    metadata = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
    profiles, ids, bounds = {}, {}, {}
    for role in ('train', 'validation', 'test'):
        rows = _json_rows(directory / f'{role}.json')
        expected = int(metadata['sample_counts'][role])
        if len(rows) != expected:
            raise ValueError(f'{role} row count {len(rows)} differs from metadata {expected}')
        frame = pd.DataFrame(rows)
        ids[role] = set(frame.transaction_id.astype(str))
        stamps = pd.to_datetime(frame.timestamp, utc=True, errors='coerce')
        if stamps.isna().any():
            raise ValueError(f'{role} contains invalid timestamps')
        bounds[role] = (stamps.min(), stamps.max())
        profiles[role] = {'rows': len(frame), 'class_distribution': {
            str(k): int(v) for k, v in frame.is_fraud.value_counts().sort_index().items()},
            'start': bounds[role][0].isoformat(), 'end': bounds[role][1].isoformat()}
    if ids['train'] & ids['validation'] or ids['train'] & ids['test'] or ids['validation'] & ids['test']:
        raise ValueError('Frozen transaction IDs overlap across splits')
    if not (bounds['train'][1] < bounds['validation'][0] and
            bounds['validation'][1] < bounds['test'][0]):
        raise ValueError('Frozen transaction splits are not strictly chronological')
    hash_checks = {}
    for name, expected in metadata['sha256'].items():
        content = (directory / name).read_bytes().replace(b'\r\n', b'\n')
        actual = hashlib.sha256(content).hexdigest()
        hash_checks[name] = actual == expected
        if actual != expected:
            raise ValueError(f'Frozen dataset hash mismatch: {name}')
    return {'dataset_version': metadata['dataset_version'], 'splits': profiles,
            'id_overlap': 0, 'chronological': True, 'canonical_hashes_valid': hash_checks,
            'scenario_modality_coverage': {
                'scenario_available_rows': int(sum(row['scenario_available'] for row in _json_rows(directory / 'train.json'))),
                'psychology_available_rows': int(sum(row['psychology_available'] for row in _json_rows(directory / 'train.json'))),
                'graph_available_rows': int(sum(row['graph_available'] for row in _json_rows(directory / 'train.json')))}}


def _csv_profile(path: Path) -> dict:
    frame = pd.read_csv(path, low_memory=False)
    result = {'rows': int(len(frame)), 'columns': list(frame.columns),
        'duplicate_rows': int(frame.duplicated().sum()),
        'missing_by_column': {str(k): int(v) for k, v in frame.isna().sum().items() if v}}
    for column in frame.columns:
        name = column.casefold()
        if any(token in name for token in ('timestamp', 'created_at', 'observed_at')):
            values = pd.to_datetime(frame[column], errors='coerce', utc=True)
            if values.notna().any():
                result['date_ranges'] = result.get('date_ranges', {})
                result['date_ranges'][column] = [values.min().isoformat(), values.max().isoformat()]
    for column in ('is_fraud', 'fraud_type', 'scenario_label', 'language', 'split',
                   'is_suspicious', 'is_known_mule', 'target', 'neutral'):
        if column in frame:
            result.setdefault('distributions', {})[column] = {
                str(k): int(v) for k, v in frame[column].value_counts(dropna=False).items()}
    return result


def audit_repository(root: Path) -> dict:
    """Build a reproducible inventory and run hard leakage invariants."""
    root = Path(root)
    inventory = {}
    for path in sorted((root / 'data').rglob('*.csv')):
        inventory[path.relative_to(root).as_posix()] = _csv_profile(path)
    for relative, text_col, split_col, group_col in TEXT_SPLITS:
        path = root / relative
        if path.suffix == '.json':
            frame = pd.DataFrame(_json_rows(path))
            inventory[relative] = {'rows': int(len(frame)), 'columns': list(frame.columns),
                'duplicate_rows': int(frame.duplicated().sum())}
        else:
            frame = pd.read_csv(path, low_memory=False)
        inventory[relative]['split_audit'] = validate_text_partitions(frame,
            text_column=text_col, split_column=split_col, group_column=group_col)

    feature_checks = {}
    for name, fields in {'transaction': TRANSACTION_FEATURES, 'recipient': RECIPIENT_FEATURES,
                         'graph': GRAPH_ML_FEATURES}.items():
        prohibited = sorted(set(fields) & FORBIDDEN_PREDICTORS)
        feature_checks[name] = {'feature_count': len(fields), 'prohibited_columns': prohibited}
        if prohibited:
            raise ValueError(f'{name} predictors include label/identity metadata: {prohibited}')

    graph_labels = pd.read_csv(root / 'data/graph/evaluation_accounts.csv')
    tx = pd.read_csv(root / 'data/synthetic/transactions.csv')
    accounts = pd.read_csv(root / 'data/synthetic/accounts.csv')
    report_rates = accounts.groupby('is_suspicious').fraud_report_count.agg(['count', 'mean']).to_dict('index')
    suspicious_accounts = int(accounts.is_suspicious.sum())
    transaction_split = tx.sort_values(['timestamp', 'transaction_id']).copy()
    n = len(transaction_split)
    first, second = transaction_split.timestamp.iloc[int(n * .6)], transaction_split.timestamp.iloc[int(n * .8)]
    transaction_split['split'] = 'train'
    transaction_split.loc[transaction_split.timestamp >= first, 'split'] = 'validation'
    transaction_split.loc[transaction_split.timestamp >= second, 'split'] = 'test'
    time_counts = transaction_split.groupby('split').agg(
        rows=('transaction_id', 'size'), fraud=('is_fraud', 'sum'),
        first=('timestamp', 'min'), last=('timestamp', 'max')).to_dict('index')
    if not (time_counts['train']['last'] < time_counts['validation']['first'] <
            time_counts['validation']['last'] < time_counts['test']['first']):
        raise ValueError('Generated transaction time split is not strictly ordered')
    raw_files = [p.name for p in (root / 'data/raw').iterdir() if p.is_file() and p.name != '.gitkeep']
    return {'schema_version': 1, 'inventory': inventory,
        'frozen_benchmark': verify_frozen_benchmark(root),
        'leakage_checks': {'text_partitions': 'PASS', 'frozen_transaction_ids': 'PASS',
            'frozen_chronology': 'PASS', 'generated_transaction_chronology': 'PASS',
            'explicit_label_and_identity_predictor_exclusion': feature_checks},
        'findings': {'raw_data_files': raw_files,
            'graph_known_mule_labels': int(graph_labels.is_known_mule.sum()),
            'graph_suspicious_labels': int(graph_labels.is_suspicious.sum()),
            'graph_suspicious_unlabeled_as_known_mule_negative': int(
                ((graph_labels.is_suspicious == 1) & (graph_labels.is_known_mule == 0)).sum()),
            'fraud_reports_mean_by_hidden_suspicious_label': {
                str(k): {'accounts': int(v['count']), 'mean_reports': float(v['mean'])}
                for k, v in report_rates.items()},
            'generated_transaction_temporal_split': time_counts,
            'synthetic_campaign_group_id_available': False}}
