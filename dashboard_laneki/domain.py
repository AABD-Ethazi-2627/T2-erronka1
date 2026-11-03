"""Shared prototype data and validation; no inference or industrial telemetry."""

import math
import re
from random import Random

REVIEW = {12, 15, 16, 20, 21, 27, 35, 38, 39, 40, 41, 43, 46, 47, 48}
STATES = {"Normala", "Berrikusteko", "Akatsa"}


def demo_machines():
    machines = []
    for n in range(1, 51):
        rng = Random(n * 123)
        machine = {
            "id": f"CNC-{n:03d}",
            "zenbakia": n,
            "tenperatura": round(rng.uniform(30, 39), 1),
            "rpm": rng.randint(1200, 1900),
            "torque": round(rng.uniform(22, 49), 1),
            "higadura": rng.randint(45, 240),
            "egoera": "Akatsa"
            if n == 4
            else "Berrikusteko"
            if n in REVIEW
            else "Normala",
        }
        if n == 4:
            machine.update(tenperatura=36.3, rpm=1380, torque=47.6, higadura=246)
        machines.append(machine)
    return machines


def validate_machines(data):
    """Reject malformed snapshots instead of replacing them with demo values."""
    if not isinstance(data, list) or len(data) > 50:
        raise ValueError("Expected 0 to 50 machines")
    cleaned, seen = [], set()
    for row in data:
        if not isinstance(row, dict) or not re.fullmatch(
            r"CNC-[0-9]{3}", str(row.get("id", ""))
        ):
            raise ValueError("Invalid machine identifier")
        n = int(row["id"][-3:])
        if (
            type(row.get("zenbakia")) is not int
            or row["zenbakia"] != n
            or row["id"] in seen
        ):
            raise ValueError("Duplicate or inconsistent machine identifier")
        if not isinstance(row.get("egoera"), str) or row["egoera"] not in STATES:
            raise ValueError("Unknown source state")
        result = dict(row)
        for key in (
            "tenperatura",
            "giro_tenperatura",
            "rpm",
            "torque",
            "higadura",
            "failure_score",
        ):
            value = row.get(key)
            if value is None:
                if key in row or key in {"tenperatura", "rpm", "torque", "higadura"}:
                    result[key] = None
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or (value < 0 and key not in {"tenperatura", "giro_tenperatura"})
                or (key == "failure_score" and value > 1)
            ):
                raise ValueError("Invalid or missing measurement")
            try:
                finite = math.isfinite(value)
            except OverflowError as exc:
                raise ValueError("Measurement exceeds supported numeric range") from exc
            if not finite:
                raise ValueError("Invalid or missing measurement")
            result[key] = value
        cleaned.append(result)
        seen.add(row["id"])
    return sorted(cleaned, key=lambda row: row["zenbakia"])


def load_machines(mode, fetch):
    if mode == "demo":
        return demo_machines(), "demo"
    if mode != "api":
        raise ValueError("LANEKI_MODE must be demo or api")
    try:
        return validate_machines(fetch("makinak")), "api"
    except ValueError:
        return [], "degraded"


def selected_machine(current, requested, machines, last_requested=None):
    """Apply a changed deep link once, then retain user selection on rerun."""
    ids = {row["id"] for row in machines}
    if not ids:
        return None
    if requested != last_requested and requested in ids:
        return requested
    return current if current in ids else machines[0]["id"]


def kpis(machines):
    temperatures = [
        m["tenperatura"] for m in machines if m.get("tenperatura") is not None
    ]
    return {
        "operatiboak": sum(m["egoera"] != "Akatsa" for m in machines),
        "guztira": len(machines),
        "akatsak": sum(m["egoera"] == "Akatsa" for m in machines),
        "gertakariak": "—",
        "osasuna": None,
        "tenperatura": round(sum(temperatures) / len(temperatures), 1)
        if temperatures
        else None,
        "motak": None,
    }


def gallery_machine(machine):
    """Decorate source state without altering its measurements or identity."""
    style = {
        "Akatsa": (
            "Larria",
            "larria",
            "#DE4651",
            "#FFF5F5",
            "#F87171",
            "#FEE2E2",
            "#DC2626",
            "⚠",
        ),
        "Berrikusteko": (
            "Ertaina",
            "ertaina",
            "#D97706",
            "#FFF7E6",
            "#FBBF24",
            "#FEF3C7",
            "#D97706",
            "⚠",
        ),
        "Normala": (
            "Normala",
            "normala",
            "#16A34A",
            "#F8FDFB",
            "#86EFAC",
            "#DCFCE7",
            "#16A34A",
            "✓",
        ),
    }[machine["egoera"]]
    result = dict(machine)
    result.update(
        zip(
            (
                "egoera_mota",
                "klasea",
                "kolorea",
                "bg_kolorea",
                "border_kolorea",
                "badge_bg",
                "badge_text",
                "abisu_ikonoa",
            ),
            style,
        )
    )
    result.update(
        abisua=machine["egoera"],
        ekintza="Uneko maila inferitua; ez da behatutako matxura.",
        kokapena=machine.get("kokapena") or "Ez dago daturik",
    )
    for field in (
        "azken_berrikuspena",
        "fabrikazio_urtea",
        "azken_matxura",
        "teknikariaren_bisita",
        "hurrengo_berrikuspena",
        "huts_egindako_osagaia",
        "geldialdiaren_iraupena",
    ):
        result[field] = machine.get(field) or "Ez dago daturik"
    return result
