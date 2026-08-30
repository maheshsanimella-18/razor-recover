"""
Networked Fraud Detection Engine (Graph Theory)
Identifies syndicated fraud rings by mapping transactions as nodes and 
shared entities (IP address, Device ID) as connecting edges.
"""

from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque
from sqlalchemy.orm import Session
from database.models import Transaction

class NetworkedFraudDetector:
    def __init__(self):
        # In-memory index structures for sub-millisecond graph queries
        self.ip_to_txns: Dict[str, Set[str]] = defaultdict(set)
        self.device_to_txns: Dict[str, Set[str]] = defaultdict(set)
        self.txn_data: Dict[str, dict] = {}
        self.known_fraud_txns: Set[str] = set()

    def build_graph_from_db(self, db: Session):
        """Constructs the bipartite entity-transaction graph from the database."""
        self.ip_to_txns.clear()
        self.device_to_txns.clear()
        self.txn_data.clear()
        self.known_fraud_txns.clear()

        all_txns = db.query(Transaction).all()
        for txn in all_txns:
            self.txn_data[txn.id] = {
                "id": txn.id,
                "customer_id": txn.customer_id,
                "amount": txn.amount,
                "status": txn.status,
                "failure_reason": txn.failure_reason,
                "ip_address": txn.ip_address,
                "device_id": txn.device_id,
                "is_fraud_ring": txn.is_fraud_ring
            }
            if txn.ip_address:
                self.ip_to_txns[txn.ip_address].add(txn.id)
            if txn.device_id:
                self.device_to_txns[txn.device_id].add(txn.id)
            
            # Identify known fraud seed nodes
            if txn.failure_reason == "suspected_fraud" or txn.is_fraud_ring:
                self.known_fraud_txns.add(txn.id)

    def analyze_transaction_network(
        self, 
        txn_id: str, 
        ip_address: Optional[str] = None, 
        device_id: Optional[str] = None,
        max_depth: int = 2
    ) -> Tuple[bool, dict]:
        """
        Traverses connected graph components up to `max_depth` hops.
        Returns: (is_connected_to_fraud: bool, details: dict)
        """
        # Find direct and indirect connected transaction nodes
        connected_txns: Set[str] = set()
        shared_ips: Set[str] = set()
        shared_devices: Set[str] = set()
        
        queue = deque([(txn_id, 0)])
        visited_txns = {txn_id}

        # Seed traversal with provided attributes if transaction is new/in-flight
        if ip_address and ip_address in self.ip_to_txns:
            for neighbor in self.ip_to_txns[ip_address]:
                if neighbor not in visited_txns:
                    visited_txns.add(neighbor)
                    queue.append((neighbor, 1))
            shared_ips.add(ip_address)

        if device_id and device_id in self.device_to_txns:
            for neighbor in self.device_to_txns[device_id]:
                if neighbor not in visited_txns:
                    visited_txns.add(neighbor)
                    queue.append((neighbor, 1))
            shared_devices.add(device_id)

        # BFS Traversal
        while queue:
            curr_txn_id, depth = queue.popleft()
            connected_txns.add(curr_txn_id)

            if depth >= max_depth:
                continue

            curr_info = self.txn_data.get(curr_txn_id)
            if not curr_info:
                continue

            c_ip = curr_info.get("ip_address")
            c_dev = curr_info.get("device_id")

            if c_ip and c_ip in self.ip_to_txns:
                shared_ips.add(c_ip)
                for neighbor in self.ip_to_txns[c_ip]:
                    if neighbor not in visited_txns:
                        visited_txns.add(neighbor)
                        queue.append((neighbor, depth + 1))

            if c_dev and c_dev in self.device_to_txns:
                shared_devices.add(c_dev)
                for neighbor in self.device_to_txns[c_dev]:
                    if neighbor not in visited_txns:
                        visited_txns.add(neighbor)
                        queue.append((neighbor, depth + 1))

        # Check for intersection with known fraud seeds
        fraud_matches = (connected_txns & self.known_fraud_txns)
        # Filter out self if self is being tested
        fraud_peers = [f for f in fraud_matches if f != txn_id]

        is_fraud_cluster = len(fraud_peers) > 0

        cluster_details = {
            "is_fraud_connected": is_fraud_cluster,
            "connected_fraud_count": len(fraud_peers),
            "connected_fraud_txns": list(fraud_peers)[:5],
            "total_cluster_size": len(connected_txns),
            "shared_ips": list(shared_ips),
            "shared_devices": list(shared_devices),
            "risk_verdict": "FRAUD_SYNDICATE_CONFIRMED" if is_fraud_cluster else "CLEAN_NETWORK"
        }

        return is_fraud_cluster, cluster_details

    def export_graph_topology(self, limit_nodes: int = 60) -> dict:
        """Exports graph nodes and edges for visualization in Streamlit."""
        nodes = []
        links = []
        
        # Identify suspicious clusters
        suspicious_txns = set()
        for fraud_id in self.known_fraud_txns:
            _, details = self.analyze_transaction_network(fraud_id, max_depth=2)
            suspicious_txns.update(details["connected_fraud_txns"])
            suspicious_txns.add(fraud_id)

        # Include all suspicious nodes + sample legitimate nodes
        sampled_txns = list(suspicious_txns)
        for t_id in list(self.txn_data.keys()):
            if len(sampled_txns) >= limit_nodes:
                break
            if t_id not in suspicious_txns:
                sampled_txns.append(t_id)

        # Generate Nodes
        for t_id in sampled_txns:
            data = self.txn_data.get(t_id, {})
            is_fraud = t_id in self.known_fraud_txns
            is_ring = t_id in suspicious_txns and not is_fraud
            
            nodes.append({
                "id": t_id,
                "customer_id": data.get("customer_id", "unknown"),
                "amount": data.get("amount", 0.0),
                "status": data.get("status", "unknown"),
                "failure_reason": data.get("failure_reason", "none"),
                "ip": data.get("ip_address", "N/A"),
                "device": data.get("device_id", "N/A"),
                "category": "Fraud Seed" if is_fraud else ("Syndicate Member" if is_ring else "Normal")
            })

        # Generate Edges
        added_edges = set()
        for i, t1 in enumerate(sampled_txns):
            d1 = self.txn_data.get(t1, {})
            for t2 in sampled_txns[i+1:]:
                d2 = self.txn_data.get(t2, {})
                shared_ip = d1.get("ip_address") and d1.get("ip_address") == d2.get("ip_address")
                shared_dev = d1.get("device_id") and d1.get("device_id") == d2.get("device_id")

                if shared_ip or shared_dev:
                    edge_key = tuple(sorted([t1, t2]))
                    if edge_key not in added_edges:
                        added_edges.add(edge_key)
                        links.append({
                            "source": t1,
                            "target": t2,
                            "reason": "Shared IP & Device" if (shared_ip and shared_dev) else ("Shared IP" if shared_ip else "Shared Device")
                        })

        return {"nodes": nodes, "links": links, "fraud_ring_count": len(suspicious_txns)}

# Global Graph Detector Instance
fraud_graph_detector = NetworkedFraudDetector()
