"""Corpus validation and transparent split/duplicate/lexical quality analysis."""
from collections import Counter
import re
import pandas as pd
from backend.app.utils.scenario_labels import get_scenario_labels
from scripts.generate_scam_messages import normalized_text


def validate_messages(data: pd.DataFrame) -> dict:
    required = {'message_id', 'text', 'scenario_label', 'template_id', 'language', 'split'}
    missing = required - set(data)
    if missing:
        raise ValueError(f'Missing scenario dataset columns: {sorted(missing)}')
    if data.empty or data[list(required)].isna().any().any():
        raise ValueError('Scenario dataset is empty or has missing required values')
    labels = get_scenario_labels()
    if set(data.scenario_label) != set(labels):
        raise ValueError('Dataset must contain every valid scenario class and no unknown labels')
    if data.message_id.duplicated().any():
        raise ValueError('Duplicate message IDs')
    normalized = data.text.map(normalized_text)
    if normalized.eq('').any() or normalized.duplicated().any():
        raise ValueError('Empty or duplicated normalized messages')
    if set(data.split) != {'train', 'validation', 'test'}:
        raise ValueError('Expected train, validation and test partitions')
    if data.groupby('template_id').split.nunique().max() != 1:
        raise ValueError('Template-family leakage across dataset splits')
    if data.groupby('template_id').scenario_label.nunique().max() != 1:
        raise ValueError('Template family cannot have conflicting targets')
    for role in ('train', 'validation', 'test'):
        if set(data.loc[data.split == role, 'scenario_label']) != set(labels):
            raise ValueError(f'{role} split is missing classes')
    # Reject direct label leakage in synthetic text, while allowing natural narrative words.
    if any(normalized.str.contains(re.escape(label), regex=True).any() for label in labels):
        raise ValueError('Scenario label text leaked into messages')
    common_words = {}
    for label, group in data.groupby('scenario_label'):
        tokens = re.findall(r'[a-z]{3,}', ' '.join(group.text).casefold())
        common_words[label] = dict(Counter(tokens).most_common(15))
    return {
        'rows': len(data), 'classes': data.scenario_label.value_counts().to_dict(),
        'average_text_length': float(data.text.str.len().mean()),
        'text_length_by_class': data.groupby('scenario_label').text.apply(lambda values: float(values.str.len().mean())).to_dict(),
        'duplicate_normalized_messages': int(normalized.duplicated().sum()),
        'train_test_message_overlap': len(set(normalized[data.split == 'train']) & set(normalized[data.split == 'test'])),
        'train_test_template_overlap': len(set(data.loc[data.split == 'train', 'template_id']) &
                                            set(data.loc[data.split == 'test', 'template_id'])),
        'template_families': int(data.template_id.nunique()),
        'split_counts': data.groupby(['split', 'scenario_label']).size().unstack(fill_value=0).to_dict('index'),
        'language_distribution': data.language.value_counts().to_dict(), 'most_common_words': common_words,
    }
