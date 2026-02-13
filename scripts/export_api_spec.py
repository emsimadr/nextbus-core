#!/usr/bin/env python3
"""
Export OpenAPI spec and JSON schemas for API contract distribution.

This script generates:
- api/openapi.json - Full OpenAPI 3.0 specification
- api/schemas/*.json - Individual JSON schemas for each model

Run this after any model changes to keep the API contract up to date.
"""

import json
import sys
from pathlib import Path

# Add project root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from src.app import app
from src.models import (
    Arrival,
    BoardItemResponse,
    BoardResponse,
    ErrorDetail,
)


def export_openapi_spec(output_path: Path):
    """Export the full OpenAPI 3.0 specification."""
    openapi_schema = app.openapi()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)
    
    print(f"[OK] Exported OpenAPI spec to {output_path}")


def export_json_schemas(output_dir: Path):
    """Export individual JSON schemas for each Pydantic model."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    models = {
        "Arrival": Arrival,
        "ErrorDetail": ErrorDetail,
        "BoardItemResponse": BoardItemResponse,
        "BoardResponse": BoardResponse,
    }
    
    for name, model in models.items():
        schema = model.model_json_schema()
        
        output_path = output_dir / f"{name}.json"
        with open(output_path, "w") as f:
            json.dump(schema, f, indent=2)
        
        print(f"[OK] Exported {name} schema to {output_path}")


def main():
    repo_root = Path(__file__).parent.parent
    api_dir = repo_root / "api"
    
    print("Exporting API specification files...\n")
    
    # Export OpenAPI spec
    export_openapi_spec(api_dir / "openapi.json")
    
    # Export JSON schemas
    export_json_schemas(api_dir / "schemas")
    
    print("\nDone! API contract files are ready for distribution.")
    print("\nNext steps:")
    print("- Review api/openapi.json for accuracy")
    print("- Commit these files to version control")
    print("- Reference them in your client projects")


if __name__ == "__main__":
    main()
