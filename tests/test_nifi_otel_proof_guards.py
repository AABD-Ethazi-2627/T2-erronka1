"""Blocked qualification must fail both process status and sealed evidence."""

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = (
    Path(__file__).resolve().parents[1]
    / "deploy/images/nifi-patches/otel-qualification"
)
SPEC = importlib.util.spec_from_file_location(
    "otel_proof_guard", HERE / "qualification_proof.py"
)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def successful():
    return {
        "status": p.PASSED,
        "replacement": None,
        "runtime_approved": False,
        "commands": [
            {"phase": n, "returncode": 0}
            for n in ["portable-guards", "oracle", "static", "runtime"]
        ],
        "image_identity_unchanged": True,
        "source_unchanged": True,
        "remaining_owned_containers": [],
        "finalization_errors": [],
    }


@pytest.mark.parametrize(
    "name",
    [
        "aligned-pins.json",
        "aligned-result.json",
        "narrow-result.json",
        "known-inputs.json",
        "incubator-allowlist.json",
        "loader-inputs.json",
    ],
)
@pytest.mark.parametrize("mutation", ["approved", "replacement", "missing"])
def test_actual_versioned_metadata_cannot_gain_approval(tmp_path, name, mutation):
    for filename in [
        "aligned-pins.json",
        "aligned-result.json",
        "narrow-result.json",
        "known-inputs.json",
        "incubator-allowlist.json",
        "loader-inputs.json",
    ]:
        (tmp_path / filename).write_bytes((HERE / filename).read_bytes())
    data = json.loads((tmp_path / name).read_text())
    if mutation == "approved":
        data["runtime_approved"] = True
    elif mutation == "replacement":
        data["replacement"] = "applied"
    else:
        data.pop("replacement")
    (tmp_path / name).write_text(json.dumps(data))
    with pytest.raises(ValueError, match="metadata must retain"):
        p.check_metadata(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "blocked-aligned-qualification"),
        ("image_identity_unchanged", False),
        ("source_unchanged", False),
        ("remaining_owned_containers", ["own-container"]),
        ("finalization_errors", ["inspection failed"]),
    ],
)
def test_integrity_or_cleanup_failure_cannot_exit_green(field, value):
    report = successful()
    report[field] = value
    assert p.finish_report(report) == 1
    assert report["status"] == "blocked-aligned-qualification"


@pytest.mark.parametrize("phase", ["portable-guards", "oracle", "static", "runtime"])
def test_nonzero_phase_cannot_be_hidden(phase):
    report = successful()
    next(c for c in report["commands"] if c["phase"] == phase)["returncode"] = 1
    assert p.finish_report(report) == 1


def test_missing_phase_is_not_completed():
    report = successful()
    report["commands"].pop()
    assert p.finish_report(report) == 1


def test_sealer_preserves_exact_input_hashes_and_refuses_overwrite(tmp_path):
    runner = successful()
    runner["source_sha256"] = {
        "deploy/images/nifi-patches/otel-qualification/probe.py": "a" * 64
    }
    (tmp_path / "aligned-reserved-result.json").write_text(json.dumps(runner))
    for phase, status in p.PHASE_STATUS.items():
        (tmp_path / (phase + "-result.json")).write_text(
            json.dumps(
                {
                    "phase": phase,
                    "status": status,
                    "replacement": None,
                    "runtime_approved": False,
                    "sources_before": {"/tools/probe.py": "a" * 64},
                    "sources_after": {"/tools/probe.py": "a" * 64},
                }
            )
        )
    out = tmp_path / "summary.json"
    result = p.seal_summary(tmp_path, out)
    assert result["runtime_approved"] is False and result["replacement"] is None
    assert len(result["input_sha256"]) == 4
    assert json.loads(out.read_text()) == result
    with pytest.raises(FileExistsError):
        p.seal_summary(tmp_path, out)
    failed = copy.deepcopy(runner)
    failed["commands"][0]["returncode"] = 1
    (tmp_path / "aligned-reserved-result.json").write_text(json.dumps(failed))
    with pytest.raises(ValueError, match="blocked or incomplete"):
        p.seal_summary(tmp_path, tmp_path / "forbidden-summary.json")
    assert not (tmp_path / "forbidden-summary.json").exists()


