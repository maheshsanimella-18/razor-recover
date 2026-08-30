from pydantic import BaseModel
from typing import Optional, List
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

class AuditLogSchema(BaseModel):
    id: int
    transaction_id: str
    agent_decision: str
    reasoning: str
    tokens_used: int
    cost_inr: float
    timestamp: datetime

    class Config:
        from_attributes = True

class EscalationQueueItem(BaseModel):
    id: str
    customer_id: str
    amount: float
    status: str
    failure_reason: Optional[str] = None
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

    class Config:
        from_attributes = True

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