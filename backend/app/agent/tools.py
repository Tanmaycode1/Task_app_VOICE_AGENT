"""Tool definitions for the task management agent."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.task import Task, TaskPriority, TaskStatus

# Tool schemas for Claude
TOOLS = [
    {
        "name": "list_tasks",
        "description": "List all tasks with optional filters. Use this to show the user their tasks or search for specific tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["todo", "in_progress", "completed", "cancelled"],
                    "description": "Filter by task status",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Filter by priority level",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tasks to return (default 10)",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task. Use this when the user wants to add a new task or todo item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Task title (required)",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the task",
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes about the task",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Priority level (default: medium)",
                    "default": "medium",
                },
                "deadline": {
                    "type": "string",
                    "description": "Deadline in ISO 8601 format (e.g., 2024-11-20T14:30:00)",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": "Update an existing task. Use this to change task details, status, priority, or deadline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID of the task to update (required)",
                },
                "title": {
                    "type": "string",
                    "description": "New title for the task",
                },
                "description": {
                    "type": "string",
                    "description": "New description",
                },
                "notes": {
                    "type": "string",
                    "description": "New notes",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "New priority level",
                },
                "status": {
                    "type": "string",
                    "enum": ["todo", "in_progress", "completed", "cancelled"],
                    "description": "New status",
                },
                "deadline": {
                    "type": "string",
                    "description": "New deadline in ISO 8601 format",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "delete_task",
        "description": "Delete a task permanently. Use this when the user wants to remove a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID of the task to delete (required)",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "get_task_stats",
        "description": "Get statistics about tasks (total, completed, in progress, etc.). Use this to give the user an overview.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "search_tasks",
        "description": "Search for tasks by keyword in title, description, or notes. Use this for queries like 'show me administrative tasks', 'find tasks about X', 'tasks related to Y'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to match against title, description, or notes (required)",
                },
                "priority": {
                    "type": "string",
                    "enum": ["urgent", "high", "medium", "low"],
                    "description": "Filter by priority",
                },
                "status": {
                    "type": "string",
                    "enum": ["todo", "in_progress", "completed", "cancelled"],
                    "description": "Filter by status",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "change_ui_view",
        "description": "Change the UI view and date selection to help the user visualize tasks. Use this when the user wants to see tasks in a specific time period, view mode, or with specific filters/sorting. Especially useful for list view with filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "view_mode": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly", "list"],
                    "description": "View mode to switch to (required)",
                },
                "target_date": {
                    "type": "string",
                    "description": "Target date in ISO 8601 format (YYYY-MM-DD). The view will center on this date. For example, use the first day of a month for monthly view, or any day in a week for weekly view.",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["deadline", "priority", "created"],
                    "description": "Sort tasks by this field (only applicable for list view)",
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort order: ascending or descending (only applicable for list view)",
                },
                "filter_status": {
                    "type": "string",
                    "enum": ["all", "todo", "in_progress", "completed", "cancelled"],
                    "description": "Filter tasks by status (only applicable for list view)",
                },
                "filter_priority": {
                    "type": "string",
                    "enum": ["all", "urgent", "high", "medium", "low"],
                    "description": "Filter tasks by priority (only applicable for list view)",
                },
            },
            "required": ["view_mode"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict[str, Any], db: Session) -> dict[str, Any]:
    """Execute a tool and return the result."""
    
    if tool_name == "list_tasks":
        return _list_tasks(db, **tool_input)
    elif tool_name == "create_task":
        return _create_task(db, **tool_input)
    elif tool_name == "update_task":
        return _update_task(db, **tool_input)
    elif tool_name == "delete_task":
        return _delete_task(db, **tool_input)
    elif tool_name == "get_task_stats":
        return _get_task_stats(db)
    elif tool_name == "search_tasks":
        return _search_tasks(db, **tool_input)
    elif tool_name == "change_ui_view":
        return _change_ui_view(**tool_input)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def _list_tasks(
    db: Session,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """List tasks with optional filters."""
    query = db.query(Task)
    
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    
    tasks = query.order_by(Task.created_at.desc()).limit(limit).all()
    
    return {
        "success": True,
        "count": len(tasks),
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "deadline": t.deadline.isoformat() if t.deadline else None,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ],
    }


def _create_task(
    db: Session,
    title: str,
    description: str | None = None,
    notes: str | None = None,
    priority: str = "medium",
    deadline: str | None = None,
) -> dict[str, Any]:
    """Create a new task."""
    task = Task(
        title=title,
        description=description,
        notes=notes,
        priority=priority,
        status=TaskStatus.TODO.value,
        deadline=datetime.fromisoformat(deadline) if deadline else None,
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    result = {
        "success": True,
        "message": f"Task '{title}' created successfully",
        "task": {
            "id": task.id,
            "title": task.title,
            "priority": task.priority,
            "status": task.status,
            "deadline": task.deadline.isoformat() if task.deadline else None,
        },
    }
    
    # Add UI command to navigate to the task's date
    if task.deadline:
        result["ui_command"] = {
            "type": "change_view",
            "view_mode": "daily",
            "target_date": task.deadline.date().isoformat(),
        }
    
    return result


def _update_task(
    db: Session,
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    deadline: str | None = None,
) -> dict[str, Any]:
    """Update an existing task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        return {"success": False, "error": f"Task with ID {task_id} not found"}
    
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if notes is not None:
        task.notes = notes
    if priority is not None:
        task.priority = priority
    if status is not None:
        task.status = status
        if status == TaskStatus.COMPLETED.value and not task.completed_at:
            task.completed_at = datetime.utcnow()
    if deadline is not None:
        task.deadline = datetime.fromisoformat(deadline)
    
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    
    result = {
        "success": True,
        "message": f"Task '{task.title}' updated successfully",
        "task": {
            "id": task.id,
            "title": task.title,
            "priority": task.priority,
            "status": task.status,
            "deadline": task.deadline.isoformat() if task.deadline else None,
        },
    }
    
    # If deadline was updated, add UI command to navigate to the new date
    if deadline is not None and task.deadline:
        result["ui_command"] = {
            "type": "change_view",
            "view_mode": "daily",
            "target_date": task.deadline.date().isoformat(),
        }
    
    return result