def test_real_runner_error_path_returns_nonzero_and_saves_blocked(
    tmp_path, monkeypatch
):
    monkeypatch.setitem(sys.modules, "qualification_proof", p)
    spec = importlib.util.spec_from_file_location(
        "otel_runner_under_test", HERE / "run_aligned_reserved.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    tools = tmp_path / "source/deploy/images/nifi-patches/otel-qualification"
    tools.mkdir(parents=True)
    for name in p.METADATA:
        (tools / name).write_bytes((HERE / name).read_bytes())
    config = tmp_path / "config/security"
    config.mkdir(parents=True)
    (config / "java.security").write_text("fixture")
    monkeypatch.setattr(runner, "CONFIG", config.parent)
    image = {"Id": runner.IMAGE, "RootFS": {"Layers": ["unchanged"]}}

    def output(args, **kwargs):
        return json.dumps([image]).encode() if args[1:3] == ["image", "inspect"] else ""

    monkeypatch.setattr(runner.subprocess, "check_output", output)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1),
    )
    assert runner.run_qualification(tmp_path) == 1
    saved = json.loads((tmp_path / "aligned-reserved-result.json").read_text())
    assert saved["status"] == "blocked-aligned-qualification"
    assert saved["commands"][0]["returncode"] == 1


def test_narrow_runner_checks_requested_phase_integrity_and_previous_failures():
    report = successful()
    report["status"] = "bounded-requested-phase-passed"
    report["commands"] = [
        {"phase": "unit-green", "returncode": 0},
        {"phase": "static", "returncode": 0},
    ]
    assert p.finish_narrow_report(report, ["static"]) == 0
    assert p.finish_narrow_report(copy.deepcopy(report), ["runtime"]) == 1
    for field, value in [
        ("image_identity_unchanged", False),
        ("source_unchanged", False),
        ("remaining_owned_containers", ["leftover"]),
    ]:
        bad = copy.deepcopy(report)
        bad[field] = value
        assert p.finish_narrow_report(bad, ["static"]) == 1
    report["commands"].append({"phase": "static", "returncode": 1})
    assert p.finish_narrow_report(report, ["static"]) == 1


