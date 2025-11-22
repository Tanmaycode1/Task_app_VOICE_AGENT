"""Conversation history API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.api_cost import ApiCost
from app.models.conversation import ConversationMessage

router = APIRouter()


@router.get("/conversation/history")
def get_conversation_history(
    page: int = Query(1, ge=1, description="Page number (1-indexed). Default: 1."),
    limit: int = Query(50, ge=1, le=200, description="Number of messages per page. Default: 50. Max: 200."),
    db: Session = Depends(get_db),
):
    """
    Get all conversation history with pagination (global, no session filtering).
    
    Returns messages sorted chronologically (oldest first, newest last) by created_at.
    """
    # Calculate offset
    offset = (page - 1) * limit
    
    # Get total count
    total_count = db.query(ConversationMessage).count()
    
    # Get paginated messages, sorted chronologically
    messages = (
        db.query(ConversationMessage)
        .order_by(ConversationMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    has_next = page < total_pages
    has_previous = page > 1
    
    return {
        "success": True,
        "count": len(messages),
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_previous": has_previous,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "tool_calls": msg.tool_calls,
                "tool_results": msg.tool_results,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ],
    }


@router.delete("/conversation/history")
def clear_conversation_history(
    db: Session = Depends(get_db),
):
    """Clear all conversation history."""
    deleted = db.query(ConversationMessage).delete()
    db.commit()
    return {
        "success": True,
        "message": f"Cleared {deleted} messages",
    }


@router.get("/costs/history")
def get_cost_history(
    page: int = Query(1, ge=1, description="Page number (1-indexed). Default: 1."),
    limit: int = Query(50, ge=1, le=200, description="Number of records per page. Default: 50. Max: 200."),
    db: Session = Depends(get_db),
):
    """
    Get API cost history with pagination.
    
    Returns cost records sorted by most recent first (newest first, oldest last).
    """
    # Calculate offset
    offset = (page - 1) * limit
    
    # Get total count
    total_count = db.query(ApiCost).count()
    
    # Get paginated cost records, sorted by most recent first
    costs = (
        db.query(ApiCost)
        .order_by(ApiCost.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    has_next = page < total_pages
    has_previous = page > 1
    
    # Calculate summary statistics
    total_cost = db.query(func.sum(ApiCost.total_cost)).scalar() or 0.0
    total_input_tokens = db.query(func.sum(ApiCost.input_tokens)).scalar() or 0
    total_output_tokens = db.query(func.sum(ApiCost.output_tokens)).scalar() or 0
    total_requests = total_count
    
    return {
        "success": True,
        "count": len(costs),
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_previous": has_previous,
        "summary": {
            "total_cost": float(total_cost),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_requests": total_requests,
            "average_cost_per_request": float(total_cost / total_requests) if total_requests > 0 else 0.0,
        },
        "costs": [
            {
                "id": cost.id,
                "user_query": cost.user_query,
                "model": cost.model,
                "input_tokens": cost.input_tokens,
                "output_tokens": cost.output_tokens,
                "total_tokens": cost.total_tokens,
                "input_cost": float(cost.input_cost),
                "output_cost": float(cost.output_cost),
                "total_cost": float(cost.total_cost),
                "iterations": cost.iterations,
                "tool_calls_count": cost.tool_calls_count,
                "created_at": cost.created_at.isoformat(),
            }
            for cost in costs
        ],
    }


@router.get("/costs/summary")
def get_cost_summary(
    db: Session = Depends(get_db),
):
    """Get cost summary statistics."""
    total_cost = db.query(func.sum(ApiCost.total_cost)).scalar() or 0.0
    total_input_tokens = db.query(func.sum(ApiCost.input_tokens)).scalar() or 0
    total_output_tokens = db.query(func.sum(ApiCost.output_tokens)).scalar() or 0
    total_requests = db.query(func.count(ApiCost.id)).scalar() or 0
    
    # Get today's costs
    from datetime import datetime, timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_costs = (
        db.query(func.sum(ApiCost.total_cost))
        .filter(ApiCost.created_at >= today_start)
        .scalar() or 0.0
    )
    today_requests = (
        db.query(func.count(ApiCost.id))
        .filter(ApiCost.created_at >= today_start)
        .scalar() or 0
    )
    
    # Get this month's costs
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_costs = (
        db.query(func.sum(ApiCost.total_cost))
        .filter(ApiCost.created_at >= month_start)
        .scalar() or 0.0
    )
    month_requests = (
        db.query(func.count(ApiCost.id))
        .filter(ApiCost.created_at >= month_start)
        .scalar() or 0
    )
    
    return {
        "success": True,
        "all_time": {
            "total_cost": float(total_cost),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_requests": total_requests,
            "average_cost_per_request": float(total_cost / total_requests) if total_requests > 0 else 0.0,
        },
        "today": {
            "total_cost": float(today_costs),
            "total_requests": today_requests,
            "average_cost_per_request": float(today_costs / today_requests) if today_requests > 0 else 0.0,
        },
        "this_month": {
            "total_cost": float(month_costs),
            "total_requests": month_requests,
            "average_cost_per_request": float(month_costs / month_requests) if month_requests > 0 else 0.0,
        },
    }

