"""Pydantic schemas for Task CRUD operations."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.task import TaskPriority, TaskStatus


class TaskBase(BaseModel):
    """Shared task fields."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    notes: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    scheduled_date: datetime  # Required: when the task is planned to be done
    deadline: datetime | None = None  # Optional: when the task MUST be completed by


class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """Schema for updating an existing task (all fields optional)."""

    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    notes: str | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    scheduled_date: datetime | None = None
    deadline: datetime | None = None
    completed_at: datetime | None = None


class TaskResponse(TaskBase):
    """Schema for task responses."""

    id: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Schema for paginated task list responses."""

    tasks: list[TaskResponse]
    total: int
    skip: int
    limit: int

