import httpx

from api.main import app


def test_openapi_exposes_only_versioned_product_routes() -> None:
    paths = app.openapi()["paths"]
    product_paths = [
        path
        for path in paths
        if path not in {"/health", "/health/live", "/health/ready"}
    ]
    assert product_paths
    assert all(
        path.startswith(("/api/v1/", "/internal/v1/")) for path in product_paths
    )
    assert "/api/v1/users/me" in paths
    assert "/internal/v1/ingestion-runs" in paths


def test_every_json_operation_documents_a_response_contract() -> None:
    for path, path_item in app.openapi()["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            assert "responses" in operation, f"{method.upper()} {path} has no response contract"
            assert any(
                status.startswith("2") for status in operation["responses"]
            ), f"{method.upper()} {path} has no success response"


async def test_unversioned_product_route_is_not_available() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/users/me")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
