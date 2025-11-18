"""Tool definitions for the task management agent."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.task import Task, TaskPriority, TaskStatus

# Tool schemas for Claude
TOOLS = [
    {
        "name": "create_multiple_tasks",
        "description": "Create multiple tasks at once. Use this when user wants to add several tasks in one command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "description": "Array of tasks to create",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Task title (required)"},
                            "description": {"type": "string", "description": "Task description"},
                            "notes": {"type": "string", "description": "Additional notes"},
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "urgent"],
                                "description": "Priority level (default: medium)",
                            },
                            "deadline": {"type": "string", "description": "Deadline in ISO 8601 format"},
                        },
                        "required": ["title"],
                    },
                },
            },
            "required": ["tasks"],
        },
    },
    {
        "name": "update_multiple_tasks",
        "description": "Update multiple tasks at once. Use when user wants to bulk update (e.g., 'push all tasks to next week').",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "IDs of tasks to update (required)",
                },
                "updates": {
                    "type": "object",
                    "description": "Updates to apply to all specified tasks",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "notes": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "urgent"],
                        },
                        "status": {
                            "type": "string",
                            "enum": ["todo", "in_progress", "completed", "cancelled"],
                        },
                        "deadline": {"type": "string", "description": "New deadline in ISO 8601"},
                        "deadline_shift_days": {
                            "type": "integer",
                            "description": "Shift deadline by N days (e.g., 7 for next week, 30 for next month)",
                        },
                    },
                },
            },
            "required": ["task_ids", "updates"],
        },
    },
    {
        "name": "delete_multiple_tasks",
        "description": "Delete multiple tasks at once. Use when user wants to bulk delete tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "IDs of tasks to delete (required)",
                },
            },
            "required": ["task_ids"],
        },
    },
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
    elif tool_name == "create_multiple_tasks":
        return _create_multiple_tasks(db, **tool_input)
    elif tool_name == "update_task":
        return _update_task(db, **tool_input)
    elif tool_name == "update_multiple_tasks":
        return _update_multiple_tasks(db, **tool_input)
    elif tool_name == "delete_task":
        return _delete_task(db, **tool_input)
    elif tool_name == "delete_multiple_tasks":
        return _delete_multiple_tasks(db, **tool_input)
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
    
    # Parse deadline and set default time to 12:00 PM if only date is provided
    # EXCEPTION: If deadline is "tomorrow" (1 day from now) and time is midnight, use today's current time
    parsed_deadline = None
    if deadline:
        try:
            parsed_deadline = datetime.fromisoformat(deadline)
            now = datetime.utcnow()
            
            # Check if this is "tomorrow" (approximately 1 day from now, within 24-48 hours)
            days_diff = (parsed_deadline.date() - now.date()).days
            
            # If time is exactly midnight (00:00:00), it means only date was provided
            if parsed_deadline.hour == 0 and parsed_deadline.minute == 0 and parsed_deadline.second == 0:
                # Special case: if it's tomorrow, use today's current time
                if days_diff == 1:
                    parsed_deadline = parsed_deadline.replace(hour=now.hour, minute=now.minute, second=now.second)
                else:
                    # For other dates, default to 12:00 PM (noon)
                    parsed_deadline = parsed_deadline.replace(hour=12, minute=0, second=0)
        except ValueError:
            # If ISO format fails, try to parse date only
            try:
                from datetime import date
                date_only = date.fromisoformat(deadline)
                now = datetime.utcnow()
                days_diff = (date_only - now.date()).days
                
                # If it's tomorrow, use today's current time
                if days_diff == 1:
                    parsed_deadline = datetime.combine(date_only, datetime.min.time()).replace(
                        hour=now.hour, minute=now.minute, second=now.second
                    )
                else:
                    # For other dates, default to 12:00 PM
                    parsed_deadline = datetime.combine(date_only, datetime.min.time()).replace(hour=12)
            except ValueError:
                parsed_deadline = None
    
    task = Task(
        title=title,
        description=description,
        notes=notes,
        priority=priority,
        status=TaskStatus.TODO.value,
        deadline=parsed_deadline,
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
    
    # DO NOT automatically navigate to the task's date
    # User must explicitly ask to see that date
    
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
    
    # Track if deadline changed and by how much
    original_deadline = task.deadline
    deadline_changed = False
    
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
        # Parse deadline and set default time to 12:00 PM if only date is provided
        try:
            parsed_deadline = datetime.fromisoformat(deadline)
            # If time is exactly midnight (00:00:00), it means only date was provided
            # Set default time to 12:00 PM (noon)
            if parsed_deadline.hour == 0 and parsed_deadline.minute == 0 and parsed_deadline.second == 0:
                parsed_deadline = parsed_deadline.replace(hour=12, minute=0, second=0)
            task.deadline = parsed_deadline
            deadline_changed = True
        except ValueError:
            # If ISO format fails, try to parse date only and add 12:00 PM
            try:
                from datetime import date
                date_only = date.fromisoformat(deadline)
                task.deadline = datetime.combine(date_only, datetime.min.time()).replace(hour=12)
                deadline_changed = True
            except ValueError:
                pass
    
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
    
    # If deadline changed significantly (moved to different week/month), navigate to new date
    if deadline_changed and original_deadline and task.deadline:
        days_diff = abs((task.deadline - original_deadline).days)
        
        # Only navigate if moved by at least 3 days (significant change)
        if days_diff >= 3:
            target_date = task.deadline.date().isoformat()
            
            # Determine view mode based on how much it shifted
            if days_diff >= 25:  # ~1 month
                view_mode = "monthly"
            elif days_diff >= 6:  # ~1 week
                view_mode = "weekly"
            else:
                view_mode = "daily"
            
            result["ui_command"] = {
                "type": "change_view",
                "view_mode": view_mode,
                "target_date": target_date,
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


def _create_multiple_tasks(db: Session, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Create multiple tasks at once."""
    created_tasks = []
    errors = []
    
    for i, task_data in enumerate(tasks):
        try:
            # Parse deadline and set default time to 12:00 PM if only date is provided
            # EXCEPTION: If deadline is "tomorrow" (1 day from now) and time is midnight, use today's current time
            parsed_deadline = None
            deadline = task_data.get("deadline")
            if deadline:
                try:
                    parsed_deadline = datetime.fromisoformat(deadline)
                    now = datetime.utcnow()
                    
                    # Check if this is "tomorrow" (1 day from now)
                    days_diff = (parsed_deadline.date() - now.date()).days
                    
                    # If time is exactly midnight (00:00:00), it means only date was provided
                    if parsed_deadline.hour == 0 and parsed_deadline.minute == 0 and parsed_deadline.second == 0:
                        # Special case: if it's tomorrow, use today's current time
                        if days_diff == 1:
                            parsed_deadline = parsed_deadline.replace(hour=now.hour, minute=now.minute, second=now.second)
                        else:
                            # For other dates, default to 12:00 PM (noon)
                            parsed_deadline = parsed_deadline.replace(hour=12, minute=0, second=0)
                except ValueError:
                    # If ISO format fails, try to parse date only
                    try:
                        from datetime import date
                        date_only = date.fromisoformat(deadline)
                        now = datetime.utcnow()
                        days_diff = (date_only - now.date()).days
                        
                        # If it's tomorrow, use today's current time
                        if days_diff == 1:
                            parsed_deadline = datetime.combine(date_only, datetime.min.time()).replace(
                                hour=now.hour, minute=now.minute, second=now.second
                            )
                        else:
                            # For other dates, default to 12:00 PM
                            parsed_deadline = datetime.combine(date_only, datetime.min.time()).replace(hour=12)
                    except ValueError:
                        parsed_deadline = None
            
            task = Task(
                title=task_data["title"],
                description=task_data.get("description"),
                notes=task_data.get("notes"),
                priority=task_data.get("priority", "medium"),
                status=TaskStatus.TODO.value,
                deadline=parsed_deadline,
            )
            
            db.add(task)
            db.flush()  # Get task ID without committing
            
            created_tasks.append({
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "deadline": task.deadline.isoformat() if task.deadline else None,
            })
        except Exception as e:
            errors.append(f"Task {i+1} ('{task_data.get('title', 'Unknown')}'): {str(e)}")
    
    if errors:
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to create tasks. Errors: {'; '.join(errors)}",
        }
    
    db.commit()
    
    return {
        "success": True,
        "message": f"{len(created_tasks)} tasks created successfully",
        "tasks": created_tasks,
    }


