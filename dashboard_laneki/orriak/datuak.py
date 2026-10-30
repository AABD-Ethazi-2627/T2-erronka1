"""CNC makinen datu historikoen analisi teknikoa."""

from __future__ import annotations

import random
from typing import Any, Callable

import altair as alt
import pandas as pd
import streamlit as st


PERIODOAK = {
    "Astea": ("astea", 7, "eguna"),
    "Hilabetea": ("hilabetea", 30, "eguna"),
    "6 hilabete": ("sei_hilabete", 6, "hilabetea"),
}

METRIKAK = (
    ("tenperatura", "Tenperatura", "°C", "#20A884"),
    ("momentua", "Momentua", "Nm", "#E89B18"),
    ("higadura", "Erremintaren higadura", "min", "#EF5E75"),
)


def _lehen_balioa(erregistroa: dict[str, Any], izenak: tuple[str, ...], lehenetsia: Any) -> Any:
    for izena in izenak:
        if izena in erregistroa and erregistroa[izena] is not None:
            return erregistroa[izena]
    return lehenetsia


def _egoera_normalizatu(balioa: Any) -> str:
    egoera = str(balioa).strip().lower()
    if egoera in {"matxura", "akatsa", "fallo", "critical", "kritikoa"}:
        return "Matxura"
    if egoera in {"arriskuan", "berrikusteko", "riesgo", "warning", "ertaina", "arina"}:
        return "Arriskuan"
    return "Normala"


@st.cache_data(ttl=30, show_spinner=False)
def _api_seriea(payload: Any) -> pd.DataFrame | None:
    """FastAPIren erantzuna barne-formatu bateratura egokitu."""
    if isinstance(payload, dict):
        payload = payload.get("datuak", payload.get("seriea", payload))
        if isinstance(payload, dict):
            try:
                payload = pd.DataFrame(payload).to_dict("records")
            except (ValueError, TypeError):
                return None
    if not isinstance(payload, list) or not payload:
        return None

    errenkadak = []
    for i, item in enumerate(payload, 1):
        if not isinstance(item, dict):
            continue
        errenkadak.append({
            "etiketa": str(_lehen_balioa(
                item, ("etiketa", "data", "fecha", "timestamp", "Ordua"), i
            )),
            "tenperatura": float(_lehen_balioa(
                item, ("tenperatura", "temperatura", "Prozesu-tenperatura (°C)"), 0
            )),
            "momentua": float(_lehen_balioa(
                item, ("momentua", "torque", "Bihurdura-momentua (Nm)"), 0
            )),
            "higadura": float(_lehen_balioa(
                item, ("higadura", "desgaste", "Erremintaren higadura (min)"), 0
            )),
            "rpm": float(_lehen_balioa(item, ("rpm", "abiadura"), 0)),
            "osasuna": float(_lehen_balioa(item, ("osasuna", "salud", "health"), 0)),
            "arriskua": float(_lehen_balioa(item, ("arriskua", "riesgo", "risk"), 0)),
            "bibrazioa": float(_lehen_balioa(item, ("bibrazioa", "vibracion", "bibrazio_rms"), 0)),
            "korrontea": float(_lehen_balioa(item, ("korrontea", "corriente", "ardatzaren_korrontea"), 0)),
            "geldialdia": float(_lehen_balioa(item, ("geldialdia", "parada_ordu", "downtime"), 0)),
            "egoera": _egoera_normalizatu(
                _lehen_balioa(item, ("egoera", "estado", "status"), "Normala")
            ),
        })
    return pd.DataFrame(errenkadak) if errenkadak else None


