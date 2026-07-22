import uuid

import httpx

from api.errors import AppError


class SupabaseAuthAdmin:
    def __init__(self, base_url: str, service_role_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_role_key = service_role_key

    async def delete_user(self, user_id: uuid.UUID) -> None:
        if not self.base_url or not self.service_role_key:
            raise AppError(
                503,
                "account_deletion_unavailable",
                "Account deletion is temporarily unavailable",
            )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    f"{self.base_url}/auth/v1/admin/users/{user_id}",
                    headers={
                        "Authorization": f"Bearer {self.service_role_key}",
                        "apikey": self.service_role_key,
                    },
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise AppError(
                503,
                "account_deletion_unavailable",
                "Account deletion is temporarily unavailable",
            ) from exc
        if response.status_code not in {200, 204, 404}:
            raise AppError(
                503,
                "account_deletion_unavailable",
                "Account deletion is temporarily unavailable",
            )
