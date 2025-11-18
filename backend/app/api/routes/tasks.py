"""CRUD API endpoints for tasks."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate

router = APIRouter()


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)) -> Task:
    """Create a new task."""
    task = Task(
        title=task_in.title,
        description=task_in.description,
        notes=task_in.notes,
        priority=task_in.priority.value,
        status=task_in.status.value,
        scheduled_date=task_in.scheduled_date,
        deadline=task_in.deadline,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status_filter: str | None = Query(None, alias="status"),
    priority_filter: str | None = Query(None, alias="priority"),
    search: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
) -> TaskListResponse:
    """List tasks with optional filters."""
    query = db.query(Task)

    # Apply filters
    if status_filter:
        query = query.filter(Task.status == status_filter)

    if priority_filter:
        query = query.filter(Task.priority == priority_filter)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern),
                Task.notes.ilike(search_pattern),
            )
        )

    if start_date:
        query = query.filter(Task.scheduled_date >= start_date)

    if end_date:
        query = query.filter(Task.scheduled_date <= end_date)

    # Get total count before pagination
    total = query.count()

    # Apply pagination and ordering
    tasks = query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

    return TaskListResponse(tasks=tasks, total=total, skip=skip, limit=limit)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    """Get a specific task by ID."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )
    return task


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)
) -> Task:
    """Update a task (partial update)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )

    update_data = task_update.model_dump(exclude_unset=True)

    # Convert enums to values
    if "priority" in update_data and update_data["priority"]:
        update_data["priority"] = update_data["priority"].value
    if "status" in update_data and update_data["status"]:
        update_data["status"] = update_data["status"].value
        # Auto-set completed_at when marking as completed
        if update_data["status"] == TaskStatus.COMPLETED.value and not task.completed_at:
            update_data["completed_at"] = datetime.utcnow()

    for field, value in update_data.items():
        setattr(task, field, value)

    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )
    db.delete(task)
    db.commit()


@router.get("/tasks/stats/summary")
def get_task_stats(db: Session = Depends(get_db)) -> dict:
    """Get summary statistics for tasks."""
    total = db.query(func.count(Task.id)).scalar()
    completed = (
        db.query(func.count(Task.id))
        .filter(Task.status == TaskStatus.COMPLETED.value)
        .scalar()
    )
    in_progress = (
        db.query(func.count(Task.id))
        .filter(Task.status == TaskStatus.IN_PROGRESS.value)
        .scalar()
    )
    todo = (
        db.query(func.count(Task.id))
        .filter(Task.status == TaskStatus.TODO.value)
        .scalar()
    )

    # Tasks with upcoming deadlines (next 7 days)
    now = datetime.utcnow()
    upcoming = (
        db.query(func.count(Task.id))
        .filter(Task.deadline.isnot(None))
        .filter(Task.deadline >= now)
        .filter(Task.status != TaskStatus.COMPLETED.value)
        .scalar()
    )

    return {
        "total": total or 0,
        "completed": completed or 0,
        "in_progress": in_progress or 0,
        "todo": todo or 0,
        "upcoming_deadlines": upcoming or 0,
    }

