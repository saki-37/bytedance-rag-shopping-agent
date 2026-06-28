from typing import Literal, Any
from datetime import UTC, datetime

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: str
    content: str
    product_ids: list[str] = Field(default_factory=list)


class ChatImageRef(BaseModel):
    image_id: str
    mime_type: str | None = None
    source: Literal["camera", "gallery", "unknown"] = "unknown"
    preview_url: str | None = None
    summary: str | None = None
    query_text: str | None = None
    image_plan: dict[str, Any] = Field(default_factory=dict)


class ConstraintOverrideSnapshot(BaseModel):
    removed_constraint_ids: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = ""
    images: list[ChatImageRef] = Field(default_factory=list)
    user_id: str | None = None
    recipient_id: str | None = None
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    constraint_overrides: ConstraintOverrideSnapshot = Field(default_factory=ConstraintOverrideSnapshot)

    @model_validator(mode="after")
    def require_text_or_image(self) -> "ChatRequest":
        if not self.message.strip() and not self.images:
            raise ValueError("message or images is required")
        if self.images:
            self.message = _compose_image_augmented_message(self.message, self.images)
        return self


def _compose_image_augmented_message(message: str, images: list[ChatImageRef]) -> str:
    clean_message = message.strip()
    image_lines: list[str] = []
    for index, image in enumerate(images[:3], start=1):
        plan = image.image_plan or {}
        query_text = (image.query_text or "").strip()
        summary = (image.summary or "").strip()
        if not query_text:
            query_text = str(plan.get("query_text") or "").strip()
        if not summary:
            summary = str(plan.get("summary") or plan.get("text") or "").strip()
        if query_text:
            image_lines.append(f"图片{index}识别线索：{query_text}")
        elif summary:
            image_lines.append(f"图片{index}识别线索：{summary}")
        else:
            image_lines.append(f"图片{index}识别线索：用户上传了一张商品/需求相关图片，image_id={image.image_id}")
    image_context = "\n".join(image_lines)
    if clean_message:
        return f"{image_context}\n用户补充需求：{clean_message}"
    return image_context


class UploadedImageResponse(BaseModel):
    image_id: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    size_bytes: int
    preview_url: str
    expires_at: str
    summary: str = ""
    query_text: str = ""
    image_plan: dict[str, Any] = Field(default_factory=dict)


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class MemorySnapshot(BaseModel):
    key: str
    weight: float = 0.5
    source: str
    created_at: str = Field(default_factory=_utcnow_iso)
    ttl_days: int = 7


class UserMemoryConstraints(BaseModel):
    allergies: list[str] = Field(default_factory=list)
    avoid_terms: list[str] = Field(default_factory=list)
    brand_exclude: list[str] = Field(default_factory=list)
    budget_max: float | None = None
    accessibility_needs: list[str] = Field(default_factory=list)


class UserMemoryLongTermPreferences(BaseModel):
    preferred_categories: dict[str, float] = Field(default_factory=dict)
    preferred_tags: dict[str, float] = Field(default_factory=dict)
    price_sensitivity: float | None = None


class UserMemoryShortTermSnapshots(BaseModel):
    recent_interests: list[MemorySnapshot] = Field(default_factory=list)
    recent_avoidance: list[MemorySnapshot] = Field(default_factory=list)


class UserMemoryShipping(BaseModel):
    address_label: str | None = None
    recipient_name: str | None = None
    phone: str | None = None
    address: str | None = None


class RecipientBodyProfile(BaseModel):
    skin_type: str | None = None
    shoe_size: str | None = None
    clothing_size: str | None = None


class RecipientProfile(BaseModel):
    recipient_id: str
    display_name: str
    relationship: str | None = None
    constraints: UserMemoryConstraints = Field(default_factory=UserMemoryConstraints)
    long_term_preferences: UserMemoryLongTermPreferences = Field(default_factory=UserMemoryLongTermPreferences)
    shipping: UserMemoryShipping = Field(default_factory=UserMemoryShipping)
    body_profile: RecipientBodyProfile = Field(default_factory=RecipientBodyProfile)
    updated_at: str = Field(default_factory=_utcnow_iso)


class RecipientShippingSummary(BaseModel):
    phone: str | None = None
    address: str | None = None


