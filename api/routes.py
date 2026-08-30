from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from database.session import get_db
from database.models import Transaction, AuditLog
from core.risk_model import risk_scorer
from core.stopping_rules import evaluate_safety_guardrails
from core.agent import diagnose_and_decide
from core.fraud_graph import fraud_graph_detector
from api.razorpay_client import razorpay_gateway
from api.schemas import (
    ProcessBatchResponse, 
    AuditLogSchema, 
    EscalationQueueItem, 
    ReviewEscalationRequest, 
    ROIMetricsResponse
)

router = APIRouter()

@router.post("/process-batch", response_model=ProcessBatchResponse)
def process_failed_batch(db: Session = Depends(get_db)):
    """
    Autonomous Recovery Pipeline:
    1. Builds real-time entity graph for networked fraud detection.
    2. Flags & isolates syndicated fraud rings (hard escalation, bypassing LLM).
    3. Runs ML risk scoring & safety guardrails.
    4. Invokes bounded Gemini decision agent with token/cost tracking.
    5. Dispatches bounded payment recovery interventions and populates HITL queue.
    """
    # Build/refresh in-memory entity graph
    fraud_graph_detector.build_graph_from_db(db)

    failed_txns = db.query(Transaction).filter(Transaction.status == "failed").all()
    
    total_at_risk = len(failed_txns)
    attempted = 0
    recovered_count = 0
    stopped_or_escalated = 0
    fraud_rings_isolated = 0
    amount_at_risk = sum(t.amount for t in failed_txns)
    revenue_recovered = 0.0
    total_batch_cost = 0.0

    for txn in failed_txns:
        # Step 1: Networked Fraud Detection (Graph Theory Analysis)
        is_fraud_connected, cluster_details = fraud_graph_detector.analyze_transaction_network(
            txn_id=txn.id,
            ip_address=txn.ip_address,
            device_id=txn.device_id,
            max_depth=2
        )

        if is_fraud_connected:
            txn.is_fraud_ring = True
            txn.queue_status = "PENDING_REVIEW"
            txn.escalated_at = datetime.utcnow()
            stopped_or_escalated += 1
            fraud_rings_isolated += 1

            fraud_msg = (
                f"NETWORKED_FRAUD_DETECTED: Connected to {cluster_details['connected_fraud_count']} "
                f"known fraud node(s) across shared infrastructure (IP: {txn.ip_address}, Device: {txn.device_id}). "
                f"Cluster Size: {cluster_details['total_cluster_size']}. Bypassed LLM."
            )
            log = AuditLog(
                transaction_id=txn.id,
                agent_decision="BLOCKED_FRAUD_GRAPH",
                reasoning=fraud_msg,
                tokens_used=0,
                cost_inr=0.0
            )
            db.add(log)
            continue

        # Step 2: ML Recovery Probability Scoring
        rec_prob = risk_scorer.predict_recovery_probability(
            txn.failure_reason, txn.amount, txn.retry_count
        )

        # Step 3: Hard Safety Guardrails & Stopping Rules
        is_safe, safety_msg = evaluate_safety_guardrails(
            retry_count=txn.retry_count,
            amount=txn.amount,
            failure_reason=txn.failure_reason,
            recovery_probability=rec_prob,
            is_fraud_connected=False
        )

        if not is_safe:
            stopped_or_escalated += 1
            txn.queue_status = "PENDING_REVIEW"
            txn.escalated_at = datetime.utcnow()
            log = AuditLog(
                transaction_id=txn.id,
                agent_decision="STOPPED_BY_GUARDRAIL",
                reasoning=safety_msg,
                tokens_used=0,
                cost_inr=0.0
            )
            db.add(log)
            continue

        # Step 4: Gemini LLM Agent Diagnosis & Execution Strategy Selection
        mock_history = f"Customer {txn.customer_id} has standard account activity."
        decision, tokens_used, cost_inr = diagnose_and_decide(
            txn.amount, txn.failure_reason, rec_prob, mock_history
        )
        total_batch_cost += cost_inr

        # Step 5: Bounded Autonomous Action Dispatch
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
            txn.queue_status = "PENDING_REVIEW"
            txn.escalated_at = datetime.utcnow()

        # Step 6: State Transition & Audit Ledger Recording
        if success:
            txn.status = "recovered"
            txn.queue_status = "RESOLVED"
            recovered_count += 1
            revenue_recovered += txn.amount
            log_reason = f"Decision: {decision}. Execution successful. ₹{txn.amount:,.2f} recovered."
        elif decision != "ESCALATE_TO_HUMAN":
            txn.retry_count += 1
            log_reason = f"Decision: {decision}. Automated attempt failed on gateway (Retry #{txn.retry_count})."
        else:
            log_reason = f"Decision: ESCALATE_TO_HUMAN. Queued for manual operator investigation."

        log = AuditLog(
            transaction_id=txn.id,
            agent_decision=decision,
            reasoning=log_reason,
            tokens_used=tokens_used,
            cost_inr=cost_inr
        )
        db.add(log)

    db.commit()

    recovery_rate = (recovered_count / attempted * 100) if attempted > 0 else 0.0
    net_value = revenue_recovered - total_batch_cost
    roi_mult = (revenue_recovered / total_batch_cost) if total_batch_cost > 0 else (revenue_recovered if revenue_recovered > 0 else 0.0)

    return ProcessBatchResponse(
        total_processed=len(failed_txns),
        at_risk_detected=total_at_risk,
        recovery_attempted=attempted,
        successfully_recovered=recovered_count,
        escalated_or_stopped=stopped_or_escalated,
        fraud_rings_isolated=fraud_rings_isolated,
        total_amount_at_risk=round(amount_at_risk, 2),
        total_revenue_recovered=round(revenue_recovered, 2),
        recovery_rate_pct=round(recovery_rate, 2),
        total_operational_cost_inr=round(total_batch_cost, 4),
        net_value_recovered=round(net_value, 2),
        roi_multiplier=round(roi_mult, 1)
    )

