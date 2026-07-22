from fastapi import APIRouter

from api.routes import (
    analytics,
    email,
    filters,
    internal,
    jobs,
    matches,
    profiles,
    sources,
    telegram,
)

api_router = APIRouter()
api_router.include_router(profiles.router)
api_router.include_router(filters.router)
api_router.include_router(jobs.router)
api_router.include_router(matches.router)
api_router.include_router(analytics.router)
api_router.include_router(sources.router)
api_router.include_router(internal.router)
api_router.include_router(telegram.router)
api_router.include_router(email.router)

__all__ = ["api_router"]