def _update_multiple_tasks(
    db: Session,
    task_ids: list[int],
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update multiple tasks at once."""
    updated_tasks = []
    errors = []
    
    # Handle deadline_shift_days for bulk date shifting
    deadline_shift_days = updates.pop("deadline_shift_days", None)
    
    for task_id in task_ids:
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            
            if not task:
                errors.append(f"Task ID {task_id} not found")
                continue
            
            # Apply updates
            if "title" in updates:
                task.title = updates["title"]
            if "description" in updates:
                task.description = updates["description"]
            if "notes" in updates:
                task.notes = updates["notes"]
            if "priority" in updates:
                task.priority = updates["priority"]
            if "status" in updates:
                task.status = updates["status"]
                if updates["status"] == TaskStatus.COMPLETED.value and not task.completed_at:
                    task.completed_at = datetime.utcnow()
            
            # Handle deadline update or shift
            if deadline_shift_days is not None and task.deadline:
                # Shift existing deadline by N days
                task.deadline = task.deadline + timedelta(days=deadline_shift_days)
            elif "deadline" in updates:
                # Set new absolute deadline
                deadline_str = updates["deadline"]
                try:
                    parsed_deadline = datetime.fromisoformat(deadline_str)
                    # If time is exactly midnight (00:00:00), it means only date was provided
                    if parsed_deadline.hour == 0 and parsed_deadline.minute == 0 and parsed_deadline.second == 0:
                        parsed_deadline = parsed_deadline.replace(hour=12, minute=0, second=0)
                    task.deadline = parsed_deadline
                except ValueError:
                    try:
                        from datetime import date
                        date_only = date.fromisoformat(deadline_str)
                        task.deadline = datetime.combine(date_only, datetime.min.time()).replace(hour=12)
                    except ValueError:
                        pass
            
            task.updated_at = datetime.utcnow()
            
            updated_tasks.append({
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "status": task.status,
                "deadline": task.deadline.isoformat() if task.deadline else None,
            })
        except Exception as e:
            errors.append(f"Task ID {task_id}: {str(e)}")
    
    if errors:
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to update some tasks. Errors: {'; '.join(errors)}",
            "updated": updated_tasks,
        }
    
    db.commit()
    
    result = {
        "success": True,
        "message": f"{len(updated_tasks)} tasks updated successfully",
        "tasks": updated_tasks,
    }
    
    # If we shifted deadlines, navigate to the new date/week/month
    if deadline_shift_days is not None and updated_tasks:
        # Get the first updated task's new deadline to determine where to navigate
        first_updated = db.query(Task).filter(Task.id == updated_tasks[0]["id"]).first()
        if first_updated and first_updated.deadline:
            target_date = first_updated.deadline.date().isoformat()
            
            # Determine view mode based on shift amount
            if abs(deadline_shift_days) >= 25:  # ~1 month
                view_mode = "monthly"
            elif abs(deadline_shift_days) >= 6:  # ~1 week
                view_mode = "weekly"
            else:
                view_mode = "daily"
            
            result["ui_command"] = {
                "type": "change_view",
                "view_mode": view_mode,
                "target_date": target_date,
            }
    
    return result


def _delete_multiple_tasks(db: Session, task_ids: list[int]) -> dict[str, Any]:
    """Delete multiple tasks at once."""
    deleted_tasks = []
    errors = []
    
    for task_id in task_ids:
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            
            if not task:
                errors.append(f"Task ID {task_id} not found")
                continue
            
            deleted_tasks.append({"id": task.id, "title": task.title})
            db.delete(task)
        except Exception as e:
            errors.append(f"Task ID {task_id}: {str(e)}")
    
    if errors:
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to delete some tasks. Errors: {'; '.join(errors)}",
            "deleted": deleted_tasks,
        }
    
    db.commit()
    
    return {
        "success": True,
        "message": f"{len(deleted_tasks)} tasks deleted successfully",
        "tasks": deleted_tasks,
    }