@router.get("/escalation-queue", response_model=List[EscalationQueueItem])
def get_escalation_queue(
    status: str = Query("PENDING_REVIEW", description="Queue status filter"),
    db: Session = Depends(get_db)
):
    """Fetches transactions awaiting human review with their latest audit diagnostics."""
    query = db.query(Transaction)
    if status != "ALL":
        query = query.filter(Transaction.queue_status == status)
    
    escalated_items = query.order_by(Transaction.created_at.desc()).all()
    
    response = []
    for item in escalated_items:
        # Fetch the most recent audit log entry for this transaction
        latest_log = (
            db.query(AuditLog)
            .filter(AuditLog.transaction_id == item.id)
            .order_by(AuditLog.timestamp.desc())
            .first()
        )
        
        response.append(EscalationQueueItem(
            id=item.id,
            customer_id=item.customer_id,
            amount=item.amount,
            status=item.status,
            failure_reason=item.failure_reason,
            retry_count=item.retry_count,
            ip_address=item.ip_address,
            device_id=item.device_id,
            is_fraud_ring=bool(item.is_fraud_ring),
            queue_status=item.queue_status or "NONE",
            reviewer_notes=item.reviewer_notes,
            escalated_at=item.escalated_at,
            reviewed_at=item.reviewed_at,
            created_at=item.created_at,
            latest_audit_reason=latest_log.reasoning if latest_log else "No audit log available"
        ))
    
    return response

