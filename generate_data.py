import random
import pandas as pd
from database.session import engine, Base, SessionLocal
from database.models import Transaction, AuditLog

# THIS IS THE FIX: Drop old tables before creating new ones
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def generate_mock_data(num_records=1000):
    db = SessionLocal()
    
    # Typical payment failure reasons
    failure_reasons = ['insufficient_balance', 'network_timeout', 'invalid_card', 'suspected_fraud']
    
    transactions = []
    
    for i in range(num_records):
        # Let's simulate an 18% payment failure rate
        is_failed = random.random() < 0.18 
        
        status = 'failed' if is_failed else 'success'
        reason = random.choice(failure_reasons) if is_failed else None
        amount = round(random.uniform(500.0, 15000.0), 2)
        
        txn = Transaction(
            id=f"txn_{1000 + i}",
            customer_id=f"cust_{random.randint(100, 500)}",
            amount=amount,
            status=status,
            failure_reason=reason,
            retry_count=0
        )
        db.add(txn)
        
        transactions.append({
            "id": txn.id, 
            "customer_id": txn.customer_id, 
            "amount": amount, 
            "status": status, 
            "failure_reason": reason
        })
        
    db.commit()
    db.close()
    
    df = pd.DataFrame(transactions)
    df.to_csv('data/synthetic_transactions.csv', index=False)
    print(f"Success! Generated {num_records} fresh transactions.")

if __name__ == "__main__":
    generate_mock_data()