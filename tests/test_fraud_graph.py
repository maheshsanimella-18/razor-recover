"""
Unit Tests for Networked Fraud Detection Graph Engine.
"""

import pytest
from core.fraud_graph import NetworkedFraudDetector

@pytest.fixture
def graph():
    detector = NetworkedFraudDetector()
    # Mock node indices
    detector.txn_data = {
        "txn_seed_1": {"id": "txn_seed_1", "failure_reason": "suspected_fraud", "ip_address": "198.51.100.42", "device_id": "dev_bad_1"},
        "txn_peer_2": {"id": "txn_peer_2", "failure_reason": "network_timeout", "ip_address": "198.51.100.42", "device_id": "dev_clean_2"},
        "txn_clean_3": {"id": "txn_clean_3", "failure_reason": "network_timeout", "ip_address": "192.168.1.99", "device_id": "dev_clean_3"}
    }
    detector.ip_to_txns["198.51.100.42"] = {"txn_seed_1", "txn_peer_2"}
    detector.ip_to_txns["192.168.1.99"] = {"txn_clean_3"}
    detector.device_to_txns["dev_bad_1"] = {"txn_seed_1"}
    detector.known_fraud_txns = {"txn_seed_1"}
    return detector

def test_peer_connected_to_fraud_seed_flagged(graph):
    is_connected, details = graph.analyze_transaction_network("txn_peer_2", ip_address="198.51.100.42")
    assert is_connected
    assert "txn_seed_1" in details["connected_fraud_txns"]
    assert details["risk_verdict"] == "FRAUD_SYNDICATE_CONFIRMED"

def test_clean_transaction_not_flagged(graph):
    is_connected, details = graph.analyze_transaction_network("txn_clean_3", ip_address="192.168.1.99")
    assert not is_connected
    assert details["risk_verdict"] == "CLEAN_NETWORK"
