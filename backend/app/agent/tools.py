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
                            "scheduled_date": {"type": "string", "description": "When task is planned to be done (ISO 8601, REQUIRED)"},
                            "deadline": {"type": "string", "description": "Hard deadline - when task MUST be done by (ISO 8601, OPTIONAL)"},
                        },
                        "required": ["title", "scheduled_date"],
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
                        "scheduled_date": {"type": "string", "description": "New scheduled date in ISO 8601"},
                        "scheduled_date_shift_days": {
                            "type": "integer",
                            "description": "Shift scheduled_date by N days (e.g., 7 for next week, 30 for next month)",
                        },
                        "deadline": {"type": "string", "description": "New deadline in ISO 8601"},
                        "shift_deadline_too": {
                            "type": "boolean",
                            "description": "If shifting scheduled_date, also shift deadline by same amount (default: false)",
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
                "has_deadline": {
                    "type": "boolean",
                    "description": "Filter tasks: true = only tasks WITH deadline, false = only tasks WITHOUT deadline",
                },
                "deadline_before": {
                    "type": "string",
                    "description": "Show tasks with deadline before this date (ISO 8601 format)",
                },
                "deadline_after": {
                    "type": "string",
                    "description": "Show tasks with deadline after this date (ISO 8601 format)",
                },
                "scheduled_before": {
                    "type": "string",
                    "description": "Show tasks scheduled before this date (ISO 8601 format)",
                },
                "scheduled_after": {
                    "type": "string",
                    "description": "Show tasks scheduled after this date (ISO 8601 format)",
                },
                "is_missed": {
                    "type": "boolean",
                    "description": "Filter missed tasks: true = only missed tasks (deadline passed, not completed)",
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
                "scheduled_date": {
                    "type": "string",
                    "description": "When task is planned to be done - REQUIRED (ISO 8601 format)",
                },
                "deadline": {
                    "type": "string",
                    "description": "Hard deadline when task MUST be done by - OPTIONAL (ISO 8601 format)",
                },
                "status": {
                    "type": "string",
                    "enum": ["todo", "in_progress", "completed", "cancelled"],
                    "description": "Task status (default: todo). If 'completed', completed_at will be set to current time.",
                    "default": "todo",
                },
            },
            "required": ["title", "scheduled_date"],
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
                "scheduled_date": {
                    "type": "string",
                    "description": "New scheduled date in ISO 8601 format",
                },
                "scheduled_date_shift_days": {
                    "type": "integer",
                    "description": "Shift scheduled_date by N days (e.g., 7 for next week)",
                },
                "deadline": {
                    "type": "string",
                    "description": "New deadline in ISO 8601 format",
                },
                "shift_deadline_too": {
                    "type": "boolean",
                    "description": "If shifting scheduled_date, also shift deadline by same amount",
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
        "name": "show_choices",
        "description": "Display a persistent choice modal to the user when there are multiple options. Use this when user needs to pick between options (delete/update ambiguity, split tasks, etc). The modal will stay visible until user selects an option.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the choice modal (e.g., 'Which task?', 'What would you like to do?')",
                },
                "choices": {
                    "type": "array",
                    "description": "Array of choices to display",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique identifier for this choice",
                            },
                            "label": {
                                "type": "string",
                                "description": "Short label (e.g., 'A', 'B', '1', '2')",
                            },
                            "description": {
                                "type": "string",
                                "description": "Full description of the choice (e.g., task title, action description)",
                            },
                            "value": {
                                "type": "string",
                                "description": "Value to return when selected (e.g., task_id, 'split', 'mark_complete', 'delete_all')",
                            },
                        },
                        "required": ["id", "label", "description", "value"],
                    },
                },
            },
            "required": ["title", "choices"],
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
    elif tool_name == "show_choices":
        return _show_choices(**tool_input)
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


