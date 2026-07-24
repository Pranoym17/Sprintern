import argparse
import copy
import json
from pathlib import Path
from typing import Any

from api.main import app


def _referenced_schemas(value: Any) -> set[str]:
    references: set[str] = set()
    if isinstance(value, dict):
        reference = value.get("$ref")
        prefix = "#/components/schemas/"
        if isinstance(reference, str) and reference.startswith(prefix):
            references.add(reference.removeprefix(prefix))
        for item in value.values():
            references.update(_referenced_schemas(item))
    elif isinstance(value, list):
        for item in value:
            references.update(_referenced_schemas(item))
    return references


def public_contract() -> dict[str, Any]:
    """Export browser-consumable routes without publishing the internal operator contract."""
    schema = copy.deepcopy(app.openapi())
    schema["paths"] = {
        path: item for path, item in schema["paths"].items() if not path.startswith("/internal/v1/")
    }
    schemas = schema.get("components", {}).get("schemas", {})
    reachable = _referenced_schemas(schema["paths"])
    pending = list(reachable)
    while pending:
        name = pending.pop()
        for dependency in _referenced_schemas(schemas.get(name, {})):
            if dependency not in reachable:
                reachable.add(dependency)
                pending.append(dependency)
    schema["components"]["schemas"] = {
        name: definition for name, definition in schemas.items() if name in reachable
    }
    # Python 3.13 adopted RFC 9110's newer phrase while Python 3.12 still reports the
    # historical phrase. Normalize documentation so supported runtimes generate one contract.
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            response = operation.get("responses", {}).get("422")
            if isinstance(response, dict):
                response["description"] = "Unprocessable Content"
    return schema


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Sprintern's public browser API contract")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(public_contract(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
