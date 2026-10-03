"""Train and compare recipient baselines; run from the project root."""
from backend.app.database.repository import DataRepository
from backend.app.config.risk_config import RECIPIENT_FEATURES
from ml.datasets import recipient_dataset
from ml.training import train_baselines


def main() -> None:
    repository = DataRepository.load()
    print(f'Validated {len(repository.transactions)} transactions, {len(repository.accounts)} accounts; '
          f'fraud rate {repository.transactions.is_fraud.mean():.2%}')
    train_baselines(recipient_dataset(repository), RECIPIENT_FEATURES, 'recipient',
                    'is_suspicious: synthetic suspicious-account proxy label')


if __name__ == '__main__':
    main()
