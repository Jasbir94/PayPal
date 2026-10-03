"""Point-in-time feature accessors that require an explicit prediction timestamp."""
import pandas as pd
from backend.app.features.recipient_features import calculate_recipient_features
from backend.app.graph.graph_features import calculate_graph_features
from backend.app.graph.graph_builder import utc_timestamp


class TemporalFeatureService:
    def __init__(self,repository,graph_builder):
        self.repository=repository
        self.graph_builder=graph_builder

    def recipient_features(self,recipient_id:str,as_of_timestamp,exclude_transaction_id:str|None=None):
        stamp=utc_timestamp(as_of_timestamp)
        account=self.repository.account(recipient_id,stamp)
        history=self.repository.recipient_history(recipient_id,stamp,exclude_transaction_id)
        return calculate_recipient_features(account,history,stamp)

    def graph_features(self,recipient_id:str,as_of_timestamp,exclude_transaction_id:str|None=None):
        stamp=utc_timestamp(as_of_timestamp)
        graph=self.graph_builder.build_graph_until(stamp,exclude_transaction_id)
        return calculate_graph_features(graph,recipient_id)
