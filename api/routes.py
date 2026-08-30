from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import uuid

from database.session import get_db
from database.models import Transaction, AuditLog
from core.risk_model import risk_scorer
from core.policy import policy_engine
from core.agent import recovery_agent
from core.fraud_graph import fraud_graph_detector
from core.simulator import payment_simulator
from core.state_machine import state_machine, TransactionState
from core.tools import record_audit_event, get_customer_history, execute_bounded_action
from core.demo import run_safe_recovery_demo, run_fraud_block_demo
from core.benchmark import BenchmarkRunner
from api.schemas import (
    ProcessBatchResponse, 
    AuditLogSchema, 
    EscalationQueueItem, 
    ReviewEscalationRequest, 
    ROIMetricsResponse,
    WebhookPaymentFailedRequest,
    WebhookRecoveryResponse,
    BenchmarkResponse
)

router = APIRouter()

@router.post("/process-batch", response_model=ProcessBatchResponse)
def process_failed_batch(db: Session = Depends(get_db)):
    """
    Autonomous Closed-Loop Revenue Recovery Pipeline:
    1. Builds/refreshes entity graph to isolate syndicated fraud clusters (bypassing LLM).
    2. Gathers customer history and computes ML risk score.
    3. Executes structured Gemini diagnosis agent.
    4. Validates decision against deterministic policy engine.
    5. Dispatches bounded recovery action, updates state machine, and records audit trail.
    """
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
            txn.status = "escalated"
            txn.lifecycle_state = TransactionState.ESCALATED.value
            txn.queue_status = "PENDING_REVIEW"
            txn.escalated_at = datetime.now(timezone.utc)
            stopped_or_escalated += 1
            fraud_rings_isolated += 1

            fraud_msg = (
                f"NETWORKED_FRAUD_DETECTED: Connected to {cluster_details['connected_fraud_count']} "
                f"fraud node(s) across shared entity infrastructure (IP: {txn.ip_address}, Device: {txn.device_id}). "
                f"Bypassed LLM."
            )
            record_audit_event(
                db=db,
                txn_id=txn.id,
                actor="SAFETY_GUARDRAIL",
                event_type="FRAUD_GATE_TRIGGERED",
                decision="BLOCKED_FRAUD_GRAPH",
                reasoning=fraud_msg,
                prev_state=TransactionState.AT_RISK.value,
                new_state=TransactionState.ESCALATED.value,
                tokens=0,
                cost_inr=0.0
            )
            continue

        # Step 2: Customer History & ML Risk Probability Scoring
        cust_profile = get_customer_history(txn.customer_id, db)
        rec_prob = risk_scorer.predict_recovery_probability(
            failure_reason=txn.failure_reason or "unknown",
            amount=txn.amount,
            retry_count=txn.retry_count,
            payment_method=txn.payment_method or "card",
            customer_tenure_months=cust_profile.get("tenure_months", 12),
            past_success_rate=cust_profile.get("success_rate", 0.85)
        )
        txn.risk_score = rec_prob

        # Step 3: Structured Gemini Agent Diagnosis
        summary_str = f"Tenure: {cust_profile.get('tenure_months')}mo, Success Rate: {cust_profile.get('success_rate')*100:.0f}%, Tier: {cust_profile.get('reliability_tier')}"
        decision_obj, tokens_used, cost_inr = recovery_agent.diagnose_and_decide(
            transaction_id=txn.id,
            amount=txn.amount,
            failure_reason=txn.failure_reason or "unknown",
            recovery_prob=rec_prob,
            customer_summary=summary_str,
            payment_method=txn.payment_method or "card",
            retry_count=txn.retry_count
        )
        total_batch_cost += cost_inr

        # Step 4: Deterministic Policy Engine Validation
        pol_res = policy_engine.evaluate_action(
            action=decision_obj.recommended_action,
            amount=txn.amount,
            retry_count=txn.retry_count,
            failure_reason=txn.failure_reason or "unknown",
            recovery_probability=rec_prob,
            is_fraud_connected=False
        )

        if not pol_res.is_allowed or pol_res.requires_human_escalation:
            stopped_or_escalated += 1
            txn.status = "escalated"
            txn.lifecycle_state = TransactionState.ESCALATED.value
            txn.queue_status = "PENDING_REVIEW"
            txn.escalated_at = datetime.now(timezone.utc)
            
            record_audit_event(
                db=db,
                txn_id=txn.id,
                actor="POLICY_ENGINE",
                event_type="POLICY_ESCALATION",
                decision="STOPPED_BY_GUARDRAIL",
                reasoning=f"Policy Block ({pol_res.policy_code}): {pol_res.reason}",
                prev_state=TransactionState.AT_RISK.value,
                new_state=TransactionState.ESCALATED.value,
                tokens=tokens_used,
                cost_inr=cost_inr
            )
            continue

        # Step 5: Bounded Action Dispatch via Closed-Loop Simulator
        action = decision_obj.recommended_action
        sim_result = execute_bounded_action(
            action=action,
            txn_id=txn.id,
            db=db,
            recovery_prob=rec_prob
        )
        
        attempted += 1
        is_success = sim_result.get("success", False)

        # Step 6: State Machine Transition & Audit Recording
        if is_success:
            txn.status = "recovered"
            txn.lifecycle_state = TransactionState.RECOVERED.value
            txn.queue_status = "RESOLVED"
            recovered_count += 1
            revenue_recovered += txn.amount
            log_reason = f"Decision: {action}. Captured ₹{txn.amount:,.2f}. Gateway Ref: {sim_result.get('gateway_reference_id')}."
            new_st = TransactionState.RECOVERED.value
        else:
            txn.retry_count += 1
            txn.lifecycle_state = TransactionState.AT_RISK.value
            log_reason = f"Decision: {action}. Gateway attempt failed ({sim_result.get('status_code')}). Retry #{txn.retry_count} recorded."
            new_st = TransactionState.AT_RISK.value

        record_audit_event(
            db=db,
            txn_id=txn.id,
            actor="AI_AGENT",
            event_type="ACTION_COMPLETED",
            decision=action,
            reasoning=f"Diagnosis: {decision_obj.diagnosis} | Execution: {log_reason}",
            prev_state=TransactionState.DIAGNOSING.value,
            new_state=new_st,
            tokens=tokens_used,
            cost_inr=cost_inr,
            amount_recovered=txn.amount if is_success else 0.0
        )

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

