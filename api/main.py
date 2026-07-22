import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session

from api.database import get_db
from api.errors import register_exception_handlers
from api.health import assert_ready
from api.observability import configure_logging, request_id_context
from api.rate_limiting import ip_rate_limit
from api.routes import api_router
from api.settings import settings

configure_logging(
    secrets=[
        settings.internal_api_key,
        settings.github_token,
        settings.telegram_bot_token,
        settings.telegram_webhook_secret,
        settings.resend_api_key,
        settings.supabase_anon_key,
        settings.supabase_service_role_key,
        settings.unsubscribe_signing_secret,
        settings.resend_webhook_secret,
    ]
)
logger = logging.getLogger(__name__)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

app = FastAPI(title="Sprintern API", version="0.1.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router)


@app.middleware("http")
async def correlate_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_id if _REQUEST_ID.fullmatch(supplied_id) else str(uuid.uuid4())
    token = request_id_context.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http.request.completed",
            extra={
                "event": "http.request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response
    finally:
        request_id_context.reset(token)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/health/live",
    tags=["system"],
    dependencies=[Depends(ip_rate_limit("health.live", 120))],
)
def health_live() -> dict[str, str]:
    return {"status": "alive"}


@app.get(
    "/health/ready",
    tags=["system"],
    dependencies=[Depends(ip_rate_limit("health.ready", 30))],
)
def health_ready(session: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    assert_ready(session)
    return {"status": "ready"}
