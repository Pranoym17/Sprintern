from fastapi import APIRouter

from api.routes import (
    analytics,
    applications,
    discovery,
    email,
    filters,
    internal,
    jobs,
    matches,
    notifications,
    profiles,
    sources,
    telegram,
    watchlists,
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
api_router.include_router(discovery.router)
api_router.include_router(watchlists.router)
api_router.include_router(applications.router)
api_router.include_router(notifications.router)

__all__ = ["api_router"]
