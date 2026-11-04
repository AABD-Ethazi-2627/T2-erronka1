import base64
import importlib
import os
import time
from datetime import UTC, datetime

import pandas as pd
import requests
import streamlit as st
from domain import demo_machines, load_machines, selected_machine
from domain import kpis as shared_kpis
from orriak import makinak as makinak_orria
from orriak.abisuak import abisuak_erakutsi
from orriak.datuak import datuak_erakutsi, show_history
from orriak.hasiera import hasiera_erakutsi
from orriak.shared import fmt, measurements, provenance

FASTAPI_HELBIDEA = os.environ.get("LANEKI_API_URL", "http://127.0.0.1:8001/api").rstrip(
    "/"
)
DATU_MODUA = os.environ.get("LANEKI_MODE", "demo")

st.set_page_config(
    page_title="Laneki IoT",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================
# APLIKAZIOAREN EGOERA
# =============================

ORRI_BALIOZKOAK = {"Hasiera", "Makinak", "Datuak", "Abisuak", "Ezarpenak"}

if "gai_iluna" not in st.session_state:
    url_gaia = st.query_params.get("gaia", "argia")
    st.session_state.gai_iluna = url_gaia == "iluna"

if "pastel_aktibatuta" not in st.session_state:
    st.session_state.pastel_aktibatuta = True


if "orria" not in st.session_state:
    url_orria = st.query_params.get("orria", "Hasiera")
    st.session_state.orria = url_orria if url_orria in ORRI_BALIOZKOAK else "Hasiera"
elif "orria" in st.query_params and st.query_params["orria"] in ORRI_BALIOZKOAK:
    st.session_state.orria = st.query_params["orria"]

if "menu_irekia" not in st.session_state:
    st.session_state.menu_irekia = False


# =============================
# PROBA-DATUAK / FASTAPI
# =============================

demo_datuak = demo_machines


@st.cache_data(ttl=5, show_spinner=False)
def _kontsultatu(api_url, amaiera_puntua, as_of):
    try:
        erantzuna = requests.get(
            f"{api_url}/{amaiera_puntua}",
            timeout=(2, 20),
            params={"as_of": as_of}
            if amaiera_puntua != "model-evaluation" and "cursor=" not in amaiera_puntua
            else None,
        )
        erantzuna.raise_for_status()
        return erantzuna.json()
    except (requests.RequestException, ValueError):
        return None


def kontsultatu(endpoint):
    return _kontsultatu(FASTAPI_HELBIDEA, endpoint, READ_AS_OF)


def refresh_reads():
    _kontsultatu.clear()
    st.session_state.pop("read_as_of", None)
    st.session_state.live_last_refresh = time.monotonic()
    for key in list(st.session_state):
        if key.startswith("history_cursor_"):
            st.session_state.pop(key, None)


kontsultatu.clear = refresh_reads


@st.fragment(run_every=5)
def live_refresh_control():
    st.session_state.setdefault("live_updates", True)
    enabled = st.toggle("Zuzeneko eguneratzea · 5 s", key="live_updates")
    now = time.monotonic()
    previous = st.session_state.get("live_last_refresh", now)
    st.session_state.setdefault("live_last_refresh", now)
    if enabled and now - previous >= 5:
        refresh_reads()
        # A full script run must consume pending widget clicks. Only a fragment
        # rerun needs to request the rest of the page; inline runs continue below.
        if not st.session_state.get("live_inline", False):
            st.rerun(scope="app")
    st.caption(
        "API kontsulta automatikoak · behaketaren adina ikusgai. "
        "Historia orrikatzeko edo xehetasunak aztertzeko, pausatu."
        if enabled
        else "PAUSATUTA · UTC ebaketa mantentzen da."
    )


# Register before empty/error stops so polling can recover after an API outage.
if DATU_MODUA == "api":
    st.session_state.live_inline = True
    try:
        live_refresh_control()
    finally:
        st.session_state.live_inline = False

# Inline refresh may invalidate the previous cutoff. Bind it after the control,
# before any data read, so every reader in this run uses the renewed value.
if "read_as_of" not in st.session_state:
    st.session_state.read_as_of = datetime.now(UTC).isoformat().replace("+00:00", "Z")
READ_AS_OF = st.session_state.read_as_of


def makinak_lortu():
    return load_machines(DATU_MODUA, kontsultatu)


def kpiak_lortu(makinak):
    return shared_kpis(makinak)


makinak, iturri_egoera = makinak_lortu()
if iturri_egoera == "api":
    for makina in makinak:
        makina["as_of"] = READ_AS_OF
        try:
            stamp = datetime.fromisoformat(makina["timestamp"])
            makina["age_seconds"] = (
                datetime.fromisoformat(READ_AS_OF) - stamp
            ).total_seconds()
        except (KeyError, TypeError, ValueError):
            makina["age_seconds"] = None
    st.caption(
        f"API kontsulten UTC ebaketa: {READ_AS_OF} · ES irakurketak ez dira transakzio bakarra."
    )
st.warning(
    "PROTOTIPOA · "
    + (
        "DEMO: datu guztiak simulatuak dira."
        if iturri_egoera == "demo"
        else "API prototipoa: ez du CNC Guard integrazioa egiaztatzen."
    )
)
if not makinak:
    if iturri_egoera == "api":
        st.info("API · Snapshot hutsa: 0 makina. Ez da demo-daturik sortu.")
        st.button("Eguneratu", on_click=kontsultatu.clear)
        st.stop()
    st.error(
        "DEGRADATUTA · API ez dago eskuragarri edo datuak baliogabeak dira. Ez da demo-daturik ordezkatu. Egiaztatu zerbitzua eta freskatu."
    )
    st.button("Eguneratu", on_click=kontsultatu.clear)
    st.stop()
kpis = kpiak_lortu(makinak)
st.caption(
    "5 segundoko cachea · Eguneratu botoiak UTC ebaketa eta kontsultak berritzen ditu."
)
st.button("Eguneratu", on_click=kontsultatu.clear)
if DATU_MODUA == "api":
    kpi_payload = kontsultatu("kpis")
    with st.expander("KPI kanonikoak · definizioa, izendatzailea eta UTC estaldura"):
        if isinstance(kpi_payload, dict):
            st.json(kpi_payload)
        else:
            st.warning(
                "KPI zerbitzua degradatuta; beheko kontaketak snapshot lokalekoak dira."
            )
eskatua = st.query_params.get("makina")
kodea = selected_machine(
    st.session_state.get("hautatutako_makina"),
    eskatua,
    makinak,
    st.session_state.get("azken_url_makina"),
)
if eskatua is not None and eskatua not in {m["id"] for m in makinak}:
    st.warning(
        "URLko makina ez da iturrian agertzen; iturriko makina baliodun bat hautatu da."
    )
st.session_state.hautatutako_makina = kodea
st.session_state.azken_url_makina = eskatua
uneko_makina = next(m for m in makinak if m["id"] == kodea)
provenance(uneko_makina)
orain = datetime.now(UTC)
data = orain.strftime("%Y-%m-%d")
ordua = orain.strftime("%H:%M UTC")


# =============================
# CSS ETA GAIAK
# =============================

css_bidea = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "css", "styles.css"
)

