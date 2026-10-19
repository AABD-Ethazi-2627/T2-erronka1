"""Deterministic lab review scheduling. Deadlines are policy, never failure ETA."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import isfinite
from zoneinfo import ZoneInfo


def instant(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Timezone-aware datetime required")
    return value.astimezone(UTC)


def business_start(value, zone):
    value = value.astimezone(zone)
    while value.weekday() >= 5 or value.hour >= 17:
        value = (value + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
    if value.hour < 9:
        value = value.replace(hour=9, minute=0, second=0, microsecond=0)
    return value


def business_add(value, minutes, zone):
    value = business_start(value, zone)
    while minutes:
        end = value.replace(hour=17, minute=0, second=0, microsecond=0)
        available = (end - value).total_seconds() / 60
        step = min(minutes, available)
        value += timedelta(minutes=step)
        minutes -= step
        if minutes:
            value = business_start(value, zone)
    return value


def build_plan(
    events,
    as_of,
    *,
    timezone_name="Europe/Madrid",
    capacity=1,
    slot_minutes=30,
    critical_minutes=30,
    warning_business_minutes=480,
    anomaly_business_minutes=960,
    stale_minutes=15,
):
    now = instant(as_of)
    zone = ZoneInfo(timezone_name)
    for number in (
        capacity,
        slot_minutes,
        critical_minutes,
        warning_business_minutes,
        anomaly_business_minutes,
        stale_minutes,
    ):
        if type(number) is not int or number <= 0:
            raise ValueError("Policy values must be positive integers")
    if slot_minutes > 480:
        raise ValueError("Review slot must fit a business day")
    unique, groups = {}, {}
    for original in events:
        e = deepcopy(original)
        for field in ("event_id", "machine_id", "source_kind"):
            if not isinstance(e.get(field), str) or not e[field].strip():
                raise ValueError(f"Missing {field}")
        if e.get("machine_type") not in ("H", "M", "L"):
            raise ValueError("machine_type must be H/M/L")
        score = e.get("failure_score")
        if (
            isinstance(score, bool)
            or not isinstance(score, (float, int))
            or not isfinite(score)
            or not 0 <= score <= 1
        ):
            raise ValueError("Invalid failure score")
        if type(e.get("anomaly_alert", False)) is not bool:
            raise ValueError("Invalid anomaly alert")
        when = instant(e["timestamp"])
        if when > now:
            raise ValueError("Future input relative to as_of")
        if e["event_id"] in unique:
            if e != unique[e["event_id"]]:
                raise ValueError("Conflicting event_id")
            continue
        unique[e["event_id"]] = e
        groups.setdefault(e["machine_id"], []).append((e, when))
    tasks = []
    for machine, records in groups.items():
        score = max(e["failure_score"] for e, _ in records)
        anomaly = any(e.get("anomaly_alert", False) for e, _ in records)
        if score < 0.15 and not anomaly:
            continue
        priority = "P1" if score >= 0.7 else "P2" if score >= 0.15 else "P3"
        due = (
            now + timedelta(minutes=critical_minutes)
            if priority == "P1"
            else business_add(
                now,
                warning_business_minutes
                if priority == "P2"
                else anomaly_business_minutes,
                zone,
            )
        )
        warnings = [
            "UNVERIFIED_ASSET_IDENTITY",
            "NO_FAILURE_ETA",
            "SCORE_NOT_CALIBRATED",
        ]
        if any(
            (now - when).total_seconds() > stale_minutes * 60 for _, when in records
        ):
            warnings.append("STALE_EVIDENCE")
        if any(e["source_kind"] == "smb_csv" for e, _ in records):
            warnings.append("SMB_REPLAY_NOT_PHYSICAL_HISTORY")
        if len({e["machine_type"] for e, _ in records}) > 1:
            warnings.append("CONFLICTING_TYPE")
        task = {
            "task_id": sha256(("review:" + machine).encode()).hexdigest()[:20],
            "machine_id": machine,
            "machine_types": sorted({e["machine_type"] for e, _ in records}),
            "priority": priority,
            "action": "REVIEW_DATA_AND_RISK",
            "status": "PROPOSED",
            "failure_score": score,
            "anomaly_alert": anomaly,
            "eta_minutes": None,
            "temporal_criticality": "UNKNOWN",
            "requires_human_review": True,
            "review_due_at": due.astimezone(UTC).isoformat(),
            "evidence_event_ids": sorted(e["event_id"] for e, _ in records),
            "independent_failure_confirmations": None,
            "warnings": warnings,
            "audit": [],
        }
        by_time = {}
        for e, when in records:
            signature = (
                e["failure_score"],
                e["machine_type"],
                e.get("anomaly_alert", False),
            )
            by_time.setdefault(when, set()).add(signature)
        if any(len(states) > 1 for states in by_time.values()):
            task["warnings"].append("CONFLICTING_SAME_TIME_PREDICTIONS")
        tasks.append(task)
    tasks.sort(key=lambda t: (t["priority"], t["review_due_at"], t["machine_id"]))
    resources = [business_start(now, zone)] * capacity
    for task in tasks:
        resource = min(range(capacity), key=lambda i: (resources[i], i))
        start = business_start(resources[resource], zone)
        if start + timedelta(minutes=slot_minutes) > start.replace(
            hour=17, minute=0, second=0, microsecond=0
        ):
            start = business_start(
                start.replace(hour=17, minute=0, second=0, microsecond=0), zone
            )
        end = start + timedelta(minutes=slot_minutes)
        resources[resource] = end
        task.update(
            resource=f"reviewer-{resource + 1}",
            proposed_start=start.astimezone(UTC).isoformat(),
            proposed_end=end.astimezone(UTC).isoformat(),
            review_deadline_missed=instant(end) > instant(task["review_due_at"]),
        )
    return {
        "schema_version": 1,
        "mode": "LAB_REVIEW_PROPOSAL",
        "as_of": now.isoformat(),
        "timezone": timezone_name,
        "tasks": tasks,
        "notice": "Review deadlines are configurable policy, not predicted failure times. Human review pending.",
    }


def review_task(task, action, actor, reason, at):
    when = instant(at)
    if (
        not isinstance(actor, str)
        or not actor.strip()
        or not isinstance(reason, str)
        or not reason.strip()
    ):
        raise ValueError("Actor and reason required")
    allowed = {
        ("PROPOSED", "approve"): "APPROVED",
        ("PROPOSED", "reject"): "REJECTED",
        ("APPROVED", "complete"): "COMPLETED",
        ("APPROVED", "reject"): "REJECTED",
    }
    state = allowed.get((task["status"], action))
    if state is None:
        raise ValueError("Invalid review transition")
    if task["audit"] and when < instant(task["audit"][-1]["at"]):
        raise ValueError("Audit time cannot go backwards")
    result = deepcopy(task)
    result["status"] = state
    result["audit"].append(
        {"action": action, "actor": actor, "reason": reason, "at": when.isoformat()}
    )
    return result
