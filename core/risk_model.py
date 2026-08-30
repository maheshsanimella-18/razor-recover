"""
Recovery Risk Probability Model (Machine Learning).
Predicts probability of payment recovery based on failure type, amount, retry history,
customer tenure, historical success rate, and payment method dynamics.
Includes honest held-out train/test evaluation metrics.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
import pickle
import os
from typing import Dict, Any, Tuple

MODEL_PATH = "core/risk_model.pkl"

class RecoveryRiskModel:
    def __init__(self):
        self.model: RandomForestClassifier = None
        self.metrics: Dict[str, Any] = {}
        self.failure_reason_map = {
            'network_timeout': 0,
            'insufficient_balance': 1,
            'invalid_card': 2,
            'suspected_fraud': 3,
            'otp_abandoned': 4,
            'mandate_declined': 5
        }
        self.payment_method_map = {
            'upi': 0,
            'card': 1,
            'netbanking': 2,
            'mandate': 3
        }
        self.feature_names = [
            'failure_reason_code',
            'amount',
            'retry_count',
            'payment_method_code',
            'customer_tenure_months',
            'past_success_rate',
            'past_failed_attempts'
        ]
        self.load_or_train_model()

    def _generate_synthetic_training_dataset(self, n_samples: int = 3000) -> Tuple[pd.DataFrame, np.ndarray]:
        """Generates realistic payment recovery training data without leakage."""
        np.random.seed(42)

        reasons = np.random.choice(
            list(self.failure_reason_map.keys()),
            size=n_samples,
            p=[0.30, 0.35, 0.12, 0.08, 0.10, 0.05]
        )
        amounts = np.random.uniform(500.0, 20000.0, size=n_samples)
        retry_counts = np.random.choice([0, 1, 2, 3], size=n_samples, p=[0.55, 0.25, 0.15, 0.05])
        methods = np.random.choice(list(self.payment_method_map.keys()), size=n_samples, p=[0.45, 0.35, 0.15, 0.05])
        tenures = np.random.randint(1, 48, size=n_samples)
        past_success_rates = np.clip(np.random.normal(0.82, 0.15, size=n_samples), 0.1, 1.0)
        past_fails = np.random.poisson(lam=1.2, size=n_samples)

        labels = []
        for r, amt, retries, method, tenure, success_rate, fails in zip(
            reasons, amounts, retry_counts, methods, tenures, past_success_rates, past_fails
        ):
            # Ground Truth Dynamics:
            # 1. Fraud & invalid cards almost never recover autonomously (label 0)
            if r in ['suspected_fraud', 'invalid_card'] or retries >= 3:
                labels.append(0)
            # 2. Network timeouts have high recovery probability (>80%)
            elif r == 'network_timeout':
                p = 0.85 if retries == 0 else 0.65
                labels.append(1 if np.random.rand() < p else 0)
            # 3. Insufficient balance: Smaller amounts + high tenure recover better on delayed retry
            elif r == 'insufficient_balance':
                base_p = 0.70 if amt < 5000 else (0.45 if amt < 12000 else 0.25)
                if tenure > 12: base_p += 0.10
                if retries >= 2: base_p -= 0.20
                labels.append(1 if np.random.rand() < np.clip(base_p, 0.05, 0.90) else 0)
            # 4. OTP Abandonment: Payment links recover well (>50%)
            elif r == 'otp_abandoned':
                base_p = 0.55 if success_rate > 0.75 else 0.30
                labels.append(1 if np.random.rand() < base_p else 0)
            # 5. Mandates
            elif r == 'mandate_declined':
                labels.append(1 if np.random.rand() < 0.35 else 0)
            else:
                labels.append(0)

        df = pd.DataFrame({
            'failure_reason_code': [self.failure_reason_map[r] for r in reasons],
            'amount': amounts,
            'retry_count': retry_counts,
            'payment_method_code': [self.payment_method_map[m] for m in methods],
            'customer_tenure_months': tenures,
            'past_success_rate': past_success_rates,
            'past_failed_attempts': past_fails
        })
        return df, np.array(labels)

    def train_and_evaluate(self):
        """Trains model on 80% split and calculates held-out test metrics on 20% split."""
        X, y = self._generate_synthetic_training_dataset(3000)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)

        clf = RandomForestClassifier(n_estimators=80, max_depth=8, random_state=42)
        clf.fit(X_train, y_train)

        # Held-out evaluation
        y_pred = clf.predict(X_test)
        y_proba = clf.predict_proba(X_test)[:, 1]

        self.metrics = {
            "test_accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "test_precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "test_recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "test_f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            "test_roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "feature_importances": {
                name: round(float(imp), 4)
                for name, imp in zip(self.feature_names, clf.feature_importances_)
            },
            "test_set_size": len(y_test),
            "train_set_size": len(y_train)
        }

        self.model = clf
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"model": self.model, "metrics": self.metrics}, f)

    def load_or_train_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, "rb") as f:
                    data = pickle.load(f)
                    if isinstance(data, dict) and "model" in data:
                        self.model = data["model"]
                        self.metrics = data.get("metrics", {})
                    else:
                        self.model = data
                        self.metrics = {}
            except Exception:
                self.train_and_evaluate()
        else:
            self.train_and_evaluate()

    def predict_recovery_probability(
        self,
        failure_reason: str,
        amount: float,
        retry_count: int = 0,
        payment_method: str = "card",
        customer_tenure_months: int = 12,
        past_success_rate: float = 0.85,
        past_failed_attempts: int = 0
    ) -> float:
        """Returns the probability score (0.0 to 1.0) of recovering the failed payment."""
        reason_code = self.failure_reason_map.get(failure_reason, 1)
        method_code = self.payment_method_map.get(payment_method, 1)

        input_data = pd.DataFrame([{
            'failure_reason_code': reason_code,
            'amount': amount,
            'retry_count': retry_count,
            'payment_method_code': method_code,
            'customer_tenure_months': customer_tenure_months,
            'past_success_rate': past_success_rate,
            'past_failed_attempts': past_failed_attempts
        }])

        prob = self.model.predict_proba(input_data)[0][1]
        return round(float(prob), 3)

    def get_evaluation_metrics(self) -> Dict[str, Any]:
        if not self.metrics:
            self.train_and_evaluate()
        return self.metrics

# Global Risk Scorer Instance
risk_scorer = RecoveryRiskModel()