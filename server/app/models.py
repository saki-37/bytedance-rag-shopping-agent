from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


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


class UniversalConstraints(BaseModel):
    budget_max: float | None = None
    brand_exclude: list[str] = Field(default_factory=list)


class QueryIntent(BaseModel):
    category_candidates: list[str] = Field(default_factory=list)
    universal_constraints: UniversalConstraints = Field(default_factory=UniversalConstraints)
    facets: dict[str, list[str]] = Field(default_factory=dict)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)
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


class RetrievalTrace(BaseModel):
    query: str
    parsed_intent: QueryIntent
    hard_filtered_out: list[FilteredProduct] = Field(default_factory=list)
    retrieval_channels: RetrievalChannels = Field(default_factory=RetrievalChannels)
    final_ranking: list[RetrievalHit] = Field(default_factory=list)
    guardrail_checks: GuardrailChecks = Field(default_factory=GuardrailChecks)


class HealthResponse(BaseModel):
    status: str
    catalog_size: int
    mock_llm: bool
