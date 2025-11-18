"""Task model for todo management."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskPriority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    """Task completion status."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(Base):
    """A single task/todo item."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    priority: Mapped[str] = mapped_column(
        String(20), default=TaskPriority.MEDIUM.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=TaskStatus.TODO.value, nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    scheduled_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )  # When the task is planned to be done (REQUIRED)
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # When the task MUST be completed by (OPTIONAL)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', priority={self.priority})>"

