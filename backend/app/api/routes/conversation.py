"""Conversation history API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
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

