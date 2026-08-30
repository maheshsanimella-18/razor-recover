import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import pickle
import os

MODEL_PATH = "core/risk_model.pkl"

class RecoveryRiskModel:
    def __init__(self):
        self.model = None
        self.failure_reason_map = {
            'network_timeout': 0,
            'insufficient_balance': 1,
            'invalid_card': 2,
            'suspected_fraud': 3
        }
        self.load_or_train_model()

    def _generate_training_data(self):
        """Creates training features based on payment failure dynamics"""
        np.random.seed(42)
        n_samples = 2000
        
        reasons = np.random.choice(list(self.failure_reason_map.keys()), size=n_samples, p=[0.35, 0.40, 0.15, 0.10])
        amounts = np.random.uniform(500.0, 15000.0, size=n_samples)
        retry_counts = np.random.choice([0, 1, 2, 3], size=n_samples, p=[0.6, 0.25, 0.1, 0.05])
        
        # Ground truth simulation:
        # High recovery: network_timeout or low amount insufficient_balance
        # Low recovery: suspected_fraud, invalid_card, high retries
        labels = []
        for r, amt, retries in zip(reasons, amounts, retry_counts):
            if r == 'suspected_fraud' or r == 'invalid_card' or retries >= 2:
                labels.append(0)  # Unlikely to recover automatically
            elif r == 'network_timeout':
                labels.append(1 if np.random.rand() < 0.85 else 0)
            elif r == 'insufficient_balance':
                # Higher amounts are harder to recover on simple immediate retry
                prob = 0.75 if amt < 5000 else 0.45
                labels.append(1 if np.random.rand() < prob else 0)
            else:
                labels.append(0)

        encoded_reasons = [self.failure_reason_map[r] for r in reasons]
        
        X = pd.DataFrame({
            'failure_reason_code': encoded_reasons,
            'amount': amounts,
            'retry_count': retry_counts
        })
        y = np.array(labels)
        return X, y

    def load_or_train_model(self):
        """Loads saved model or trains a new Random Forest model"""
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                self.model = pickle.load(f)
        else:
            X, y = self._generate_training_data()
            self.model = RandomForestClassifier(n_estimators=50, random_state=42)
            self.model.fit(X, y)
            with open(MODEL_PATH, "wb") as f:
                pickle.dump(self.model, f)

    def predict_recovery_probability(self, failure_reason: str, amount: float, retry_count: int = 0) -> float:
        """Returns the probability score (0.0 to 1.0) of successfully recovering the payment"""
        reason_code = self.failure_reason_map.get(failure_reason, 1)
        input_data = pd.DataFrame({
            'failure_reason_code': [reason_code],
            'amount': [amount],
            'retry_count': [retry_count]
        })
        # Probability of class 1 (successful recovery)
        prob = self.model.predict_proba(input_data)[0][1]
        return round(float(prob), 3)

# Global instance for quick reuse
risk_scorer = RecoveryRiskModel()