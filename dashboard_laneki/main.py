from datetime import UTC, datetime
from random import Random

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Laneki IoT API", version="2.0")

from domain import demo_machines
from domain import kpis as shared_kpis

MAKINAK = demo_machines()


def makina_bilatu(cnc_id: str):
    kodea = cnc_id.upper().replace("M-", "CNC-")
    makina = next((m for m in MAKINAK if m["id"] == kodea), None)

    if makina is None:
        raise HTTPException(status_code=404, detail="Ez da makina aurkitu")

    return makina


@app.get("/api/ordutegia")
def ordutegia():
    orain = datetime.now(UTC)
    return {"data": orain.strftime("%Y-%m-%d"), "ordua": orain.strftime("%H:%M UTC")}


@app.get("/api/makinak")
def makinak():
    return MAKINAK


@app.get("/api/kpis")
def kpis():
    return shared_kpis(MAKINAK)


@app.get("/api/telemetria")
def telemetria():
    return [
        {
            "CNC": m["id"],
            "Tenp. (°C)": m["tenperatura"],
            "RPM": m["rpm"],
            "Higadura (min)": m["higadura"],
            "Torque": m["torque"],
            "Egoera": m["egoera"],
        }
        for m in MAKINAK
    ]


@app.get("/api/historikoa/{cnc_id}")
def historikoa(cnc_id: str):
    m = makina_bilatu(cnc_id)
    rng = Random(m["zenbakia"] * 100)

    orduak = ["06:00", "06:30", "07:00", "07:30", "08:00", "08:30"]

    return {
        "Ordua": orduak,
        "Prozesu-tenperatura (°C)": [
            round(m["tenperatura"] + rng.uniform(-2, 2), 1) for _ in orduak
        ],
        "Bihurdura-momentua (Nm)": [
            round(m["torque"] + rng.uniform(-4, 4), 1) for _ in orduak
        ],
        "Erremintaren higadura (min)": [
            max(0, m["higadura"] - (5 - i) * 4) for i in range(len(orduak))
        ],
    }


@app.get("/api/{cnc_id}/azken-neurketa")
def azken_neurketa(cnc_id: str):
    m = makina_bilatu(cnc_id)

    return {
        "temp": m["tenperatura"],
        "rpm": m["rpm"],
        "torque": m["torque"],
        "higadura": m["higadura"],
        "egoera": m["egoera"],
    }


@app.get("/api/status")
def status():
    return {"source": "demo", "industrial_connection": False}
