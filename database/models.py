from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from .session import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)      # e.g., txn_1001
    customer_id = Column(String, index=True)               # e.g., cust_A
    amount = Column(Float)                                 # e.g., 8000.00
    status = Column(String)                                # 'failed', 'success', 'recovered'
    failure_reason = Column(String, nullable=True)         # e.g., 'insufficient_funds'
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, index=True)
    agent_decision = Column(String)                        # e.g., 'retry', 'escalate'
    reasoning = Column(String)                             # Why the AI made this choice
    timestamp = Column(DateTime, default=datetime.utcnow)