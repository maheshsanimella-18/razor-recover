from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from datetime import datetime, timezone
from .session import Base

def utcnow():
    return datetime.now(timezone.utc)

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)          # e.g., txn_1001
    customer_id = Column(String, index=True)                   # e.g., cust_123
    amount = Column(Float, nullable=False)                     # e.g., 8000.00
    currency = Column(String, default="INR")                   # e.g., 'INR'
    status = Column(String, default="failed", index=True)      # 'failed', 'recovered', 'escalated', 'stopped', 'pending'
    lifecycle_state = Column(String, default="AT_RISK")        # 'AT_RISK', 'DIAGNOSING', 'ACTION_PENDING', 'ACTION_EXECUTED', 'RECOVERED', 'ESCALATED', 'STOPPED'
    failure_reason = Column(String, nullable=True)             # e.g., 'insufficient_balance', 'network_timeout', 'suspected_fraud'
    payment_method = Column(String, default="card")            # 'card', 'upi', 'netbanking', 'mandate'
    retry_count = Column(Integer, default=0)
    idempotency_key = Column(String, nullable=True, index=True)

    # Customer & Behavioral Context
    customer_tenure_months = Column(Integer, default=12)
    past_success_rate = Column(Float, default=0.85)
    past_failed_attempts = Column(Integer, default=0)
    risk_score = Column(Float, default=0.5)

    # Networked Fraud Detection Attributes (Graph Nodes & Edges)
    ip_address = Column(String, index=True, nullable=True)
    device_id = Column(String, index=True, nullable=True)
    is_fraud_ring = Column(Boolean, default=False)

    # Human-in-the-Loop Queue Attributes
    queue_status = Column(String, default="NONE", index=True)  # 'NONE', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'RESOLVED'
    reviewer_notes = Column(Text, nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True, nullable=True)       # Unique event UUID (e.g. evt_99812)
    transaction_id = Column(String, index=True)
    actor = Column(String, default="AI_AGENT")                 # 'SYSTEM', 'AI_AGENT', 'SAFETY_GUARDRAIL', 'HUMAN_OPERATOR'
    event_type = Column(String, default="RECOVERY_ACTION")     # 'RISK_SCORED', 'FRAUD_CHECKED', 'DIAGNOSIS', 'POLICY_VALIDATION', 'ACTION_EXECUTED'
    agent_decision = Column(String)                            # e.g., 'IMMEDIATE_RETRY', 'ESCALATE_TO_HUMAN', 'BLOCKED_FRAUD_GRAPH'
    reasoning = Column(Text)                                   # Detailed diagnosis, evidence trace, or policy justification
    
    previous_state = Column(String, nullable=True)
    new_state = Column(String, nullable=True)
    
    # Financial & Unit Economics Tracking
    tokens_used = Column(Integer, default=0)
    cost_inr = Column(Float, default=0.0)
    amount_recovered = Column(Float, default=0.0)
    
    timestamp = Column(DateTime, default=utcnow)