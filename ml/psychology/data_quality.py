"""Validate multi-label targets and isolation of every source phrase across partitions."""
import numpy as np
import pandas as pd
from backend.app.features.text_features import normalize_text
from backend.app.utils.psychology_labels import get_psychology_labels


def validate_psychology_data(data: pd.DataFrame) -> dict:
    labels = list(get_psychology_labels())
    required = {'message_id', 'text', 'language', 'split', 'source_families', *labels}
    if missing := required - set(data):
        raise ValueError(f'Missing psychology dataset columns: {sorted(missing)}')
    if data.empty or data[list(required)].isna().any().any():
        raise ValueError('Empty psychology dataset or missing required values')
    if data.message_id.duplicated().any() or data.text.map(normalize_text).duplicated().any():
        raise ValueError('Duplicate psychology IDs or normalized messages')
    if data.text.str.strip().eq('').any():
        raise ValueError('Empty psychology text')
    if not np.isin(data[labels].to_numpy(), [0, 1]).all():
        raise ValueError('Psychology targets must be binary indicators')
    if set(data.split) != {'train', 'validation', 'test'} or set(data.language) != {'English', 'Hinglish'}:
        raise ValueError('Expected all splits and both corpus languages')
    families = data[['split', 'source_families']].assign(
        source_families=data.source_families.str.split('|')).explode('source_families')
    if families.groupby('source_families').split.nunique().max() > 1:
        raise ValueError('Source-phrase leakage across psychology splits')
    for split in ('train', 'validation', 'test'):
        for label in labels:
            if data.loc[data.split == split, label].nunique() != 2:
                raise ValueError(f'{split} must contain positives and negatives for {label}')
    counts = data[labels].sum(axis=1)
    return {'rows': len(data), 'positive_counts': data[labels].sum().astype(int).to_dict(),
            'split_counts': data.split.value_counts().to_dict(),
            'positive_counts_by_split': data.groupby('split')[labels].sum().to_dict('index'),
            'language_counts': data.language.value_counts().to_dict(),
            'neutral_rows': int(counts.eq(0).sum()), 'single_label_rows': int(counts.eq(1).sum()),
            'multi_label_rows': int(counts.gt(1).sum()), 'average_label_count': float(counts.mean()),
            'average_text_length': float(data.text.str.len().mean()),
            'source_family_count': int(families.source_families.nunique()),
            'cross_split_source_overlap': 0, 'duplicate_messages': 0,
            'stratification_note': 'Exact 70/15/15 row allocation with balanced languages and randomly sampled label combinations. '
                'Source-family isolation and authored co-labels cause prevalence differences; this is not perfect iterative multi-label stratification.'}
