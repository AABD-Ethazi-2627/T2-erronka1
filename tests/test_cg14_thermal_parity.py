"""Kelvin domain and all five embedded scripts must agree with the source."""

import json
from pathlib import Path

import pytest

from cg14_validation.validator import parse_csv_event

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("index", [3, 4])
@pytest.mark.parametrize("value,valid", [(-1, False), (0, False), (0.1, True)])
def test_kelvin_strictly_positive(index, value, valid):
    fields = (
        (ROOT / "tests/fixtures/cg14/valid_event.csv").read_text().strip().split(",")
    )
    fields[index] = str(value)
    result = parse_csv_event(
        ",".join(fields), source_uri="fixture://thermal", record_ref="0"
    )
    assert result.valid is valid
    if not valid:
        assert result.issues[0].code == "NEGATIVE_PHYSICAL_VALUE"


def test_all_five_exports_embed_source_and_preserve_thermal_rule():
    script = (ROOT / "nifi-flows/cg14_validate.groovy").read_text()
    assert "v < 0 || (kelvin.contains(s) && v == 0)" in script

    def scripts(obj):
        if isinstance(obj, dict):
            body = obj.get("properties", {}).get("Script Body")
            if body and "cnc.telemetry.v" in body:
                yield body
            for value in obj.values():
                yield from scripts(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from scripts(value)

    exports = list((ROOT / "nifi-flows").glob("cg14_validation_flow*.json"))
    assert len(exports) == 5
    for export in exports:
        assert list(scripts(json.loads(export.read_text()))) == [script]
