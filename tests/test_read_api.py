"""Fixture-only read contract acceptance; no live ES/SMB claims."""

import hashlib
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from scoring.read_api import evaluation
from scoring.read_models import ReadScope
from scoring.read_storage import ArchiveReader, ElasticsearchReader
from scoring.score_api import create_app
from scripts.archive_consumer import consume

BASE = json.loads(Path("contracts/examples/valid/prediction.json").read_text())
BASE.update(json.loads(Path("contracts/examples/valid/telemetry.json").read_text()))
BASE.update(
    alert_level="OK",
    source={"kind": "lab_fixture", "uri": "fixture://read-test", "record_ref": "row-1"},
)
BASE["model_artifact_sha256"] = hashlib.sha256(b"fixture-model").hexdigest()
SCOPE = ReadScope(
    source_uri=BASE["source"]["uri"],
    model_artifact_sha256=BASE["model_artifact_sha256"],
    policy=BASE["policy"],
    risk_threshold=BASE["risk_threshold"],
)
END = "2026-10-16T00:00:00Z"


class Reader:
    def __init__(self, rows):
        self.data = rows

    def rows(self, *args):
        return self.data


def client(rows=(), archive=None):
    return TestClient(
        create_app(
            read_config={"scope": SCOPE, "current": Reader(rows), "archive": archive}
        )
    )


def get(c, path, **params):
    return c.get("/api/" + path, params={"as_of": END, **params})


def archive_at(tmp_path, rows):
    messages = [
        (str(i), "prediction", json.dumps(row).encode()) for i, row in enumerate(rows)
    ]
    consume(tmp_path, messages, lambda: None)
    return ArchiveReader(tmp_path)


def test_opt_in():
    assert TestClient(create_app()).get("/api/makinak").status_code == 404


def test_empty_and_no_health():
    c = client()
    assert get(c, "makinak").json() == []
    result = get(c, "kpis").json()
    assert result["guztira"] == result["gertakariak"] == 0
    assert result["osasuna"] is result["tenperatura"] is None


def test_sentinel_partial_replay_and_units():
    row = {**BASE, "process_temp_K": 309.8, "torque_Nm": 42.5, "tool_wear_min": 123}
    c = client([row, row])
    result = get(c, "makinak").json()[0]
    assert result["tenperatura"] == pytest.approx(36.65)
    assert result["torque"] == 42.5 and result["higadura"] == 123
    assert result["failure_score"] == row["failure_score"]
    assert result["source"]["kind"] == "lab_fixture"
    assert get(c, "kpis").json()["gertakariak"] == 1
    row["process_temp_K"] = None
    assert get(client([row]), "makinak").json()[0]["tenperatura"] is None


def test_ties_scope_and_exclusive_end():
    lower = {**BASE, "event_id": "0" * 64}
    other = {**BASE, "policy": "f2", "event_id": "1" * 64}
    boundary = {**BASE, "timestamp": END, "event_id": "2" * 64}
    data = get(client([BASE, lower, other, boundary]), "makinak").json()
    assert len(data) == 1 and data[0]["event_id"] == "0" * 64


@pytest.mark.parametrize(
    "change",
    [
        {"failure_score": float("nan")},
        {"alert_level": "unknown"},
        {"timestamp": "nope"},
    ],
)
def test_invalid_storage_is_degraded(change):
    assert get(client([{**BASE, **change}]), "makinak").status_code == 503


def test_duplicate_conflict_and_capacity():
    assert get(client([BASE, {**BASE, "rpm": 1}]), "makinak").status_code == 503
    rows = [
        {**BASE, "machine_id": f"CNC-{i:03}", "event_id": f"{i:064x}"}
        for i in range(51)
    ]
    assert get(client(rows), "makinak").status_code == 503


@pytest.mark.parametrize("as_of", ["bad", "2026-10-16T00:00:00"])
def test_invalid_cutoff(as_of):
    assert get(client(), "makinak", as_of=as_of).status_code == 422


