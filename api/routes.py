from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Transaction, AuditLog
from core.risk_model import risk_scorer
from core.stopping_rules import evaluate_safety_guardrails
from core.agent import diagnose_and_decide
from api.razorpay_client import razorpay_gateway
from api.schemas import ProcessBatchResponse, AuditLogSchema
from typing import List

router = APIRouter()

@router.post("/process-batch", response_model=ProcessBatchResponse)
def process_failed_batch(db: Session = Depends(get_db)):
    # 1. Fetch all failed transactions
    failed_txns = db.query(Transaction).filter(Transaction.status == "failed").all()
    
    total_at_risk = len(failed_txns)
    attempted = 0
    recovered_count = 0
    stopped_or_escalated = 0
    amount_at_risk = sum(t.amount for t in failed_txns)
    revenue_recovered = 0.0

    for txn in failed_txns:
        # A. Predict ML recovery probability
        rec_prob = risk_scorer.predict_recovery_probability(
            txn.failure_reason, txn.amount, txn.retry_count
        )

        # B. Check hard safety guardrails
        is_safe, safety_msg = evaluate_safety_guardrails(
            txn.retry_count, txn.amount, txn.failure_reason, rec_prob
        )

        if not is_safe:
            stopped_or_escalated += 1
            log = AuditLog(
                transaction_id=txn.id,
                agent_decision="STOPPED_BY_GUARDRAIL",
                reasoning=safety_msg
            )
            db.add(log)
            continue

        # C. LLM Agent Diagnosis
        mock_history = f"Customer {txn.customer_id} has standard account activity."
        decision = diagnose_and_decide(txn.amount, txn.failure_reason, rec_prob, mock_history)

        # D. Execute bounded action
        success = False
        if decision in ["IMMEDIATE_RETRY", "DELAYED_RETRY"]:
            attempted += 1
            success = razorpay_gateway.execute_retry(txn.amount, rec_prob)
        elif decision == "SEND_PAYMENT_LINK":
            attempted += 1
            success = razorpay_gateway.send_payment_link(txn.amount)
        else:
            # ESCALATE_TO_HUMAN
            stopped_or_escalated += 1

        # E. Update state & save audit trail
        if success:
            txn.status = "recovered"
            recovered_count += 1
            revenue_recovered += txn.amount
            log_reason = f"Decision: {decision}. Execution successful. ₹{txn.amount} recovered."
        else:
            txn.retry_count += 1
            log_reason = f"Decision: {decision}. Attempt failed or escalated to human."

        log = AuditLog(
            transaction_id=txn.id,
            agent_decision=decision,
            reasoning=log_reason
        )
        db.add(log)

    db.commit()

    recovery_rate = (recovered_count / attempted * 100) if attempted > 0 else 0.0

    return ProcessBatchResponse(
        total_processed=len(failed_txns),
        at_risk_detected=total_at_risk,
        recovery_attempted=attempted,
        successfully_recovered=recovered_count,
        escalated_or_stopped=stopped_or_escalated,
        total_amount_at_risk=round(amount_at_risk, 2),
        total_revenue_recovered=round(revenue_recovered, 2),
        recovery_rate_pct=round(recovery_rate, 2)
    )

@router.get("/audit-logs", response_model=List[AuditLogSchema])
def get_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()