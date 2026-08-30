"""
Bounded Tool Registry for Autonomous Recovery Agent.
Provides controlled, read-only context tools and safe, policy-bounded action dispatchers.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import Transaction, AuditLog
from core.risk_model import risk_scorer
from core.fraud_graph import fraud_graph_detector
from core.simulator import payment_simulator, PaymentExecutionResult
from core.policy import policy_engine, PolicyEvaluationResult
from core.state_machine import state_machine, TransactionState
import uuid
from datetime import datetime, timezone

def get_customer_history(customer_id: str, db: Session) -> Dict[str, Any]:
    """Tool 1: Retrieves customer historical transaction profile and reliability score."""
    txns = db.query(Transaction).filter(Transaction.customer_id == customer_id).all()
    total_txns = len(txns)
    if total_txns == 0:
        return {
            "customer_id": customer_id,
            "total_transactions": 0,
            "success_rate": 0.85,
            "tenure_months": 12,
            "reliability_tier": "STANDARD"
        }
    
    successful = sum(1 for t in txns if t.status in ["success", "recovered"])
    success_rate = successful / total_txns
    now_utc = datetime.now(timezone.utc)
    first_txn = min(txns, key=lambda x: x.created_at.replace(tzinfo=timezone.utc) if (x.created_at and x.created_at.tzinfo is None) else (x.created_at or now_utc))
    first_created = first_txn.created_at
    if first_created is None:
        tenure_months = 12
    else:
        if first_created.tzinfo is None:
            first_created = first_created.replace(tzinfo=timezone.utc)
        days_diff = max(0, (now_utc - first_created).days)
        tenure_months = max(1, int(days_diff / 30)) + 6
    
    tier = "VIP" if success_rate > 0.85 and total_txns >= 3 else ("STANDARD" if success_rate >= 0.5 else "HIGH_RISK")
    
    return {
        "customer_id": customer_id,
        "total_transactions": total_txns,
        "success_rate": round(success_rate, 2),
        "tenure_months": tenure_months,
        "reliability_tier": tier
    }

def get_failure_context(txn_id: str, db: Session) -> Dict[str, Any]:
    """Tool 2: Gathers technical payment failure attributes."""
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        return {"error": f"Transaction {txn_id} not found"}
    return {
        "transaction_id": txn.id,
        "amount": txn.amount,
        "currency": txn.currency or "INR",
        "failure_reason": txn.failure_reason,
        "payment_method": txn.payment_method or "card",
        "retry_count": txn.retry_count,
        "current_status": txn.status,
        "ip_address": txn.ip_address,
        "device_id": txn.device_id
    }

def get_risk_score(txn_id: str, db: Session) -> Dict[str, Any]:
    """Tool 3 & 7: Computes ML recovery probability score."""
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        return {"recovery_probability": 0.5, "risk_level": "MEDIUM"}
    
    prob = risk_scorer.predict_recovery_probability(
        failure_reason=txn.failure_reason or "unknown",
        amount=txn.amount,
        retry_count=txn.retry_count,
        payment_method=txn.payment_method or "card",
        customer_tenure_months=txn.customer_tenure_months or 12,
        past_success_rate=txn.past_success_rate or 0.85,
        past_failed_attempts=txn.past_failed_attempts or 0
    )
    
    risk_level = "LOW" if prob >= 0.70 else ("MEDIUM" if prob >= 0.40 else ("HIGH" if prob >= 0.20 else "CRITICAL"))
    return {
        "recovery_probability": prob,
        "risk_level": risk_level
    }

def check_fraud_network(txn_id: str, db: Session) -> Dict[str, Any]:
    """Tool 5: Executes bipartite graph traversal to detect connected fraud syndicate clusters."""
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        return {"is_fraud_connected": False, "risk_verdict": "UNKNOWN"}
    
    is_connected, details = fraud_graph_detector.analyze_transaction_network(
        txn_id=txn.id,
        ip_address=txn.ip_address,
        device_id=txn.device_id,
        max_depth=2
    )
    return {
        "is_fraud_connected": is_connected,
        "details": details
    }

def execute_bounded_action(
    action: str,
    txn_id: str,
    db: Session,
    recovery_prob: float = 0.5,
    force_success: Optional[bool] = None
) -> Dict[str, Any]:
    """Tool 9 & 10: Executes safe, bounded recovery action through payment simulator."""
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        return {"success": False, "message": f"Transaction {txn_id} not found."}

    action = action.upper().strip()
    idempotency_key = state_machine.generate_idempotency_key(txn.id, txn.retry_count, action)

    if action in ["IMMEDIATE_RETRY", "DELAYED_RETRY"]:
        sim_res: PaymentExecutionResult = payment_simulator.execute_retry(
            amount=txn.amount,
            recovery_probability=recovery_prob,
            failure_reason=txn.failure_reason,
            force_success=force_success
        )
    elif action == "SEND_PAYMENT_LINK":
        sim_res: PaymentExecutionResult = payment_simulator.send_payment_link(
            amount=txn.amount,
            customer_id=txn.customer_id,
            force_success=force_success
        )
    else:
        return {"success": False, "message": f"Action '{action}' does not perform automated execution."}

    txn.idempotency_key = idempotency_key
    return sim_res.to_dict()

def record_audit_event(
    db: Session,
    txn_id: str,
    actor: str,
    event_type: str,
    decision: str,
    reasoning: str,
    prev_state: Optional[str] = None,
    new_state: Optional[str] = None,
    tokens: int = 0,
    cost_inr: float = 0.0,
    amount_recovered: float = 0.0
) -> AuditLog:
    """Tool 13: Records an immutable audit log entry."""
    log = AuditLog(
        event_id=f"evt_{uuid.uuid4().hex[:10]}",
        transaction_id=txn_id,
        actor=actor,
        event_type=event_type,
        agent_decision=decision,
        reasoning=reasoning,
        previous_state=prev_state,
        new_state=new_state,
        tokens_used=tokens,
        cost_inr=cost_inr,
        amount_recovered=amount_recovered,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(log)
    db.commit()
    return log