if os.path.exists(css_bidea):
    with open(css_bidea, "r", encoding="utf-8") as fitxategia:
        st.markdown(f"<style>{fitxategia.read()}</style>", unsafe_allow_html=True)

logo_bidea = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "images", "logo_laneki.webp"
)

with open(logo_bidea, "rb") as logo_fitxategia:
    logo_base64 = base64.b64encode(logo_fitxategia.read()).decode("ascii")

iluna = st.session_state.gai_iluna

# Txartelen pastel-koloreak EZ dira aldatzen.
# Atzeko plano orokorra, panelak eta bigarren mailako testuak soilik aldatzen dira.

if iluna:
    atzeko_planoa = "#172330"
    panela = "#223344"
    testua = "#F1F5F9"
    bigarren_mailakoa = "#CED9E5"
    ertza = "#40566B"
    grafiko_atzeko_planoa = "#223344"
    azalera_leuna = "#2B3E50"
    sarrera_atzeko_planoa = "#1B2A38"
    xehetasun_azalera = "rgba(23, 35, 48, 0.10)"
    xehetasun_ertza = "rgba(15, 23, 42, 0.20)"
    pastel_urdina = "#294662"
    pastel_arrosa = "#57343A"
    pastel_izotza = "#304858"
    pastel_arbela = "#344759"
    pastel_berdea = "#294D42"
    semantiko_testua = "#F8FAFC"
    semantiko_bigarrena = "#D7E1EA"
    egoera_gorria = "#57343A"
    egoera_laranja = "#55451F"
    egoera_urdina = "#294662"
    egoera_berdea = "#294D42"
