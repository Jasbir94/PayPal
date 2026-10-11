"""Safely create only missing bundled demo assets without replacing user data."""
from pathlib import Path
import subprocess
import sys
from backend.app.config.risk_config import DATA_DIR, MODEL_DIR, PROJECT_ROOT


def initialize_demo(data_dir: Path = DATA_DIR, model_dir: Path = MODEL_DIR,
                    evaluation_dir: Path | None = None, run_module=None) -> None:
    run_module = run_module or subprocess.run
    evaluation_dir = evaluation_dir or PROJECT_ROOT / 'data' / 'processed' / 'day2'
    transaction_file = data_dir / 'transactions.csv'
    accounts_file = data_dir / 'accounts.csv'
    data_files = (transaction_file, accounts_file)
    data_present = tuple(path.is_file() for path in data_files)
    if any(data_present) and not all(data_present):
        raise RuntimeError('Demo data is incomplete. Existing files were preserved; restore the missing companion file before starting.')
    if not all(data_present):
        run_module([sys.executable, '-m', 'scripts.generate_transactions', '--output-dir', str(data_dir)],
                   cwd=PROJECT_ROOT, check=True)

    model_files = (model_dir / 'transaction_model.pkl', model_dir / 'recipient_model.pkl')
    models_present = tuple(path.is_file() for path in model_files)
    if any(models_present) and not all(models_present):
        raise RuntimeError('Only some baseline models are present. Existing models were preserved; restore the missing model before starting.')
    if not all(models_present):
        generated_reports = tuple(evaluation_dir / name for name in (
            'transaction_evaluation.json', 'transaction_features.csv',
            'recipient_evaluation.json', 'recipient_features.csv'))
        generated_metadata = (model_dir / 'transaction_model.metadata.json',
                              model_dir / 'recipient_model.metadata.json')
        if any(path.exists() for path in (*generated_reports, *generated_metadata)):
            raise RuntimeError('Baseline model artifacts are incomplete. Existing evaluation outputs were preserved; repair the model set manually.')
        run_module([sys.executable, '-m', 'ml.transaction.train'], cwd=PROJECT_ROOT, check=True)
        run_module([sys.executable, '-m', 'ml.recipient.train'], cwd=PROJECT_ROOT, check=True)


def main() -> None:
    initialize_demo()
    from scripts.seed_demo import main as validate_demo
    validate_demo()


if __name__ == '__main__':
    main()
