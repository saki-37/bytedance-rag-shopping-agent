import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.models import FeedbackRequest, FeedbackResponse


def save_feedback(settings: Settings, request: FeedbackRequest) -> FeedbackResponse:
    now = datetime.now(UTC)
    record_id = str(uuid4())
    record = {
        "schema_version": "1.0",
        "record_id": record_id,
        "created_at": now.isoformat(),
        "conversation_id": request.conversation_id,
        "turn_id": request.turn_id,
        "feedback": request.feedback,
        "note": request.note,
        "snapshot": {
            "message": request.message,
            "retrieval_message": request.retrieval_message,
            "answer": request.answer,
            "history": [item.model_dump(mode="json") for item in request.history[-8:]],
            "products": [item.model_dump(mode="json") for item in request.products],
            "clarification_question": request.clarification_question,
            "trace": request.trace.model_dump(mode="json") if request.trace else None,
        },
    }
    path = _feedback_path(settings.feedback_dir, now)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return FeedbackResponse(ok=True, record_id=record_id, feedback=request.feedback)


def _feedback_path(feedback_dir: Path, created_at: datetime) -> Path:
    return feedback_dir / f"feedback_{created_at:%Y-%m-%d}.jsonl"