def test_archive_roundtrip_replay_orphan_and_immutable(tmp_path):
    reader = archive_at(tmp_path, [BASE, BASE])
    orphan = tmp_path / "prediction" / "orphan.parquet"
    orphan.write_bytes(b"not a parquet")
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    c = client(archive=reader)
    result = get(c, "historikoa/CNC-049").json()
    assert result["metadata"]["count"] == 1
    assert result["metadata"]["events"][0]["event_id"] == BASE["event_id"]
    assert result["datuak"]["Bihurdura-momentua (Nm)"] == [BASE["torque_Nm"]]
    assert set(get(c, "historikoa/CNC-049/periodoak").json()) == {
        "astea",
        "hilabetea",
        "sei_hilabete",
    }
    assert before == {
        str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("fault", ["object", "event", "delivery", "path"])
def test_archive_corrupt_receipts(tmp_path, fault):
    reader = archive_at(tmp_path, [BASE])
    if fault == "object":
        next(tmp_path.rglob("*.parquet")).write_bytes(b"corrupt")
    else:
        with sqlite3.connect(tmp_path / "ledger.sqlite") as db:
            if fault == "event":
                db.execute("UPDATE events SET hash='wrong'")
            elif fault == "delivery":
                db.execute("UPDATE deliveries SET outcome='rejected'")
            else:
                db.execute(
                    "UPDATE objects SET path='../escape' WHERE path LIKE 'prediction/%'"
                )
    assert get(client(archive=reader), "historikoa/CNC-049").status_code == 503


def test_history_pagination_and_entire_period(tmp_path):
    rows = [{**BASE, "event_id": f"{i:064x}", "torque_Nm": i} for i in range(1002)]
    c = client(archive=archive_at(tmp_path, rows))
    page = get(c, "historikoa/CNC-049", limit=1000).json()
    assert page["metadata"]["count"] == 1002 and page["next_cursor"]
    next_page = get(c, "historikoa/CNC-049", cursor=page["next_cursor"]).json()
    assert len(next_page["datuak"]["Ordua"]) == 2 and next_page["next_cursor"] is None
    period = get(c, "historikoa/CNC-049/periodoak").json()["astea"]
    assert period["metadata"]["count"] == 1002
    assert period["datuak"]["Bihurdura-momentua (Nm)"] == [500.5]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 1001},
        {"desde": END},
        {"desde": "2020-01-01T00:00:00Z"},
        {"cursor": "bad"},
    ],
)
def test_history_invalid_params(tmp_path, params):
    c = client(archive=archive_at(tmp_path, [BASE]))
    assert get(c, "historikoa/CNC-049", **params).status_code == 422


def test_history_empty_unknown_missing_and_utc(tmp_path):
    row = {**BASE, "timestamp": "2026-10-25T01:30:00.123456Z"}
    c = client(archive=archive_at(tmp_path, [row]))
    assert get(c, "historikoa/CNC-049").json()["datuak"]["Ordua"] == []
    assert get(c, "historikoa/CNC-050").status_code == 404
    assert get(c, "historikoa/bad").status_code == 422
    assert (
        get(
            client(archive=ArchiveReader(tmp_path / "absent")), "historikoa/CNC-049"
        ).status_code
        == 503
    )
    result = get(
        c,
        "historikoa/CNC-049",
        desde="2026-10-25T02:00:00+02:00",
        hasta="2026-10-25T03:00:00+01:00",
    ).json()
    assert result["datuak"]["Ordua"] == [row["timestamp"]]


def test_es_pit_scope_and_failure():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("_pit"):
            return httpx.Response(200, json={"id": "pit"})
        return httpx.Response(
            200, json={"hits": {"hits": []}, "_shards": {"failed": 0}}
        )

    es = ElasticsearchReader(
        "http://local",
        "fixture",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    from scoring.read_api import utc

    assert es.rows(SCOPE, utc("2026-01-01T00:00:00Z"), utc(END)) == []
    filters = json.loads(requests[1].content)["query"]["bool"]["filter"]
    assert filters[0]["term"]["source.uri"] == SCOPE.source_uri
    assert requests[-1].method == "DELETE"

    class Down:
        def rows(self, *args):
            raise OSError()

    c = TestClient(create_app(read_config={"scope": SCOPE, "current": Down()}))
    assert get(c, "makinak").status_code == 503


def evaluation_config(tmp_path):
    artifact = {
        "threshold": SCOPE.risk_threshold,
        "overall": {
            "tn": 8,
            "fp": 2,
            "fn": 1,
            "tp": 3,
            "rows": 14,
            "positives": 4,
            "negatives": 10,
            "alerts": 5,
        },
        "provenance": {"source_sha256": "a" * 64, "partition": "synthetic_validation"},
    }
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps(artifact))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    proof = {
        "evaluation_sha256": sha,
        "scope": SCOPE.model_dump(),
        "model_version": "fixture",
        "provenance": artifact["provenance"],
    }
    binding = tmp_path / "binding.json"
    binding.write_text(json.dumps(proof))
    (tmp_path / "rf.pkl").write_bytes(b"fixture-model")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "model_version": "fixture",
                "risk_threshold": SCOPE.risk_threshold,
                "policy": SCOPE.policy,
                "files": {"rf.pkl": SCOPE.model_artifact_sha256},
            }
        )
    )
    return {
        "model_manifest_path": str(manifest),
        "model_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "path": str(path),
        "sha256": sha,
        "provenance_path": str(binding),
        "provenance_sha256": hashlib.sha256(binding.read_bytes()).hexdigest(),
    }


