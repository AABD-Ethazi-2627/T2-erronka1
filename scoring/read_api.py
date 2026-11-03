"""Opt-in current-state projections, UTC history and verified offline evaluation."""

import base64
import calendar
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response

from scoring.read_models import Evaluation, History, KPIs, Machine, Periods, ReadScope
from scoring.read_storage import compatible


def utc(value):
    if not isinstance(value, (str, datetime)):
        raise TypeError("UTC timestamp must be text or datetime")
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if result.tzinfo is None:
        raise ValueError("Timezone required")
    return result.astimezone(UTC)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def project(row):
    def sensor(key, offset=0):
        value = row.get(key)
        return None if value is None else value - offset

    if row["risk_alert"] != (row["failure_score"] >= row["risk_threshold"]):
        raise ValueError("Decision does not match persisted threshold")
    return Machine(
        machine_type=row.get("machine_type"),
        risk_threshold=row["risk_threshold"],
        decision_rule="risk_alert@"
        + row["policy"]
        + ": failure_score >= risk_threshold",
        event_key=hashlib.sha256(
            json.dumps(
                [
                    "prediction",
                    row["event_id"],
                    row["model_artifact_sha256"],
                    row["policy"],
                ]
            ).encode()
        ).hexdigest(),
        **{
            k: row[k]
            for k in (
                "event_id",
                "scored_at",
                "model_version",
                "model_artifact_sha256",
                "policy",
                "quality_flag",
                "source",
                "prediction_scope",
                "score_semantics",
                "temporal_prediction_enabled",
                "failure_score",
                "risk_alert",
                "alert_level",
            )
        },
        id=row["machine_id"],
        zenbakia=int(row["machine_id"].split("-")[-1]),
        timestamp=iso(utc(row["timestamp"])),
        tenperatura=sensor("process_temp_K", 273.15),
        giro_tenperatura=sensor("air_temp_K", 273.15),
        rpm=sensor("rpm"),
        torque=sensor("torque_Nm"),
        higadura=sensor("tool_wear_min"),
        egoera={"OK": "Normala", "AVISO": "Berrikusteko", "CRITICA": "Akatsa"}[
            row["alert_level"]
        ],
    )


COLUMNS = {
    "Ordua": "timestamp",
    "Prozesu-tenperatura (°C)": "tenperatura",
    "Bihurdura-momentua (Nm)": "torque",
    "Erremintaren higadura (min)": "higadura",
}


def columns(rows):
    return {label: [r[key] for r in rows] for label, key in COLUMNS.items()}


def window(as_of, desde=None, hasta=None):
    try:
        end = utc(hasta or as_of or datetime.now(UTC))
        end - timedelta(days=185)  # all read windows must be representable
        start = utc(desde) if desde else end - timedelta(days=1)
        if not timedelta(0) < end - start <= timedelta(days=185):
            raise ValueError()
        return start, end
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, "Invalid UTC interval; maximum 185 days") from None


def metadata(scope, start, end, rows):
    latest = max((utc(r["timestamp"]) for r in rows), default=None)
    return {
        "source": scope.model_dump(),
        "desde": iso(start),
        "hasta": iso(end),
        "as_of": iso(end),
        "interval": "[desde,hasta)",
        "count": len(rows),
        "coverage": {
            "observations": len(rows),
            "first": min((r["timestamp"] for r in rows), default=None),
            "last": iso(latest) if latest else None,
        },
        "latest_observation": iso(latest) if latest else None,
        "age_seconds": (end - latest).total_seconds() if latest else None,
    }


def load(reader, scope, start, end, *, all_history=False):
    if reader is None:
        raise HTTPException(503, "Read storage not configured")
    try:
        unique = {}
        for row in reader.rows(scope, start, end):
            if not compatible(row, scope):
                continue
            value = project(row).model_dump()
            value["scored_at"] = iso(utc(value["scored_at"]))
            # A duplicate identity with different content is incompatible, not replay.
            key = value["event_id"]
            if key in unique and unique[key] != value:
                raise ValueError("Conflicting event identity")
            unique[key] = value
        rows = sorted(
            unique.values(), key=lambda r: (utc(r["timestamp"]), r["event_id"])
        )
        return (
            rows
            if all_history
            else [r for r in rows if start <= utc(r["timestamp"]) < end]
        )
    except Exception:  # noqa: BLE001 -- storage adapters fail closed at HTTP boundary
        raise HTTPException(503, "Read storage unavailable or incompatible") from None


