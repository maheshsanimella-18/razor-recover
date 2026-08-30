from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ProcessBatchResponse(BaseModel):
    total_processed: int
    at_risk_detected: int
    recovery_attempted: int
    successfully_recovered: int
    escalated_or_stopped: int
    total_amount_at_risk: float
    total_revenue_recovered: float
    recovery_rate_pct: float

class AuditLogSchema(BaseModel):
    id: int
    transaction_id: str
    agent_decision: str
    reasoning: str
    timestamp: datetime

    class Config:
        from_attributes = True