@router.post("/escalation-queue/{txn_id}/action")
def review_escalated_transaction(
    txn_id: str,
    payload: ReviewEscalationRequest,
    db: Session = Depends(get_db)
):
    """Executes human approval or rejection on an escalated transaction."""
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail=f"Transaction {txn_id} not found.")

    action = payload.action.upper()
    notes = payload.reviewer_notes or "Review decision submitted via Escalation Queue"
    now = datetime.utcnow()

    if action in ["APPROVE_RETRY", "APPROVE_PAYMENT_LINK", "APPROVE"]:
        # Human approved recovery intervention
        rec_prob = risk_scorer.predict_recovery_probability(txn.failure_reason, txn.amount, txn.retry_count)
        
        if "LINK" in action:
            success = razorpay_gateway.send_payment_link(txn.amount)
            exec_method = "PAYMENT_LINK"
        else:
            success = razorpay_gateway.execute_retry(txn.amount, rec_prob)
            exec_method = "MANUAL_RETRY"

        if success:
            txn.status = "recovered"
            txn.queue_status = "APPROVED"
            result_msg = f"Human Approved ({exec_method}). Successfully recovered ₹{txn.amount:,.2f}."
        else:
            txn.retry_count += 1
            txn.queue_status = "RETRY_FAILED"
            result_msg = f"Human Approved ({exec_method}). Gateway execution did not succeed."

        txn.reviewed_at = now
        txn.reviewer_notes = f"{notes} | {result_msg}"

        log = AuditLog(
            transaction_id=txn.id,
            agent_decision=f"HUMAN_APPROVED_{exec_method}",
            reasoning=f"Operator Action: {notes}. Execution: {result_msg}",
            tokens_used=0,
            cost_inr=0.0
        )
        db.add(log)
        db.commit()

        return {
            "status": "success",
            "transaction_id": txn_id,
            "queue_status": txn.queue_status,
            "recovered": success,
            "message": result_msg
        }

    elif action == "REJECT":
        txn.queue_status = "REJECTED"
        txn.reviewed_at = now
        txn.reviewer_notes = f"{notes} | Escalation Rejected. Transaction marked unrecoverable/blocked."

        log = AuditLog(
            transaction_id=txn.id,
            agent_decision="HUMAN_REJECTED",
            reasoning=f"Operator Rejected: {notes}",
            tokens_used=0,
            cost_inr=0.0
        )
        db.add(log)
        db.commit()

        return {
            "status": "success",
            "transaction_id": txn_id,
            "queue_status": "REJECTED",
            "message": f"Transaction {txn_id} successfully marked as REJECTED."
        }

    else:
        raise HTTPException(status_code=400, detail=f"Invalid action '{action}'. Use APPROVE_RETRY, APPROVE_PAYMENT_LINK, or REJECT.")

@router.get("/roi-metrics", response_model=ROIMetricsResponse)
def get_roi_metrics(db: Session = Depends(get_db)):
    """Calculates executive ROI unit economics and operational metrics."""
    all_txns = db.query(Transaction).all()
    all_logs = db.query(AuditLog).all()

    total_recovered = sum(t.amount for t in all_txns if t.status == "recovered")
    total_at_risk = sum(t.amount for t in all_txns if t.status in ["failed", "recovered", "escalated"])
    
    total_tokens = sum(log.tokens_used or 0 for log in all_logs)
    total_cost = sum(log.cost_inr or 0.0 for log in all_logs)
    
    # Add nominal simulated gateway API cost for attempts (~₹0.05 per retry attempt)
    attempt_count = sum(1 for log in all_logs if "RETRY" in log.agent_decision or "LINK" in log.agent_decision)
    gateway_cost = attempt_count * 0.05
    total_operational_cost = total_cost + gateway_cost

    net_recovered = total_recovered - total_operational_cost
    roi_multiplier = (total_recovered / total_operational_cost) if total_operational_cost > 0 else (total_recovered if total_recovered > 0 else 0.0)
    
    recovered_count = sum(1 for t in all_txns if t.status == "recovered")
    attempted_count = len([t for t in all_txns if t.retry_count > 0 or t.status == "recovered"])
    recovery_rate = (recovered_count / attempted_count * 100) if attempted_count > 0 else 0.0
    
    escalated_count = sum(1 for t in all_txns if t.queue_status in ["PENDING_REVIEW", "APPROVED", "REJECTED"])
    fraud_rings_count = sum(1 for t in all_txns if t.is_fraud_ring)

    return ROIMetricsResponse(
        total_recovered_revenue=round(total_recovered, 2),
        total_at_risk_revenue=round(total_at_risk, 2),
        total_operational_cost=round(total_operational_cost, 4),
        total_api_tokens=total_tokens,
        net_revenue_recovered=round(net_recovered, 2),
        roi_multiplier=round(roi_multiplier, 1),
        recovery_rate_pct=round(recovery_rate, 2),
        escalated_count=escalated_count,
        fraud_rings_prevented_count=fraud_rings_count,
        total_processed=len(all_txns)
    )

@router.get("/fraud-network")
def get_fraud_network_topology(limit: int = 70, db: Session = Depends(get_db)):
    """Exports graph network nodes and link relationships for interactive dashboard visualizer."""
    fraud_graph_detector.build_graph_from_db(db)
    return fraud_graph_detector.export_graph_topology(limit_nodes=limit)

@router.get("/audit-logs", response_model=List[AuditLogSchema])
def get_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()