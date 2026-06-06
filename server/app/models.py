from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str
    product_ids: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


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


class FeedbackRequest(BaseModel):
    feedback: Literal["helpful", "inaccurate"]
    message: str = Field(min_length=1)
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
