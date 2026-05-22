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


class HealthResponse(BaseModel):
    status: str
    catalog_size: int
    mock_llm: bool
