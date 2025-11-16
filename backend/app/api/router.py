"""Root API router for the application."""

from fastapi import APIRouter

from app.api.routes import agent, flux, health, tasks

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(tasks.router, tags=["tasks"])
api_router.include_router(agent.router, tags=["agent"])
api_router.include_router(flux.router, tags=["flux"])

