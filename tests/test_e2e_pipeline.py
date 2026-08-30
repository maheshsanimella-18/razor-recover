"""
End-to-End Pipeline & Webhook Integration Tests.
Tests full pipeline: Webhook Ingest -> ML Risk -> Fraud Check -> Agent -> Policy -> Gateway -> Audit Log -> ROI Metrics.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from api.main import app
from database.session import SessionLocal, Base, engine
from database.models import Transaction, AuditLog

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

def test_webhook_payment_failed_safe_recovery():
    uid = uuid.uuid4().hex[:6]
    txn_id = f"test_e2e_safe_{uid}"
    payload = {
        "transaction_id": txn_id,
        "customer_id": f"cust_{uid}",
        "amount": 3500.0,
        "failure_reason": "network_timeout",
        "payment_method": "card",
        "ip_address": f"192.168.1.{uuid.uuid4().int % 200 + 1}",
        "device_id": f"dev_safe_{uid}"
    }
    res = client.post("/api/webhooks/payment-failed", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["transaction_id"] == txn_id
    assert data["recommended_action"] in ["IMMEDIATE_RETRY", "DELAYED_RETRY"]
    assert data["execution_mode"] == "SIMULATED_TEST_MODE"

def test_webhook_payment_failed_fraud_blocked():
    uid = uuid.uuid4().hex[:6]
    shared_ip = f"198.51.100.{uuid.uuid4().int % 100 + 1}"
    
    # Insert seed fraud
    db = SessionLocal()
    seed = Transaction(
        id=f"seed_fraud_{uid}",
        customer_id=f"cust_seed_{uid}",
        amount=15000.0,
        failure_reason="suspected_fraud",
        ip_address=shared_ip,
        device_id=f"dev_fraud_{uid}"
    )
    db.add(seed)
    db.commit()
    db.close()

    # Now post webhook sharing same IP
    peer_txn_id = f"test_e2e_fraud_{uid}"
    payload = {
        "transaction_id": peer_txn_id,
        "customer_id": f"cust_peer_{uid}",
        "amount": 12000.0,
        "failure_reason": "network_timeout",
        "ip_address": shared_ip,
        "device_id": f"dev_peer_{uid}"
    }
    res = client.post("/api/webhooks/payment-failed", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "CRITICAL"
    assert data["recommended_action"] == "ESCALATE_TO_HUMAN"
    assert data["recovery_status"] == "ESCALATED_TO_HUMAN_QUEUE"


def test_pitch_demo_endpoints():
    res_a = client.post("/api/demo/run?scenario=A")
    assert res_a.status_code == 200
    assert res_a.json()["status"] == "RECOVERED"
    assert res_a.json()["amount_recovered"] == 12500.0

    res_b = client.post("/api/demo/run?scenario=B")
    assert res_b.status_code == 200
    assert res_b.json()["status"] == "ESCALATED_AND_BLOCKED"

def test_benchmarks_endpoint():
    res = client.get("/api/benchmarks?samples=100")
    assert res.status_code == 200
    data = res.json()
    assert "comparison" in data
    assert len(data["comparison"]) == 3

def test_model_metrics_endpoint():
    res = client.get("/api/model-metrics")
    assert res.status_code == 200
    data = res.json()
    assert "test_accuracy" in data
    assert "test_precision" in data
    assert "feature_importances" in data