else:
    atzeko_planoa = "#F0F4F8"
    panela = "#FFFFFF"
    testua = "#142A40"
    bigarren_mailakoa = "#526578"
    ertza = "#D9E3EC"
    grafiko_atzeko_planoa = "#FFFFFF"
    azalera_leuna = "#F2F6F9"
    sarrera_atzeko_planoa = "#FFFFFF"
    xehetasun_azalera = "#F8FAFC"
    xehetasun_ertza = "#E2E8F0"
    pastel_urdina = "#DCEBFA"
    pastel_arrosa = "#F9E2E4"
    pastel_izotza = "#E7F0F5"
    pastel_arbela = "#E5EDF5"
    pastel_berdea = "#DFF4E9"
    semantiko_testua = "#142A40"
    semantiko_bigarrena = "#475569"
    egoera_gorria = "#FFF1F2"
    egoera_laranja = "#FFF7E6"
    egoera_urdina = "#EFF6FF"
    egoera_berdea = "#F0FDF4"

st.markdown(
    f"""
<style>
:root {{
    --app-bg: {atzeko_planoa};
    --panel-bg: {panela};
    --main-text: {testua};
    --secondary-text: {bigarren_mailakoa};
    --panel-border: {ertza};
    --surface-muted: {azalera_leuna};
    --input-bg: {sarrera_atzeko_planoa};
    --detail-surface: {xehetasun_azalera};
    --detail-border: {xehetasun_ertza};
    --pastel-blue: {pastel_urdina};
    --pastel-pink: {pastel_arrosa};
    --pastel-ice: {pastel_izotza};
    --pastel-slate: {pastel_arbela};
    --pastel-green: {pastel_berdea};
    --semantic-text: {semantiko_testua};
    --semantic-muted: {semantiko_bigarrena};
    --state-red-bg: {egoera_gorria};
    --state-amber-bg: {egoera_laranja};
    --state-blue-bg: {egoera_urdina};
    --state-green-bg: {egoera_berdea};
}}

.stApp,
[data-testid="stAppViewContainer"] {{
    background: {atzeko_planoa} !important;
    color: {testua};
}}

[data-testid="stHeader"] {{
    background: transparent !important;
}}

[data-testid="stSidebar"] {{
    background: #142E4B !important;
}}

[data-testid="stSidebar"] * {{
    color: #FFFFFF;
}}

.panel-title {{
    color: {testua};
}}

.panel-box {{
    background: {panela};
    border: 1px solid {ertza};
}}

.status-bar {{
    background: {panela};
    border: 1px solid {ertza};
    color: {testua};
}}

.dashboard-subtitle,
.panel-description {{
    color: {bigarren_mailakoa};
}}

div[data-testid="stDataFrame"] {{
    border: 1px solid {ertza};
    border-radius: 9px;
}}

[data-testid="stSidebarCollapsedControl"] {{
    color: {testua};
}}

/* Menua aplikaziotik kontrolatzen da, ez nabigatzailearen egoeratik. */
[data-testid="stMainBlockContainer"] {{
    /* The transparent Streamlit header still intercepts clicks. Leave room
       even when the collaborator's responsive CSS zooms the main container. */
    padding-top: 80px !important;
}}

/* Canonical controls and provenance add content above the original single-screen
   prototype. Keep every page reachable instead of clipping the lower controls. */
[data-testid="stMain"],
[data-testid="stMain"]:has(.datuak-page-marker) {{
    overflow-y: auto !important;
}}
[data-testid="stMainBlockContainer"],
[data-testid="stMainBlockContainer"]:has(.datuak-page-marker) {{
    height: auto !important;
    min-height: 100%;
    overflow: visible !important;
}}
@media (max-width: 640px) {{
    [data-testid="stMainBlockContainer"] {{ zoom: 1 !important; }}
    .dashboard-title, .machines-page-title, .alerts-page-title, h1, h2, h3 {{
        white-space: normal !important;
        overflow-wrap: anywhere;
    }}
}}

[data-testid="stSidebar"] {{
    display: {"block" if st.session_state.menu_irekia else "none"} !important;
    transform: none !important;
}}

.st-key-menu_toggle {{
    position: fixed !important;
    top: 8px;
    left: {"198px" if st.session_state.menu_irekia else "10px"};
    width: 40px;
    z-index: 1000000;
    transition: left 0.25s ease;
}}

.st-key-menu_toggle button {{
    width: 38px !important;
    min-width: 38px !important;
    height: 36px !important;
    min-height: 36px !important;
    padding: 0 !important;
    border-radius: 8px !important;
    border: 1px solid #46627D !important;
    background: #142E4B !important;
    color: #FFFFFF !important;
    box-shadow: 0 3px 10px rgba(20, 46, 75, 0.22) !important;
}}

.st-key-menu_toggle button:hover {{
    background: #27608E !important;
    border-color: #3498DB !important;
}}

.st-key-gaia_aldatu button {{
    width: 38px !important;
    min-width: 38px !important;
    height: 36px !important;
    min-height: 36px !important;
    padding: 0 !important;
    border: 1px solid {ertza} !important;
    border-radius: 8px !important;
    background: {panela} !important;
    color: {testua} !important;
    box-shadow: 0 2px 7px rgba(20, 42, 64, 0.10) !important;
}}

.st-key-gaia_aldatu button p {{
    font-size: 19px !important;
    line-height: 1 !important;
}}

.st-key-gaia_aldatu button:hover {{
    background: {"#31475B" if iluna else "#E3EDF5"} !important;
    border-color: #3976BD !important;
}}

[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}
/* ==========================================
   PASTEL DISEINUA - LANTEGIKO MAPA OPERATIBOA ETA METRIKAK
   ========================================== */

.st-key-machine_panel {{
    background: {panela} !important;
    border: 1px solid {ertza} !important;
    border-radius: 14px !important;
    padding: 14px 16px !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04) !important;
    box-sizing: border-box !important;
    height: 372px !important;
    min-height: 372px !important;
    max-height: 372px !important;
    overflow: hidden !important;
}}

.machine-map-top {{
    display: flex !important;
    justify-content: space-between !important;
    margin: 0 2px 8px !important;
    color: {bigarren_mailakoa} !important;
    font-size: 9px !important;
    font-weight: 800 !important;
    letter-spacing: 0.5px !important;
}}

.machine-line-label {{
    display: flex !important;
    min-height: 30px !important;
    flex-direction: column !important;
    justify-content: center !important;
    color: {testua} !important;
    line-height: 1.1 !important;
}}

.machine-line-label strong {{
    font-size: 10px !important;
    font-weight: 800 !important;
    color: {testua} !important;
    white-space: nowrap !important;
}}

.machine-line-label small {{
    margin-top: 2px !important;
    color: {bigarren_mailakoa} !important;
    font-size: 8px !important;
    font-weight: 600 !important;
}}

div[class*="st-key-machine_"] button {{
    width: 100% !important;
    min-height: 30px !important;
    height: 30px !important;
    padding: 2px 0 !important;
    border-radius: 6px !important;
    box-shadow: none !important;
    transition: all 0.15s ease !important;
}}

div[class*="st-key-machine_"] button p {{
    font-size: 11px !important;
    font-weight: 800 !important;
}}

div[class*="st-key-machine_normal_"] button {{
    background: var(--state-green-bg) !important;
    border: 1.5px solid #A3E4C4 !important;
}}
div[class*="st-key-machine_normal_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_recommended_"] button {{
    background: var(--state-blue-bg) !important;
    border: 1.5px solid #A8D1FA !important;
}}
div[class*="st-key-machine_recommended_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_necessary_"] button {{
    background: var(--state-amber-bg) !important;
    border: 1.5px solid #FDE48A !important;
}}
div[class*="st-key-machine_necessary_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_accelerated_"] button {{
    background: var(--state-amber-bg) !important;
    border: 1.5px solid #FDC4A8 !important;
}}
div[class*="st-key-machine_accelerated_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_emergency_"] button {{
    background: var(--state-red-bg) !important;
    border: 1.5px solid #FCA7AF !important;
}}
div[class*="st-key-machine_emergency_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_nodata_"] button {{
    background: var(--surface-muted) !important;
    border: 1.5px solid #CBD8E5 !important;
}}
div[class*="st-key-machine_nodata_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_"] button:hover {{
    transform: translateY(-1px) !important;
    filter: brightness(0.96) !important;
}}

.st-key-machine_panel div[class*="_selected"] button {{
    outline: none !important;
    box-shadow: 0 0 0 2px {panela}, 0 0 0 4.5px #2563EB !important;
    transform: scale(1.05) !important;
    z-index: 2 !important;
}}

.machine-legend {{
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    gap: 14px !important;
    color: {bigarren_mailakoa} !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    margin-top: 10px !important;
}}
.machine-legend span {{
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    color: {bigarren_mailakoa} !important;
}}
.machine-legend strong {{
    margin-left: auto !important;
    color: {testua} !important;
}}
.state-normal {{ background: #A3E4C4 !important; border: 1px solid #156648 !important; }}
.state-recommended {{ background: #A8D1FA !important; border: 1px solid #174E82 !important; }}
.state-necessary {{ background: #FDE48A !important; border: 1px solid #8C5505 !important; }}
.state-accelerated {{ background: #FDC4A8 !important; border: 1px solid #963806 !important; }}
.state-emergency {{ background: #FCA7AF !important; border: 1px solid #A31F2E !important; }}
.state-nodata {{ background: #CBD8E5 !important; border: 1px solid #475E75 !important; }}

.st-key-history_panel,
.st-key-measure_panel {{
    background: {panela} !important;
    border: 1px solid {ertza} !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04) !important;
}}

.sensor-track {{
    background: {azalera_leuna} !important;
    border-radius: 10px !important;
    height: 10px !important;
}}
</style>
""",
    unsafe_allow_html=True,
)


