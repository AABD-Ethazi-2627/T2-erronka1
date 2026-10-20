"""Structural tests for the versionable CG14 NiFi flow (G06).

No live NiFi/Kafka exists here, so these tests verify the artifact itself:
valid template shape, single source of truth for the validation script, no
secrets, everything environment-driven, and the valid/rejected/retry wiring.
"""

import json
import re
from pathlib import Path

NIFI = Path(__file__).parent.parent / "nifi-flows"
FLOW = NIFI / "cg14_validation_flow_v0.1.0.json"
GROOVY = NIFI / "cg14_validate.groovy"

CODES = [
    "MESSAGE_TOO_LARGE",
    "MALFORMED_CSV",
    "HEADER_ROW",
    "INVALID_TIMESTAMP",
    "INVALID_MACHINE_ID",
    "INVALID_MACHINE_TYPE",
    "INVALID_NUMERIC",
    "NON_FINITE_NUMERIC",
    "NEGATIVE_PHYSICAL_VALUE",
    "INVALID_LABEL",
    "TRAINING_LABEL_STRIPPED",
]


def _flow():
    return json.loads(FLOW.read_text(encoding="utf-8"))


def _group(flow):
    groups = flow["flowContents"]["processGroups"]
    assert len(groups) == 1
    return groups[0]


def test_flow_is_importable_json_with_bound_parameter_context():
    flow = _flow()
    group = _group(flow)

    assert flow["encodingVersion"] == {"majorVersion": 2, "minorVersion": 0}
    assert group["parameterContextName"] == "CG14-params"
    assert "CG14-params" in {ctx["name"] for ctx in flow["parameterContexts"].values()}


def test_embedded_script_matches_the_single_source_of_truth():
    flow = _flow()
    scripts = [
        p for p in _group(flow)["processors"] if p["type"].endswith("ExecuteScript")
    ]

    assert len(scripts) == 1
    assert scripts[0]["properties"]["Script Engine"] == "Groovy"
    assert scripts[0]["properties"]["Script Body"] == GROOVY.read_text(encoding="utf-8")


def test_script_covers_every_stable_rejection_code():
    body = GROOVY.read_text(encoding="utf-8")

    for code in CODES:
        assert code in body, f"script lacks {code}"


def test_no_secrets_or_hardcoded_credentials_in_flow():
    text = FLOW.read_text(encoding="utf-8")

    assert "adminpassword123" not in text
    assert not re.search(r"(?i)(sasl\.password|ssl\.key\.password)\s*[\"']?\s*:", text)
    for match in re.findall(r"#{([A-Za-z0-9_.]+)}", text):
        assert match.startswith("CG14_"), f"unexpected parameter: {match}"


def test_all_parameter_references_resolve():
    flow = _flow()
    text = FLOW.read_text(encoding="utf-8")
    refs = set(re.findall(r"#{([A-Za-z0-9_.]+)}", text))
    defined = set()
    for ctx in flow["parameterContexts"].values():
        defined.update(ctx["parameters"].keys())

    assert refs <= defined, f"unresolved: {refs - defined}"


def test_processors_pin_nifi_versions_and_valid_rejected_wiring():
    flow = _flow()
    group = _group(flow)
    by_id = {p["identifier"]: p for p in group["processors"]}

    for proc in group["processors"]:
        assert proc["bundle"]["version"] == "1.25.0", proc["identifier"]

    kinds = [p["type"].split(".")[-1] for p in group["processors"]]
    assert "ConsumeKafka_2_6" in kinds
    assert kinds.count("PublishKafka_2_6") == 3  # valid, rejected, retry
    assert "ExecuteScript" in kinds

    rels = {
        (c["source"]["id"], c["destination"]["id"]): c["selectedRelationships"]
        for c in group["connections"]
    }
    assert rels[("cg14-validate", "cg14-route")] == ["success"]
    assert rels[("cg14-validate", "cg14-engine-errors")] == ["failure"]
    assert rels[("cg14-route", "cg14-tag-valid")] == ["valid"]
    assert rels[("cg14-route", "cg14-tag-rejected")] == ["rejected"]
    assert rels[("cg14-retry-route", "cg14-retry-target")] == ["retry"]
    assert rels[("cg14-retry-route", "cg14-dead-letter")] == ["unmatched"]
    # Bounded retry loop: exhausted publishers return to counting, never vanish.
    assert rels[("cg14-retry-target", "cg14-retry-count")] == ["failure"]
    assert by_id["cg14-publish-valid"]["autoTerminatedRelationships"] == ["success"]
    assert by_id["cg14-dead-letter"]["autoTerminatedRelationships"] == ["success"]


def test_starter_skeleton_is_untouched():
    """The teacher-provided skeleton must survive next to the new CG14 flow."""
    skeleton = NIFI / "cnc_fase1_INCOMPLETO.json"

    assert skeleton.exists()
    assert FLOW.exists() and FLOW != skeleton
