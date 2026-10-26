
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone
from random import Random

app = FastAPI(title="Laneki IoT API", version="2.0")

BERRIKUSPENA = {
    12, 15, 16, 20, 21, 27, 35, 38,
    39, 40, 41, 43, 46, 47, 48
}
AKATSAK = {4}

def makinak_sortu():
    makinak = []

    for n in range(1, 51):
        rng = Random(n * 123)
        kodea = f"CNC-{n:03d}"

        if n in AKATSAK:
            egoera = "Akatsa"
        elif n in BERRIKUSPENA:
            egoera = "Berrikusteko"
        else:
            egoera = "Normala"

        temp = round(rng.uniform(30, 39), 1)
        rpm = rng.randint(1200, 1900)
        torque = round(rng.uniform(22, 49), 1)
        higadura = rng.randint(45, 240)

        if n == 4:
            temp, rpm, torque, higadura = 36.3, 1380, 47.6, 246

        makinak.append({
            "id": kodea,
            "zenbakia": n,
            "tenperatura": temp,
            "rpm": rpm,
            "torque": torque,
            "higadura": higadura,
            "egoera": egoera,
        })

    return makinak


MAKINAK = makinak_sortu()


def makina_bilatu(cnc_id: str):
    kodea = cnc_id.upper().replace("M-", "CNC-")
    makina = next(
        (m for m in MAKINAK if m["id"] == kodea),
        None
    )

    if makina is None:
        raise HTTPException(
            status_code=404,
            detail="Ez da makina aurkitu"
        )

    return makina


@app.get("/api/ordutegia")
def ordutegia():
    orain = datetime.now(timezone.utc)
    return {
        "data": orain.strftime("%Y-%m-%d"),
        "ordua": orain.strftime("%H:%M UTC")
    }


@app.get("/api/makinak")
def makinak():
    return MAKINAK


@app.get("/api/kpis")
def kpis():
    erabilgarriak = sum(
        m["egoera"] != "Akatsa" for m in MAKINAK
    )
    akatsak = sum(
        m["egoera"] == "Akatsa" for m in MAKINAK
    )

    return {
        "operatiboak": erabilgarriak,
        "guztira": len(MAKINAK),
        "akatsak": akatsak,
        "gertakariak": 15,
        "osasuna": 89,
        "tenperatura": 27.3,
        "motak": {"H": 10, "M": 25, "L": 15}
    }


@app.get("/api/telemetria")
def telemetria():
    return [
        {
            "CNC": m["id"],
            "Tenp. (°C)": m["tenperatura"],
            "RPM": m["rpm"],
            "Higadura (min)": m["higadura"],
            "Torque": m["torque"],
            "Egoera": m["egoera"]
        }
        for m in MAKINAK
    ]


@app.get("/api/historikoa/{cnc_id}")
def historikoa(cnc_id: str):
    m = makina_bilatu(cnc_id)
    rng = Random(m["zenbakia"] * 100)

    orduak = [
        "06:00", "06:30", "07:00",
        "07:30", "08:00", "08:30"
    ]

    return {
        "Ordua": orduak,
        "Prozesu-tenperatura (°C)": [
            round(m["tenperatura"] + rng.uniform(-2, 2), 1)
            for _ in orduak
        ],
        "Bihurdura-momentua (Nm)": [
            round(m["torque"] + rng.uniform(-4, 4), 1)
            for _ in orduak
        ],
        "Erremintaren higadura (min)": [
            max(0, m["higadura"] - (5 - i) * 4)
            for i in range(len(orduak))
        ]
    }


@app.get("/api/{cnc_id}/azken-neurketa")
def azken_neurketa(cnc_id: str):
    m = makina_bilatu(cnc_id)

    return {
        "temp": m["tenperatura"],
        "rpm": m["rpm"],
        "torque": m["torque"],
        "higadura": m["higadura"],
        "egoera": m["egoera"]
    }
