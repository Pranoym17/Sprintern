from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.auth.dependencies import CurrentUser
from api.auth.models import AuthenticatedUser
from api.settings import settings


def require_administrator(user: CurrentUser) -> AuthenticatedUser:
    if str(user.id).casefold() not in settings.admin_user_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


Administrator = Annotated[AuthenticatedUser, Depends(require_administrator)]