def _delete_task(db: Session, task_id: int) -> dict[str, Any]:
    """Delete a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        return {"success": False, "error": f"Task with ID {task_id} not found"}
    
    title = task.title
    db.delete(task)
    db.commit()
    
    return {
        "success": True,
        "message": f"Task '{title}' deleted successfully",
    }


def _get_task_stats(db: Session) -> dict[str, Any]:
    """Get task statistics."""
    total = db.query(Task).count()
    todo = db.query(Task).filter(Task.status == TaskStatus.TODO.value).count()
    in_progress = db.query(Task).filter(Task.status == TaskStatus.IN_PROGRESS.value).count()
    completed = db.query(Task).filter(Task.status == TaskStatus.COMPLETED.value).count()
    
    upcoming = (
        db.query(Task)
        .filter(Task.deadline.isnot(None))
        .filter(Task.deadline >= datetime.utcnow())
        .filter(Task.status != TaskStatus.COMPLETED.value)
        .count()
    )
    
    return {
        "success": True,
        "stats": {
            "total": total,
            "todo": todo,
            "in_progress": in_progress,
            "completed": completed,
            "upcoming_deadlines": upcoming,
        },
    }


def _search_tasks(
    db: Session,
    query: str,
    priority: str | None = None,
    status: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search for tasks by keyword with optional filters."""
    search_pattern = f"%{query}%"
    
    query_obj = db.query(Task).filter(
        (Task.title.ilike(search_pattern))
        | (Task.description.ilike(search_pattern))
        | (Task.notes.ilike(search_pattern))
    )
    
    # Apply filters if provided
    if priority:
        query_obj = query_obj.filter(Task.priority == priority)
    if status:
        query_obj = query_obj.filter(Task.status == status)
    
    tasks = query_obj.limit(limit).all()
    
    result = {
        "success": True,
        "count": len(tasks),
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "deadline": t.deadline.isoformat() if t.deadline else None,
            }
            for t in tasks
        ],
    }
    
    # Add UI command to switch to list view with ONLY these search results
    # The UI will display exactly these tasks, not all tasks with filters
    ui_command = {
        "type": "change_view",
        "view_mode": "list",
        "search_results": [t.id for t in tasks],  # Pass task IDs to display
        "search_query": query,  # Show what was searched
    }
    
    # Also include filters if they were applied
    if priority and priority != "all":
        ui_command["filter_priority"] = priority
    if status and status != "all":
        ui_command["filter_status"] = status
    
    result["ui_command"] = ui_command
    
    return result


def _change_ui_view(
    view_mode: str,
    target_date: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    filter_status: str | None = None,
    filter_priority: str | None = None,
) -> dict[str, Any]:
    """
    Change the UI view and date selection.
    This returns a special UI control command that will be handled by the frontend.
    """
    result = {
        "success": True,
        "ui_command": {
            "type": "change_view",
            "view_mode": view_mode,
        },
        "message": f"Switched to {view_mode} view",
    }
    
    if target_date:
        result["ui_command"]["target_date"] = target_date
        result["message"] += f" for {target_date}"
    
    # Add list view filters and sorting
    if view_mode == "list":
        if sort_by:
            result["ui_command"]["sort_by"] = sort_by
            result["message"] += f", sorted by {sort_by}"
        
        if sort_order:
            result["ui_command"]["sort_order"] = sort_order
            result["message"] += f" ({sort_order}ending)"
        
        if filter_status and filter_status != "all":
            result["ui_command"]["filter_status"] = filter_status
            result["message"] += f", filtered by status: {filter_status}"
        
        if filter_priority and filter_priority != "all":
            result["ui_command"]["filter_priority"] = filter_priority
            result["message"] += f", filtered by priority: {filter_priority}"
    
    return result

