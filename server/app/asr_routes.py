import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, Form, UploadFile

from app.config import get_settings
from app.models import AsrTranscribeResponse
from app.trace_logger import write_runtime_trace


router = APIRouter(prefix="/api/asr", tags=["asr"])


@router.post("/transcribe", response_model=AsrTranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    profile: str = Form(default="bilingual"),
    hotword: str | None = Form(default=None),
    conversation_id: str | None = Form(default=None),
) -> AsrTranscribeResponse:
    settings = get_settings()
    trace_id = f"asr_proxy_{datetime.now(UTC):%Y%m%d_%H%M%S}_{uuid4().hex[:8]}"
    started_at = time.perf_counter()
    upload_path: Path | None = None
    file_size = 0

    try:
        upload_path, file_size = await _save_upload(
            file=file,
            upload_dir=settings.asr_upload_dir,
            trace_id=trace_id,
            max_upload_mb=settings.asr_max_upload_mb,
        )
        response = await _call_sidecar(
            sidecar_url=settings.asr_sidecar_url,
            timeout_seconds=settings.asr_timeout_seconds,
            upload_path=upload_path,
            original_filename=file.filename or upload_path.name,
            content_type=file.content_type or "application/octet-stream",
            profile=profile,
            hotword=hotword,
        )
        result = _normalize_sidecar_response(response, profile, trace_id)
        _write_asr_trace(
            trace_id=trace_id,
            status="ok" if result.ok else "error",
            started_at=started_at,
            filename=file.filename,
            file_size=file_size,
            profile=profile,
            conversation_id=conversation_id,
            sidecar_trace_id=result.asr_trace_id,
            text_char_count=len(result.text),
            error=result.error,
        )
        return result
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        _write_asr_trace(
            trace_id=trace_id,
            status="error",
            started_at=started_at,
            filename=file.filename,
            file_size=file_size,
            profile=profile,
            conversation_id=conversation_id,
            sidecar_trace_id=None,
            text_char_count=0,
            error=str(exc),
        )
        return AsrTranscribeResponse(
            ok=False,
            text="",
            raw_text=None,
            profile=profile,
            language="unknown",
            duration_ms=duration_ms,
            asr_trace_id=trace_id,
            segments=[],
            punctuation_applied=False,
            punctuation_model=None,
            error=str(exc),
        )
    finally:
        if upload_path and upload_path.exists():
            upload_path.unlink(missing_ok=True)


async def _save_upload(
    *,
    file: UploadFile,
    upload_dir: Path,
    trace_id: str,
    max_upload_mb: int,
) -> tuple[Path, int]:
    max_bytes = max_upload_mb * 1024 * 1024
    payload = await file.read(max_bytes + 1)
    if not payload:
        raise ValueError("录音文件为空")
    if len(payload) > max_bytes:
        raise ValueError(f"录音文件过大，请控制在 {max_upload_mb}MB 以内")

    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix or ".audio"
    upload_path = upload_dir / f"{trace_id}{suffix}"
    upload_path.write_bytes(payload)
    return upload_path, len(payload)


async def _call_sidecar(
    *,
    sidecar_url: str,
    timeout_seconds: float,
    upload_path: Path,
    original_filename: str,
    content_type: str,
    profile: str,
    hotword: str | None,
) -> dict:
    data = {"profile": profile}
    if hotword:
        data["hotword"] = hotword
    timeout = httpx.Timeout(timeout_seconds, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        with upload_path.open("rb") as audio_file:
            response = await client.post(
                sidecar_url,
                data=data,
                files={"file": (original_filename, audio_file, content_type)},
            )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError(f"ASR sidecar returned non-JSON response: HTTP {response.status_code}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"ASR sidecar returned invalid JSON response: HTTP {response.status_code}")
    return payload


def _normalize_sidecar_response(payload: dict, requested_profile: str, trace_id: str) -> AsrTranscribeResponse:
    return AsrTranscribeResponse(
        ok=bool(payload.get("ok")),
        text=str(payload.get("text") or ""),
        raw_text=str(payload.get("raw_text")) if payload.get("raw_text") is not None else None,
        profile=str(payload.get("profile") or requested_profile),
        language=str(payload.get("language") or "unknown"),
        duration_ms=_optional_int(payload.get("duration_ms")),
        asr_trace_id=str(payload.get("asr_trace_id") or trace_id),
        segments=_segments(payload.get("segments")),
        punctuation_applied=bool(payload.get("punctuation_applied")),
        punctuation_model=str(payload.get("punctuation_model")) if payload.get("punctuation_model") else None,
        error=str(payload.get("error")) if payload.get("error") else None,
    )


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _segments(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _write_asr_trace(
    *,
    trace_id: str,
    status: str,
    started_at: float,
    filename: str | None,
    file_size: int,
    profile: str,
    conversation_id: str | None,
    sidecar_trace_id: str | None,
    text_char_count: int,
    error: str | None,
) -> None:
    settings = get_settings()
    write_runtime_trace(
        settings.trace_dir,
        {
            "trace_id": trace_id,
            "endpoint": "asr_transcribe",
            "status": status,
            "filename": filename,
            "file_size": file_size,
            "profile": profile,
            "conversation_id": conversation_id,
            "sidecar_trace_id": sidecar_trace_id,
            "text_char_count": text_char_count,
            "error": error,
            "latency_ms": int((time.perf_counter() - started_at) * 1000),
        },
    )
