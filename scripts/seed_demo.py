"""Validate bundled synthetic data/models and the five simulator scenario fixtures."""
import json
from backend.app.config.risk_config import DATA_DIR
from backend.app.database.repository import DataRepository
from backend.app.models.transaction_model import TransactionModel
from backend.app.models.recipient_model import RecipientModel
from backend.app.simulation.payment_simulator import _SCENARIOS


def main():
    repository=DataRepository.load()
    TransactionModel();RecipientModel()
    required={'government_impersonation','large_purchase','small_investment','mule_network','family_emergency'}
    ids={row['id'] for row in _SCENARIOS}
    if not required.issubset(ids):raise RuntimeError('Required demo scenario fixtures are missing.')
    print(json.dumps({'status':'ready','environment':'SYNTHETIC DEMO','data_directory':str(DATA_DIR.name),
        'transactions':len(repository.transactions),'accounts':len(repository.accounts),
        'required_scenarios':sorted(required),'message':'Demo data and baseline models validated; no source data was overwritten.'},indent=2))


if __name__=='__main__':main()
