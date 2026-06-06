import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


MAX_TEXT_LENGTH = 20000


def new_trace_id() -> str:
    return str(uuid4())


def write_runtime_trace(trace_dir: Path, record: dict[str, Any]) -> Path:
    now = datetime.now(UTC)
    payload = {
        "schema_version": "1.0",
        "created_at": now.isoformat(),
        **_trim_json(record),
    }
    path = trace_dir / f"trace_{now:%Y-%m-%d}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def _trim_json(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= MAX_TEXT_LENGTH:
            return value
        return f"{value[:MAX_TEXT_LENGTH]}...[truncated]"
    if isinstance(value, list):
        return [_trim_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _trim_json(item) for key, item in value.items()}
    return value