@router.post("/webhooks/payment-failed", response_model=WebhookRecoveryResponse)
def handle_payment_failed_webhook(payload: WebhookPaymentFailedRequest, db: Session = Depends(get_db)):
    """
    Real-time Webhook Ingestion Endpoint:
    Receives live payment failure webhooks from Razorpay, runs autonomous investigation,
    and returns immediate intervention decision & execution status.
    """
    txn_id = payload.transaction_id
    
    # Upsert transaction
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        txn = Transaction(
            id=txn_id,
            customer_id=payload.customer_id,
            amount=payload.amount,
            currency="INR",
            status="failed",
            lifecycle_state=TransactionState.AT_RISK.value,
            failure_reason=payload.failure_reason,
            payment_method=payload.payment_method or "card",
            retry_count=0,
            ip_address=payload.ip_address,
            device_id=payload.device_id,
            queue_status="NONE",
            created_at=datetime.now(timezone.utc)
        )
        db.add(txn)
        db.commit()

    # Step 1: Real-time Network Fraud Check
    fraud_graph_detector.build_graph_from_db(db)
    is_fraud, fraud_details = fraud_graph_detector.analyze_transaction_network(
        txn_id=txn.id,
        ip_address=txn.ip_address,
        device_id=txn.device_id
    )

    if is_fraud:
        txn.status = "escalated"
        txn.lifecycle_state = TransactionState.ESCALATED.value
        txn.queue_status = "PENDING_REVIEW"
        txn.is_fraud_ring = True
        db.commit()

        record_audit_event(
            db=db,
            txn_id=txn.id,
            actor="SAFETY_GUARDRAIL",
            event_type="WEBHOOK_FRAUD_BLOCKED",
            decision="BLOCKED_FRAUD_GRAPH",
            reasoning=f"Webhook Event: Fraud syndicate cluster isolated ({fraud_details.get('connected_fraud_count')} nodes).",
            new_state=TransactionState.ESCALATED.value
        )

        return WebhookRecoveryResponse(
            transaction_id=txn.id,
            lifecycle_state=TransactionState.ESCALATED.value,
            diagnosis="Flagged as syndicate fraud cluster. Bypassed automated retry.",
            risk_level="CRITICAL",
            recommended_action="ESCALATE_TO_HUMAN",
            action_executed=False,
            recovery_status="ESCALATED_TO_HUMAN_QUEUE",
            amount_recovered=0.0
        )

    # Step 2: ML Probability & Agent Decision
    cust_profile = get_customer_history(txn.customer_id, db)
    rec_prob = risk_scorer.predict_recovery_probability(
        failure_reason=txn.failure_reason or "unknown",
        amount=txn.amount,
        retry_count=txn.retry_count,
        payment_method=txn.payment_method or "card"
    )

    decision_obj, tokens, cost = recovery_agent.diagnose_and_decide(
        transaction_id=txn.id,
        amount=txn.amount,
        failure_reason=txn.failure_reason or "unknown",
        recovery_prob=rec_prob,
        customer_summary=f"Tenure: {cust_profile.get('tenure_months')}mo, Success: {cust_profile.get('success_rate')*100:.0f}%",
        payment_method=txn.payment_method or "card"
    )

    # Step 3: Policy Check
    pol_res = policy_engine.evaluate_action(
        action=decision_obj.recommended_action,
        amount=txn.amount,
        retry_count=txn.retry_count,
        failure_reason=txn.failure_reason or "unknown",
        recovery_probability=rec_prob
    )

    if not pol_res.is_allowed:
        txn.status = "escalated"
        txn.lifecycle_state = TransactionState.ESCALATED.value
        txn.queue_status = "PENDING_REVIEW"
        db.commit()

        return WebhookRecoveryResponse(
            transaction_id=txn.id,
            lifecycle_state=TransactionState.ESCALATED.value,
            diagnosis=decision_obj.diagnosis,
            risk_level=decision_obj.risk_level,
            recommended_action=decision_obj.recommended_action,
            action_executed=False,
            recovery_status="STOPPED_BY_POLICY",
            amount_recovered=0.0
        )

    # Step 4: Dispatch Action
    sim_res = execute_bounded_action(
        action=decision_obj.recommended_action,
        txn_id=txn.id,
        db=db,
        recovery_prob=rec_prob
    )
    is_success = sim_res.get("success", False)

    if is_success:
        txn.status = "recovered"
        txn.lifecycle_state = TransactionState.RECOVERED.value
        txn.queue_status = "RESOLVED"
    else:
        txn.retry_count += 1

    db.commit()

    record_audit_event(
        db=db,
        txn_id=txn.id,
        actor="AI_AGENT",
        event_type="WEBHOOK_RECOVERY_EXECUTED",
        decision=decision_obj.recommended_action,
        reasoning=f"Webhook Dispatch: {sim_res.get('message')}",
        new_state=txn.lifecycle_state,
        tokens=tokens,
        cost_inr=cost,
        amount_recovered=txn.amount if is_success else 0.0
    )

    return WebhookRecoveryResponse(
        transaction_id=txn.id,
        lifecycle_state=txn.lifecycle_state,
        diagnosis=decision_obj.diagnosis,
        risk_level=decision_obj.risk_level,
        recommended_action=decision_obj.recommended_action,
        action_executed=True,
        recovery_status="RECOVERED" if is_success else "RETRY_DISPATCHED",
        amount_recovered=txn.amount if is_success else 0.0,
        idempotency_key=txn.idempotency_key
    )

