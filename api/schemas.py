from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class ProcessBatchResponse(BaseModel):
    total_processed: int
    at_risk_detected: int
    recovery_attempted: int
    successfully_recovered: int
    escalated_or_stopped: int
    fraud_rings_isolated: int
    total_amount_at_risk: float
    total_revenue_recovered: float
    recovery_rate_pct: float
    total_operational_cost_inr: float
    net_value_recovered: float
    roi_multiplier: float

class WebhookPaymentFailedRequest(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float
    failure_reason: str
    payment_method: Optional[str] = "card"
    ip_address: Optional[str] = None
    device_id: Optional[str] = None
    created_at: Optional[datetime] = None

class WebhookRecoveryResponse(BaseModel):
    transaction_id: str
    lifecycle_state: str
    diagnosis: str
    risk_level: str
    recommended_action: str
    action_executed: bool
    recovery_status: str
    amount_recovered: float
    execution_mode: str = "SIMULATED_TEST_MODE"
    idempotency_key: Optional[str] = None

class AuditLogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: Optional[str] = None
    transaction_id: str
    actor: Optional[str] = "AI_AGENT"
    event_type: Optional[str] = "RECOVERY_ACTION"
    agent_decision: str
    reasoning: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    tokens_used: int = 0
    cost_inr: float = 0.0
    amount_recovered: float = 0.0
    timestamp: datetime

class EscalationQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    amount: float
    status: str
    failure_reason: Optional[str] = None
    payment_method: Optional[str] = "card"
    retry_count: int
    ip_address: Optional[str] = None
    device_id: Optional[str] = None
    is_fraud_ring: bool
    queue_status: str
    reviewer_notes: Optional[str] = None
    escalated_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    latest_audit_reason: Optional[str] = None

class ReviewEscalationRequest(BaseModel):
    action: str  # 'APPROVE_RETRY', 'APPROVE_PAYMENT_LINK', 'REJECT'
    reviewer_notes: Optional[str] = "Manual review action from Escalation Queue"

class ROIMetricsResponse(BaseModel):
    total_recovered_revenue: float
    total_at_risk_revenue: float
    total_operational_cost: float
    total_api_tokens: int
    net_revenue_recovered: float
    roi_multiplier: float
    recovery_rate_pct: float
    escalated_count: int
    fraud_rings_prevented_count: int
    total_processed: int

class BenchmarkResponse(BaseModel):
    test_sample_size: int
    comparison: List[Dict[str, Any]]
    lift_over_naive_inr: float
    lift_over_rules_inr: float
    relative_recovery_rate_lift_pct: float