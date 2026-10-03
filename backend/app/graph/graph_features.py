"""Windowed topology, bounded cycles and amount-conserving FIFO flow evidence."""
from collections import deque
import statistics
import networkx as nx
from backend.app.features.recipient_features import calculate_outgoing_ratio, count_unique_senders
from backend.app.config.graph_config import MAX_CYCLE_LENGTH, MAX_SEARCH_STEPS, MAX_PATH_DEPTH, RAPID_WINDOW_MINUTES

def flow_timing(graph, account_id, window_minutes=RAPID_WINDOW_MINUTES):
    if window_minutes <= 0:
        raise ValueError('Rapid window must be positive')
    events = [(edge['timestamp'], 1, edge['transaction_id'], edge['amount'])
              for _, _, edge in graph.in_edges(account_id, data=True) if edge]
    events += [(edge['timestamp'], 0, edge['transaction_id'], edge['amount'])
               for _, _, edge in graph.out_edges(account_id, data=True) if edge]
    # Same-time outgoing processed first: ties cannot establish a receive-then-send link.
    events.sort()
    inflow, matched, rapid, holding = 0.0, 0.0, 0.0, []
    queue = deque()
    for stamp, incoming, _, amount in events:
        if incoming:
            inflow += amount
            queue.append([stamp, amount])
        else:
            remaining = amount
            while remaining > 1e-9 and queue:
                received, available = queue[0]
                used = min(remaining, available)
                minutes = (stamp - received).total_seconds() / 60
                matched += used
                if 0 < minutes <= window_minutes:
                    rapid += used
                holding.append(minutes)
                remaining -= used
                queue[0][1] -= used
                if queue[0][1] <= 1e-9:
                    queue.popleft()
    return {'rapid_outflow_ratio': min(1.0, rapid / inflow) if inflow else 0.0,
            'matched_outflow_ratio': min(1.0, matched / inflow) if inflow else 0.0,
            'median_fund_holding_time': statistics.median(holding) if holding else None,
            'matched_inflow_amount': matched}

def calculate_rapid_outflow_ratio(graph, account_id, window_minutes=RAPID_WINDOW_MINUTES):
    return flow_timing(graph, account_id, window_minutes)['rapid_outflow_ratio']

def bounded_cycles(simple, account_id):
    count, steps = 0, 0
    stack = [(account_id, (account_id,))]
    while stack and steps < MAX_SEARCH_STEPS:
        node, visited = stack.pop()
        for neighbor in sorted(simple.successors(node)):
            steps += 1
            if neighbor == account_id:
                count += 1
            elif neighbor not in visited and len(visited) < MAX_CYCLE_LENGTH:
                stack.append((neighbor, visited + (neighbor,)))
            if steps >= MAX_SEARCH_STEPS:
                break
    return count, bool(stack) or steps >= MAX_SEARCH_STEPS

def temporal_path_depth(graph, account_id):
    best, steps = 0, 0
    stack = [(account_id, None, (account_id,))]
    while stack and steps < MAX_SEARCH_STEPS:
        node, previous, visited = stack.pop()
        if len(visited) - 1 >= MAX_PATH_DEPTH:
            continue
        for _, neighbor, edge in graph.out_edges(node, data=True):
            steps += 1
            if neighbor in visited:
                continue
            stamp = edge['timestamp']
            if previous is not None and not 0 < (stamp - previous).total_seconds() <= RAPID_WINDOW_MINUTES * 60:
                continue
            depth = len(visited)
            best = max(best, depth)
            stack.append((neighbor, stamp, visited + (neighbor,)))
            if steps >= MAX_SEARCH_STEPS:
                break
    return best, bool(stack) or steps >= MAX_SEARCH_STEPS

def calculate_graph_features(graph, account_id):
    if account_id not in graph:
        raise KeyError(f'Account absent from snapshot: {account_id}')
    if account_id in graph.graph['feature_cache']:
        return dict(graph.graph['feature_cache'][account_id])
    incoming = list(graph.in_edges(account_id, data=True))
    outgoing = list(graph.out_edges(account_id, data=True))
    senders = {sender for sender, _, _ in incoming}
    receivers = {receiver for _, receiver, _ in outgoing}
    inflow = sum(edge['amount'] for _, _, edge in incoming)
    outflow = sum(edge['amount'] for _, _, edge in outgoing)
    neighbors = (senders | receivers) - {account_id}
    cycles, cycle_truncated = bounded_cycles(graph.graph['simple'], account_id)
    depth, path_truncated = temporal_path_depth(graph, account_id)
    features = {'in_degree': len(incoming), 'out_degree': len(outgoing),
        'unique_incoming_senders': len(senders), 'unique_outgoing_receivers': len(receivers),
        'incoming_amount': inflow, 'outgoing_amount': outflow,
        'in_out_amount_ratio': calculate_outgoing_ratio(inflow, outflow),
        **flow_timing(graph, account_id),
        'known_mule_neighbors': len(neighbors & graph.graph['known_mules']),
        'fraud_reported_neighbors': len(neighbors & graph.graph['reported']),
        'distance_to_known_mule': graph.graph['mule_distances'].get(account_id),
        'cycle_count': cycles, 'cycle_search_truncated': cycle_truncated,
        'connected_component_size': graph.graph['component_sizes'].get(account_id, 1),
        'pagerank': graph.graph['pagerank'].get(account_id, 0.0),
        'suspicious_path_depth': depth, 'path_search_truncated': path_truncated}
    graph.graph['feature_cache'][account_id] = features
    return dict(features)