def test_runner_refuses_failed_phase_logs_before_any_docker_call(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "qualification_proof", p)
    spec = importlib.util.spec_from_file_location(
        "otel_existing_guard", HERE / "run_aligned_reserved.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    failure = tmp_path / "static.stderr"
    failure.write_text("previous failure must survive")

    def forbidden(*args, **kwargs):
        raise AssertionError("Docker must not run")

    monkeypatch.setattr(runner.subprocess, "check_output", forbidden)
    with pytest.raises(ValueError, match="fresh proof root"):
        runner.run_qualification(tmp_path)
    assert failure.read_text() == "previous failure must survive"


def module(name):
    spec = importlib.util.spec_from_file_location(
        "otel_v2_" + name, HERE / (name + ".py")
    )
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def static_fixture():
    g = module("gates")
    c = module("coverage")
    r = {
        field: [row | {"scenario": scenario} for row in c.optional_records(scenario)]
        for field, scenario in [
            ("unresolved_old", "old"),
            ("unresolved_current_references", "aligned"),
            ("unresolved_including_api_family", "aligned-all-family-including-api"),
        ]
    }
    r.update(
        phase="static",
        status="aligned-symbolic-analysis-completed",
        replacement=None,
        runtime_approved=False,
        newly_broken_references=[],
        abi_delta={"external_impacts": []},
        narrow_negative_control=[{}] * 10,
        reversed_sdk_api_negative_control=[
            {
                "category": "unknown",
                "reference": ["io/opentelemetry/common/impl/ConfigUtil"],
            }
        ]
        * 8,
        missing_api_negative_new_failures=1,
        selected_external_consumers=list(g.EXTERNAL_CONSUMERS),
        observed_external_class_names=list(g.EXTERNAL_CONSUMERS),
    )
    return r


def runtime_fixture():
    g = module("gates")
    passed = {k: {"status": "PASS", "cause": "-"} for k in g.EXTERNAL_CONSUMERS}
    ordinary = {
        "returncode": 0,
        "configutil_consumer_passed": True,
        "observed_external_consumer_initialization": passed,
        "service_provider_lines": ["service-provider\tgcp\tPASS\t-"],
        "class_load_otel_count": 1,
        "loader_model": "real-instance-pass-through-tccl-with-jetty-parent",
        "behavior_results": {
            k: {"status": "PASS", "value": "observed"} for k in g.BEHAVIORS
        },
    }
    return {
        "phase": "runtime",
        "status": "bounded-real-NarClassLoader-aligned-controls-passed",
        "replacement": None,
        "runtime_approved": False,
        "outcomes": [
            copy.deepcopy(ordinary) | {"variant": "old"},
            {
                "variant": "narrow",
                "returncode": 1,
                "expected_configutil_failure": True,
                "observed_external_consumer_initialization": {},
            },
            copy.deepcopy(ordinary) | {"variant": "aligned"},
            {
                "variant": "aligned-missing-attributekey",
                "returncode": 1,
                "expected_attribute_key_failure": True,
                "observed_external_consumer_initialization": {
                    "com.google.cloud.bigquery.storage.v1.TelemetryMetrics": {
                        "status": "FAIL",
                        "cause": "java.lang.ClassNotFoundException",
                    }
                },
            },
        ],
    }


@pytest.mark.parametrize(
    "field",
    [
        "unresolved_old",
        "unresolved_current_references",
        "unresolved_including_api_family",
    ],
)
def test_static_gate_rejects_unknown_for_every_scenario(field):
    r = static_fixture()
    r[field].append(
        {"category": "unknown", "consumer": "real/caller", "reference": ["missing"]}
    )
    with pytest.raises(ValueError, match="unclassified"):
        module("gates").gate_static(r)


@pytest.mark.parametrize(
    "field",
    [
        "unresolved_old",
        "unresolved_current_references",
        "unresolved_including_api_family",
    ],
)
def test_static_gate_pins_every_optional_coverage(field):
    r = static_fixture()
    r[field].pop()
    with pytest.raises(ValueError, match="optional"):
        module("gates").gate_static(r)


@pytest.mark.parametrize(
    "kind",
    [
        "removed-reference",
        "removed-descriptor-type",
        "unimplemented-new-abstract",
        "access-or-static-change",
        "methodref-interface-kind-change",
    ],
)
def test_static_gate_rejects_each_external_abi_impact(kind):
    r = static_fixture()
    r["abi_delta"]["external_impacts"] = [{"kind": kind}]
    with pytest.raises(ValueError, match="ABI"):
        module("gates").gate_static(r)


@pytest.mark.parametrize(
    "field,value",
    [
        ("newly_broken_references", [{}]),
        ("narrow_negative_control", []),
        ("reversed_sdk_api_negative_control", []),
        ("missing_api_negative_new_failures", 0),
        (
            "selected_external_consumers",
            ["org.apache.nifi.processors.gcp.bigquery.PutBigQuery"],
        ),
        ("observed_external_class_names", []),
    ],
)
def test_static_gate_connection_rejects_missing_controls(field, value):
    r = static_fixture()
    r[field] = value
    with pytest.raises(ValueError):
        module("gates").gate_static(r)


@pytest.mark.parametrize("phase", ["static", "runtime"])
def test_actual_phase_emitter_calls_decision_gate_and_writes_nothing_on_rejection(
    tmp_path, monkeypatch, phase
):
    aligned = module("aligned")
    r = static_fixture() if phase == "static" else runtime_fixture()
    observed = []

    def reject(record):
        observed.append(record)
        raise ValueError("deliberate gate rejection")

    monkeypatch.setattr(aligned.g, "gate_" + phase, reject)
    with pytest.raises(ValueError, match="deliberate"):
        aligned.complete_phase(r, tmp_path)
    assert observed == [r] and not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "field,value",
    [
        ("returncode", 1),
        ("configutil_consumer_passed", False),
        ("service_provider_lines", []),
        ("class_load_otel_count", 0),
        ("loader_model", None),
        ("behavior_results", {}),
    ],
)
def test_runtime_gate_requires_observed_coverage(field, value):
    r = runtime_fixture()
    r["outcomes"][2][field] = value
    with pytest.raises(ValueError):
        module("gates").gate_runtime(r)


def test_runtime_gate_cannot_call_equal_failures_success():
    r = runtime_fixture()
    for i in (0, 2):
        for v in r["outcomes"][i]["observed_external_consumer_initialization"].values():
            v.update(status="FAIL", cause="missing")
    with pytest.raises(ValueError, match="failures"):
        module("gates").gate_runtime(r)


def test_runtime_gate_checks_semantic_parity_not_only_counts():
    for target in (
        "behavior_results",
        "service_provider_lines",
        "observed_external_consumer_initialization",
    ):
        r = runtime_fixture()
        if target == "service_provider_lines":
            r["outcomes"][2][target] = ["different"]
        elif target == "behavior_results":
            r["outcomes"][2][target]["gax-metrics"]["value"] = "different"
        else:
            r["outcomes"][2][target].pop(next(iter(r["outcomes"][2][target])))
        with pytest.raises(ValueError):
            module("gates").gate_runtime(r)