class RecipientManagementProfile(BaseModel):
    display_name: str
    relationship: str | None = None
    shipping: RecipientShippingSummary = Field(default_factory=RecipientShippingSummary)


class UserMemoryInteractionPreferences(BaseModel):
    answer_length: Literal["brief", "normal", "detailed"] = "normal"
    explanation_depth: Literal["short", "medium", "full"] = "medium"
    tone: str = "natural"
    show_trace_reason: bool = True


class UserMemoryGovernance(BaseModel):
    auto_learn_enabled: bool = False
    user_editable: bool = True
    retention_days: int = 30


class MemorySourceEvent(BaseModel):
    event_type: str
    event_value: str
    created_at: str = Field(default_factory=_utcnow_iso)
    source: str | None = None


class UserMemoryProfile(BaseModel):
    schema_version: str = "0.1"
    user_id: str
    updated_at: str = Field(default_factory=_utcnow_iso)
    constraints: UserMemoryConstraints = Field(default_factory=UserMemoryConstraints)
    long_term_preferences: UserMemoryLongTermPreferences = Field(default_factory=UserMemoryLongTermPreferences)
    recipients: list[RecipientProfile] = Field(default_factory=list)
    selected_recipient_id: str = "self"
    short_term_snapshots: UserMemoryShortTermSnapshots = Field(default_factory=UserMemoryShortTermSnapshots)
    interaction_preferences: UserMemoryInteractionPreferences = Field(default_factory=UserMemoryInteractionPreferences)
    governance: UserMemoryGovernance = Field(default_factory=UserMemoryGovernance)
    source_events: list[MemorySourceEvent] = Field(default_factory=list)


class MemoryTrace(BaseModel):
    provider: str
    user_id: str
    enabled: bool = True
    selected_recipient_id: str | None = None
    recipient_memory_trace: dict[str, object] = Field(default_factory=dict)
    applied_constraints: dict[str, object] = Field(default_factory=dict)
    applied_short_term_signals: list[str] = Field(default_factory=list)
    applied_preferences: dict[str, object] = Field(default_factory=dict)
    skipped_items: list[str] = Field(default_factory=list)
    fallback: str | None = None
    updated_at: str = Field(default_factory=_utcnow_iso)


class MemorySearchHit(BaseModel):
    key: str
    score: float
    source: str


class ProductVariantCard(BaseModel):
    variant_id: str
    parent_product_id: str
    label: str
    properties: dict[str, str] = Field(default_factory=dict)
    price: float
    image_path: str
    reason: str


class ProductCard(BaseModel):
    product_id: str
    title: str
    brand: str
    category: str
    sub_category: str
    price: float
    image_path: str
    tags: list[str] = Field(default_factory=list)
    reason: str
    target_users: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    suitable_for: list[str] = Field(default_factory=list)
    avoid_for: list[str] = Field(default_factory=list)
    description: str = ""
    variants: list[ProductVariantCard] = Field(default_factory=list)


class AnswerDirective(BaseModel):
    mode: Literal["compare"] = "compare"
    output_format: Literal["markdown_table"] = "markdown_table"
    target_product_ids: list[str] = Field(default_factory=list)
    focus_dimensions: list[str] = Field(default_factory=list)


class UniversalConstraints(BaseModel):
    budget_max: float | None = None
    brand_exclude: list[str] = Field(default_factory=list)


class QueryIntent(BaseModel):
    category_candidates: list[str] = Field(default_factory=list)
    referenced_product_ids: list[str] = Field(default_factory=list)
    universal_constraints: UniversalConstraints = Field(default_factory=UniversalConstraints)
    facets: dict[str, list[str]] = Field(default_factory=dict)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)
    comparison_mode: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None
    confidence: float = 0.0


class FilteredProduct(BaseModel):
    product_id: str
    reason: str


class RetrievalHit(BaseModel):
    product_id: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class RetrievalChannels(BaseModel):
    keyword: list[RetrievalHit] = Field(default_factory=list)
    vector: list[RetrievalHit] = Field(default_factory=list)
    graph: list[RetrievalHit] = Field(default_factory=list)


class GuardrailChecks(BaseModel):
    over_budget_candidates: int = 0
    excluded_term_candidates: int = 0
    needs_clarification: bool = False


