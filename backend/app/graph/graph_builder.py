"""Immutable, strictly past-only MultiDiGraph snapshots with bounded LRU reuse."""
from collections import OrderedDict
from threading import RLock
from time import perf_counter
import networkx as nx
import numpy as np
import pandas as pd
from backend.app.config.graph_config import LOOKBACK_HOURS, MAX_CACHE_SNAPSHOTS

def utc_timestamp(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError('A timezone-aware timestamp is required')
    return stamp.tz_convert('UTC')

class TransactionGraphBuilder:
    def __init__(self, transactions, accounts, intelligence=None):
        required = {'transaction_id', 'sender_id', 'receiver_id', 'amount', 'timestamp'}
        if not required <= set(transactions):
            raise ValueError('Missing graph transaction columns')
        self.transactions = transactions.copy()
        self.transactions['timestamp'] = pd.to_datetime(self.transactions.timestamp, utc=True)
        self.transactions = self.transactions.sort_values(['timestamp', 'transaction_id']).reset_index(drop=True)
        if self.transactions.transaction_id.duplicated().any():
            raise ValueError('Duplicate graph transaction IDs')
        if not np.isfinite(self.transactions.amount).all() or self.transactions.amount.le(0).any():
            raise ValueError('Graph amounts must be finite and positive')
        self.accounts = accounts.copy().set_index('account_id', drop=False)
        self.accounts['created_at'] = pd.to_datetime(self.accounts.created_at, utc=True)
        endpoints = set(self.transactions.sender_id) | set(self.transactions.receiver_id)
        if not endpoints <= set(self.accounts.index):
            raise ValueError('Unknown graph account endpoint')
        for field in ('sender_id', 'receiver_id'):
            if (self.transactions.timestamp < self.transactions[field].map(self.accounts.created_at)).any():
                raise ValueError('Graph transfer before account creation')
        self.intelligence = intelligence.copy() if intelligence is not None else pd.DataFrame(
            columns=['account_id', 'kind', 'observed_at'])
        if len(self.intelligence):
            if not set(self.intelligence.account_id) <= set(self.accounts.index):
                raise ValueError('Unknown intelligence account')
            if not self.intelligence.kind.isin(['known_mule', 'fraud_report']).all():
                raise ValueError('Unknown graph intelligence kind')
            self.intelligence['observed_at'] = pd.to_datetime(self.intelligence.observed_at, utc=True)
            if self.intelligence.observed_at.isna().any():
                raise ValueError('Invalid intelligence timestamp')
        self._times = self.transactions.timestamp.astype('int64').to_numpy()
        self._transaction_ids = set(self.transactions.transaction_id)
        self._cache = OrderedDict()
        self._lock = RLock()
        self.build_count = 0

    def build_graph_until(self, timestamp, exclude_id=None):
        stamp = utc_timestamp(timestamp)
        # Most API transaction IDs are new; normalize absent IDs to reuse the immutable time snapshot.
        if exclude_id not in self._transaction_ids:
            exclude_id = None
        key = (stamp.value, exclude_id)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            start_time = perf_counter()
            left = np.searchsorted(self._times, (stamp - pd.Timedelta(hours=LOOKBACK_HOURS)).value, side='left')
            right = np.searchsorted(self._times, stamp.value, side='left')  # strictly < T
            frame = self.transactions.iloc[left:right]
            if exclude_id is not None:
                frame = frame[frame.transaction_id != exclude_id]
            graph = nx.MultiDiGraph()
            graph.add_nodes_from(self.accounts.index[self.accounts.created_at <= stamp])
            for row in frame.itertuples(index=False):
                graph.add_edge(row.sender_id, row.receiver_id, key=row.transaction_id,
                               transaction_id=row.transaction_id, amount=float(row.amount), timestamp=row.timestamp)
            simple = nx.DiGraph()
            simple.add_nodes_from(graph)
            for sender, receiver, edge in graph.edges(data=True):
                weight = simple.get_edge_data(sender, receiver, {}).get('weight', 0.0)
                simple.add_edge(sender, receiver, weight=weight + edge['amount'])
            ranks = nx.pagerank(simple, weight='weight', max_iter=200, tol=1e-8) if len(simple) else {}
            components = {node: len(group) for group in nx.weakly_connected_components(simple) for node in group}
            known = set(self.intelligence.loc[(self.intelligence.observed_at < stamp) &
                        self.intelligence.kind.eq('known_mule'), 'account_id']) if len(self.intelligence) else set()
            reported = set(self.intelligence.loc[(self.intelligence.observed_at < stamp) &
                           self.intelligence.kind.eq('fraud_report'), 'account_id']) if len(self.intelligence) else set()
            distances = nx.multi_source_dijkstra_path_length(simple.to_undirected(), known & set(simple), weight=None) if known & set(simple) else {}
            graph.graph.update(as_of=stamp, lookback_hours=LOOKBACK_HOURS, simple=simple,
                pagerank=ranks, component_sizes=components, known_mules=known, reported=reported,
                mule_distances=distances, feature_cache={}, build_ms=(perf_counter() - start_time) * 1000)
            nx.freeze(graph)
            self._cache[key] = graph
            self.build_count += 1
            while len(self._cache) > MAX_CACHE_SNAPSHOTS:
                self._cache.popitem(last=False)
            return graph

def build_graph_until(transactions, accounts, timestamp, intelligence=None):
    return TransactionGraphBuilder(transactions, accounts, intelligence).build_graph_until(timestamp)