@pytest.mark.parametrize(
    "index,field,value",
    [
        (1, "returncode", 0),
        (1, "expected_configutil_failure", False),
        (1, "observed_external_consumer_initialization", {"invented": {}}),
        (3, "returncode", 0),
        (3, "expected_attribute_key_failure", False),
        (3, "observed_external_consumer_initialization", {}),
    ],
)
def test_runtime_gate_requires_actual_negative_controls(index, field, value):
    r = runtime_fixture()
    r["outcomes"][index][field] = value
    with pytest.raises(ValueError):
        module("gates").gate_runtime(r)


def test_literal_metadata_coverage_is_not_parameterized_from_implementation():
    assert set(p.METADATA) == {
        "aligned-pins.json",
        "aligned-result.json",
        "narrow-result.json",
        "known-inputs.json",
        "incubator-allowlist.json",
        "loader-inputs.json",
    }


@pytest.mark.parametrize("mutation", ["duplicate", "boolean"])
def test_finish_report_rejects_duplicate_commands_and_boolean_exit(mutation):
    r = successful()
    if mutation == "duplicate":
        r["commands"].append(copy.deepcopy(r["commands"][0]))
    else:
        r["commands"][0]["returncode"] = False
    assert p.finish_report(r) == 1


def proof_fixture(tmp_path):
    runner = successful()
    runner["source_sha256"] = {
        "deploy/images/nifi-patches/otel-qualification/probe.py": "a" * 64
    }
    (tmp_path / "aligned-reserved-result.json").write_text(json.dumps(runner))
    for phase, status in p.PHASE_STATUS.items():
        (tmp_path / (phase + "-result.json")).write_text(
            json.dumps(
                {
                    "phase": phase,
                    "status": status,
                    "replacement": None,
                    "runtime_approved": False,
                    "sources_before": {"/tools/probe.py": "a" * 64},
                    "sources_after": {"/tools/probe.py": "a" * 64},
                }
            )
        )


@pytest.mark.parametrize("phase", ["oracle", "static", "runtime"])
@pytest.mark.parametrize(
    "mutation", ["status", "approval", "source", "missing", "symlink"]
)
def test_sealer_rejects_each_phase_gap_before_output(tmp_path, phase, mutation):
    proof_fixture(tmp_path)
    file = tmp_path / (phase + "-result.json")
    r = json.loads(file.read_text())
    if mutation == "status":
        r["status"] = "blocked"
    elif mutation == "approval":
        r["runtime_approved"] = True
    elif mutation == "source":
        r["sources_before"]["/tools/probe.py"] = "b" * 64
    if mutation == "missing":
        file.unlink()
    elif mutation == "symlink":
        other = tmp_path / "real.json"
        file.rename(other)
        file.symlink_to(other)
    else:
        file.write_text(json.dumps(r))
    with pytest.raises((ValueError, FileNotFoundError)):
        p.seal_summary(tmp_path, tmp_path / "forbidden.json")
    assert not (tmp_path / "forbidden.json").exists()


def test_manifest_exports_only_recorded_sources_and_positive_raw_outputs(tmp_path):
    import hashlib

    proof_fixture(tmp_path)
    source = tmp_path / "source/deploy/images/nifi-patches/otel-qualification/probe.py"
    source.parent.mkdir(parents=True)
    source.write_text("fixed source")
    r = json.loads((tmp_path / "aligned-reserved-result.json").read_text())
    r["source_sha256"][str(source.relative_to(tmp_path / "source"))] = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    (tmp_path / "aligned-reserved-result.json").write_text(json.dumps(r))
    (tmp_path / "static.stdout").write_text("actual raw")
    (tmp_path / "planted.py").write_text("not an allowed artifact")
    exported = p.export_compact_manifest(tmp_path, tmp_path / "compact.json")
    assert (
        "static.stdout" in exported
        and "planted.py" not in exported
        and str(source.relative_to(tmp_path)) in exported
    )
    with pytest.raises(FileExistsError):
        p.export_compact_manifest(tmp_path, tmp_path / "compact.json")