@st.cache_data(show_spinner=False)
def _demo_seriea(makina: dict[str, Any], puntuak: int, periodoa: str) -> pd.DataFrame:
    """FastAPI prest egon arte erabiltzen den serie determinista."""
    rng = random.Random(int(makina.get("zenbakia", 1)) * 97 + puntuak)
    if periodoa == "sei_hilabete":
        etiketak = [f"{i}. hil." for i in range(1, puntuak + 1)]
    else:
        etiketak = [f"{i}. eg." for i in range(1, puntuak + 1)]

    tenp = float(makina.get("tenperatura", 35))
    torque = float(makina.get("torque", 35))
    higadura = float(makina.get("higadura", 80))
    rpm = float(makina.get("rpm", 1500))
    egoera_nagusia = str(makina.get("egoera", "Normala"))
    oinarrizko_arriskua = 82 if egoera_nagusia == "Akatsa" else 52 if egoera_nagusia == "Berrikusteko" else 14
    arriskuak = [max(2, min(98, round(oinarrizko_arriskua + rng.uniform(-10, 10), 1))) for _ in range(puntuak)]
    return pd.DataFrame({
        "etiketa": etiketak,
        "tenperatura": [round(tenp + rng.uniform(-2.2, 2.2) + i * .025, 1) for i in range(puntuak)],
        "momentua": [round(torque + rng.uniform(-4.5, 4.5), 1) for _ in range(puntuak)],
        "higadura": [round(max(0, higadura - (puntuak - i - 1) * 1.7), 1) for i in range(puntuak)],
        "rpm": [round(max(0, rpm + rng.uniform(-130, 130))) for _ in range(puntuak)],
        "osasuna": [round(100 - arriskua * .82, 1) for arriskua in arriskuak],
        "arriskua": arriskuak,
        "bibrazioa": [round(1.2 + arriskua * .032 + rng.uniform(-.25, .25), 2) for arriskua in arriskuak],
        "korrontea": [round(8.2 + arriskua * .075 + rng.uniform(-.8, .8), 1) for arriskua in arriskuak],
        "geldialdia": [round(max(0, (arriskua - 35) * .018 + rng.uniform(0, .35)), 2) for arriskua in arriskuak],
        "egoera": ["Matxura" if a >= 75 else "Arriskuan" if a >= 35 else "Normala" for a in arriskuak],
    })


def _grafikoa(df: pd.DataFrame, eremua: str, kolorea: str, gai_iluna: bool) -> alt.Chart:
    testua = "#FFFFFF" if gai_iluna else "#18324A"
    sareta = "#40556C" if gai_iluna else "#DCE6EF"
    atzea = "#182A3A" if gai_iluna else "#F8FAFC"
    oinarria = alt.Chart(df).encode(
        x=alt.X("etiketa:N", title=None, axis=alt.Axis(labelAngle=0, labelLimit=70)),
        y=alt.Y(f"{eremua}:Q", title=None, scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("etiketa:N", title="Epea"), alt.Tooltip(f"{eremua}:Q", title="Balioa", format=".1f")],
    )
    area = oinarria.mark_area(color=kolorea, opacity=.13)
    line = oinarria.mark_line(color=kolorea, strokeWidth=2.6, point=alt.OverlayMarkDef(size=28))
    return (area + line).properties(height=135, background=atzea).configure_axis(
        labelColor=testua, domainColor=sareta, tickColor=sareta, gridColor=sareta,
        labelFontSize=11,
    ).configure_view(strokeOpacity=0)


