import random
import pandas as pd
from datetime import datetime, timezone
from database.session import engine, Base, SessionLocal
from database.models import Transaction, AuditLog

# Drop old tables before creating new ones with the updated schema
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def generate_mock_data(num_records=1000):
    db = SessionLocal()
    
    failure_reasons = ['insufficient_balance', 'network_timeout', 'invalid_card', 'otp_abandoned', 'suspected_fraud']
    payment_methods = ['upi', 'card', 'netbanking', 'mandate']
    
    # Generate entity pools to simulate network graphs & shared attributes
    customer_pool = [f"cust_{i}" for i in range(100, 350)]
    ip_pool = [f"192.168.{random.randint(1, 20)}.{random.randint(1, 254)}" for _ in range(120)]
    device_pool = [f"dev_{random.choice(['ios', 'android', 'web'])}_{random.randint(1000, 9999)}" for _ in range(150)]
    
    # Dedicated Fraud Syndicate Seed Pools (creates distinct graph clusters)
    fraud_syndicate_ips = ["198.51.100.42", "198.51.100.88", "203.0.113.15"]
    fraud_syndicate_devices = ["dev_rooted_fraud_99", "dev_botnet_alpha_12", "dev_emulator_x99"]
    
    transactions = []
    
    for i in range(num_records):
        txn_id = f"txn_{1000 + i}"
        
        # Simulate syndicate cluster membership (~4% of total traffic)
        is_syndicate = random.random() < 0.04
        method = random.choice(payment_methods)
        
        if is_syndicate:
            customer_id = f"cust_bad_{random.randint(1, 10)}"
            ip_address = random.choice(fraud_syndicate_ips)
            device_id = random.choice(fraud_syndicate_devices)
            is_failed = True
            reason = "suspected_fraud" if random.random() < 0.65 else random.choice(['invalid_card', 'insufficient_balance'])
            status = "failed"
            amount = round(random.uniform(7000.0, 28000.0), 2)
            tenure = random.randint(1, 3)
            past_success_rate = round(random.uniform(0.1, 0.4), 2)
            past_fails = random.randint(3, 8)
        else:
            customer_id = random.choice(customer_pool)
            ip_address = random.choice(ip_pool)
            device_id = random.choice(device_pool)
            
            # Simulate standard 18% failure rate
            is_failed = random.random() < 0.18
            status = 'failed' if is_failed else 'success'
            reason = random.choice(['insufficient_balance', 'network_timeout', 'invalid_card', 'otp_abandoned']) if is_failed else None
            amount = round(random.uniform(500.0, 16000.0), 2)
            tenure = random.randint(4, 48)
            past_success_rate = round(random.uniform(0.70, 0.98), 2)
            past_fails = random.randint(0, 2)
            
        txn = Transaction(
            id=txn_id,
            customer_id=customer_id,
            amount=amount,
            currency="INR",
            status=status,
            lifecycle_state="AT_RISK" if is_failed else "RECOVERED",
            failure_reason=reason,
            payment_method=method,
            retry_count=0,
            customer_tenure_months=tenure,
            past_success_rate=past_success_rate,
            past_failed_attempts=past_fails,
            risk_score=0.5,
            ip_address=ip_address,
            device_id=device_id,
            is_fraud_ring=False,
            queue_status="NONE",
            reviewer_notes=None,
            created_at=datetime.now(timezone.utc)
        )
        db.add(txn)
        
        transactions.append({
            "id": txn.id, 
            "customer_id": txn.customer_id, 
            "amount": amount, 
            "status": status, 
            "failure_reason": reason,
            "payment_method": method,
            "customer_tenure_months": tenure,
            "past_success_rate": past_success_rate,
            "ip_address": ip_address,
            "device_id": device_id,
            "is_fraud_ring": False,
            "queue_status": "NONE"
        })
        
    db.commit()
    db.close()
    
    df = pd.DataFrame(transactions)
    df.to_csv('data/synthetic_transactions.csv', index=False)
    print(f"Success! Generated {num_records} fresh transactions with rich behavioral & graph network attributes.")

if __name__ == "__main__":
    generate_mock_data()