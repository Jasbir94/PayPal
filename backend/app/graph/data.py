"""Graph inputs reuse cached Day 1 history and optional deterministic overlay."""
import pandas as pd
from backend.app.config.graph_config import GRAPH_DATA_DIR
from backend.app.graph.graph_builder import TransactionGraphBuilder

def load_graph_builder(repository, directory=GRAPH_DATA_DIR):
    transactions = repository.transactions[['transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp']].copy()
    overlay = directory / 'network_transactions.csv'
    intelligence = directory / 'intelligence.csv'
    if overlay.exists():
        transactions = pd.concat([transactions, pd.read_csv(overlay)], ignore_index=True)
    intel = pd.read_csv(intelligence) if intelligence.exists() else None
    return TransactionGraphBuilder(transactions, repository.accounts.reset_index(drop=True), intel)