if st.button(
    "☰" if not st.session_state.menu_irekia else "‹",
    key="menu_toggle",
    help=(
        "Alboko menua erakutsi"
        if not st.session_state.menu_irekia
        else "Alboko menua ezkutatu"
    ),
):
    st.session_state.menu_irekia = not st.session_state.menu_irekia
    st.rerun()


# =============================
# ALBOKO MENUA
# =============================

with st.sidebar:
    st.markdown(
        f"""
    <div class="sidebar-logo">
        <img
            src="data:image/webp;base64,{logo_base64}"
            alt="Laneki"
            class="sidebar-logo-image"
        >
        <div class="sidebar-sub">IoT Sistema</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    aukerak = [
        ("🏠 Hasiera", "Hasiera"),
        ("🏭 Makinak", "Makinak"),
        ("📊 Datuak", "Datuak"),
        ("🔔 Abisuak", "Abisuak"),
    ]

    for etiketa, orria in aukerak:
        mota = "primary" if st.session_state.orria == orria else "secondary"

        if st.button(etiketa, key=f"nav_{orria}", width="stretch", type=mota):
            st.session_state.orria = orria
            st.query_params["orria"] = orria
            st.rerun()

    if st.button("Eguneratu", key="refresh_data"):
        kontsultatu.clear()
        st.rerun()
    st.caption("Eskuzko freskatzea · ez da sentsorearen timestamp-a.")
    st.html(f"""
    <div class="sidebar-system-card" aria-label="Sistemaren egoera">
        <strong><i></i> Prototipoa · {iturri_egoera.upper()}</strong>
        <span>{len(makinak)} makina iturrian</span>
    </div>
    <div class="sidebar-user-card" aria-label="Demo erabiltzailea">
        <div class="sidebar-user-avatar">AC</div>
        <div class="sidebar-user-info">
            <strong>Demo erabiltzailea</strong>
            <span><i></i> Autentifikaziorik gabe</span>
        </div>
        <div class="sidebar-user-menu" aria-hidden="true">⋮</div>
    </div>
    """)


# =============================
# DATU OROKORRAK
# =============================

# =============================
# GOIBURUA
# =============================

goiburu1, data_zutabea, gai_zutabea = st.columns([4, 1.35, 0.25])

with goiburu1:
    st.markdown(
        '<div class="dashboard-title">Makinen egoera eta datuak</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="dashboard-subtitle">CNC egoera · prototipoa</div>',
        unsafe_allow_html=True,
    )

with data_zutabea:
    st.markdown(
        f'<div class="header-datetime">'
        f"<span>Interfazea: {data}</span><span>🕒 {ordua}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

with gai_zutabea:
    etiketa = "☀️" if iluna else "🌙"

    if st.button(etiketa, key="gaia_aldatu", help="Gai argia/iluna aldatu"):
        st.session_state.gai_iluna = not iluna
        st.query_params["gaia"] = "iluna" if st.session_state.gai_iluna else "argia"
        st.rerun()


# =============================
# IKUSIZKO FUNTZIOAK
# =============================


def panel_izenburua(izenburu_testua, deskribapena=""):
    st.markdown(
        f'<div class="panel-heading">{izenburu_testua}</div>', unsafe_allow_html=True
    )

    if deskribapena:
        st.markdown(
            f'<div class="panel-description">{deskribapena}</div>',
            unsafe_allow_html=True,
        )


def kpi_txartelak():
    zutabeak = st.columns(5, gap="small")

    ikonoak = {
        "makina": """<svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 21V10l5 3V9l5 3V5h4l1 16M3 21h18M7 17h1m4 0h1m4 0h1"/>
        </svg>""",
        "abisua": """<svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 3 2.8 20h18.4L12 3Zm0 6v5m0 3h.01"/>
        </svg>""",
        "osasuna": """<svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M20.8 4.8a5.5 5.5 0 0 0-7.8 0L12 5.9l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.4a5.5 5.5 0 0 0 0-7.8Z"/>
            <path d="M7 12h3l1.2-2.5L13 15l1.2-3H17"/>
        </svg>""",
        "motak": """<svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
            <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>""",
        "tenperatura": """<svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M11 14.7V5a3 3 0 0 0-6 0v9.7a5 5 0 1 0 6 0Z"/>
            <path d="M8 8v9"/>
            <circle class="kpi-icon-fill" cx="8" cy="17" r="2.2"/>
            <path d="M16 5c1 1 1 2.2 0 3.2s-1 2.2 0 3.2 1 2.2 0 3.2M20 5c1 1 1 2.2 0 3.2s-1 2.2 0 3.2"/>
        </svg>""",
    }

    txartelen_datuak = [
        {
            "klasea": "blue",
            "ikonoa": ikonoak["makina"],
            "izenburua": "Ez-CRITICA inferituak",
            "balioa": f"{kpis['operatiboak']} / {kpis['guztira']}",
            "sub": "Snapshoteko kontaketa; ez jarduera fisikoa",
        },
        {
            "klasea": "pink",
            "ikonoa": ikonoak["abisua"],
            "izenburua": "CRITICA inferituak",
            "balioa": str(kpis["akatsak"]),
            "sub": f"{kpis['gertakariak']} historikorik egiaztatu gabe",
        },
        {
            "klasea": "ice",
            "ikonoa": ikonoak["osasuna"],
            "izenburua": "Batez besteko osasuna",
            "balioa": "Ez dago daturik",
            "sub": "Flotaren osasun-indizea",
        },
    ]

    for zutabea, datua in zip(zutabeak[:3], txartelen_datuak):
        with zutabea:
            st.markdown(
                f"""
            <div class="kpi-card kpi-{datua["klasea"]}">
                <div class="kpi-heading">
                    <span class="kpi-icon">{datua["ikonoa"]}</span>
                    <span>{datua["izenburua"]}</span>
                </div>
                <div class="kpi-body">
                    <span class="kpi-number">{datua["balioa"]}</span>
                    <span class="kpi-description">{datua["sub"]}</span>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

    with zutabeak[3]:
        st.markdown(
            '<div class="kpi-card kpi-slate"><span>Makina motak</span><p>Ez dago daturik</p></div>',
            unsafe_allow_html=True,
        )

    with zutabeak[4]:
        st.markdown(
            f"""
        <div class="kpi-card kpi-green">
            <div class="kpi-heading">
                <span class="kpi-icon">{ikonoak["tenperatura"]}</span>
                <span>Prozesu-tenperatura</span>
            </div>
            <div class="kpi-body">
                <span class="kpi-number">
                    {fmt(kpis["tenperatura"])}{" °C" if kpis["tenperatura"] is not None else ""}
                </span>
                <span class="kpi-description">
                    Batez besteko prozesu-tenperatura
                </span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )


def telemetria_taula():
    st.caption("Snapshoteko neurketak · maila inferituak")
    st.dataframe(
        pd.DataFrame(makinak)[
            ["id", "tenperatura", "rpm", "torque", "higadura", "egoera"]
        ],
        hide_index=True,
    )


def historiko_grafikoa():
    st.subheader(f"{kodea} · Historikoa")
    if DATU_MODUA == "api":
        show_history(kontsultatu(f"historikoa/{kodea}"))
    else:
        st.info("DEMO · ez dago artxibatutako historiko egiaztaturik.")


def azken_neurketak():
    measurements(uneko_makina)


def makina_sarea():
    with st.container(key="machine_panel"):
        panel_izenburua(
            "Makinen hautatzailea",
            "IDaren araberako aurkezpena · ez da kokapen fisikoa",
        )
        for start in range(0, len(makinak), 10):
            for col, makina in zip(st.columns(10), makinak[start : start + 10]):
                with col:
                    if st.button(
                        str(makina["zenbakia"]),
                        key=f"machine_button_{makina['zenbakia']}",
                        help=f"{makina['id']}: {makina['egoera']}",
                    ):
                        st.session_state.hautatutako_makina = makina["id"]
                        st.query_params["makina"] = makina["id"]
                        st.rerun()
        st.caption(f"Hautatua: {kodea} · {len(makinak)} makina iturrian")


def egutegi_taula():
    st.html("""
    <div class="calendar-grid">
        <div class="calendar-day-title">LARUNBATA · GELDIALDIA</div>
        <div class="calendar-day-title">IGANDEA · GELDIALDIA</div>

        <div class="calendar-event calendar-event-warn"><time>08:00</time><b>CNC-007 · Ikuskapen mekanikoa</b><small>2 ordu · Lehentasun bizkortua</small></div>
        <div class="calendar-event calendar-event-info"><time>08:00</time><b>CNC-014 · Berrikuspen termikoa</b><small>2 ordu · Gomendatua</small></div>
        <div class="calendar-event calendar-event-warn"><time>10:00</time><b>CNC-038 · Erreminta</b><small>1 ordu · Beharrezkoa</small></div>
        <div class="calendar-event calendar-event-info"><time>10:00</time><b>CNC-042 · Ikuskapena</b><small>1 ordu · Gomendatua</small></div>
        <div class="calendar-event calendar-event-info"><time>11:00</time><b>CNC-028 · Prebentzioa</b><small>3 ordu · Teknikariaren berrikuspena</small></div>
        <div class="calendar-event calendar-event-free"><time>11:00</time><b>Libre</b><small>Erabilgarri</small></div>
    </div>
    <div class="calendar-alert">
        <b>△ Egutegitik kanpo · CNC-023</b>
        <small>Ebaztu orain; alarma ez da asteburura arte atzeratuko.</small>
    </div>
    """)


@st.dialog("Asteko berrikuspen-egutegia", width="large")
def asteko_egutegia_ireki():
    st.caption("Demo adibidea · ez da benetako erregistroa. Ez da agindu operatiboa")
    if DATU_MODUA != "demo":
        st.info("Ez dago mantentze-egutegi egiaztaturik.")
        return
    st.caption("DEMO egutegia · ez da benetako mantentze-erregistroa.")
    egutegi_taula()


def egutegia():
    ikono_zutabea, izenburu_zutabea = st.columns([0.28, 3.72])

    with ikono_zutabea:
        ireki = st.button("📅", key="calendar_open", help="Asteko egutegia ireki")

    with izenburu_zutabea:
        st.markdown(
            '<div class="calendar-heading">'
            "<strong>Aste honetako berrikuspen-egutegia</strong>"
            "<small>Demo adibidea · ez da benetako erregistroa. "
            "Ez da agindu operatiboa</small></div>",
            unsafe_allow_html=True,
        )

    if DATU_MODUA != "demo":
        st.info("Ez dago mantentze-egutegi egiaztaturik.")
        return
    st.caption("DEMO egutegia · ez da benetako mantentze-erregistroa.")
    egutegi_taula()

    if ireki:
        asteko_egutegia_ireki()


def egoera_zerbitzuak():
    testua = (
        "API prototipoa (ez CNC Guard konexio egiaztatua)"
        if iturri_egoera == "api"
        else "DEMO · Datu lokal simulatuak"
    )

    st.markdown(
        f"""
    <div class="status-bar">
        <strong>🛠 Zerbitzuen egoera</strong>
        <span>
            ● {testua} · {len(makinak)} CNC
            {kpis["akatsak"]} CRITICA inferitu · UTC ebaketa: {READ_AS_OF}
        </span>
    </div>
    """,
        unsafe_allow_html=True,
    )


# =============================
# ORRI NAGUSIA
# =============================

orria = st.session_state.orria

if orria == "Hasiera":
    hasiera_erakutsi(
        kpi_txartelak=kpi_txartelak,
        egoera_zerbitzuak=egoera_zerbitzuak,
        telemetria_taula=telemetria_taula,
        historiko_grafikoa=historiko_grafikoa,
        azken_neurketak=azken_neurketak,
        makina_sarea=makina_sarea,
        egutegia=egutegia,
    )


elif orria == "Makinak":
    # Streamlit-ek inportatutako orriak memorian gordetzen ditu. Birkargatzeak
    # makinak.py-ko azken bertsioa berehala erabiltzea bermatzen du.
    makinak_orria = importlib.reload(makinak_orria)
    makinak_orria.makinak_erakutsi(
        makinak=makinak,
        uneko_makina=uneko_makina,
        makina_sarea=makina_sarea,
        historiko_grafikoa=historiko_grafikoa,
        azken_neurketak=azken_neurketak,
    )


elif orria == "Datuak":
    datuak_erakutsi(uneko_makina, kontsultatu, DATU_MODUA)


elif orria == "Abisuak":
    abisuak_erakutsi(makinak)


elif orria == "Ezarpenak":
    st.subheader("Ezarpenak")
    st.info(
        "DEMO: datuak simulatuak dira."
        if iturri_egoera == "demo"
        else "API prototipoaren datuak; CNC Guard integrazioa ez dago egiaztatuta."
    )

    st.write("API:", FASTAPI_HELBIDEA)
    st.write("Uneko gaia:", "Iluna" if iluna else "Argia")
    st.write("Konfiguratutako makinak:", len(makinak))
