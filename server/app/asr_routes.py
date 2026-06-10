import base64
import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from openai import AsyncOpenAI

from app.config import get_settings
from app.models import AsrTranscribeResponse, UploadedImageResponse
from app.trace_logger import write_runtime_trace


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["asr", "multimodal"])

IMAGE_MIME_TO_SUFFIX = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
IMAGE_UNDERSTANDING_PROMPT = """你是电商导购 RAG 系统的图片理解模块。请只基于图片可见信息，把商品/包装/场景转成可检索文本线索。

只输出 JSON object，不要 Markdown，不要解释。字段如下：
{
  "detected_category": "可见品类或 null",
  "detected_brand": "可见品牌或 null",
  "visible_text": ["图片里可读文字，如 SPF50+、型号、容量"],
  "visual_attributes": ["颜色、包装形态、材质、场景等视觉属性"],
  "possible_use_cases": ["可能的使用场景"],
  "uncertain_fields": ["不确定或看不清的字段"],
  "retrieval_terms": ["适合直接检索的关键词"],
  "confidence": "low | medium | high",
  "needs_clarification": false,
  "clarification_question": null,
  "query_text": "图片识别线索：..."
}

要求：
- 不要臆造品牌、功效、价格、成分或库存。
- 如果看不清，confidence 用 low，并给出 clarification_question。
- query_text 要适合接到电商商品检索，优先包含品类、品牌、可见文字、颜色/包装、场景。
"""


@router.post("/asr/transcribe", response_model=AsrTranscribeResponse)
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
            text=result.text,
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
            text="",
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


@router.post("/multimodal/images", response_model=UploadedImageResponse)
async def upload_multimodal_image(
    file: UploadFile = File(...),
    user_id: str = Form(default="local-demo-user"),
    conversation_id: str | None = Form(default=None),
) -> UploadedImageResponse:
    settings = get_settings()
    started_at = time.perf_counter()
    image_id = f"img_{datetime.now(UTC):%Y%m%d}_{uuid4().hex[:8]}"
    safe_user_id = _safe_path_part(user_id or "local-demo-user")
    mime_type = _normalize_image_mime(file.content_type)
    if mime_type not in IMAGE_MIME_TO_SUFFIX:
        raise HTTPException(status_code=400, detail="P0 只支持 JPEG/PNG 图片")

    max_bytes = settings.multimodal_max_upload_mb * 1024 * 1024
    payload = await file.read(max_bytes + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="图片文件为空")
    if len(payload) > max_bytes:
        raise HTTPException(status_code=413, detail=f"图片文件过大，请控制在 {settings.multimodal_max_upload_mb}MB 以内")

    suffix = IMAGE_MIME_TO_SUFFIX[mime_type]
    upload_dir = settings.multimodal_upload_dir / safe_user_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    image_path = upload_dir / f"{image_id}{suffix}"
    image_path.write_bytes(payload)

    width, height = _read_image_size(payload, mime_type)
    image_plan = await _understand_image_payload(
        payload=payload,
        mime_type=mime_type,
        image_id=image_id,
        original_filename=file.filename,
    )
    query_text = str(image_plan.get("query_text") or "")
    summary = _image_plan_summary(image_plan)
    expires_at = datetime.now(UTC) + timedelta(hours=settings.multimodal_retention_hours)
    response = UploadedImageResponse(
        image_id=image_id,
        mime_type=mime_type,
        width=width,
        height=height,
        size_bytes=len(payload),
        preview_url=f"/api/multimodal/images/{image_id}/preview",
        expires_at=expires_at.replace(microsecond=0).isoformat(),
        summary=summary,
        query_text=query_text,
        image_plan=image_plan,
    )
    _write_multimodal_trace(
        trace_id=image_id,
        status="ok",
        started_at=started_at,
        user_id=safe_user_id,
        conversation_id=conversation_id,
        filename=file.filename,
        mime_type=mime_type,
        size_bytes=len(payload),
        width=width,
        height=height,
        image_plan=image_plan,
        error=None,
    )
    return response


