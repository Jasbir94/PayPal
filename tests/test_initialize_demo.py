from pathlib import Path
import pytest
from scripts.initialize_demo import initialize_demo


def test_initializer_preserves_partial_demo_data(tmp_path):
    data_dir = tmp_path / 'synthetic'
    data_dir.mkdir()
    transactions = data_dir / 'transactions.csv'
    transactions.write_text('keep this data', encoding='utf-8')

    with pytest.raises(RuntimeError, match='Existing files were preserved'):
        initialize_demo(data_dir=data_dir, model_dir=tmp_path / 'models',
                        evaluation_dir=tmp_path / 'reports', run_module=lambda *args, **kwargs: pytest.fail('must not run'))

    assert transactions.read_text(encoding='utf-8') == 'keep this data'


def test_initializer_preserves_partial_model_set(tmp_path):
    data_dir = tmp_path / 'synthetic'
    data_dir.mkdir()
    (data_dir / 'transactions.csv').write_text('transactions', encoding='utf-8')
    (data_dir / 'accounts.csv').write_text('accounts', encoding='utf-8')
    model_dir = tmp_path / 'models'
    model_dir.mkdir()
    existing_model = model_dir / 'transaction_model.pkl'
    existing_model.write_bytes(b'keep this model')

    with pytest.raises(RuntimeError, match='Existing models were preserved'):
        initialize_demo(data_dir=data_dir, model_dir=model_dir,
                        evaluation_dir=tmp_path / 'reports', run_module=lambda *args, **kwargs: pytest.fail('must not run'))

    assert existing_model.read_bytes() == b'keep this model'
