"""Offline Draft 2020-12 validators for the existing CG03 proposals."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


def contract_hashes():
    """Pin schema bytes for coordinated worker/API upgrades."""
    root = Path(__file__).resolve().parents[1] / "contracts"
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.glob("*.schema.json"))
    }


def validators(root=Path("contracts")):
    formats = FormatChecker()

    @formats.checks("date-time", raises=(ValueError, TypeError))
    def utc(value):
        if not isinstance(value, str):
            return True
        if not value.endswith("Z"):
            return False
        datetime.fromisoformat(value)
        return True

    schemas = {
        p.name.removesuffix(".schema.json"): json.loads(p.read_text())
        for p in root.glob("*.schema.json")
    }
    registry = Registry()
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return {
        name: Draft202012Validator(schema, registry=registry, format_checker=formats)
        for name, schema in schemas.items()
    }
