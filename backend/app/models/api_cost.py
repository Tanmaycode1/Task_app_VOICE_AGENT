"""API cost tracking model for monitoring LLM usage and expenses."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiCost(Base):
    """Track API costs for each LLM request."""

    __tablename__ = "api_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Request identification
    user_query: Mapped[str] = mapped_column(String(1000), nullable=False)  # First 1000 chars of query
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "claude-sonnet-4-20250514"
    
    # Token usage
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Cost breakdown (in USD)
    input_cost: Mapped[float] = mapped_column(Float, nullable=False)  # Cost for input tokens
    output_cost: Mapped[float] = mapped_column(Float, nullable=False)  # Cost for output tokens
    total_cost: Mapped[float] = mapped_column(Float, nullable=False)  # Total cost for this request
    
    # Request metadata
    iterations: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # Number of API calls (for multi-iteration requests)
    tool_calls_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Number of tools called
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<ApiCost(id={self.id}, model={self.model}, cost=${self.total_cost:.6f}, tokens={self.total_tokens})>"