def test_evaluation_verified_absent_incompatible_and_nan(tmp_path):
    config = evaluation_config(tmp_path)
    result = evaluation(config, SCOPE)
    assert result.available and result.confusion_matrix == [[8, 2], [1, 3]]
    assert result.metrics["recall"] == 0.75
    assert not evaluation(None, SCOPE).available
    assert not evaluation(config, SCOPE.model_copy(update={"policy": "f2"})).available
    Path(config["path"]).write_text("NaN")
    assert not evaluation(config, SCOPE).available


@pytest.mark.parametrize(
    "fault", ["matrix", "negative", "zero", "nan", "model", "provenance", "missing"]
)
def test_evaluation_edge_cases(tmp_path, fault):
    config = evaluation_config(tmp_path)
    path = Path(config["path"])
    obj = json.loads(path.read_text())
    if fault == "matrix":
        obj["overall"]["rows"] = 15
    elif fault == "negative":
        obj["overall"]["tp"] = -1
    elif fault == "zero":
        obj["overall"] = dict.fromkeys(obj["overall"], 0)
    elif fault == "nan":
        obj["threshold"] = float("nan")
    elif fault == "model":
        (tmp_path / "rf.pkl").write_bytes(b"different")
    elif fault == "provenance":
        obj["provenance"]["partition"] = ""
    elif fault == "missing":
        obj.pop("overall")
    path.write_text(json.dumps(obj))
    config["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    binding = Path(config["provenance_path"])
    proof = json.loads(binding.read_text())
    proof["evaluation_sha256"] = config["sha256"]
    proof["provenance"] = obj["provenance"]
    binding.write_text(json.dumps(proof))
    config["provenance_sha256"] = hashlib.sha256(binding.read_bytes()).hexdigest()
    result = evaluation(config, SCOPE)
    assert result.available == (fault == "zero")
    if fault == "zero":
        assert all(v is None for v in result.metrics.values())


def test_live_writer_uncommitted_object_invisible(tmp_path):
    import threading

    reader = archive_at(tmp_path, [BASE])
    entered, release = threading.Event(), threading.Event()
    errors = []

    def checkpoint(stage):
        if stage == "before_commit":
            entered.set()
            assert release.wait(10)

    def writer():
        try:
            consume(
                tmp_path,
                [
                    (
                        "new",
                        "prediction",
                        json.dumps({**BASE, "event_id": "f" * 64}).encode(),
                    )
                ],
                lambda: None,
                checkpoint,
            )
        except Exception as exc:  # noqa: BLE001 -- transfer writer thread failures to assertion
            errors.append(exc)

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        assert entered.wait(10)
        response = get(client(archive=reader), "historikoa/CNC-049")
        assert response.status_code == 200
        assert response.json()["metadata"]["count"] == 1
    finally:
        release.set()
        thread.join(10)
    assert not errors
    assert (
        get(client(archive=reader), "historikoa/CNC-049").json()["metadata"]["count"]
        == 2
    )


def test_archive_outside_window_corruption_fails_closed_and_capacity(tmp_path):
    reader = archive_at(tmp_path, [BASE])
    assert (
        get(
            client(archive=ArchiveReader(tmp_path, max_bytes=1)), "historikoa/CNC-049"
        ).status_code
        == 503
    )
    next(tmp_path.rglob("*.parquet")).write_bytes(b"corrupt")
    assert (
        get(
            client(archive=reader), "historikoa/CNC-049", as_of="2026-11-01T00:00:00Z"
        ).status_code
        == 503
    )


def test_period_calendar_clamp_null_and_exact_edges():
    rows = [
        {**BASE, "timestamp": "2026-08-31T12:00:00Z", "torque_Nm": None},
        {**BASE, "timestamp": "2026-09-01T00:00:00Z", "event_id": "a" * 64},
        {**BASE, "timestamp": "2027-02-28T12:00:00Z", "event_id": "b" * 64},
    ]
    c = client(archive=Reader(rows))
    result = get(
        c, "historikoa/CNC-049/periodoak", as_of="2027-02-28T12:00:00Z"
    ).json()["sei_hilabete"]
    assert result["metadata"]["desde"] == "2026-08-28T12:00:00Z"
    assert result["metadata"]["count"] == 2
    assert result["datuak"]["Bihurdura-momentua (Nm)"][0] is None


def test_get_never_infers_or_creates_response_ledger(tmp_path):
    app = create_app(
        ledger_path=tmp_path / "responses.sqlite3",
        read_config={"scope": SCOPE, "current": Reader([BASE])},
    )

    class Forbidden:
        def predict_proba(self, *args):
            raise AssertionError("GET inferred")

    app.state.models = {"rf.pkl": Forbidden()}
    c = TestClient(app)
    assert get(c, "makinak").status_code == 200
    assert get(c, "kpis").status_code == 200
    assert not (tmp_path / "responses.sqlite3").exists()


def test_mixed_ledger_telemetry_is_not_a_model_scoped_point(tmp_path):
    telemetry = json.loads(Path("contracts/examples/valid/telemetry.json").read_text())
    telemetry["source"] = BASE["source"]
    reader = archive_at(tmp_path, [BASE, {**BASE, "policy": "f2"}])
    consume(
        tmp_path,
        [
            ("telemetry", "telemetry", json.dumps(telemetry).encode()),
            ("rejected", "telemetry", b"invalid"),
        ],
        lambda: None,
    )
    result = get(client(archive=reader), "historikoa/CNC-049").json()
    assert result["metadata"]["count"] == 1
    assert result["metadata"]["events"][0]["policy"] == SCOPE.policy
    assert result["metadata"]["events"][0]["event_key"] == next(
        p.stem
        for p in (tmp_path / "prediction").rglob("*.parquet")
        if p.stem == result["metadata"]["events"][0]["event_key"]
    )


def test_api_snapshot_is_accepted_by_dashboard_domain():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "dashboard_domain_interop", Path("dashboard_laneki/domain.py")
    )
    domain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(domain)
    response = get(client([BASE]), "makinak")
    rows = domain.validate_machines(response.json())
    assert rows[0]["zenbakia"] == 49
    assert f"{rows[0]['zenbakia']:03}" == "049"
    assert rows[0]["event_id"] == BASE["event_id"]


