"""Restore runner safety tests. No daemon, network, credentials or import."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "restore_e2e", Path(__file__).parents[1] / "deploy/cg14/scripts/run-restore-e2e.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


@pytest.fixture
def lab():
    flow, inv, _ = m.static()
    r = m.resources("restoretest001")
    logical = {
        p["identifier"]: p["instanceIdentifier"] for key in inv for p in inv[key]
    }
    ps, cs = {}, {}
    for key, entities in [("processors", ps), ("controllerServices", cs)]:
        for p in flow[key]:
            c = {
                "id": logical[p["identifier"]],
                "name": p["name"],
                "type": p["type"],
                "bundle": p["bundle"],
                "parentGroupId": m.TARGET,
                "state": "DISABLED",
                "validationStatus": "VALID",
            }
            props = copy.deepcopy(p["properties"])
            if key == "processors":
                if p["name"] == m.CONSUMER:
                    props["Kafka Connection Service"] = m.SERVICE
                c["config"] = {
                    "properties": props,
                    "retriedRelationships": [],
                    "autoTerminatedRelationships": p.get(
                        "autoTerminatedRelationships", []
                    ),
                }
            else:
                c["properties"] = props
            entities[c["id"]] = {"component": c, "revision": {"version": 0}}
    connections = []
    for c in flow["connections"]:
        component = copy.deepcopy(c)
        component["id"] = logical[c["identifier"]]
        for end in ("source", "destination"):
            component[end]["id"] = logical[c[end]["id"]]
        connections.append(
            {
                "component": component,
                "status": {"aggregateSnapshot": {"queuedCount": 0}},
            }
        )
    f = {"processors": list(ps.values()), "connections": connections}
    return flow, inv, r, ps, cs, f


def isolated(lab):
    flow, inv, r, ps, _cs, _f = lab
    for cid, patch in m.desired(flow, inv, r).items():
        m.properties(ps[cid]).update(patch)
    return lab


class FakeApi:
    def __init__(self, lab):
        self.flow_def, self.inv, self.r, self.ps, self.cs, self.f = lab
        self.calls = []

    def flow(self, gid):
        assert gid == m.TARGET
        return {"flow": self.f}

    def get(self, path):
        if path == "/process-groups/" + m.TARGET:
            return {"component": {"id": m.TARGET, "name": m.NAME}}
        if path.endswith("/controller-services"):
            return {"controllerServices": list(self.cs.values())}
        cid = path.split("/")[-1]
        return self.ps.get(cid) or self.cs[cid]

    def call(self, path, method="GET", payload=None):
        self.calls.append((path, method, payload))
        assert m.ORIGINAL not in path
        kind, cid = path.strip("/").split("/")[:2]
        e = self.ps[cid] if kind == "processors" else self.cs[cid]
        if path.endswith("/run-status"):
            e["component"]["state"] = payload["state"]
        else:
            m.properties(e).update(payload["component"]["config"]["properties"])
        return e


def runner(lab, tmp_path):
    flow, inv, r, ps, _cs, _f = lab
    s = {
        "resources": r,
        "original_sha256": "original",
        "prior_properties": {
            cid: copy.deepcopy(m.properties(e)) for cid, e in ps.items()
        },
        "pending": None,
    }
    return m.Runner(FakeApi(lab), flow, inv, r, tmp_path / "manifest.json", s)


def test_plan_is_offline_and_creates_nothing(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline plan attempted I/O mutation/network/auth")

    for name in ("Api", "docker", "lock", "save"):
        monkeypatch.setattr(m, name, forbidden)
    assert m.main(["--plan", "--run-id", "restoretest001"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["network_used"] is False and plan["mutations"] is False
    assert plan["functional"] == "NOT_TESTED"


@pytest.mark.parametrize("run", ["../escape", "CG13", "short", "x" * 33, "a;b0123456"])
def test_resource_names_constrained(run):
    with pytest.raises(m.GuardError):
        m.resources(run)


def test_snapshot_exact_destination_and_runtime_ids(lab):
    _, inv, _, ps, cs, _ = lab
    observed, services, _ = m.snapshot(FakeApi(lab), inv)
    assert observed == ps and services == cs
    assert m.ORIGINAL not in observed and m.SERVICE in services


@pytest.mark.parametrize(
    "change",
    [
        "group-name",
        "group-id",
        "processor-id",
        "parent",
        "bundle",
        "external",
        "connection",
    ],
)
def test_identity_drift_aborts(lab, change):
    _, inv, _, _ps, _cs, f = lab
    api = FakeApi(lab)
    real_get = api.get
    if change in ("group-name", "group-id"):

        def get(path):
            e = real_get(path)
            if path == "/process-groups/" + m.TARGET:
                e["component"]["name" if change == "group-name" else "id"] = "original"
            return e

        api.get = get
    elif change == "processor-id":
        f["processors"][0]["component"]["id"] = m.ORIGINAL
    elif change == "parent":
        f["processors"][0]["component"]["parentGroupId"] = m.ORIGINAL
    elif change == "bundle":
        f["processors"][0]["component"]["bundle"] = {"version": "wrong"}
    elif change == "external":
        f["remoteProcessGroups"] = [{}]
    else:
        f["connections"][0]["component"]["source"]["id"] = m.ORIGINAL
    with pytest.raises(m.GuardError):
        m.snapshot(api, inv)
    assert not api.calls


def test_exact_isolation_passes(lab):
    flow, inv, r, ps, cs, f = isolated(lab)
    m.configuration_guard(ps, cs, f, flow, inv, r, isolated=True)


@pytest.mark.parametrize(
    "name,prop",
    [
        (m.CONSUMER, "Topics"),
        (m.CONSUMER, "Group ID"),
        (m.DLQ, "Directory"),
        (m.HTTP, "HTTP URL"),
    ],
)
def test_shared_resources_rejected(lab, name, prop):
    flow, inv, r, ps, cs, f = isolated(lab)
    original = next(
        p["properties"][prop] for p in flow["processors"] if p["name"] == name
    )
    e = next(e for e in ps.values() if e["component"]["name"] == name)
    m.properties(e)[prop] = original
    with pytest.raises(m.GuardError, match="Aislamiento"):
        m.configuration_guard(ps, cs, f, flow, inv, r, isolated=True)


@pytest.mark.parametrize(
    "prop,value",
    [("Script File", "/tmp/evil.groovy"), ("Additional Classpath", "https://external")],
)
def test_unexpected_external_effect_aborts(lab, prop, value):
    flow, inv, r, ps, cs, f = isolated(lab)
    e = next(
        e for e in ps.values() if e["component"]["type"].endswith("ExecuteGroovyScript")
    )
    m.properties(e)[prop] = value
    with pytest.raises(m.GuardError, match="Propiedad inesperada"):
        m.configuration_guard(ps, cs, f, flow, inv, r, isolated=True)


def test_shared_stateful_mock_ownership_rejected(lab):
    r = lab[2]
    obj = {
        "Name": "/" + r["mock"],
        "State": {"Running": True},
        "Config": {"Labels": {"cg14.restore.run": "another"}},
    }
    with pytest.raises(m.GuardError, match="compartido"):
        m.mock_guard(obj, r)


def test_running_or_unknown_queues_abort(lab):
    _, _, _, ps, cs, f = lab
    e = next(iter(ps.values()))
    e["component"]["state"] = "RUNNING"
    with pytest.raises(m.GuardError, match="running"):
        m.stopped(ps, cs, f)
    e["component"]["state"] = "DISABLED"
    del f["connections"][0]["status"]
    with pytest.raises(m.GuardError, match="Colas"):
        m.stopped(ps, cs, f)


def test_apply_isolation_failure_has_no_mutations(lab, tmp_path, monkeypatch):
    rr = runner(lab, tmp_path)

    def fail(*args, **kwargs):
        raise m.GuardError("isolation failed")

    monkeypatch.setattr(rr, "guard", fail)
    monkeypatch.setattr(m, "docker", lambda *a, **kw: pytest.fail("Docker mutation"))
    with pytest.raises(m.GuardError):
        rr.apply()
    assert not rr.api.calls and not rr.path.exists()


def test_patch_idempotent_and_original_protected(lab, tmp_path):
    rr = runner(lab, tmp_path)
    patches = m.desired(rr.flow, rr.inv, rr.r)
    cid, patch = next(iter(patches.items()))
    rr.patch(cid, patch)
    assert len(rr.api.calls) == 1
    rr.patch(cid, patch)
    assert len(rr.api.calls) == 1
    with pytest.raises(m.GuardError, match="no autorizado"):
        rr.patch(m.ORIGINAL, patch)
    with pytest.raises(m.GuardError, match="no autorizado"):
        rr.state(m.ORIGINAL, "STOPPED")


def test_interrupted_mutation_has_durable_intent(lab, tmp_path):
    rr = runner(lab, tmp_path)

    def interrupted():
        assert json.loads(rr.path.read_text())["pending"] == "produce-once"
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        rr.action("produce-once", interrupted)
    assert json.loads(rr.path.read_text())["pending"] == "produce-once"


@pytest.mark.parametrize("producer", ["OUTCOME_UNCERTAIN", "RESPONDED"])
def test_interrupted_test_is_never_replayed(lab, tmp_path, monkeypatch, producer):
    rr = runner(lab, tmp_path)
    rr.s.update(prepared=True, test_intent=True, producer=producer)
    monkeypatch.setattr(rr, "guard", lambda **kw: pytest.fail("replayed"))
    with pytest.raises(m.GuardError, match="no se repetirá"):
        rr.test()
    assert not rr.api.calls


def test_stop_only_owned_enablements_and_idempotent(lab, tmp_path):
    rr = runner(lab, tmp_path)
    cid = next(iter(rr.api.ps))
    rr.api.ps[cid]["component"]["state"] = "RUNNING"
    rr.api.cs[m.SERVICE]["component"]["state"] = "ENABLED"
    rr.s.update(activated=[cid], service_intent=True)
    rr.stop()
    calls = len(rr.api.calls)
    rr.stop()
    assert len(rr.api.calls) == calls
    assert {path.split("/")[2] for path, _, _ in rr.api.calls} == {cid, m.SERVICE}
    assert rr.api.ps[cid]["component"]["state"] == "DISABLED"


def test_rollback_only_target_patches_and_no_activation(lab, tmp_path):
    rr = runner(lab, tmp_path)
    for cid, patch in m.desired(rr.flow, rr.inv, rr.r).items():
        rr.patch(cid, patch)
    rr.api.calls.clear()
    rr.rollback()
    assert rr.s["rolled_back"] and not rr.s["prepared"]
    assert all(
        m.ORIGINAL not in path and not path.endswith("run-status")
        for path, _, _ in rr.api.calls
    )
    for cid, patch in m.desired(rr.flow, rr.inv, rr.r).items():
        assert all(
            m.properties(rr.api.ps[cid])[k] == rr.s["prior_properties"][cid][k]
            for k in patch
        )


def test_secret_property_never_saved(lab, tmp_path):
    rr = runner(lab, tmp_path)
    e = next(iter(rr.api.ps.values()))
    e["component"]["config"]["descriptors"] = {"secret": {"sensitive": True}}
    m.properties(e)["secret"] = "TEST_PASSWORD_MUST_NOT_LEAK"
    with pytest.raises(m.GuardError, match="sensible"):
        m.snapshot(rr.api, rr.inv)
    assert not rr.path.exists()


def test_producer_offset_parser_exclusive_topic():
    assert m.offset_row("g original 0 5 5 0\ng isolated 0 5 5 0", "isolated") == (
        5,
        5,
        0,
    )
    assert m.offset_row("g original 0 5 5 0", "isolated") is None


def test_functional_evidence_cannot_pass_empty_or_just_event_id(lab):
    e = {
        "provenance": [],
        "original_unchanged": True,
        "queue": 0,
        "service_state": "DISABLED",
        "processors": {},
        "offsets": "g topic 0 5 5 0",
        "topic": "topic",
        "dlq": [],
    }
    assert not m.functional_pass(e, lab[1])


@pytest.mark.parametrize("interrupt_after_create", [False, True])
def test_apply_idempotent_and_reconciles_interrupted_topic(
    lab, tmp_path, monkeypatch, interrupt_after_create
):
    rr = runner(lab, tmp_path)
    rr.r["host_dlq"] = str(tmp_path / "dlq")
    topics, containers, writes = set(), set(), []
    interrupted = False
    monkeypatch.setattr(m.auth, "original_fingerprint", lambda api: "original")
    monkeypatch.setattr(m, "compare_original", lambda *args: None)
    monkeypatch.setattr(m, "runtime_guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "mock_guard", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "mock_ready", lambda *args: None)
    monkeypatch.setattr(m, "inspect", lambda *args: {})

    def kafka(tool, *args, **kwargs):
        nonlocal interrupted
        if "--list" in args:
            return "\n".join(topics) if tool == "topics" else ""
        if "--describe" in args:
            return "PartitionCount: 1 ReplicationFactor: 1 retention.ms=86400000"
        assert "--create" in args
        writes.append("topic")
        topics.add(rr.r["topic"])
        if interrupt_after_create and not interrupted:
            interrupted = True
            raise KeyboardInterrupt()
        return ""

    def docker(*args, **kwargs):
        if args[0] == "ps":
            return "\n".join(containers)
        if args[0] == "run":
            containers.add(rr.r["mock"])
            writes.append("mock")
            return "container-id"
        assert args[0] == "exec" and "mkdir" in args[-3]
        return ""

    monkeypatch.setattr(m, "kafka", kafka)
    monkeypatch.setattr(m, "docker", docker)
    if interrupt_after_create:
        with pytest.raises(KeyboardInterrupt):
            rr.apply()
        assert json.loads(rr.path.read_text())["pending"] == "create-topic"
        rr.s = json.loads(rr.path.read_text())  # fresh process resumes durable state
    rr.apply()
    calls = len(rr.api.calls)
    rr.apply()
    assert len(rr.api.calls) == calls
    assert writes == ["topic", "mock"]
    assert rr.s["prepared"] and rr.s["pending"] is None


def test_original_resource_collision_rejected(lab, monkeypatch):
    _flow, _inv, r, ps, _cs, f = lab
    original = copy.deepcopy(f)
    ce = next(e for e in original["processors"] if e["component"]["name"] == m.CONSUMER)
    m.properties(ce)["Topics"] = "another, " + r["topic"]
    monkeypatch.setattr(m.auth, "components", lambda api, gid: (original, []))
    with pytest.raises(m.GuardError, match="Topic compartido"):
        m.compare_original(object(), ps, r)


def test_verify_without_manifest_does_not_create_or_authenticate(monkeypatch):
    monkeypatch.setattr(m, "lock", lambda: pytest.fail("Created resource for verify"))
    monkeypatch.setattr(
        m, "Api", lambda *a: pytest.fail("Authenticated without manifest")
    )
    with pytest.raises(m.GuardError, match="Sin manifiesto"):
        m.main(["--verify", "--run-id", "absenttest123"])


def test_http_error_does_not_expose_credentials(monkeypatch, capsys):
    # Client only forwards an allowlist diagnostic, never a server body/exception repr.
    import subprocess

    script = Path(m.__file__)
    source = script.read_text()
    assert (
        "verify=False" not in source and "ssl._create_unverified_context" not in source
    )
    assert "read_env" not in source and ".env" not in source.replace(".env access", "")
    assert "/upload" not in source
    monkeypatch.setattr(
        m.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            [], 1, b"", b"PASSWORD=TEST_PASSWORD_MUST_NOT_LEAK"
        ),
    )
    with pytest.raises(m.GuardError) as exc:
        m.docker("inspect", "cnc-cg14-nifi")
    assert "TEST_PASSWORD" not in str(exc.value)
    assert "TEST_PASSWORD" not in capsys.readouterr().out


@pytest.fixture
def functional_evidence(lab):
    from cg14_validation.reconciliation import content_hash, dlq_summary
    from cg14_validation.validator import parse_csv_event

    inv, r = lab[1:3]
    names = {p["name"]: p["instanceIdentifier"] for p in inv["processors"]}
    wire, expected = m.fixture_manifest(r, "2026-10-21T10:00:00+00:00")
    e = {
        "expected_deliveries": expected,
        "provenance_complete": True,
        "transitions": [
            {"component_id": m.SERVICE, "state": "ENABLED", "validation": "VALID"}
        ],
        "provenance": [],
        "original_unchanged": True,
        "queue": 0,
        "service_state": "DISABLED",
        "processors": {cid: {"state": "DISABLED"} for cid in names.values()},
        "offsets": "group " + r["topic"] + " 0 5 5 0",
        "topic": r["topic"],
        "dlq": [],
    }

    e["transitions"].extend(
        {
            "component_id": p["instanceIdentifier"],
            "state": "RUNNING",
            "validation": "VALID",
        }
        for p in inv["processors"]
        if not p["type"].endswith("GenerateFlowFile")
        and p["name"] != "Unused Groovy API probe — no input"
    )

    def add(d, name, event_type, relation=None, **attrs):
        a = {
            "kafka.topic": d["topic"],
            "kafka.partition": d["partition"],
            "kafka.offset": d["offset"],
            "cg14.event.id": d["event_id"] or "",
            "cg14.mock.scenario": "2xx"
            if d["scenario"] == "invalid"
            else d["scenario"],
        }
        a.update(attrs)
        e["provenance"].append(
            {
                "event_id": len(e["provenance"]),
                "component_id": names[name],
                "type": event_type,
                "relationship": relation,
                "attributes": a,
            }
        )

    for d, line in zip(expected, wire, strict=True):
        scenario = d["scenario"]
        raw = line.split("|", 1)[1].rstrip("\n")
        if scenario == "invalid":
            add(
                d,
                "RouteOnAttribute — accepted or rejected",
                "ROUTE",
                "rejected",
                **{"cg14.valid": "false", "cg14.code": "MALFORMED_CSV"},
            )
        else:
            attempts = range(3) if scenario in ("5xx", "timeout") else range(1)
            relation = {
                "2xx": "Original",
                "422": "No Retry",
                "5xx": "Retry",
                "timeout": "Failure",
            }[scenario]
            for attempt in attempts:
                a = {"cg14.http.attempt": str(attempt)}
                if scenario == "timeout":
                    a["invokehttp.java.exception.class"] = (
                        "java.net.SocketTimeoutException"
                    )
                else:
                    a["invokehttp.status.code"] = {
                        "2xx": "200",
                        "422": "422",
                        "5xx": "503",
                    }[scenario]
                add(d, m.HTTP, "ROUTE", relation, **a)
                if scenario in ("5xx", "timeout"):
                    add(
                        d,
                        "UpdateAttribute — count mock retries",
                        "ATTRIBUTES_MODIFIED",
                        **{"cg14.http.attempt": str(attempt + 1)},
                    )
            if scenario in ("5xx", "timeout"):
                add(
                    d,
                    "RouteOnAttribute — max two retries",
                    "ROUTE",
                    "exhausted",
                    **{"cg14.http.attempt": "3"},
                )
        if scenario == "2xx":
            add(d, "Local HTTP original sink — attributes only", "DROP")
            continue
        source = {**d["source"], "raw_record": raw}
        if scenario == "invalid":
            body = {
                "valid": False,
                "event_id": None,
                "code": "MALFORMED_CSV",
                "source": source,
                "original": raw,
                "reject_time": "2026-10-21T10:00:00Z",
            }
        else:
            body = parse_csv_event(
                raw,
                source_uri=source["uri"],
                record_ref=source["record_ref"],
                source_kind=source["kind"],
            ).normalized_event
            assert content_hash(body) == d["body_sha256"]
        name = "delivery-" + d["offset"] + ".json"
        e["dlq"].append(dlq_summary(name, json.dumps(body).encode()))
        add(d, m.DLQ, "SEND", filename=name)
    return e


def test_functional_checks_accept_complete_evidence(functional_evidence, lab):
    assert m.functional_pass(functional_evidence, lab[1])


@pytest.mark.parametrize("complete", [True, False])
def test_collector_reconciles_detailed_provenance_and_real_dlq_files(
    functional_evidence, lab, tmp_path, monkeypatch, complete
):
    from cg14_validation.validator import parse_csv_event

    rr = runner(lab, tmp_path)
    directory = tmp_path / "dlq"
    directory.mkdir()
    rr.r["host_dlq"] = str(directory)
    expected = functional_evidence["expected_deliveries"]
    wire, _ = m.fixture_manifest(rr.r, "2026-10-21T10:00:00+00:00")
    for d, line in zip(expected[1:], wire[1:], strict=True):
        raw = line.split("|", 1)[1].rstrip("\n")
        source = {**d["source"], "raw_record": raw}
        if d["scenario"] == "invalid":
            body = {
                "valid": False,
                "event_id": None,
                "code": "MALFORMED_CSV",
                "source": source,
            }
        else:
            body = parse_csv_event(
                raw,
                source_uri=source["uri"],
                record_ref=source["record_ref"],
                source_kind=source["kind"],
            ).normalized_event
        (directory / ("delivery-" + d["offset"] + ".json")).write_text(json.dumps(body))
    rr.s.update(
        expected_deliveries=expected,
        test_intent=True,
        transitions=functional_evidence["transitions"],
        provenance_query="query",
    )
    monkeypatch.setattr(m, "compare_original", lambda *args: None)
    monkeypatch.setattr(m, "runtime_guard", lambda *args: None)
    monkeypatch.setattr(m.auth, "original_fingerprint", lambda api: "original")
    monkeypatch.setattr(m, "read_offsets", lambda group: functional_evidence["offsets"])
    original_get = rr.api.get
    rows = functional_evidence["provenance"]
    reads = []

    def get(path):
        reads.append(path)
        if "/status" in path:
            return {"processGroupStatus": {"aggregateSnapshot": {"flowFilesQueued": 0}}}
        if path == "/provenance/query":
            return {
                "provenance": {
                    "finished": True,
                    "results": {
                        "totalCount": len(rows) if complete else len(rows) + 1,
                        "provenanceEvents": [{"id": str(i)} for i in range(len(rows))],
                    },
                }
            }
        if path.startswith("/provenance-events/"):
            r = rows[int(path.rsplit("/", 1)[1])]
            return {
                "provenanceEvent": {
                    "eventId": r["event_id"],
                    "componentId": r["component_id"],
                    "eventType": r["type"],
                    "relationship": r["relationship"],
                    "attributes": [
                        {"name": k, "value": v} for k, v in r["attributes"].items()
                    ],
                }
            }
        return original_get(path)

    monkeypatch.setattr(rr.api, "get", get)
    e = rr.collect()
    assert e["provenance_complete"] is complete
    assert len(e["dlq"]) == 4 and len(e["provenance"]) == len(rows)
    assert rr.s["functional"] == ("VERIFIED" if complete else "NOT_VERIFIED")
    assert len(
        [path for path in reads if path.startswith("/provenance-events/")]
    ) == len(rows)
    assert not rr.api.calls


@pytest.mark.parametrize(
    "failure",
    [
        "original",
        "queue",
        "service",
        "processor",
        "offset",
        "http200",
        "invalid",
        "timeout",
        "unlimited-retry",
        "dlq",
        "event-collision",
        "empty-processors",
        "missing-processor",
        "empty-dlq",
        "foreign-dlq",
        "duplicate-dlq",
        "wrong-code",
        "missing-terminal",
        "missing-retry",
        "wrong-body",
        "wrong-raw",
        "missing-manifest",
        "missing-delivery",
        "incomplete-provenance",
        "foreign-delivery",
        "missing-count",
        "wrong-retry-order",
        "missing-success-terminal",
        "missing-active-transition",
        "unknown-original",
        "terminal-before-route",
    ],
)
def test_functional_checks_require_every_gate(functional_evidence, lab, failure):
    e = functional_evidence
    http = [
        r
        for r in e["provenance"]
        if r["component_id"]
        == next(
            p["instanceIdentifier"] for p in lab[1]["processors"] if p["name"] == m.HTTP
        )
    ]
    if failure == "original":
        e["original_unchanged"] = False
    elif failure == "queue":
        e["queue"] = 1
    elif failure == "service":
        e["service_state"] = "ENABLED"
    elif failure == "processor":
        next(iter(e["processors"].values()))["state"] = "RUNNING"
    elif failure == "offset":
        e["offsets"] = "group " + e["topic"] + " 0 4 5 1"
    elif failure == "http200":
        del http[0]["attributes"]["invokehttp.status.code"]
    elif failure == "invalid":
        e["provenance"] = [
            r for r in e["provenance"] if r["attributes"]["kafka.offset"] != "4"
        ]
    elif failure == "timeout":
        del http[-1]["attributes"]["invokehttp.java.exception.class"]
    elif failure == "unlimited-retry":
        http[2]["attributes"]["cg14.http.attempt"] = "4"
    elif failure == "dlq":
        e["dlq"].pop()
    elif failure == "event-collision":
        http[-1]["attributes"]["cg14.event.id"] = e["expected_deliveries"][2][
            "event_id"
        ]
    elif failure == "empty-processors":
        e["processors"] = {}
    elif failure == "missing-processor":
        e["processors"].pop(next(iter(e["processors"])))
    elif failure == "empty-dlq":
        e["dlq"] = [{}, {}, {}, {}]
    elif failure == "foreign-dlq":
        e["dlq"][0]["source"]["record_ref"] = "other/0/1"
    elif failure == "duplicate-dlq":
        e["dlq"][1] = copy.deepcopy(e["dlq"][0])
    elif failure == "wrong-code":
        http[0]["attributes"]["invokehttp.status.code"] = "422"
        http[1]["attributes"]["invokehttp.status.code"] = "200"
    elif failure == "missing-terminal":
        e["provenance"] = [r for r in e["provenance"] if r["type"] != "SEND"]
    elif failure == "missing-retry":
        e["provenance"].remove(http[3])
    elif failure == "wrong-body":
        e["dlq"][0]["body_sha256"] = "0" * 64
    elif failure == "wrong-raw":
        e["dlq"][0]["raw_sha256"] = "0" * 64
    elif failure == "missing-manifest":
        e.pop("expected_deliveries")
    elif failure == "missing-delivery":
        e["expected_deliveries"].pop()
    elif failure == "incomplete-provenance":
        e["provenance_complete"] = False
    elif failure == "foreign-delivery":
        r = copy.deepcopy(http[0])
        r["attributes"]["kafka.offset"] = "99"
        e["provenance"].append(r)
    elif failure == "missing-count":
        e["provenance"] = [
            r for r in e["provenance"] if r["type"] != "ATTRIBUTES_MODIFIED"
        ]
    elif failure == "wrong-retry-order":
        http[2]["event_id"], http[3]["event_id"] = (
            http[3]["event_id"],
            http[2]["event_id"],
        )
    elif failure == "missing-success-terminal":
        e["provenance"] = [r for r in e["provenance"] if r["type"] != "DROP"]
    elif failure == "missing-active-transition":
        e["transitions"] = e["transitions"][:1]
    elif failure == "unknown-original":
        e["original_unchanged"] = "NOT_TESTED"
    elif failure == "terminal-before-route":
        send = next(r for r in e["provenance"] if r["type"] == "SEND")
        unrelated_send = copy.deepcopy(send)
        unrelated_send["event_id"] = 100000
        unrelated_send["attributes"]["filename"] = "other-file.json"
        e["provenance"].append(unrelated_send)
        send["event_id"] = -1
    assert not m.functional_pass(e, lab[1])


def test_verify_does_not_describe_uncreated_consumer_group(monkeypatch):
    calls = []

    def kafka(tool, *args):
        calls.append((tool, args))
        assert args == ("--list",)
        return "some-other-group\n"

    monkeypatch.setattr(m, "kafka", kafka)
    assert m.read_offsets("cg14-restore-group-absent0001") == ""
    assert len(calls) == 1


@pytest.mark.parametrize("status", [201, 400])
def test_runner_auth_normalizes_only_username_and_preserves_form_contract(
    monkeypatch, capsys, status
):
    import io
    import ssl
    import urllib.error
    import urllib.parse

    username = "synthetic-usuario+ñ"
    password = "  synthetic-password+&=ñ\t "
    token = "synthetic-private-token"
    private_body = "synthetic-private-error-body"
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return token.encode()

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert request.get_method() == "POST"
            assert request.full_url == m.auth.API_BASE + "/access/token"
            assert (
                request.get_header("Content-type")
                == "application/x-www-form-urlencoded"
            )
            assert request.get_header("Accept") == "text/plain"
            assert request.get_header("Authorization") is None
            assert timeout == 60
            assert urllib.parse.parse_qs(request.data.decode("utf-8")) == {
                "username": [username],
                "password": [password],
            }
            if status == 400:
                raise urllib.error.HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    {},
                    io.BytesIO(private_body.encode()),
                )
            response = Response()
            response.status = status
            return response

    assert m.Api.login is m.auth.Api.login
    assert m.Api.request is m.auth.Api.request
    api = m.Api(ssl.create_default_context())
    api.opener = Opener()
    monkeypatch.setattr("builtins.input", lambda prompt: " \t" + username + "  ")
    monkeypatch.setattr(m.auth.getpass, "getpass", lambda prompt: password)
    monkeypatch.setattr(
        api, "call", lambda *a, **kw: pytest.fail("JSON client used for login")
    )
    if status == 400:
        with pytest.raises(urllib.error.HTTPError) as error:
            api.login()
        assert error.value.code == 400
        assert api.token is None
    else:
        api.login()
        assert api.token == token
    assert len(requests) == 1  # No retry of a rejected token request.
    output = capsys.readouterr()
    assert f"HTTP {status}" in output.err
    for secret in (username, password, token, private_body):
        assert secret not in output.out + output.err


def test_runner_blank_username_aborts_before_password_or_request(monkeypatch, capsys):
    import ssl

    api = m.Api(ssl.create_default_context())
    monkeypatch.setattr("builtins.input", lambda prompt: " \t  ")
    monkeypatch.setattr(
        m.auth.getpass, "getpass", lambda prompt: pytest.fail("Password requested")
    )
    monkeypatch.setattr(
        api, "request", lambda *a, **kw: pytest.fail("Authentication POST sent")
    )
    with pytest.raises(m.GuardError, match="vacío tras normalizar"):
        api.login()
    assert api.token is None
    assert not capsys.readouterr().out


@pytest.fixture
def resumable(lab, tmp_path, monkeypatch):
    rr = runner(isolated(lab), tmp_path)
    rr.s.update(
        prepared=True, resources_intent=True, stopped=True, functional="NOT_TESTED"
    )
    obj = {
        "Id": "a" * 64,
        "Name": "/" + rr.r["mock"],
        "State": {
            "Status": "exited",
            "Running": False,
            "Paused": False,
            "Restarting": False,
        },
        "Config": {
            "Labels": {"cg14.restore.run": rr.r["run_id"]},
            "Image": m.MOCK_IMAGE,
            "Cmd": ["python", "-u", "/app/mock_predict.py"],
            "User": "65534:65534",
            "Entrypoint": None,
        },
        "NetworkSettings": {"Networks": {m.NETWORK: {}}, "Ports": {}},
        "HostConfig": {
            "ReadonlyRootfs": True,
            "Privileged": False,
            "NetworkMode": m.NETWORK,
            "PortBindings": {},
            "RestartPolicy": {"Name": "no"},
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
        },
        "Mounts": [
            {
                "Type": "bind",
                "Source": str(m.DEPLOY / "scripts/mock_predict.py"),
                "Destination": "/app/mock_predict.py",
                "RW": False,
            }
        ],
    }
    calls = []
    monkeypatch.setattr(m, "inspect", lambda name: copy.deepcopy(obj))
    monkeypatch.setattr(m, "compare_original", lambda *a: None)
    monkeypatch.setattr(m, "runtime_guard", lambda *a, **kw: None)
    monkeypatch.setattr(m.auth, "original_fingerprint", lambda api: "original")
    monkeypatch.setattr(rr, "topic_guard", lambda: None)
    monkeypatch.setattr(rr, "unused_data", lambda: None)
    monkeypatch.setattr(m, "mock_ready", lambda r: calls.append(("healthz", r["mock"])))

    def docker(*args, **kwargs):
        # Any create/run/restart or access to the original mock fails the test.
        assert args == ("start", obj["Id"])
        saved = json.loads(rr.path.read_text())
        assert saved["pending"] == "resume-owned-mock"
        assert saved["mock_resume"]["start_attempted"] is True
        assert saved["stopped"] is False
        calls.append(args)
        obj["State"].update(Status="running", Running=True)
        return obj["Id"]

    monkeypatch.setattr(m, "docker", docker)
    return rr, obj, calls


def test_resume_stopped_owned_mock_persists_and_reuses_id(resumable):
    rr, obj, calls = resumable
    rr.resume()
    assert calls == [("start", obj["Id"]), ("healthz", rr.r["mock"])]
    s = json.loads(rr.path.read_text())
    assert s["mock_resume"]["status"] == "STARTED"
    assert s["mock_resume"]["phase"] == "HEALTHY"
    assert s["pending"] is None and s["stopped"] is False and s["prepared"] is True
    assert s["functional"] == "NOT_TESTED" and not s.get("test_intent")
    assert not rr.api.calls
    rr.resume()
    assert len([c for c in calls if c[0] == "start"]) == 1
    assert rr.s["mock_resume"]["status"] == "ALREADY_RUNNING"


def test_resume_already_running_does_not_restart(resumable):
    rr, obj, calls = resumable
    obj["State"].update(Status="running", Running=True)
    rr.resume()
    assert calls == [("healthz", rr.r["mock"])]
    assert rr.s["mock_resume"]["status"] == "ALREADY_RUNNING"
    assert not rr.s["mock_resume"].get("start_attempted")


@pytest.mark.parametrize(
    "mismatch",
    [
        "name",
        "label",
        "image",
        "network",
        "ports",
        "portbindings",
        "mount",
        "mount-rw",
        "cmd",
        "user",
        "rootfs",
        "entrypoint",
        "privileged",
        "restartpolicy",
        "paused",
        "restarting",
        "dead",
        "replaced",
        "original",
    ],
)
def test_resume_property_or_state_mismatch_never_starts(resumable, mismatch):
    rr, obj, calls = resumable
    if mismatch == "name":
        obj["Name"] = "/cnc-cg14-mock-predict"
    elif mismatch == "label":
        obj["Config"]["Labels"]["cg14.restore.run"] = "another-run"
    elif mismatch == "image":
        obj["Config"]["Image"] = "python:latest"
    elif mismatch == "network":
        obj["NetworkSettings"]["Networks"] = {"bridge": {}}
    elif mismatch == "ports":
        obj["NetworkSettings"]["Ports"] = {
            "8080/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]
        }
    elif mismatch == "portbindings":
        obj["HostConfig"]["PortBindings"] = {"8080/tcp": [{"HostPort": "8080"}]}
    elif mismatch == "mount":
        obj["Mounts"][0]["Source"] = "/another/project/mock.py"
    elif mismatch == "mount-rw":
        obj["Mounts"][0]["RW"] = True
    elif mismatch == "cmd":
        obj["Config"]["Cmd"] = ["python", "/app/other.py"]
    elif mismatch == "user":
        obj["Config"]["User"] = "0"
    elif mismatch == "rootfs":
        obj["HostConfig"]["ReadonlyRootfs"] = False
    elif mismatch == "entrypoint":
        obj["Config"]["Entrypoint"] = ["/bin/sh"]
    elif mismatch == "privileged":
        obj["HostConfig"]["Privileged"] = True
    elif mismatch == "restartpolicy":
        obj["HostConfig"]["RestartPolicy"]["Name"] = "always"
    elif mismatch == "paused":
        obj["State"]["Paused"] = True
    elif mismatch == "restarting":
        obj["State"].update(Status="restarting", Restarting=True)
    elif mismatch == "dead":
        obj["State"]["Status"] = "dead"
    elif mismatch == "replaced":
        rr.s["mock_resume"] = {"container_id": "b" * 64}
    else:
        rr.r["mock"] = "cnc-cg14-mock-predict"
    with pytest.raises(m.GuardError):
        rr.resume()
    assert calls == [] and not rr.api.calls
    assert rr.s["mock_resume"]["status"] == "BLOCKED"
    assert rr.s["pending"] is None


def test_resume_missing_mock_never_creates_replacement(resumable, monkeypatch):
    rr, _obj, calls = resumable

    def missing(*args):
        raise m.GuardError("Missing owned mock")

    monkeypatch.setattr(m, "inspect", missing)
    with pytest.raises(m.GuardError):
        rr.resume()
    assert calls == [] and rr.s["mock_resume"]["status"] == "BLOCKED"


def test_resume_failed_health_preserves_intent_then_reconciles_reads_only(
    resumable, monkeypatch
):
    rr, obj, calls = resumable

    def unhealthy(*args):
        raise m.GuardError("healthz failed")

    monkeypatch.setattr(m, "mock_ready", unhealthy)
    with pytest.raises(m.GuardError):
        rr.resume()
    s = json.loads(rr.path.read_text())
    assert (
        s["mock_resume"]["status"] == "FAILED" and s["pending"] == "resume-owned-mock"
    )
    assert len(calls) == 1 and obj["State"]["Running"]
    rr.s = s
    monkeypatch.setattr(m, "mock_ready", lambda *a: None)
    rr.resume()
    assert len(calls) == 1 and rr.s["pending"] is None
    assert rr.s["mock_resume"]["status"] == "STARTED"


@pytest.mark.parametrize("start_completed", [False, True])
def test_interruption_never_repeats_uncertain_start(
    resumable, monkeypatch, start_completed
):
    rr, obj, calls = resumable

    def interrupted(*args, **kwargs):
        calls.append(args)
        if start_completed:
            obj["State"].update(Status="running", Running=True)
        raise KeyboardInterrupt()

    monkeypatch.setattr(m, "docker", interrupted)
    with pytest.raises(KeyboardInterrupt):
        rr.resume()
    rr.s = json.loads(rr.path.read_text())
    assert rr.s["pending"] == "resume-owned-mock"
    assert rr.s["mock_resume"]["status"] == "FAILED"
    if start_completed:
        rr.resume()  # Only inspections and health check, never a second start.
        assert rr.s["pending"] is None
    else:
        with pytest.raises(m.GuardError, match="no repetir"):
            rr.resume()
        assert rr.s["pending"] == "resume-owned-mock"
    assert len([c for c in calls if c[0] == "start"]) == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("pending", "produce-once"),
        ("prepared", False),
        ("resources_intent", False),
        ("test_intent", True),
        ("producer", "OUTCOME_UNCERTAIN"),
        ("activated", ["owned"]),
        ("service_intent", True),
        ("functional", "VERIFIED"),
    ],
)
def test_resume_and_test_reject_unsafe_manifest_before_activation(
    resumable, key, value
):
    rr, _obj, calls = resumable
    rr.s[key] = value
    with pytest.raises(m.GuardError):
        rr.resume()
    with pytest.raises(m.GuardError):
        rr.test()
    assert not calls and not rr.api.calls


def test_resume_and_test_preserve_isolation_barrier(resumable):
    rr, _obj, calls = resumable
    ce = next(e for e in rr.api.ps.values() if e["component"]["name"] == m.CONSUMER)
    m.properties(ce)["Topics"] = "cg13-real"
    with pytest.raises(m.GuardError, match="Propiedad inesperada"):
        rr.resume()
    # Test's real guard uses the same config check; no processor may be enabled.
    with pytest.raises(m.GuardError, match="Propiedad inesperada"):
        rr.test()
    assert not calls and not rr.api.calls


def test_unused_data_rejects_used_group_before_dlq_access(resumable, monkeypatch):
    rr, _obj, calls = resumable
    monkeypatch.setattr(m, "kafka", lambda *a: rr.r["consumer_group"] + "\n")
    with pytest.raises(m.GuardError, match="Consumer group"):
        m.Runner.unused_data(rr)
    assert not calls


def test_explicit_stop_then_resume_can_start_same_container_again(
    resumable, monkeypatch
):
    rr, obj, calls = resumable
    original_docker = m.docker

    def docker(*args, **kwargs):
        if args[0] == "ps":
            return rr.r["mock"] + "\n"
        if args[0] == "stop":
            assert args[1] == rr.r["mock"]
            calls.append(args)
            obj["State"].update(Status="exited", Running=False)
            return args[1]
        return original_docker(*args, **kwargs)

    monkeypatch.setattr(m, "docker", docker)
    rr.resume()
    rr.stop()
    assert rr.s["stopped"] and rr.s["mock_resume"]["stop_confirmed"]
    rr.resume()
    assert (
        rr.s["mock_resume"]["status"] == "STARTED"
        and rr.s["mock_resume"]["start_attempts"] == 2
    )
    assert rr.s["pending"] is None and not rr.s["stopped"]
    assert len([c for c in calls if c[0] == "start"]) == 2
    assert not rr.api.calls


def test_failed_health_on_running_mock_is_failed_without_start(resumable, monkeypatch):
    rr, obj, calls = resumable
    obj["State"].update(Status="running", Running=True)
    monkeypatch.setattr(
        m, "mock_ready", lambda *a: (_ for _ in ()).throw(m.GuardError("unhealthy"))
    )
    with pytest.raises(m.GuardError):
        rr.resume()
    assert rr.s["mock_resume"]["status"] == "FAILED"
    assert not calls and rr.s["pending"] is None


def test_real_health_probe_has_bounded_read_only_failure(monkeypatch):
    calls = []
    ticks = iter([0, 16])
    monkeypatch.setattr(m.time, "monotonic", lambda: next(ticks))

    def docker(*args, **kwargs):
        calls.append(args)
        assert args[:4] == ("exec", "owned-mock", "python", "-c")
        assert (
            "/healthz" in args[4] and "json.load" in args[4] and "SystemExit" in args[4]
        )
        raise m.GuardError("failed HTTP probe")

    monkeypatch.setattr(m, "docker", docker)
    with pytest.raises(m.GuardError, match="healthz"):
        m.mock_ready({"mock": "owned-mock"})
    assert len(calls) == 1


def test_unused_data_checks_exclusive_dlq_and_nifi_write_access(
    lab, tmp_path, monkeypatch
):
    rr = runner(lab, tmp_path)
    rr.r["host_dlq"] = str(tmp_path / "dlq")
    monkeypatch.setattr(m, "kafka", lambda *a: "")
    calls = []
    monkeypatch.setattr(m, "docker", lambda *a: calls.append(a))
    with pytest.raises(m.GuardError, match="DLQ"):
        rr.unused_data()
    directory = Path(rr.r["host_dlq"])
    directory.mkdir()
    rr.unused_data()
    assert len(calls) == 1 and calls[0][:2] == ("exec", "cnc-cg14-nifi")
    assert calls[0][-1] == rr.r["dlq"] and "test -w" in calls[0][-3]
    (directory / "existing.json").write_text("{}")
    with pytest.raises(m.GuardError, match="DLQ"):
        rr.unused_data()
    assert len(calls) == 1


def test_verify_records_running_health_and_never_starts_mock(
    resumable, tmp_path, monkeypatch
):
    rr, obj, calls = resumable
    rr.r["host_dlq"] = str(tmp_path / "dlq")
    Path(rr.r["host_dlq"]).mkdir()
    get = rr.api.get
    monkeypatch.setattr(
        rr.api,
        "get",
        lambda path: (
            {"processGroupStatus": {"aggregateSnapshot": {"flowFilesQueued": 0}}}
            if "/status" in path
            else get(path)
        ),
    )
    monkeypatch.setattr(m, "read_offsets", lambda group: "")
    e = rr.collect()
    assert e["mock"]["healthz"] == "NOT_CHECKED_STOPPED" and calls == []
    obj["State"].update(Status="running", Running=True)
    e = rr.collect()
    assert e["mock"]["healthz"] == "READY" and e["mock"]["container_id"] == obj["Id"]
    assert calls == [("healthz", rr.r["mock"])] and not rr.api.calls


@pytest.mark.parametrize("failure", ["stopped", "unhealthy"])
def test_test_requires_running_healthy_owned_mock_before_intent(
    resumable, monkeypatch, failure
):
    rr, obj, calls = resumable
    if failure == "unhealthy":
        obj["State"].update(Status="running", Running=True)

        def unhealthy(*a):
            raise m.GuardError("unhealthy")

        monkeypatch.setattr(m, "mock_ready", unhealthy)

    def runtime(r, mock_required=False):
        if mock_required:
            m.mock_guard(obj, r)
            m.mock_ready(r)

    monkeypatch.setattr(m, "runtime_guard", runtime)
    with pytest.raises(m.GuardError):
        rr.test()
    assert not rr.s.get("test_intent") and not rr.api.calls and not calls
