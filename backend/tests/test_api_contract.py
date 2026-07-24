import httpx

from api.main import app
from api.schemas.common import strip_internal_origin
from scripts.export_openapi import public_contract


def test_openapi_exposes_only_versioned_product_routes() -> None:
    paths = app.openapi()["paths"]
    product_paths = [
        path for path in paths if path not in {"/health", "/health/live", "/health/ready"}
    ]
    assert product_paths
    assert all(path.startswith(("/api/v1/", "/internal/v1/")) for path in product_paths)
    assert "/api/v1/users/me" in paths
    assert "/internal/v1/ingestion-runs" in paths


def test_every_json_operation_documents_a_response_contract() -> None:
    for path, path_item in app.openapi()["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            assert "responses" in operation, f"{method.upper()} {path} has no response contract"
            assert any(status.startswith("2") for status in operation["responses"]), (
                f"{method.upper()} {path} has no success response"
            )


def test_public_job_contract_does_not_expose_ingestion_origin() -> None:
    properties = app.openapi()["components"]["schemas"]["PublicJobResponse"]["properties"]

    assert "source" not in properties
    assert "sources" not in properties
    assert "deadline_source" not in properties
    assert "application_url" in properties


def test_public_json_sanitizer_removes_nested_origin_metadata() -> None:
    value = {
        "trigger": "bookmark",
        "source": "github_repo",
        "nested": [{"source_key": "private", "safe": "visible"}],
    }

    assert strip_internal_origin(value) == {
        "trigger": "bookmark",
        "nested": [{"safe": "visible"}],
    }


def test_frontend_contract_excludes_internal_operations_and_schemas() -> None:
    schema = public_contract()

    assert all(not path.startswith("/internal/") for path in schema["paths"])
    assert "/api/v1/users/me" in schema["paths"]
    assert "/api/v1/admin/sources" in schema["paths"]
    assert "SourceStatusResponse" not in schema["components"]["schemas"]


async def test_unversioned_product_route_is_not_available() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/users/me")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
