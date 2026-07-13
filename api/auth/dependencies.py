import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth.jwt import verifier
from api.auth.models import AuthenticatedUser
from api.settings import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await verifier.verify(credentials.credentials)


def require_internal_api_key(x_internal_api_key: Annotated[str | None, Header()] = None) -> None:
    if not settings.internal_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Internal API is not configured")
    if x_internal_api_key is None or not secrets.compare_digest(
        x_internal_api_key, settings.internal_api_key
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal API key")


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
