from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
from .session import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)      # e.g., txn_1001
    customer_id = Column(String, index=True)               # e.g., cust_123
    amount = Column(Float)                                 # e.g., 8000.00
    status = Column(String)                                # 'failed', 'success', 'recovered', 'escalated'
    failure_reason = Column(String, nullable=True)         # e.g., 'insufficient_balance', 'suspected_fraud'
    retry_count = Column(Integer, default=0)

    # 1. Networked Fraud Detection Attributes (Graph Nodes & Edges)
    ip_address = Column(String, index=True, nullable=True)       # e.g., '192.168.1.45'
    device_id = Column(String, index=True, nullable=True)        # e.g., 'dev_fingerprint_829'
    is_fraud_ring = Column(Boolean, default=False)               # Flagged by graph engine

    # 2. Human-in-the-Loop Queue Attributes
    queue_status = Column(String, default="NONE", index=True)    # 'NONE', 'PENDING_REVIEW', 'APPROVED', 'REJECTED'
    reviewer_notes = Column(String, nullable=True)               # Rationale recorded by human operator
    escalated_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, index=True)
    agent_decision = Column(String)                        # e.g., 'IMMEDIATE_RETRY', 'ESCALATE_TO_HUMAN', 'BLOCKED_FRAUD_GRAPH'
    reasoning = Column(String)                             # Why the AI or safety guardrail made this choice
    
    # 3. Executive ROI & Cost Attribution
    tokens_used = Column(Integer, default=0)               # LLM prompt + completion tokens
    cost_inr = Column(Float, default=0.0)                  # Estimated operational cost of recovery intervention (INR)
    
    timestamp = Column(DateTime, default=datetime.utcnow)