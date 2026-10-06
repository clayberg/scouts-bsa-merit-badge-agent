#!/usr/bin/env python3
"""Exports the live FastAPI OpenAPI 3.1 specification to docs/openapi.yaml."""

import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.server import app  # noqa: E402


def export_openapi_schema(output_path: Path | None = None) -> Path:
    """Generates and writes the OpenAPI 3.1 YAML specification from `src.server.app`."""
    target = output_path or (PROJECT_ROOT / "docs" / "openapi.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    yaml_text = yaml.safe_dump(schema, sort_keys=False, allow_unicode=True)
    target.write_text(yaml_text, encoding="utf-8")
    return target


if __name__ == "__main__":
    out = export_openapi_schema()
    print(f"Exported OpenAPI 3.1 schema ({out.stat().st_size} bytes) to {out}")
