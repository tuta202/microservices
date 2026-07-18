import json, os, uuid
from datetime import datetime, timezone

def envelope(event_type: str, aggregate_id: str, payload: dict, correlation_id: str | None = None) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": 1,
        "aggregate_id": aggregate_id,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": os.getenv("SERVICE_NAME", "unknown"),
        "payload": payload,
    }

def dumps(data: dict) -> bytes:
    return json.dumps(data, separators=(",", ":")).encode()