@st.fragment
def datuak_erakutsi(
    makina: dict[str, Any],
    makinak: list[dict[str, Any]] | None = None,
    historikoak: dict[str, Any] | None = None,
    historikoen_kargatzailea: Callable[[str], dict[str, Any] | None] | None = None,
) -> None:
    """Makina bakoitzaren uneko datuak eta serie historikoak erakutsi."""
    gai_iluna = bool(st.session_state.get("gai_iluna", False))
    datuak_dark_css = """
      .datuak-history-head *, .model-title *, .confusion-wrap *,
      .model-metrics *, .period-summary *, .historical-overview *,
      .status-history * { color: #FFFFFF !important; }
      .stApp [data-testid="stMarkdownContainer"] *,
      .stApp [data-testid="stCaptionContainer"] { color: #FFFFFF !important; }
    """ if gai_iluna else ""
    makinak = makinak or [makina]
    makina_idak = [m.get("id", "CNC") for m in makinak]
    uneko_kodea = makina.get("id", makina_idak[0])
    hautatutako_kodea = st.selectbox(
        "Aztertu beharreko makina",
        makina_idak,
        index=makina_idak.index(uneko_kodea) if uneko_kodea in makina_idak else 0,
        key="datuak_makina_hautatzailea",
    )
    makina = next(
        (m for m in makinak if m.get("id") == hautatutako_kodea),
        makina,
    )
    if hautatutako_kodea != uneko_kodea:
        st.session_state.hautatutako_makina = hautatutako_kodea
        st.query_params["makina"] = hautatutako_kodea

    if historikoen_kargatzailea is not None:
        kargatutakoak = historikoen_kargatzailea(hautatutako_kodea)
        historikoak = kargatutakoak if isinstance(kargatutakoak, dict) else None

    historikoak = historikoak if isinstance(historikoak, dict) else {}
    kodea = hautatutako_kodea
    demo_rng = random.Random(int(makina.get("zenbakia", 1)) * 211)
    ebaluazioa = historikoak.get("ereduaren_ebaluazioa", {})
    ebaluazioa = ebaluazioa if isinstance(ebaluazioa, dict) else {}
    matrizea = ebaluazioa.get("nahaste_matrizea")
    matrize_baliozkoa = (
        isinstance(matrizea, list) and len(matrizea) == 3
        and all(isinstance(errenkada, list) and len(errenkada) == 3 for errenkada in matrizea)
    )
    if not matrize_baliozkoa:
        matrizea = [
            [42 + demo_rng.randint(0, 6), demo_rng.randint(1, 4), 0],
            [demo_rng.randint(1, 4), 25 + demo_rng.randint(0, 5), demo_rng.randint(1, 3)],
            [0, demo_rng.randint(1, 3), 17 + demo_rng.randint(0, 4)],
        ]
    matrizea = [[max(0, int(v)) for v in errenkada] for errenkada in matrizea]
    guztira = sum(sum(errenkada) for errenkada in matrizea)
    zuzenak = sum(matrizea[i][i] for i in range(3))
    accuracy = zuzenak / guztira if guztira else 0
    doitasunak, sentikortasunak, f1ak = [], [], []
    for i in range(3):
        tp = matrizea[i][i]
        fp = sum(matrizea[r][i] for r in range(3)) - tp
        fn = sum(matrizea[i]) - tp
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        doitasunak.append(precision)
        sentikortasunak.append(recall)
        f1ak.append(f1)
    precision_macro = sum(doitasunak) / 3
    recall_macro = sum(sentikortasunak) / 3
    f1_macro = sum(f1ak) / 3
    st.html(f"""
    <div class="datuak-history-head">
      <div><h2>{kodea} · Datu historikoak</h2>
      </div>
      <span>Datu dinamikoak</span>
    </div>
    <div class="model-title"><strong>Eredu prediktiboaren ebaluazioa · {kodea}</strong><span>Ereduaren metrikak</span></div>
    <div class="model-evaluation">
      <div class="confusion-wrap">
        <div class="matrix-axis">Iragarritakoa →</div>
        <table class="confusion-matrix">
          <thead><tr><th>Benetakoa ↓</th><th>Normala</th><th>Arriskuan</th><th>Matxura</th></tr></thead>
          <tbody>
            <tr><th>Normala</th><td class="hit">{matrizea[0][0]}</td><td>{matrizea[0][1]}</td><td>{matrizea[0][2]}</td></tr>
            <tr><th>Arriskuan</th><td>{matrizea[1][0]}</td><td class="hit">{matrizea[1][1]}</td><td>{matrizea[1][2]}</td></tr>
            <tr><th>Matxura</th><td>{matrizea[2][0]}</td><td>{matrizea[2][1]}</td><td class="hit">{matrizea[2][2]}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="model-metrics">
        <div><small>Zehaztasuna</small><strong>{accuracy:.1%}</strong><span>Iragarpen zuzen guztiak</span></div>
        <div><small>Doitasunaren media</small><strong>{precision_macro:.1%}</strong><span>3 klaseen batezbestekoa</span></div>
        <div><small>Sentikortasunaren media</small><strong>{recall_macro:.1%}</strong><span>Detektatutako benetako kasuak</span></div>
        <div><small>F1 macro media</small><strong>{f1_macro:.1%}</strong><span>Doitasuna + sentikortasuna</span></div>
      </div>
    </div>
    <style>
      .datuak-history-head{{display:flex;justify-content:space-between;align-items:end;margin:0 0 4px}}
      .datuak-history-head h2{{margin:0;color:var(--main-text,#102A43);font-size:1.35rem}}
      .datuak-history-head p{{margin:4px 0 0;color:var(--secondary-text,#52677C);font-weight:700}}
      .datuak-history-head span{{padding:6px 10px;border-radius:8px;background:var(--state-green-bg,#DDF4E8);color:#087B49;font-weight:800;font-size:.75rem}}
      .model-title{{display:flex;align-items:center;justify-content:space-between;margin:1px 0 3px;color:var(--main-text,#102A43)}}
      .model-title span{{font-size:.68rem;color:var(--secondary-text,#52677C);font-weight:800}}
      .model-evaluation{{display:grid;grid-template-columns:minmax(420px,.9fr) minmax(0,1.1fr);gap:7px;margin-bottom:5px}}
      .confusion-wrap{{padding:4px 8px;border:1px solid var(--panel-border,#D6E1EB);border-radius:9px;background:var(--panel-bg,#FFF)}}
      .matrix-axis{{text-align:right;font-size:.65rem;font-weight:800;color:var(--secondary-text,#52677C);margin-bottom:3px}}
      .confusion-matrix{{width:100%;border-collapse:separate;border-spacing:3px;text-align:center;font-size:.7rem}}
      .confusion-matrix th{{color:var(--secondary-text,#52677C);font-weight:800}}
      .confusion-matrix td{{padding:3px;border-radius:6px;background:var(--state-red-bg,#F5B8B8);color:var(--main-text,#102A43);font-weight:900}}
      .confusion-matrix td.hit{{background:var(--state-green-bg,#D8F0E4);color:#087B49}}
      .model-metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}}
      .model-metrics>div{{min-width:0;padding:5px;border:1px solid var(--panel-border,#D6E1EB);border-radius:9px;background:var(--surface-muted,#F1F5F9);text-align:center}}
      .model-metrics small,.model-metrics strong,.model-metrics span{{display:block}}
      .model-metrics small{{font-size:.65rem;font-weight:800;color:var(--secondary-text,#52677C)}}
      .model-metrics strong{{margin:2px 0;color:var(--main-text,#102A43);font-size:1.1rem}}
      .model-metrics span{{font-size:.57rem;font-weight:700;color:var(--secondary-text,#52677C)}}
      .period-summary{{display:flex;justify-content:space-between;align-items:center;margin:0 0 3px;font-weight:800;color:var(--secondary-text,#52677C)}}
      .period-summary strong{{color:var(--main-text,#102A43);font-size:1rem}}
      .historical-overview{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin:3px 0 5px}}
      .historical-overview>div{{min-width:0;padding:4px 8px;border:1px solid var(--panel-border,#D6E1EB);border-radius:9px;background:var(--panel-bg,#FFF);text-align:center}}
      .historical-overview small,.historical-overview strong,.historical-overview span{{display:block}}
      .historical-overview small{{font-size:.64rem;font-weight:800;color:var(--secondary-text,#52677C)}}
      .historical-overview strong{{margin:2px 0;color:var(--main-text,#102A43);font-size:.98rem}}
      .historical-overview span{{font-size:.56rem;font-weight:700;color:var(--secondary-text,#52677C)}}
      .status-history{{display:flex;gap:7px;margin:0 0 4px}}
      .status-history span{{flex:1;padding:4px 8px;border-radius:8px;text-align:center;font-size:.68rem;font-weight:900}}
      .status-normal{{background:var(--state-green-bg,#D8F0E4);color:#087B49}}
      .status-risk{{background:var(--state-amber-bg,#F8E7B5);color:#A85A05}}
      .status-fault{{background:var(--state-red-bg,#F5B8B8);color:#A61B1B}}
      {datuak_dark_css}
      @media(max-width:1000px){{.model-evaluation{{grid-template-columns:1fr}}.historical-overview{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
      div[data-testid="stVegaLiteChart"]{{border:1px solid var(--panel-border,#D6E1EB);border-radius:10px;padding:5px;background:var(--panel-bg,#FFF)}}
    </style>
    """)

    aukeratutako_izena = st.segmented_control(
        "Denbora-tartea",
        options=list(PERIODOAK),
        default="Astea",
        key="datuak_periodoa",
        label_visibility="collapsed",
        width="stretch",
    ) or "Astea"
    api_gakoa, puntuak, _ = PERIODOAK[aukeratutako_izena]
    df = _api_seriea(historikoak.get(api_gakoa))
    simulazioa = df is None
    if simulazioa:
        df = _demo_seriea(makina, puntuak, api_gakoa)

    st.html(f'<div class="period-summary"><strong>{aukeratutako_izena}</strong><span>{len(df)} neurketa · {"Simulazioa" if simulazioa else "Datu errealak"}</span></div>')
    egoera_kopuruak = df["egoera"].value_counts()
    normala_kop = int(egoera_kopuruak.get("Normala", 0))
    arriskuan_kop = int(egoera_kopuruak.get("Arriskuan", 0))
    matxura_kop = int(egoera_kopuruak.get("Matxura", 0))
    st.html(f"""
    <div class="status-history">
      <span class="status-normal">Normala  {normala_kop}</span>
      <span class="status-risk">Arriskuan  {arriskuan_kop}</span>
      <span class="status-fault">Matxura  {matxura_kop}</span>
    </div>
    <div class="historical-overview">
      <div><small>Osasunaren media</small><strong>{df['osasuna'].mean():.1f}%</strong><span>Azkena: {df['osasuna'].iloc[-1]:.1f}%</span></div>
      <div><small>Arriskuaren media</small><strong>{df['arriskua'].mean():.1f}%</strong><span>Gehienez: {df['arriskua'].max():.1f}%</span></div>
      <div><small>Tenperaturaren media</small><strong>{df['tenperatura'].mean():.1f} °C</strong><span>Gehienez: {df['tenperatura'].max():.1f} °C</span></div>
      <div><small>Abiaduraren media</small><strong>{df['rpm'].mean():.0f} RPM</strong><span>Gehienez: {df['rpm'].max():.0f} RPM</span></div>
      <div><small>Momentuaren media</small><strong>{df['momentua'].mean():.1f} Nm</strong><span>Gehienez: {df['momentua'].max():.1f} Nm</span></div>
      <div><small>Higaduraren media</small><strong>{df['higadura'].mean():.1f} min</strong><span>Azkena: {df['higadura'].iloc[-1]:.1f} min</span></div>
      <div><small>Bibrazioaren media</small><strong>{df['bibrazioa'].mean():.2f} mm/s</strong><span>Gehienez: {df['bibrazioa'].max():.2f} mm/s</span></div>
      <div><small>Korrontearen media</small><strong>{df['korrontea'].mean():.1f} A</strong><span>Gehienez: {df['korrontea'].max():.1f} A</span></div>
      <div><small>Geldialdia guztira</small><strong>{df['geldialdia'].sum():.1f} h</strong><span>Planifikatu gabekoa</span></div>
      <div><small>Neurketa kopurua</small><strong>{len(df)}</strong><span>{aukeratutako_izena}</span></div>
    </div>
    """)
    for zutabea, (eremua, izenburua, unitatea, kolorea) in zip(st.columns(3, gap="medium"), METRIKAK):
        with zutabea:
            batezbestekoa = df[eremua].mean()
            azkena = df[eremua].iloc[-1]
            st.markdown(f"**{izenburua}** · {azkena:.1f} {unitatea}  ")
            st.caption(f"Batezbestekoa: {batezbestekoa:.1f} {unitatea}")
            st.altair_chart(_grafikoa(df, eremua, kolorea, gai_iluna), use_container_width=True)