def evaluation(config, scope):
    if not config:
        return Evaluation(available=False, reason="not_configured")
    if scope.risk_threshold is None:
        return Evaluation(available=False, reason="read_threshold_not_pinned")
    try:
        raw = Path(config["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != config["sha256"]:
            raise ValueError()
        artifact = json.loads(raw)
        if not isinstance(artifact, dict):
            raise TypeError()
        model_path = Path(config["model_manifest_path"])
        model_raw = model_path.read_bytes()
        if hashlib.sha256(model_raw).hexdigest() != config["model_manifest_sha256"]:
            raise ValueError()
        model = json.loads(model_raw)
        if (
            model["files"]["rf.pkl"] != scope.model_artifact_sha256
            or hashlib.sha256((model_path.parent / "rf.pkl").read_bytes()).hexdigest()
            != scope.model_artifact_sha256
            or model["policy"] != scope.policy
            or model["risk_threshold"] != artifact["threshold"]
            or artifact["threshold"] != scope.risk_threshold
        ):
            raise ValueError()
        # An operator-pinned provenance manifest binds artifact + model + scope.
        proof_raw = Path(config["provenance_path"]).read_bytes()
        if hashlib.sha256(proof_raw).hexdigest() != config["provenance_sha256"]:
            raise ValueError()
        proof = json.loads(proof_raw)
        if (
            proof["evaluation_sha256"] != config["sha256"]
            or proof["scope"] != scope.model_dump()
            or proof["model_version"] != model["model_version"]
            or proof["provenance"] != artifact["provenance"]
        ):
            raise ValueError()
        p = artifact["provenance"]
        if not p["partition"] or not p["source_sha256"]:
            raise ValueError()
        o = artifact["overall"]
        tn, fp, fn, tp = (o[k] for k in ("tn", "fp", "fn", "tp"))
        if any(type(n) is not int or n < 0 for n in (tn, fp, fn, tp)):
            raise ValueError()
        n = tn + fp + fn + tp
        if any(
            o[k] != v
            for k, v in {
                "rows": n,
                "positives": tp + fn,
                "negatives": tn + fp,
                "alerts": tp + fp,
            }.items()
        ):
            raise ValueError()

        def ratio(a, b):
            return a / b if b else None

        return Evaluation(
            available=True,
            model_version=proof["model_version"],
            model_artifact_sha256=scope.model_artifact_sha256,
            partition=p["partition"],
            decision_rule="risk_alert@" + scope.policy + ": failure_score >= threshold",
            threshold=artifact["threshold"],
            labels=[0, 1],
            confusion_matrix=[[tn, fp], [fn, tp]],
            denominators={
                "rows": n,
                "positives": tp + fn,
                "negatives": tn + fp,
                "alerts": tp + fp,
            },
            metrics={
                "accuracy": ratio(tp + tn, n),
                "precision": ratio(tp, tp + fp),
                "recall": ratio(tp, tp + fn),
                "f1": ratio(2 * tp, 2 * tp + fp + fn),
            },
            provenance={
                **p,
                "evaluation_sha256": config["sha256"],
                "binding_sha256": config["provenance_sha256"],
            },
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return Evaluation(available=False, reason="unverified_or_incompatible")


def create_read_router(
    scope: ReadScope, current=None, archive=None, evaluation_config=None
):
    router = APIRouter(prefix="/api")

    def snapshot(as_of, *, with_count=False):
        _, end = window(as_of)
        start = end - timedelta(days=185)
        if current is not None and hasattr(current, "snapshot"):
            try:
                result = current.snapshot(
                    scope, start, end, include_event_count=with_count
                )
                rows = []
                for row in result["rows"]:
                    if (
                        not compatible(row, scope)
                        or not start <= utc(row["timestamp"]) < end
                    ):
                        raise ValueError("Unexpected snapshot scope")
                    value = project(row).model_dump()
                    value["scored_at"] = iso(utc(value["scored_at"]))
                    rows.append(value)
                event_count = result["event_count"]
                if with_count and (type(event_count) is not int or event_count < 0):
                    raise ValueError("Invalid exact event count")
            except Exception:  # noqa: BLE001 -- adapters fail closed at HTTP boundary
                raise HTTPException(
                    503, "Read storage unavailable or incompatible"
                ) from None
        else:
            rows = load(current, scope, start, end)
            event_count = sum(
                utc(r["timestamp"]) >= end - timedelta(days=1) for r in rows
            )
        latest = {}
        for row in sorted(
            rows, key=lambda r: (-utc(r["timestamp"]).timestamp(), r["event_id"])
        ):
            latest.setdefault(row["id"], row)
        if len(latest) > 50:
            raise HTTPException(503, "Configured scope exceeds 50 machines")
        return start, end, [latest[k] for k in sorted(latest)], event_count

    @router.get("/makinak", response_model=list[Machine])
    def machines(response: Response, as_of: str | None = None):
        start, end, latest, _count = snapshot(as_of)
        response.headers["X-CNC-As-Of"] = iso(end)
        response.headers["X-CNC-Lookback-Start"] = iso(start)
        return latest

    @router.get("/kpis", response_model=KPIs)
    def kpis(as_of: str | None = None):
        start, end, latest, event_count = snapshot(as_of, with_count=True)
        temps = [r["tenperatura"] for r in latest if r["tenperatura"] is not None]
        critical = sum(r["alert_level"] == "CRITICA" for r in latest)
        counts = {
            kind: sum(r["machine_type"] == kind for r in latest)
            for kind in ("H", "M", "L")
        }
        meta = metadata(scope, start, end, latest)
        meta.update(
            {
                "coverage_basis": "latest_per_machine",
                "event_window": {
                    "desde": iso(end - timedelta(days=1)),
                    "hasta": iso(end),
                },
                "denominators": {"machines": len(latest), "temperature": len(temps)},
                "definitions": {
                    "operatiboak": "inferred non-CRITICA; not physical operation",
                    "akatsak": "inferred CRITICA; not observed failures",
                    "motak": "machine_type H/M/L counts; absent type excluded",
                    "tenperatura": "mean process Celsius",
                    "gertakariak": "unique events in last 24h",
                    "osasuna": "unavailable",
                },
            }
        )
        return KPIs(
            guztira=len(latest),
            operatiboak=len(latest) - critical,
            akatsak=critical,
            motak=counts,
            tenperatura=sum(temps) / len(temps) if temps else None,
            gertakariak=event_count,
            metadata=meta,
        )

    def history_rows(id, start, end):
        import re

        if not re.fullmatch(r"CNC-[0-9]{3}", id):
            raise HTTPException(422, "Invalid machine ID")
        rows = load(archive, scope, start, end, all_history=True)
        machine = [r for r in rows if r["id"] == id]
        if not machine:
            raise HTTPException(404, "Machine absent from configured archive scope")
        return [r for r in machine if start <= utc(r["timestamp"]) < end]

    @router.get("/historikoa/{id}", response_model=History)
    def history(
        id: str,
        as_of: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        limit: int = Query(1000, ge=1, le=1000),
        cursor: str | None = Query(None, max_length=2048),
    ):
        state = None
        if cursor:
            try:
                state = json.loads(base64.urlsafe_b64decode(cursor))
                if (
                    not isinstance(state, dict)
                    or not isinstance(state.get("start"), str)
                    or not isinstance(state.get("end"), str)
                    or state["id"] != id
                    or state["scope"] != scope.model_dump()
                ):
                    raise ValueError()
                if not as_of and not hasta:
                    hasta = state["end"]
                if not desde:
                    desde = state["start"]
            except (ValueError, TypeError, KeyError):
                raise HTTPException(422, "Invalid cursor") from None
        start, end = window(as_of, desde, hasta)
        rows = history_rows(id, start, end)
        fingerprint = hashlib.sha256(
            json.dumps(rows, sort_keys=True).encode()
        ).hexdigest()
        offset = 0
        if state:
            if state.get("start") != iso(start) or state.get("end") != iso(end):
                raise HTTPException(422, "Cursor interval mismatch")
            if state.get("fingerprint") != fingerprint:
                raise HTTPException(409, "Archive snapshot changed; restart pagination")
            offset = state.get("offset")
            if type(offset) is not int or not 0 <= offset <= len(rows):
                raise HTTPException(422, "Invalid cursor offset")
        page = rows[offset : offset + limit]
        next_cursor = None
        if offset + limit < len(rows):
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "id": id,
                        "scope": scope.model_dump(),
                        "start": iso(start),
                        "end": iso(end),
                        "fingerprint": fingerprint,
                        "offset": offset + limit,
                    }
                ).encode()
            ).decode()
        meta = metadata(scope, start, end, rows)
        meta.update({"kind": "samples", "events": page, "page_count": len(page)})
        return History(datuak=columns(page), metadata=meta, next_cursor=next_cursor)

    @router.get("/historikoa/{id}/periodoak", response_model=Periods)
    def periods(id: str, as_of: str | None = None):
        _, end = window(as_of)
        month = end.year * 12 + end.month - 1 - 6
        six = end.replace(
            year=month // 12,
            month=month % 12 + 1,
            day=min(end.day, calendar.monthrange(month // 12, month % 12 + 1)[1]),
        )
        all_rows = history_rows(id, six, end)
        result = {}
        for name, start, monthly in [
            ("astea", end - timedelta(days=7), False),
            ("hilabetea", end - timedelta(days=30), False),
            ("sei_hilabete", six, True),
        ]:
            rows = [r for r in all_rows if start <= utc(r["timestamp"]) < end]
            buckets = {}
            for row in rows:
                stamp = utc(row["timestamp"]).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                if monthly:
                    stamp = stamp.replace(day=1)
                # Fixed 24h bins anchored at the cutoff for week/month: at most 7/30.
                else:
                    stamp = start + timedelta(days=(utc(row["timestamp"]) - start).days)
                buckets.setdefault(iso(stamp), []).append(row)
            means, details = [], []
            for stamp, group in sorted(buckets.items()):
                mean = {"timestamp": stamp}
                ns = {}
                for key in ("tenperatura", "torque", "higadura"):
                    values = [r[key] for r in group if r[key] is not None]
                    mean[key] = sum(values) / len(values) if values else None
                    ns[key] = len(values)
                means.append(mean)
                details.append(
                    {
                        "timestamp": stamp,
                        "count": len(group),
                        "n": ns,
                        "last": group[-1],
                    }
                )
            meta = metadata(scope, start, end, rows)
            meta.update(
                {
                    "kind": "mean",
                    "buckets": details,
                    "aggregation": "calendar_month_UTC"
                    if monthly
                    else "24h_from_start_UTC",
                }
            )
            result[name] = History(datuak=columns(means), metadata=meta)
        return Periods(**result)

    @router.get(
        "/model-evaluation", response_model=Evaluation, response_model_exclude_none=True
    )
    def model_evaluation():
        return evaluation(evaluation_config, scope)

    return router


def read_config_from_file(path):
    """Deployment opt-in. No storage access until a GET request."""
    from scoring.read_storage import ArchiveReader, ElasticsearchReader

    config = json.loads(Path(path).read_text())
    return {
        "scope": ReadScope.model_validate(config["scope"]),
        "current": ElasticsearchReader(
            config["elasticsearch"]["url"], config["elasticsearch"]["index"]
        ),
        "archive": ArchiveReader(config["archive_root"])
        if config.get("archive_root")
        else None,
        "evaluation_config": config.get("evaluation"),
    }