def test_archive_releases_sqlite_snapshot_before_object_validation(
    tmp_path, monkeypatch
):
    from scoring import read_storage

    reader = archive_at(tmp_path, [BASE])
    original = read_storage.digest
    written = False

    def digest_with_writer(raw):
        nonlocal written
        if not written:
            written = True
            consume(
                tmp_path,
                [
                    (
                        "concurrent",
                        "prediction",
                        json.dumps({**BASE, "event_id": "c" * 64}).encode(),
                    )
                ],
                lambda: None,
            )
        return original(raw)

    monkeypatch.setattr(read_storage, "digest", digest_with_writer)
    result = get(client(archive=reader), "historikoa/CNC-049")
    assert result.status_code == 200
    assert result.json()["metadata"]["count"] == 1
    assert (
        get(client(archive=reader), "historikoa/CNC-049").json()["metadata"]["count"]
        == 2
    )


@pytest.mark.parametrize(
    "endpoint", ["makinak", "kpis", "historikoa/CNC-049/periodoak"]
)
def test_early_cutoff_is_bounded_422(endpoint):
    assert (
        get(client([BASE]), endpoint, as_of="0001-01-02T00:00:00Z").status_code == 422
    )


def test_cursor_nonstring_bounds_is_422():
    import base64

    cursor = base64.urlsafe_b64encode(
        json.dumps(
            {"id": "CNC-049", "scope": SCOPE.model_dump(), "start": {}, "end": END}
        ).encode()
    ).decode()
    assert get(client(), "historikoa/CNC-049", cursor=cursor).status_code == 422


def test_periods_share_one_committed_archive_snapshot():
    from unittest.mock import Mock

    reader = Reader([BASE])
    reader.rows = Mock(wraps=reader.rows)
    assert (
        get(client(archive=reader), "historikoa/CNC-049/periodoak").status_code == 200
    )
    assert reader.rows.call_count == 1


def test_server_scope_binds_prediction_and_evaluation_threshold(tmp_path):
    config = evaluation_config(tmp_path)
    assert evaluation(config, SCOPE).available
    assert not evaluation(
        config, SCOPE.model_copy(update={"risk_threshold": None})
    ).available
    assert not evaluation(
        config, SCOPE.model_copy(update={"risk_threshold": 0.9})
    ).available
    changed = {**BASE, "risk_threshold": 0.9}
    with client([BASE, {**changed, "event_id": "f" * 64}]) as api:
        rows = api.get("/api/makinak", params={"as_of": END}).json()
        assert len(rows) == 1 and rows[0]["risk_threshold"] == SCOPE.risk_threshold
    from scoring.read_api import utc

    filters = ElasticsearchReader._filters(SCOPE, utc(END), utc(END))
    assert {"term": {"risk_threshold": SCOPE.risk_threshold}} in filters