class ConstraintTrace(BaseModel):
    current_turn: dict[str, object] = Field(default_factory=dict)
    inherited: dict[str, object] = Field(default_factory=dict)
    relaxed: list[str] = Field(default_factory=list)
    effective: dict[str, object] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)


class ConstraintChip(BaseModel):
    id: str
    type: Literal["budget_max", "exclude_terms", "brand_exclude"]
    label: str
    value: Any
    source: Literal["current_turn", "inherited", "memory", "effective"] = "effective"
    scope: Literal["turn", "session", "profile"] = "session"
    removable: bool = True


class ConstraintActionRequest(BaseModel):
    user_id: str | None = None
    recipient_id: str | None = None
    action: Literal["remove"] = "remove"
    constraint_id: str


class ConstraintActionResponse(BaseModel):
    ok: bool = True
    conversation_id: str
    removed_constraint_ids: list[str] = Field(default_factory=list)


class SafetyTrace(BaseModel):
    triggered_risks: list[str] = Field(default_factory=list)
    required_boundaries: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"


class SourceClaim(BaseModel):
    claim: str
    source: str
    product_id: str | None = None


class SourceTrace(BaseModel):
    supported_claims: list[SourceClaim] = Field(default_factory=list)
    review_only_claims: list[SourceClaim] = Field(default_factory=list)
    unsupported_claims: list[SourceClaim] = Field(default_factory=list)


class PlannerTrace(BaseModel):
    enabled: bool = False
    called: bool = False
    applied: bool = False
    fallback_reason: str | None = None
    latency_ms: int | None = None
    raw_plan: dict[str, object] = Field(default_factory=dict)
    validated_plan: dict[str, object] = Field(default_factory=dict)
    validation_errors: list[str] = Field(default_factory=list)


class RetrievalTrace(BaseModel):
    query: str
    parsed_intent: QueryIntent
    metadata_filter: dict[str, object] = Field(default_factory=dict)
    hard_filtered_out: list[FilteredProduct] = Field(default_factory=list)
    filter_summary: dict[str, int] = Field(default_factory=dict)
    retrieval_channels: RetrievalChannels = Field(default_factory=RetrievalChannels)
    final_ranking: list[RetrievalHit] = Field(default_factory=list)
    ranking_signals: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    guardrail_checks: GuardrailChecks = Field(default_factory=GuardrailChecks)
    constraint_trace: ConstraintTrace = Field(default_factory=ConstraintTrace)
    safety_trace: SafetyTrace = Field(default_factory=SafetyTrace)
    source_trace: SourceTrace = Field(default_factory=SourceTrace)
    planner_trace: PlannerTrace = Field(default_factory=PlannerTrace)


class HealthResponse(BaseModel):
    status: str
    catalog_size: int
    mock_llm: bool
    llm_provider: str
    llm_model: str | None = None


class AsrTranscribeResponse(BaseModel):
    ok: bool
    text: str = ""
    raw_text: str | None = None
    profile: str = "bilingual"
    language: str = "unknown"
    duration_ms: int | None = None
    asr_trace_id: str
    segments: list[dict[str, object]] = Field(default_factory=list)
    punctuation_applied: bool = False
    punctuation_model: str | None = None
    error: str | None = None


class FeedbackRequest(BaseModel):
    feedback: Literal["helpful", "inaccurate"]
    message: str = Field(min_length=1)
    trace_id: str | None = None
    conversation_id: str | None = None
    turn_id: str | None = None
    note: str | None = None
    answer: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    products: list[ProductCard] = Field(default_factory=list)
    retrieval_message: str | None = None
    clarification_question: str | None = None
    trace: RetrievalTrace | None = None


class FeedbackResponse(BaseModel):
    ok: bool
    record_id: str
    feedback: Literal["helpful", "inaccurate"]


class RecipientsUpdateRequest(BaseModel):
    recipients: list[RecipientManagementProfile] = Field(default_factory=list)
    selected_recipient_id: str | None = None


class RecipientSelectionRequest(BaseModel):
    selected_recipient_id: str


class RecipientsResponse(BaseModel):
    user_id: str
    selected_recipient_id: str
    recipients: list[RecipientManagementProfile] = Field(default_factory=list)
    updated_at: str = Field(default_factory=_utcnow_iso)