@router.get("/multimodal/images/{image_id}/preview")
def preview_multimodal_image(image_id: str) -> FileResponse:
    settings = get_settings()
    if not _safe_image_id(image_id):
        raise HTTPException(status_code=404, detail="Image not found")
    image_path = _find_uploaded_image(settings.multimodal_upload_dir, image_id)
    if image_path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    suffix = image_path.suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    return FileResponse(image_path, media_type=mime_type)


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


async def _understand_image_payload(
    *,
    payload: bytes,
    mime_type: str,
    image_id: str,
    original_filename: str | None,
) -> dict[str, object]:
    settings = get_settings()
    if settings.mock_llm or not settings.multimodal_configured:
        return _fallback_image_plan(image_id=image_id, reason="multimodal_disabled_by_mock_or_missing_config")

    image_b64 = base64.b64encode(payload).decode("ascii")
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.multimodal_timeout_seconds,
    )
    try:
        response = await client.chat.completions.create(
            model=settings.active_multimodal_model,
            messages=[
                {"role": "system", "content": "你只做电商图片理解，输出严格 JSON。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": IMAGE_UNDERSTANDING_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                    ],
                },
            ],
            temperature=0.0,
            max_tokens=700,
        )
        content = response.choices[0].message.content or ""
        payload_json = _loads_json_object(content)
        return _normalize_image_plan(payload_json, image_id=image_id)
    except Exception as exc:
        logger.warning("Image understanding failed; using fallback plan for %s: %s", original_filename or image_id, exc)
        return _fallback_image_plan(image_id=image_id, reason=f"multimodal_api_error:{exc.__class__.__name__}")
    finally:
        await client.close()


def _normalize_image_plan(raw: dict, *, image_id: str) -> dict[str, object]:
    raw_plan = raw.get("image_plan") if isinstance(raw.get("image_plan"), dict) else raw
    image_item = {
        "image_id": image_id,
        "image_index": 0,
        "detected_category": _optional_text(raw_plan.get("detected_category")),
        "detected_brand": _optional_text(raw_plan.get("detected_brand")),
        "visible_text": _string_list(raw_plan.get("visible_text"), limit=12),
        "visual_attributes": _string_list(raw_plan.get("visual_attributes"), limit=12),
        "possible_use_cases": _string_list(raw_plan.get("possible_use_cases"), limit=8),
        "uncertain_fields": _string_list(raw_plan.get("uncertain_fields"), limit=8),
        "confidence": _confidence(raw_plan.get("confidence")),
        "needs_clarification": bool(raw_plan.get("needs_clarification", False)),
        "clarification_question": _optional_text(raw_plan.get("clarification_question")),
    }
    terms = _string_list(raw_plan.get("retrieval_terms"), limit=16)
    terms.extend(
        term
        for term in [image_item["detected_category"], image_item["detected_brand"]]
        if isinstance(term, str) and term
    )
    terms.extend(image_item["visible_text"])
    terms.extend(image_item["visual_attributes"][:4])
    terms = list(dict.fromkeys(str(term).strip() for term in terms if str(term).strip()))[:16]
    query_text = _optional_text(raw_plan.get("query_text"))
    if not query_text:
        query_text = "图片识别线索：" + ("，".join(terms) if terms else "用户上传了一张商品/包装图片，但可识别线索不足。")
    confidence = _confidence(raw_plan.get("confidence"))
    return {
        "enabled": True,
        "mode": "image_to_text_retrieval",
        "images": [image_item],
        "retrieval_terms": terms,
        "query_text": query_text,
        "confidence": confidence,
        "needs_clarification": bool(image_item["needs_clarification"] or confidence == "low"),
    }


def _fallback_image_plan(*, image_id: str, reason: str) -> dict[str, object]:
    question = "我已经收到图片，但暂时还不能稳定识别内容。你想找同款、相似款，还是按用途找替代品？"
    return {
        "enabled": True,
        "mode": "image_to_text_retrieval",
        "images": [
            {
                "image_id": image_id,
                "image_index": 0,
                "detected_category": None,
                "detected_brand": None,
                "visible_text": [],
                "visual_attributes": [],
                "possible_use_cases": [],
                "uncertain_fields": [reason],
                "confidence": "low",
                "needs_clarification": True,
                "clarification_question": question,
            }
        ],
        "retrieval_terms": [],
        "query_text": "用户上传了一张商品/包装图片，需要结合用户文字判断同款、相似款或替代品。",
        "confidence": "low",
        "needs_clarification": True,
    }


