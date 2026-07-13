from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError, PyJWK

from api.auth.models import AuthenticatedUser
from api.settings import Settings, settings

ALLOWED_ALGORITHMS = {"ES256", "RS256"}


class SupabaseJWTVerifier:
    def __init__(self, config: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self.client = client
        self._keys: dict[str, PyJWK] = {}
        self._expires_at = datetime.min.replace(tzinfo=UTC)

    async def verify(self, token: str) -> AuthenticatedUser:
        if not self.config.supabase_url:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured"
            )
        try:
            header = jwt.get_unverified_header(token)
            key_id = header.get("kid")
            algorithm = header.get("alg")
            if not key_id or algorithm not in ALLOWED_ALGORITHMS:
                raise InvalidTokenError("Unsupported token header")
            key = await self._get_key(key_id)
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key.key,
                algorithms=[algorithm],
                audience=self.config.supabase_jwt_audience,
                issuer=self.config.supabase_issuer,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
            return AuthenticatedUser(id=claims["sub"], email=claims.get("email"))
        except (InvalidTokenError, ValueError, TypeError, KeyError) as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    async def _get_key(self, key_id: str) -> PyJWK:
        now = datetime.now(UTC)
        if now >= self._expires_at or key_id not in self._keys:
            await self._refresh_keys()
        try:
            return self._keys[key_id]
        except KeyError as exc:
            raise InvalidTokenError("Unknown signing key") from exc

    async def _refresh_keys(self) -> None:
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=5.0)
        try:
            response = await client.get(self.config.supabase_jwks_url)
            response.raise_for_status()
            payload = response.json()
            self._keys = {
                key["kid"]: PyJWK.from_dict(key)
                for key in payload.get("keys", [])
                if key.get("kid") and key.get("alg") in ALLOWED_ALGORITHMS
            }
            self._expires_at = datetime.now(UTC) + timedelta(
                seconds=min(self.config.supabase_jwks_cache_seconds, 600)
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            raise InvalidTokenError("Unable to load signing keys") from exc
        finally:
            if owns_client:
                await client.aclose()


verifier = SupabaseJWTVerifier(settings)