def _show_choices(
    title: str,
    choices: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Display a choice modal to the user.
    This returns a special UI command that will be handled by the frontend.
    """
    return {
        "success": True,
        "ui_command": {
            "type": "show_choices",
            "title": title,
            "choices": choices,
        },
        "message": "Please select an option",
    }


def _list_tasks(
    db: Session,
    status: str | None = None,
    priority: str | None = None,
    has_deadline: bool | None = None,
    deadline_before: str | None = None,
    deadline_after: str | None = None,
    scheduled_before: str | None = None,
    scheduled_after: str | None = None,
    is_missed: bool | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """List tasks with optional filters."""
    query = db.query(Task)
    
    # Status and priority filters
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    
    # Deadline existence filter
    if has_deadline is not None:
        if has_deadline:
            query = query.filter(Task.deadline.isnot(None))
        else:
            query = query.filter(Task.deadline.is_(None))
    
    # Deadline range filters
    if deadline_before:
        try:
            before_date = datetime.fromisoformat(deadline_before)
            query = query.filter(Task.deadline < before_date)
        except ValueError:
            pass  # Ignore invalid dates
    
    if deadline_after:
        try:
            after_date = datetime.fromisoformat(deadline_after)
            query = query.filter(Task.deadline > after_date)
        except ValueError:
            pass
    
    # Scheduled date range filters
    if scheduled_before:
        try:
            before_date = datetime.fromisoformat(scheduled_before)
            query = query.filter(Task.scheduled_date < before_date)
        except ValueError:
            pass
    
    if scheduled_after:
        try:
            after_date = datetime.fromisoformat(scheduled_after)
            query = query.filter(Task.scheduled_date > after_date)
        except ValueError:
            pass
    
    # Missed tasks filter (deadline passed and not completed)
    if is_missed is True:
        now = datetime.utcnow()
        query = query.filter(
            Task.deadline.isnot(None),
            Task.deadline < now,
            Task.status != TaskStatus.COMPLETED.value
        )
    
    # Order by scheduled_date (nearest first) and limit results
    tasks = query.order_by(Task.scheduled_date.asc()).limit(limit).all()
    
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
                "scheduled_date": t.scheduled_date.isoformat() if t.scheduled_date else None,
                "deadline": t.deadline.isoformat() if t.deadline else None,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ],
    }


def _create_task(
    db: Session,
    title: str,
    scheduled_date: str,
    description: str | None = None,
    notes: str | None = None,
    priority: str = "medium",
    deadline: str | None = None,
    status: str = "todo",
) -> dict[str, Any]:
    """Create a new task."""
    
    def parse_date_with_defaults(date_str: str) -> datetime:
        """Parse date string and apply default time rules."""
        try:
            parsed = datetime.fromisoformat(date_str)
            now = datetime.utcnow()
            days_diff = (parsed.date() - now.date()).days
            
            # If time is midnight, apply default time rules
            if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
                # Special case: tomorrow uses current time
                if days_diff == 1:
                    parsed = parsed.replace(hour=now.hour, minute=now.minute, second=now.second)
                else:
                    # Other dates default to 12:00 PM
                    parsed = parsed.replace(hour=12, minute=0, second=0)
            return parsed
        except ValueError:
            # Try parsing date only
            try:
                from datetime import date
                date_only = date.fromisoformat(date_str)
                now = datetime.utcnow()
                days_diff = (date_only - now.date()).days
                
                if days_diff == 1:
                    # Tomorrow: use current time
                    return datetime.combine(date_only, datetime.min.time()).replace(
                        hour=now.hour, minute=now.minute, second=now.second
                    )
                else:
                    # Other dates: 12:00 PM
                    return datetime.combine(date_only, datetime.min.time()).replace(hour=12)
            except ValueError:
                raise ValueError(f"Invalid date format: {date_str}")
    
    # Parse scheduled_date (REQUIRED)
    parsed_scheduled = parse_date_with_defaults(scheduled_date)
    
    # Parse deadline (OPTIONAL)
    parsed_deadline = None
    if deadline:
        parsed_deadline = parse_date_with_defaults(deadline)
        
        # Validate: deadline should be >= scheduled_date
        if parsed_deadline < parsed_scheduled:
            return {
                "success": False,
                "error": f"Deadline ({parsed_deadline.date()}) cannot be before scheduled date ({parsed_scheduled.date()})"
            }
    
    # Set completed_at if status is "completed"
    completed_at = None
    if status == TaskStatus.COMPLETED.value:
        completed_at = datetime.utcnow()
    
    task = Task(
        title=title,
        description=description,
        notes=notes,
        priority=priority,
        status=status,
        scheduled_date=parsed_scheduled,
        deadline=parsed_deadline,
        completed_at=completed_at,
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
            "scheduled_date": task.scheduled_date.isoformat(),
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
    scheduled_date: str | None = None,
    scheduled_date_shift_days: int | None = None,
    deadline: str | None = None,
    shift_deadline_too: bool = False,
) -> dict[str, Any]:
    """Update an existing task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        return {"success": False, "error": f"Task with ID {task_id} not found"}
    
    def parse_date(date_str: str) -> datetime:
        """Parse date with 12 PM default for midnight times."""
        try:
            parsed = datetime.fromisoformat(date_str)
            if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
                parsed = parsed.replace(hour=12, minute=0, second=0)
            return parsed
        except ValueError:
            from datetime import date
            date_only = date.fromisoformat(date_str)
            return datetime.combine(date_only, datetime.min.time()).replace(hour=12)
    
    # Track changes
    original_scheduled = task.scheduled_date
    scheduled_changed = False
    
    # Update simple fields
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
    
    # Handle scheduled_date updates
    if scheduled_date_shift_days is not None:
        # Shift scheduled_date by N days
        task.scheduled_date = task.scheduled_date + timedelta(days=scheduled_date_shift_days)
        scheduled_changed = True
        
        # If shift_deadline_too, shift deadline by same amount
        if shift_deadline_too and task.deadline:
            task.deadline = task.deadline + timedelta(days=scheduled_date_shift_days)
        # Otherwise, check if new scheduled_date is after deadline
        elif task.deadline and task.scheduled_date > task.deadline:
            return {
                "success": False,
                "error": f"New scheduled date ({task.scheduled_date.date()}) would be after deadline ({task.deadline.date()}). Use shift_deadline_too=true to move both.",
                "needs_confirmation": True
            }
    elif scheduled_date is not None:
        # Set absolute scheduled_date
        task.scheduled_date = parse_date(scheduled_date)
        scheduled_changed = True
        
        # Validate against deadline
        if task.deadline and task.scheduled_date > task.deadline:
            return {
                "success": False,
                "error": f"Scheduled date ({task.scheduled_date.date()}) cannot be after deadline ({task.deadline.date()})"
            }
    
    # Handle deadline updates
    if deadline is not None:
        task.deadline = parse_date(deadline)
        
        # Validate: deadline should be >= scheduled_date
        if task.deadline < task.scheduled_date:
            return {
                "success": False,
                "error": f"Deadline ({task.deadline.date()}) cannot be before scheduled date ({task.scheduled_date.date()})"
            }
    
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
            "scheduled_date": task.scheduled_date.isoformat(),
            "deadline": task.deadline.isoformat() if task.deadline else None,
        },
    }
    
    # If scheduled_date changed significantly, navigate to new date
    if scheduled_changed and original_scheduled:
        days_diff = abs((task.scheduled_date - original_scheduled).days)
        
        if days_diff >= 3:
            target_date = task.scheduled_date.date().isoformat()
            
            if days_diff >= 25:
                view_mode = "monthly"
            elif days_diff >= 6:
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
    """
    Search for tasks using hybrid approach:
    1. Exact keyword matching (ILIKE)
    2. Fuzzy matching for typos and variations
    """
    from difflib import SequenceMatcher
    
    # Step 1: Keyword search (fast, catches exact and partial matches)
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
    
    keyword_tasks = query_obj.all()
    
    # Step 2: Fuzzy matching on all tasks (catches typos, variations)
    # Only run if keyword search returns fewer than limit results
    fuzzy_tasks = []
    if len(keyword_tasks) < limit:
        all_tasks_query = db.query(Task)
        if priority:
            all_tasks_query = all_tasks_query.filter(Task.priority == priority)
        if status:
            all_tasks_query = all_tasks_query.filter(Task.status == status)
        
        all_tasks = all_tasks_query.all()
        query_lower = query.lower()
        
        for task in all_tasks:
            if task in keyword_tasks:
                continue  # Skip already found tasks
            
            # Calculate similarity scores
            title_similarity = SequenceMatcher(None, query_lower, (task.title or "").lower()).ratio()
            desc_similarity = SequenceMatcher(None, query_lower, (task.description or "").lower()).ratio() if task.description else 0
            notes_similarity = SequenceMatcher(None, query_lower, (task.notes or "").lower()).ratio() if task.notes else 0
            
            max_similarity = max(title_similarity, desc_similarity, notes_similarity)
            
            # Include if similarity is above threshold (0.5 = 50% match)
            if max_similarity >= 0.5:
                fuzzy_tasks.append((task, max_similarity))
        
        # Sort by similarity score (highest first)
        fuzzy_tasks.sort(key=lambda x: x[1], reverse=True)
        fuzzy_tasks = [task for task, _ in fuzzy_tasks]
    
    # Combine results: keyword matches first, then fuzzy matches
    tasks = keyword_tasks + fuzzy_tasks
    tasks = tasks[:limit]  # Limit total results
    
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
                "scheduled_date": t.scheduled_date.isoformat() if t.scheduled_date else None,
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
    
    def parse_date_with_defaults(date_str: str) -> datetime:
        """Parse date string and apply default time rules."""
        try:
            parsed = datetime.fromisoformat(date_str)
            now = datetime.utcnow()
            days_diff = (parsed.date() - now.date()).days
            
            if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
                if days_diff == 1:
                    parsed = parsed.replace(hour=now.hour, minute=now.minute, second=now.second)
                else:
                    parsed = parsed.replace(hour=12, minute=0, second=0)
            return parsed
        except ValueError:
            from datetime import date
            date_only = date.fromisoformat(date_str)
            now = datetime.utcnow()
            days_diff = (date_only - now.date()).days
            
            if days_diff == 1:
                return datetime.combine(date_only, datetime.min.time()).replace(
                    hour=now.hour, minute=now.minute, second=now.second
                )
            else:
                return datetime.combine(date_only, datetime.min.time()).replace(hour=12)
    
    for i, task_data in enumerate(tasks):
        try:
            # Parse scheduled_date (REQUIRED)
            scheduled_date = task_data.get("scheduled_date")
            if not scheduled_date:
                errors.append(f"Task {i+1} ('{task_data.get('title', 'Unknown')}'): scheduled_date is required")
                continue
            
            parsed_scheduled = parse_date_with_defaults(scheduled_date)
            
            # Parse deadline (OPTIONAL)
            parsed_deadline = None
            deadline = task_data.get("deadline")
            if deadline:
                parsed_deadline = parse_date_with_defaults(deadline)
                
                # Validate deadline >= scheduled_date
                if parsed_deadline < parsed_scheduled:
                    errors.append(f"Task {i+1} ('{task_data.get('title', 'Unknown')}'): deadline before scheduled_date")
                    continue
            
            # Set completed_at if status is "completed"
            status = task_data.get("status", TaskStatus.TODO.value)
            completed_at = None
            if status == TaskStatus.COMPLETED.value:
                completed_at = datetime.utcnow()
            
            task = Task(
                title=task_data["title"],
                description=task_data.get("description"),
                notes=task_data.get("notes"),
                priority=task_data.get("priority", "medium"),
                status=status,
                scheduled_date=parsed_scheduled,
                deadline=parsed_deadline,
                completed_at=completed_at,
            )
            
            db.add(task)
            db.flush()  # Get task ID without committing
            
            created_tasks.append({
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "scheduled_date": task.scheduled_date.isoformat(),
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
    
    # Handle scheduled_date_shift_days for bulk date shifting
    scheduled_shift_days = updates.pop("scheduled_date_shift_days", None)
    shift_deadline_too = updates.pop("shift_deadline_too", False)
    
    for task_id in task_ids:
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            
            if not task:
                errors.append(f"Task ID {task_id} not found")
                continue
            
            # Apply simple updates
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
            
            # Handle scheduled_date shifting
            if scheduled_shift_days is not None:
                task.scheduled_date = task.scheduled_date + timedelta(days=scheduled_shift_days)
                
                # If shift_deadline_too, shift deadline by same amount
                if shift_deadline_too and task.deadline:
                    task.deadline = task.deadline + timedelta(days=scheduled_shift_days)
                # Otherwise check if new scheduled_date is after deadline
                elif task.deadline and task.scheduled_date > task.deadline:
                    errors.append(f"Task ID {task_id}: scheduled_date would be after deadline")
                    continue
            elif "scheduled_date" in updates:
                # Set absolute scheduled_date
                try:
                    parsed = datetime.fromisoformat(updates["scheduled_date"])
                    if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
                        parsed = parsed.replace(hour=12, minute=0, second=0)
                    task.scheduled_date = parsed
                    
                    # Validate against deadline
                    if task.deadline and task.scheduled_date > task.deadline:
                        errors.append(f"Task ID {task_id}: scheduled_date after deadline")
                        continue
                except ValueError:
                    errors.append(f"Task ID {task_id}: invalid scheduled_date format")
                    continue
            
            # Handle deadline updates
            if "deadline" in updates:
                try:
                    parsed = datetime.fromisoformat(updates["deadline"])
                    if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
                        parsed = parsed.replace(hour=12, minute=0, second=0)
                    task.deadline = parsed
                    
                    # Validate against scheduled_date
                    if task.deadline < task.scheduled_date:
                        errors.append(f"Task ID {task_id}: deadline before scheduled_date")
                        continue
                except ValueError:
                    pass
            
            task.updated_at = datetime.utcnow()
            
            updated_tasks.append({
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "status": task.status,
                "scheduled_date": task.scheduled_date.isoformat(),
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
    
    # If we shifted scheduled_date, navigate to the new date/week/month
    if scheduled_shift_days is not None and updated_tasks:
        # Get the first updated task's new scheduled_date to determine where to navigate
        first_updated = db.query(Task).filter(Task.id == updated_tasks[0]["id"]).first()
        if first_updated:
            target_date = first_updated.scheduled_date.date().isoformat()
            
            # Determine view mode based on shift amount
            if abs(scheduled_shift_days) >= 25:  # ~1 month
                view_mode = "monthly"
            elif abs(scheduled_shift_days) >= 6:  # ~1 week
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

