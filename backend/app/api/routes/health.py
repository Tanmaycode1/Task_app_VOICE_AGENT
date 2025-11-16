"""Health and diagnostics endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Response model for health probes."""

    status: str = "ok"


@router.get(
    "/",
    summary="Readiness probe",
    response_model=HealthResponse,
)
def readiness_probe() -> HealthResponse:
    """Return a simple readiness response."""
    return HealthResponse()