@router.post("/demo/run")
def execute_pitch_demo(scenario: str = Query("A", description="Scenario 'A' (Safe Recovery) or 'B' (Fraud Block)"), db: Session = Depends(get_db)):
    """Executes a 100% deterministic pitch scenario for 5-minute competition presentations."""
    if scenario.upper() == "A":
        return run_safe_recovery_demo(db)
    elif scenario.upper() == "B":
        return run_fraud_block_demo(db)
    else:
        return {
            "scenario_a": run_safe_recovery_demo(db),
            "scenario_b": run_fraud_block_demo(db)
        }

@router.get("/benchmarks", response_model=BenchmarkResponse)
def get_benchmarks(samples: int = 500):
    """Returns honest, reproducible empirical benchmark evaluation comparing Naive, Rules, and AI Agent."""
    return BenchmarkRunner.run_full_benchmark(n_samples=samples)

@router.get("/model-metrics")
def get_ml_model_metrics():
    """Returns held-out test evaluation metrics for the ML Random Forest risk scorer."""
    return risk_scorer.get_evaluation_metrics()

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
            payment_method=item.payment_method or "card",
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
    now = datetime.now(timezone.utc)

    if action in ["APPROVE_RETRY", "APPROVE_PAYMENT_LINK", "APPROVE"]:
        rec_prob = risk_scorer.predict_recovery_probability(
            failure_reason=txn.failure_reason or "unknown",
            amount=txn.amount,
            retry_count=txn.retry_count
        )
        
        if "LINK" in action:
            sim_res = payment_simulator.send_payment_link(txn.amount, customer_id=txn.customer_id)
            exec_method = "PAYMENT_LINK"
        else:
            sim_res = payment_simulator.execute_retry(txn.amount, recovery_probability=rec_prob)
            exec_method = "MANUAL_RETRY"

        is_success = sim_res.success
        if is_success:
            txn.status = "recovered"
            txn.lifecycle_state = TransactionState.RECOVERED.value
            txn.queue_status = "APPROVED"
            result_msg = f"Human Approved ({exec_method}). Successfully recovered ₹{txn.amount:,.2f}."
        else:
            txn.retry_count += 1
            txn.queue_status = "RETRY_FAILED"
            result_msg = f"Human Approved ({exec_method}). Gateway execution did not succeed."

        txn.reviewed_at = now
        txn.reviewer_notes = f"{notes} | {result_msg}"

        record_audit_event(
            db=db,
            txn_id=txn.id,
            actor="HUMAN_OPERATOR",
            event_type="HUMAN_INTERVENTION",
            decision=f"HUMAN_APPROVED_{exec_method}",
            reasoning=f"Operator Action: {notes}. Execution: {result_msg}",
            new_state=txn.lifecycle_state,
            amount_recovered=txn.amount if is_success else 0.0
        )
        db.commit()

        return {
            "status": "success",
            "transaction_id": txn_id,
            "queue_status": txn.queue_status,
            "recovered": is_success,
            "message": result_msg
        }

    elif action == "REJECT":
        txn.status = "stopped"
        txn.lifecycle_state = TransactionState.STOPPED.value
        txn.queue_status = "REJECTED"
        txn.reviewed_at = now
        txn.reviewer_notes = f"{notes} | Escalation Rejected. Transaction marked unrecoverable/blocked."

        record_audit_event(
            db=db,
            txn_id=txn.id,
            actor="HUMAN_OPERATOR",
            event_type="HUMAN_REJECTION",
            decision="HUMAN_REJECTED",
            reasoning=f"Operator Rejected: {notes}",
            new_state=TransactionState.STOPPED.value
        )
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
    
    # Nominal gateway API cost (~₹0.05 per retry attempt)
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