def _image_plan_summary(image_plan: dict[str, object]) -> str:
    images = image_plan.get("images")
    image = images[0] if isinstance(images, list) and images and isinstance(images[0], dict) else {}
    terms = _string_list(image_plan.get("retrieval_terms"), limit=6)
    if terms:
        return "我先看到了：" + "、".join(terms[:6])
    question = _optional_text(image.get("clarification_question"))
    if question:
        return question
    return "我已经收到图片，会先把图片线索转成文本再检索商品。"


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


def _loads_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if "{" not in text or "}" not in text:
        raise ValueError("image understanding response did not contain a JSON object")
    start = text.find("{")
    end = text.rfind("}") + 1
    payload = json.loads(text[start:end])
    if not isinstance(payload, dict):
        raise ValueError("image understanding response JSON is not an object")
    return payload


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _segments(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text[:120]


def _string_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value[:limit]:
        text = str(item).strip()
        if text and text.lower() != "null":
            values.append(text[:60])
    return list(dict.fromkeys(values))


def _confidence(value: object) -> str:
    text = str(value or "medium").strip().lower()
    if text in {"low", "medium", "high"}:
        return text
    return "medium"


def _normalize_image_mime(content_type: str | None) -> str:
    value = (content_type or "").split(";")[0].strip().lower()
    if value in {"image/jpg", "image/pjpeg"}:
        return "image/jpeg"
    return value


def _safe_path_part(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return safe.strip(".-") or "local-demo-user"


def _safe_image_id(value: str) -> bool:
    return bool(re.fullmatch(r"img_[A-Za-z0-9_-]+", value))


def _find_uploaded_image(upload_root: Path, image_id: str) -> Path | None:
    for suffix in IMAGE_MIME_TO_SUFFIX.values():
        matches = list(upload_root.glob(f"*/{image_id}{suffix}"))
        if matches:
            return matches[0]
    return None


def _read_image_size(payload: bytes, mime_type: str) -> tuple[int | None, int | None]:
    try:
        if mime_type == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n") and len(payload) >= 24:
            return int.from_bytes(payload[16:20], "big"), int.from_bytes(payload[20:24], "big")
        if mime_type == "image/jpeg":
            return _read_jpeg_size(payload)
    except Exception:
        logger.debug("Failed to parse image dimensions", exc_info=True)
    return None, None


def _read_jpeg_size(payload: bytes) -> tuple[int | None, int | None]:
    if not payload.startswith(b"\xff\xd8"):
        return None, None
    index = 2
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while index + 9 < len(payload):
        if payload[index] != 0xFF:
            index += 1
            continue
        marker = payload[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(payload):
            break
        segment_length = int.from_bytes(payload[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(payload):
            break
        if marker in sof_markers and segment_length >= 7:
            height = int.from_bytes(payload[index + 3:index + 5], "big")
            width = int.from_bytes(payload[index + 5:index + 7], "big")
            return width, height
        index += segment_length
    return None, None


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
    text: str,
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
            "text": text,
            "text_char_count": text_char_count,
            "error": error,
            "latency_ms": int((time.perf_counter() - started_at) * 1000),
        },
    )


def _write_multimodal_trace(
    *,
    trace_id: str,
    status: str,
    started_at: float,
    user_id: str,
    conversation_id: str | None,
    filename: str | None,
    mime_type: str,
    size_bytes: int,
    width: int | None,
    height: int | None,
    image_plan: dict[str, object],
    error: str | None,
) -> None:
    settings = get_settings()
    write_runtime_trace(
        settings.trace_dir,
        {
            "trace_id": trace_id,
            "endpoint": "multimodal_image_upload",
            "status": status,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "width": width,
            "height": height,
            "image_plan": image_plan,
            "error": error,
            "latency_ms": int((time.perf_counter() - started_at) * 1000),
        },
    )
