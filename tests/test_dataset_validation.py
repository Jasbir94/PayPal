import json
from pathlib import Path

import pandas as pd
import pytest

from ml.data_validation import audit_repository, validate_text_partitions, verify_frozen_benchmark

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_dataset_corpora_have_group_disjoint_splits_and_valid_frozen_hashes():
    report = audit_repository(ROOT)
    assert report['leakage_checks']['text_partitions'] == 'PASS'
    assert report['leakage_checks']['frozen_transaction_ids'] == 'PASS'
    assert report['frozen_benchmark']['chronological'] is True
    assert all(report['frozen_benchmark']['canonical_hashes_valid'].values())
    assert report['inventory']['data/adversarial/benchmark.json']['split_audit'][
        'cross_split_source_groups'] == 0


def test_text_example_overlap_across_partitions_is_rejected():
    frame = pd.DataFrame([
        {'text': 'A unique payment message', 'split': 'train', 'family': 'f1'},
        {'text': 'A UNIQUE payment message', 'split': 'test', 'family': 'f2'},
    ])
    with pytest.raises(ValueError, match='normalized messages cross'):
        validate_text_partitions(frame, text_column='text', split_column='split', group_column='family')


def test_source_family_overlap_across_partitions_is_rejected():
    frame = pd.DataFrame([
        {'text': 'First example', 'split': 'train', 'family': 'family-1'},
        {'text': 'Second distinct example', 'split': 'test', 'family': 'family-1'},
    ])
    with pytest.raises(ValueError, match='source groups cross'):
        validate_text_partitions(frame, text_column='text', split_column='split', group_column='family')


def test_frozen_benchmark_profile_matches_metadata():
    profile = verify_frozen_benchmark(ROOT)
    assert {key: value['rows'] for key, value in profile['splits'].items()} == {
        'train': 1200, 'validation': 400, 'test': 400}
    assert profile['id_overlap'] == 0

\n