def test_actual_runner_command_has_network_and_resource_bounds(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "qualification_proof", p)
    runner = module("run_aligned_reserved")
    tools = tmp_path / "source/deploy/images/nifi-patches/otel-qualification"
    tools.mkdir(parents=True)
    for name in [
        "aligned-pins.json",
        "aligned-result.json",
        "narrow-result.json",
        "known-inputs.json",
        "incubator-allowlist.json",
        "loader-inputs.json",
    ]:
        (tools / name).write_bytes((HERE / name).read_bytes())
    config = tmp_path / "config/security"
    config.mkdir(parents=True)
    (config / "java.security").write_text("fixture")
    monkeypatch.setattr(runner, "CONFIG", config.parent)
    image = {"Id": runner.IMAGE, "RootFS": {"Layers": ["same"]}}
    monkeypatch.setattr(
        runner.subprocess,
        "check_output",
        lambda args, **kw: (
            json.dumps([image]).encode() if args[1:3] == ["image", "inspect"] else ""
        ),
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(args, 0, stdout="", stderr=""),
    )
    commands = []

    class Process:
        def __init__(self, args, **kw):
            commands.append(args)

        def wait(self, **kw):
            return 1

    monkeypatch.setattr(runner.subprocess, "Popen", Process)
    assert runner.run_qualification(tmp_path) == 1
    assert len(commands) == 1
    args = commands[0]
    for flag, value in [
        ("--network", "none"),
        ("--memory", "512m"),
        ("--memory-swap", "512m"),
        ("--cpus", "1"),
        ("--cpuset-cpus", "0"),
        ("--cap-drop", "ALL"),
        ("--pids-limit", "64"),
        ("--user", "1000:1000"),
    ]:
        assert args[args.index(flag) + 1] == value
    assert "--read-only" in args and "no-new-privileges" in args and "core=0:0" in args


def test_actual_runner_rejects_metadata_before_any_phase(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "qualification_proof", p)
    runner = module("run_aligned_reserved")
    tools = tmp_path / "source/deploy/images/nifi-patches/otel-qualification"
    tools.mkdir(parents=True)
    for name in p.METADATA:
        (tools / name).write_bytes((HERE / name).read_bytes())
    value = json.loads((tools / "aligned-result.json").read_text())
    value["runtime_approved"] = True
    (tools / "aligned-result.json").write_text(json.dumps(value))
    config = tmp_path / "config/security"
    config.mkdir(parents=True)
    (config / "java.security").write_text("fixture")
    monkeypatch.setattr(runner, "CONFIG", config.parent)
    monkeypatch.setattr(
        runner.subprocess,
        "check_output",
        lambda *a, **kw: json.dumps([{"Id": runner.IMAGE}]).encode(),
    )
    monkeypatch.setattr(
        runner.subprocess, "Popen", lambda *a, **kw: pytest.fail("phase must not start")
    )
    with pytest.raises(ValueError, match="metadata"):
        runner.run_qualification(tmp_path)


def test_positive_gates_emit_only_preparation_and_exact_classification():
    g = module("gates")
    for r in (static_fixture(), runtime_fixture()):
        assert getattr(g, "gate_" + r["phase"])(r) is r
        assert r["replacement"] is None and r["runtime_approved"] is False
    c = module("coverage")
    assert {
        s: len(c.optional_records(s))
        for s in ["old", "aligned", "aligned-all-family-including-api"]
    } == {"old": 67, "aligned": 50, "aligned-all-family-including-api": 50}


def test_consumer_origins_must_match_independent_fixed_jars():
    g = module("gates")
    known = {
        "nar_chain": [
            {
                "direct_jars": [
                    {"entry": name, "sha256": "hash-" + name}
                    for name in sorted(set(g.EXTERNAL_JARS.values()))
                ]
            }
        ]
    }
    pins = {"files": []}
    rows = g.expected_consumer_origins(known, pins)
    g.require_consumer_origins(known, pins, rows)
    for key, value in [
        ("class", "org.apache.nifi.processors.gcp.bigquery.PutBigQuery"),
        ("jar", "other.jar"),
        ("sha256", "computed-from-planted-tree"),
    ]:
        changed = copy.deepcopy(rows)
        changed[0][key] = value
        with pytest.raises(ValueError, match="independent"):
            g.require_consumer_origins(known, pins, changed)


def test_behavior_output_is_observed_and_duplicates_fail():
    a = module("aligned")
    assert a.observed_behaviors("behavior\tgax-metrics\tPASS\tactual-data\n") == {
        "gax-metrics": {"status": "PASS", "value": "actual-data"}
    }
    with pytest.raises(ValueError, match="ambiguous"):
        a.observed_behaviors("behavior\tx\tPASS\ta\nbehavior\tx\tPASS\ta\n")


def test_negative_api_mutation_removes_exact_class_in_private_jar(tmp_path):
    import zipfile

    a = module("aligned")
    file = tmp_path / "private-negative.jar"
    with zipfile.ZipFile(file, "w") as z:
        z.writestr(
            "io/opentelemetry/api/common/AttributeKey.class", b"explicit fixture"
        )
        z.writestr("untouched", b"original bytes")
    a.omit_attribute_key(file)
    with zipfile.ZipFile(file) as z:
        assert (
            z.namelist() == ["untouched"] and z.read("untouched") == b"original bytes"
        )
    with pytest.raises(ValueError, match="missing"):
        a.omit_attribute_key(file)
