"""
Structured JSON Logger & Observability Engine.
Outputs structured JSON logs tracking latencies, token consumption, 
policy guardrail evaluations, and gateway operations with secret sanitization.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Merge structured extra attributes if present
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            # Sanitize any sensitive tokens/keys
            sanitized = {}
            for k, v in record.extra_data.items():
                if any(secret in k.lower() for secret in ["key", "secret", "password", "token"]):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = v
            log_entry["data"] = sanitized

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)

def setup_logger(name: str = "RazorRecover") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger

app_logger = setup_logger()

def log_event(
    event_type: str,
    message: str,
    txn_id: Optional[str] = None,
    actor: str = "SYSTEM",
    latency_ms: Optional[int] = None,
    tokens: int = 0,
    cost_inr: float = 0.0,
    level: str = "INFO",
    **kwargs
):
    """Utility function to log structured observability events."""
    extra = {
        "event_type": event_type,
        "transaction_id": txn_id,
        "actor": actor,
        "latency_ms": latency_ms,
        "tokens_used": tokens,
        "cost_inr": cost_inr,
        **kwargs
    }
    log_func = getattr(app_logger, level.lower(), app_logger.info)
    record = app_logger.makeRecord(
        name=app_logger.name,
        level=getattr(logging, level.upper(), logging.INFO),
        fn="",
        lno=0,
        msg=message,
        args=(),
        exc_info=None
    )
    record.extra_data = extra
    app_logger.handle(record)
