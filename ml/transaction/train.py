"""Train and compare transaction baselines; run from the project root."""
from backend.app.database.repository import DataRepository
from backend.app.config.risk_config import TRANSACTION_FEATURES
from ml.datasets import transaction_dataset
from ml.training import train_baselines


def main() -> None:
    repository = DataRepository.load()
    print(f'Validated {len(repository.transactions)} transactions, {len(repository.accounts)} accounts; '
          f'fraud rate {repository.transactions.is_fraud.mean():.2%}')
    train_baselines(transaction_dataset(repository), TRANSACTION_FEATURES, 'transaction',
                    'is_fraud: synthetic transaction fraud-propensity baseline')


if __name__ == '__main__':
    main()
