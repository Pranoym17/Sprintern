import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm

from api.auth.jwt import SupabaseJWTVerifier
from api.settings import Settings


def signing_material() -> tuple[object, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    return private_key, jwk


def make_token(private_key: object, **claim_overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "email": "student@example.com",
        "aud": "authenticated",
        "iss": "https://project.supabase.co/auth/v1",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(claim_overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def verifier_with_jwks(jwk: dict[str, object]) -> SupabaseJWTVerifier:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [jwk]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = Settings(
        database_url="postgresql+psycopg://unused",
        supabase_url="https://project.supabase.co",
    )
    return SupabaseJWTVerifier(config, client)


async def test_verifies_supabase_token_and_caches_jwks() -> None:
    private_key, jwk = signing_material()
    verifier = verifier_with_jwks(jwk)
    token = make_token(private_key)

    user = await verifier.verify(token)
    cached_user = await verifier.verify(token)

    assert user == cached_user
    assert user.email == "student@example.com"
    await verifier.client.aclose()  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "wrong"},
        {"iss": "https://attacker.example/auth/v1"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
    ],
)
async def test_rejects_invalid_claims(overrides: dict[str, object]) -> None:
    private_key, jwk = signing_material()
    verifier = verifier_with_jwks(jwk)

    with pytest.raises(HTTPException) as error:
        await verifier.verify(make_token(private_key, **overrides))

    assert error.value.status_code == 401
    await verifier.client.aclose()  # type: ignore[union-attr]


async def test_rejects_unknown_signing_key() -> None:
    private_key, _jwk = signing_material()
    _other_key, other_jwk = signing_material()
    verifier = verifier_with_jwks(other_jwk)

    with pytest.raises(HTTPException) as error:
        await verifier.verify(make_token(private_key))

    assert error.value.status_code == 401
    await verifier.client.aclose()  # type: ignore[union-attr]
