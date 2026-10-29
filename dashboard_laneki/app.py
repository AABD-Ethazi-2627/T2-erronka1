
import base64
import importlib
import io
import os
from datetime import datetime, timezone

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import streamlit.components.v1 as components

from orriak.hasiera import hasiera_erakutsi
from orriak import makinak as makinak_orria
from orriak import abisuak as abisuak_orria
from orriak import datuak as datuak_orria


FASTAPI_HELBIDEA = "http://127.0.0.1:8000/api"

st.set_page_config(
    page_title="Laneki IoT",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================
# APLIKAZIOAREN EGOERA
# =============================

ORRI_BALIOZKOAK = {
    "Hasiera", "Makinak", "Datuak", "Abisuak", "Ezarpenak"
}

if "gai_iluna" not in st.session_state:
    url_gaia = st.query_params.get("gaia", "argia")
    st.session_state.gai_iluna = url_gaia == "iluna"

if "pastel_aktibatuta" not in st.session_state:
    st.session_state.pastel_aktibatuta = True



if "hautatutako_makina" not in st.session_state:
    st.session_state.hautatutako_makina = "CNC-004"

if "makina" in st.query_params:
    st.session_state.hautatutako_makina = st.query_params["makina"]

if "orria" not in st.session_state:
    url_orria = st.query_params.get("orria", "Hasiera")
    st.session_state.orria = (
        url_orria
        if url_orria in ORRI_BALIOZKOAK
        else "Hasiera"
    )
elif "orria" in st.query_params and st.query_params["orria"] in ORRI_BALIOZKOAK:
    st.session_state.orria = st.query_params["orria"]

if "menu_irekia" not in st.session_state:
    st.session_state.menu_irekia = True


# =============================
# PROBA-DATUAK / FASTAPI
# =============================

BERRIKUSPENA = {
    12, 15, 16, 20, 21, 27, 35, 38,
    39, 40, 41, 43, 46, 47, 48
}

def demo_datuak():
    import random

    makinak = []

    for i in range(1, 51):
        rng = random.Random(i * 123)

        egoera = (
            "Akatsa" if i == 4 else
            "Berrikusteko" if i in BERRIKUSPENA else
            "Normala"
        )

        makina = {
            "id": f"CNC-{i:03d}",
            "zenbakia": i,
            "tenperatura": round(rng.uniform(30, 39), 1),
            "rpm": rng.randint(1200, 1900),
            "torque": round(rng.uniform(22, 49), 1),
            "higadura": rng.randint(45, 240),
            "egoera": egoera
        }

        if i == 4:
            makina.update({
                "tenperatura": 36.3,
                "rpm": 1380,
                "torque": 47.6,
                "higadura": 246
            })

        makinak.append(makina)

    return makinak


@st.cache_data(ttl=5, show_spinner=False)
def kontsultatu(amaiera_puntua):
    try:
        erantzuna = requests.get(
            f"{FASTAPI_HELBIDEA}/{amaiera_puntua}",
            timeout=0.5
        )
        erantzuna.raise_for_status()
        return erantzuna.json()
    except (requests.RequestException, ValueError):
        return None


def makinak_lortu():
    datuak = kontsultatu("makinak")
    if isinstance(datuak, list) and len(datuak) == 50:
        return datuak, True
    return demo_datuak(), False


def kpiak_lortu(makinak):
    datuak = kontsultatu("kpis")
    if isinstance(datuak, dict) and "motak" in datuak:
        return datuak

    return {
        "operatiboak": sum(
            m["egoera"] != "Akatsa" for m in makinak
        ),
        "guztira": 50,
        "akatsak": sum(
            m["egoera"] == "Akatsa" for m in makinak
        ),
        "gertakariak": 15,
        "osasuna": 89,
        "tenperatura": 27.3,
        "motak": {"H": 10, "M": 25, "L": 15}
    }


def historikoa_lortu(kodea, makina):
    datuak = kontsultatu(f"historikoa/{kodea}")

    if isinstance(datuak, dict) and "Ordua" in datuak:
        return pd.DataFrame(datuak)

    import random
    rng = random.Random(makina["zenbakia"] * 100)

    orduak = [
        "06:00", "06:30", "07:00",
        "07:30", "08:00", "08:30"
    ]

    return pd.DataFrame({
        "Ordua": orduak,
        "Prozesu-tenperatura (°C)": [
            round(makina["tenperatura"] + rng.uniform(-2, 2), 1)
            for _ in orduak
        ],
        "Bihurdura-momentua (Nm)": [
            round(makina["torque"] + rng.uniform(-4, 4), 1)
            for _ in orduak
        ],
        "Erremintaren higadura (min)": [
            max(0, makina["higadura"] - (5 - i) * 4)
            for i in range(6)
        ]
    })


def aldiko_historikoak_lortu(kodea):
    """FastAPI: GET /api/historikoa/{kodea}/periodoak.

    Espero diren gakoak: astea, hilabetea eta sei_hilabetea. APIa oraindik
    erabilgarri ez badago, datuak.py-k simulazio-serieak sortzen ditu.
    """
    datuak = kontsultatu(f"historikoa/{kodea}/periodoak")
    return datuak if isinstance(datuak, dict) else None


# =============================
# CSS ETA GAIAK
# =============================

css_bidea = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "css", "styles.css"
)

if os.path.exists(css_bidea):
    with open(css_bidea, "r", encoding="utf-8") as fitxategia:
        st.markdown(
            f"<style>{fitxategia.read()}</style>",
            unsafe_allow_html=True
        )

logo_bidea = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "assets", "images", "logo_laneki.webp"
)

with open(logo_bidea, "rb") as logo_fitxategia:
    logo_base64 = base64.b64encode(
        logo_fitxategia.read()
    ).decode("ascii")

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
    kpi_ikono_kolorea = "#E6F2FF"
    kpi_ikono_atzeko_planoa = "rgba(248, 250, 252, 0.12)"
    egoera_gorria = "#754957"
    egoera_laranja = "#70623F"
    egoera_melokotoia = "#765748"
    egoera_urdina = "#45647D"
    egoera_berdea = "#3F6858"
    mapa_gorria = egoera_gorria
    mapa_laranja = egoera_laranja
    mapa_melokotoia = egoera_melokotoia
    mapa_urdina = egoera_urdina
    mapa_berdea = egoera_berdea
    alerta_kritikoa = "#754957"
    alerta_handia = "#765748"
    alerta_berrikustea = "#70623F"
    ertz_gorria = "#B97889"
    ertz_laranja = "#B39B57"
    ertz_melokotoia = "#B88469"
    ertz_urdina = "#7299BA"
    ertz_berdea = "#6B9C87"
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
    pastel_urdina = "#C5DCF3"
    pastel_arrosa = "#F1C9CF"
    pastel_izotza = "#D1E2EB"
    pastel_arbela = "#CFDCE8"
    pastel_berdea = "#C6E7D6"
    semantiko_testua = "#142A40"
    semantiko_bigarrena = "#475569"
    kpi_ikono_kolorea = "#153B5C"
    kpi_ikono_atzeko_planoa = "rgba(20, 42, 64, 0.08)"
    egoera_gorria = "#F7CDD2"
    egoera_laranja = "#F7E2AE"
    egoera_melokotoia = "#F4D1BC"
    egoera_urdina = "#C8DEF4"
    egoera_berdea = "#C8EAD8"
    mapa_gorria = "#EEAAB5"
    mapa_laranja = "#F3D989"
    mapa_melokotoia = "#F2BE9F"
    mapa_urdina = "#AFCFEE"
    mapa_berdea = "#A9DFC6"
    alerta_kritikoa = "#F5D1D6"
    alerta_handia = "#F6D9C4"
    alerta_berrikustea = "#F5E4B8"
    ertz_gorria = "#FCA7AF"
    ertz_laranja = "#FDE48A"
    ertz_melokotoia = "#FDC4A8"
    ertz_urdina = "#A8D1FA"
    ertz_berdea = "#A3E4C4"

gai_ikono_maskara = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
    "%3Ccircle cx='12' cy='12' r='4' fill='none' stroke='black' stroke-width='2'/%3E"
    "%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E"
    if iluna else
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
    "%3Cpath d='M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"
)
kanpai_ikono_maskara = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
    "%3Cpath d='M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"
)

st.markdown(f"""
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
    --kpi-icon-color: {kpi_ikono_kolorea};
    --kpi-icon-bg: {kpi_ikono_atzeko_planoa};
    --state-red-bg: {egoera_gorria};
    --state-amber-bg: {egoera_laranja};
    --state-orange-bg: {egoera_melokotoia};
    --state-blue-bg: {egoera_urdina};
    --state-green-bg: {egoera_berdea};
    --map-red-bg: {mapa_gorria};
    --map-amber-bg: {mapa_laranja};
    --map-orange-bg: {mapa_melokotoia};
    --map-blue-bg: {mapa_urdina};
    --map-green-bg: {mapa_berdea};
    --alert-critical-bg: {alerta_kritikoa};
    --alert-high-bg: {alerta_handia};
    --alert-review-bg: {alerta_berrikustea};
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
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    position: relative !important;
}}

.st-key-gaia_aldatu button [data-testid="stMarkdownContainer"] {{
    display: none !important;
}}

.st-key-gaia_aldatu button::before {{
    content: "";
    display: block;
    width: 25px;
    height: 25px;
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    background: currentColor;
    -webkit-mask: url("{gai_ikono_maskara}") center / contain no-repeat;
    mask: url("{gai_ikono_maskara}") center / contain no-repeat;
}}

.st-key-gaia_aldatu button:hover {{
    background: {"#31475B" if iluna else "#E3EDF5"} !important;
    border-color: #3976BD !important;
}}

.st-key-goiburu_abisua_aktibo button,
.st-key-goiburu_abisua_inaktibo button {{
    width: 38px !important;
    min-width: 38px !important;
    height: 36px !important;
    min-height: 36px !important;
    padding: 0 !important;
    border: 1px solid {ertza} !important;
    border-radius: 8px !important;
    background: {panela} !important;
    box-shadow: 0 2px 7px rgba(20, 42, 64, 0.10) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    position: relative !important;
}}
.st-key-goiburu_abisua_aktibo button [data-testid="stMarkdownContainer"],
.st-key-goiburu_abisua_inaktibo button [data-testid="stMarkdownContainer"] {{
    display: none !important;
}}
.st-key-goiburu_abisua_aktibo button::before,
.st-key-goiburu_abisua_inaktibo button::before {{
    content: "";
    width: 21px;
    height: 21px;
    background: currentColor;
    -webkit-mask: url("{kanpai_ikono_maskara}") center / contain no-repeat;
    mask: url("{kanpai_ikono_maskara}") center / contain no-repeat;
}}
.st-key-goiburu_abisua_inaktibo button,
.st-key-goiburu_abisua_aktibo button {{
    color: #F4B942 !important;
    border-color: {ertza} !important;
    background: {panela} !important;
}}
.st-key-goiburu_abisua_aktibo button::after {{
    content: "";
    position: absolute;
    top: 5px;
    right: 6px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #E63946;
    box-shadow: 0 0 0 2px {panela};
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
    background: var(--map-green-bg) !important;
    border: 1.5px solid {ertz_berdea} !important;
}}
div[class*="st-key-machine_normal_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_recommended_"] button {{
    background: var(--map-blue-bg) !important;
    border: 1.5px solid {ertz_urdina} !important;
}}
div[class*="st-key-machine_recommended_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_necessary_"] button {{
    background: var(--map-amber-bg) !important;
    border: 1.5px solid {ertz_laranja} !important;
}}
div[class*="st-key-machine_necessary_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_accelerated_"] button {{
    background: var(--map-orange-bg) !important;
    border: 1.5px solid {ertz_melokotoia} !important;
}}
div[class*="st-key-machine_accelerated_"] button p {{
    color: var(--semantic-text) !important;
}}

div[class*="st-key-machine_emergency_"] button {{
    background: var(--map-red-bg) !important;
    border: 1.5px solid {ertz_gorria} !important;
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
.state-normal {{ background: var(--map-green-bg) !important; border: 1px solid {ertz_berdea} !important; }}
.state-recommended {{ background: var(--map-blue-bg) !important; border: 1px solid {ertz_urdina} !important; }}
.state-necessary {{ background: var(--map-amber-bg) !important; border: 1px solid {ertz_laranja} !important; }}
.state-accelerated {{ background: var(--map-orange-bg) !important; border: 1px solid {ertz_melokotoia} !important; }}
.state-emergency {{ background: var(--map-red-bg) !important; border: 1px solid {ertz_gorria} !important; }}
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
""", unsafe_allow_html=True)


if st.button(
    "☰" if not st.session_state.menu_irekia else "‹",
    key="menu_toggle",
    help=(
        "Alboko menua erakutsi"
        if not st.session_state.menu_irekia
        else "Alboko menua ezkutatu"
    )
):
    st.session_state.menu_irekia = not st.session_state.menu_irekia
    st.rerun()


# =============================
# ALBOKO MENUA
# =============================

with st.sidebar:
    st.markdown(f"""
    <div class="sidebar-logo">
        <img
            src="data:image/webp;base64,{logo_base64}"
            alt="Laneki"
            class="sidebar-logo-image"
        >
        <div class="sidebar-sub">IoT Sistema</div>
    </div>
    """, unsafe_allow_html=True)

    aukerak = [
        ("🏠 Hasiera", "Hasiera"),
        ("🏭 Makinak", "Makinak"),
        ("📊 Datuak", "Datuak"),
        ("🔔 Abisuak", "Abisuak")
    ]

    for etiketa, orria in aukerak:
        mota = (
            "primary"
            if st.session_state.orria == orria
            else "secondary"
        )

        if st.button(
            etiketa,
            key=f"nav_{orria}",
            use_container_width=True,
            type=mota
        ):
            st.session_state.orria = orria
            st.query_params["orria"] = orria
            st.rerun()

    st.html("""
    <div class="sidebar-system-card" aria-label="Sistemaren egoera">
        <strong><i></i> Sistema aktiboa</strong>
        <span>50 makina konektatuta</span>
    </div>
    <div class="sidebar-user-card" aria-label="Saioa hasitako erabiltzailea">
        <div class="sidebar-user-avatar">AC</div>
        <div class="sidebar-user-info">
            <strong>Angie Criollo</strong>
            <span><i></i> Saioa hasita</span>
        </div>
        <div class="sidebar-user-menu" aria-hidden="true">⋮</div>
    </div>
    """)


# =============================
# DATU OROKORRAK
# =============================

makinak, api_aktibo = makinak_lortu()
kpis = kpiak_lortu(makinak)

kodea = st.session_state.hautatutako_makina
uneko_makina = next(
    (m for m in makinak if m["id"] == kodea),
    makinak[0]
)

historikoa = historikoa_lortu(
    uneko_makina["id"], uneko_makina
)

orain = datetime.now(timezone.utc)
data = orain.strftime("%Y-%m-%d")
ordua = orain.strftime("%H:%M UTC")
uneko_tenperatura = kpis.get("tenperatura", "--")


# =============================
# GOIBURUA
# =============================

abisuak_goiburua = st.session_state.orria == "Abisuak"
goiburu_klasea = " alerts-header-title" if abisuak_goiburua else ""
azpititulu_klasea = " alerts-header-subtitle" if abisuak_goiburua else ""
goiburu_testua = (
    "Abisuak eta lehentasunak"
    if abisuak_goiburua
    else "Makinen egoera eta datuak"
)
azpititulu_testua = (
    "Egoera okerrenetik onenera ordenatuta · "
    "geldialdi-kostua makina eta larritasun-mailaren arabera"
    if abisuak_goiburua
    else "CNC Prediktiboa"
)
abisua_duten_makinak = [
    makina for makina in makinak
    if bool(makina.get("alerta_activa", makina.get("abisua_aktibo", False)))
    or str(makina.get("egoera", "Normala")).strip().lower()
    not in {"normala", "normal", "ondo", "ok"}
]
abisu_kopurua = len(abisua_duten_makinak)

goiburu1, data_zutabea, abisu_zutabea, gai_zutabea = st.columns([4, 1.65, 0.25, 0.25])

with goiburu1:
    st.markdown(
        f'<div class="dashboard-title{goiburu_klasea}">'
        f'{goiburu_testua}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="dashboard-subtitle{azpititulu_klasea}">'
        f'{azpititulu_testua}'
        '</div>',
        unsafe_allow_html=True
    )

with data_zutabea:
    st.markdown(
        f'<div class="header-datetime">'
        f'<span>📅 {data}</span><span>🕒 {ordua}</span>'
        f'<span title="Uneko giro-tenperatura">🌡 {uneko_tenperatura} °C</span>'
        f'</div>',
        unsafe_allow_html=True
    )

with abisu_zutabea:
    abisu_etiketa = (
        f"{abisu_kopurua} makina abisuekin"
        if abisu_kopurua else "Ez dago abisurik"
    )
    if st.button(
        abisu_etiketa,
        key=("goiburu_abisua_aktibo" if abisu_kopurua else "goiburu_abisua_inaktibo"),
        help=abisu_etiketa,
    ):
        st.session_state.orria = "Abisuak"
        st.query_params["orria"] = "Abisuak"
        st.rerun()

with gai_zutabea:
    etiketa = "Cambiar a modo claro" if iluna else "Cambiar a modo oscuro"

    if st.button(
        etiketa,
        key="gaia_aldatu",
        help="Gai argia/iluna aldatu"
    ):
        st.session_state.gai_iluna = not iluna
        st.query_params["gaia"] = (
            "iluna" if st.session_state.gai_iluna else "argia"
        )
        st.rerun()


# =============================
# IKUSIZKO FUNTZIOAK
# =============================

def panel_izenburua(izenburu_testua, deskribapena=""):
    st.markdown(
        f'<div class="panel-heading">{izenburu_testua}</div>',
        unsafe_allow_html=True
    )

    if deskribapena:
        st.markdown(
            f'<div class="panel-description">'
            f'{deskribapena}</div>',
            unsafe_allow_html=True
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
        </svg>"""
    }

    txartelen_datuak = [
        {
            "klasea": "blue",
            "ikonoa": ikonoak["makina"],
            "izenburua": "Makina operatiboak",
            "balioa": f"{kpis['operatiboak']} / {kpis['guztira']}",
            "sub": "Uneko egoera"
        },
        {
            "klasea": "pink",
            "ikonoa": ikonoak["abisua"],
            "izenburua": "Akats aktiboak",
            "balioa": str(kpis["akatsak"]),
            "sub": f"{kpis['gertakariak']} gertakari historiko"
        },
        {
            "klasea": "ice",
            "ikonoa": ikonoak["osasuna"],
            "izenburua": "Bataz besteko osasuna",
            "balioa": f"{kpis['osasuna']}%",
            "sub": "Flotaren osasun-indizea"
        }
    ]

    for zutabea, datua in zip(zutabeak[:3], txartelen_datuak):
        with zutabea:
            st.markdown(f"""
            <div class="kpi-card kpi-{datua['klasea']}">
                <div class="kpi-heading">
                    <span class="kpi-icon">{datua['ikonoa']}</span>
                    <span>{datua['izenburua']}</span>
                </div>
                <div class="kpi-body">
                    <span class="kpi-number">{datua['balioa']}</span>
                    <span class="kpi-description">{datua['sub']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Eraztun-grafikoa CSS bidez, Plotly erabili gabe.
    # Telemetria-grafikoek Matplotlib eta Seaborn erabiltzen dituzte.
    with zutabeak[3]:
        h = kpis["motak"]["H"]
        m = kpis["motak"]["M"]
        l = kpis["motak"]["L"]
        total = max(h + m + l, 1)
        a = h / total * 100
        b = (h + m) / total * 100

        st.markdown(f"""
        <div class="kpi-card kpi-slate">
            <div class="kpi-heading">
                <span class="kpi-icon">{ikonoak['motak']}</span>
                <span>Makina motak</span>
            </div>
            <div class="kpi-donut-row">
                <div class="donut"
                     style="background:conic-gradient(
                        #4F83CC 0% {a}%,
                        #48AD85 {a}% {b}%,
                        #D9A72E {b}% 100%
                     );">
                    <div class="donut-center">
                        <strong>{total}</strong>
                        <small>CNC</small>
                    </div>
                </div>
                <div class="donut-legend">
                    <span><i class="legend-h"></i>H: {h}</span>
                    <span><i class="legend-m"></i>M: {m}</span>
                    <span><i class="legend-l"></i>L: {l}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with zutabeak[4]:
        st.markdown(f"""
        <div class="kpi-card kpi-green">
            <div class="kpi-heading">
                <span class="kpi-icon">{ikonoak['tenperatura']}</span>
                <span>Giro-tenperatura</span>
            </div>
            <div class="kpi-body">
                <span class="kpi-number">
                    {kpis['tenperatura']} °C
                </span>
                <span class="kpi-description">
                    Bataz besteko tenperatura
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)


def telemetria_taula():
    errenkadak_html = []

    for makina in makinak:
        egoera = makina["egoera"]
        higadura = makina["higadura"]

        if egoera == "Akatsa":
            errenkada_klasea = "telemetria-akatsa"
            egoera_klasea = "egoera-akatsa"
            egoera_ikonoa = "!"
        elif egoera == "Berrikusteko":
            errenkada_klasea = "telemetria-abisua"
            egoera_klasea = "egoera-abisua"
            egoera_ikonoa = "•"
        else:
            errenkada_klasea = ""
            egoera_klasea = "egoera-normala"
            egoera_ikonoa = "✓"

        if higadura >= 230:
            higadura_klasea = "higadura-handia"
        elif higadura >= 200:
            higadura_klasea = "higadura-ertaina"
        else:
            higadura_klasea = "higadura-txikia"

        makina_kodea = makina["id"].replace("CNC-", "M-")
        errenkadak_html.append(f"""
            <tr class="{errenkada_klasea}">
                <td>{makina_kodea}</td>
                <td>{makina['tenperatura']:.1f}</td>
                <td>{makina['rpm']}</td>
                <td><span class="higadura-marka {higadura_klasea}">{higadura}</span></td>
                <td>{makina['torque']:.1f}</td>
                <td><span class="egoera-marka {egoera_klasea}">{egoera_ikonoa}</span>{egoera}</td>
            </tr>
        """)

    csv_taula = pd.DataFrame([
        {
            "CNC": makina["id"].replace("CNC-", "M-"),
            "Tenp. (°C)": f'{makina["tenperatura"]:.1f}',
            "RPM": makina["rpm"],
            "Higadura (min)": makina["higadura"],
            "Torque": f'{makina["torque"]:.1f}',
            "Egoera": makina["egoera"],
        }
        for makina in makinak
    ]).to_csv(index=False).encode("utf-8-sig")
    csv_base64 = base64.b64encode(csv_taula).decode("ascii")
    telemetria_goiburua = azalera_leuna
    telemetria_hover = "#30465A" if iluna else "#F2F7FA"
    telemetria_akatsa = alerta_kritikoa
    telemetria_abisua = alerta_berrikustea
    telemetria_gorria = egoera_gorria if iluna else "#E94355"
    telemetria_horia = egoera_laranja if iluna else "#E5A636"
    telemetria_berdea = egoera_berdea if iluna else "#25B57A"
    telemetria_gorri_testua = ertz_gorria if iluna else "#E94355"
    telemetria_hori_testua = ertz_laranja if iluna else "#D68A00"
    telemetria_berde_testua = ertz_berdea if iluna else "#25B57A"

    components.html(f"""
    <!doctype html>
    <html lang="eu"><head><style>
        * {{ box-sizing: border-box; }}
        html, body {{ margin: 0; width: 100%; height: 100%; overflow: hidden; }}
        #telemetry-root {{
            position: relative; width: 100%; height: 100%; padding: 0;
            background: {panela}; color: {testua};
            font-family: Verdana, Arial, sans-serif; font-weight: 700;
        }}
        .telemetry-title {{ font-size: 16px; font-weight: 800; margin: 0 90px 8px 0; }}
        .telemetry-subtitle {{ font-size: 12px; font-weight: 500; margin: 0 90px 10px 0; color: {bigarren_mailakoa}; }}
        .telemetry-actions {{ position: absolute; top: 0; right: 0; z-index: 5; display: flex; gap: 7px; opacity: 0; pointer-events: none; transition: opacity .15s ease; }}
        #telemetry-root:hover .telemetry-actions,
        .telemetry-actions:focus-within {{ opacity: 1; pointer-events: auto; }}
        .telemetry-action {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 36px; height: 36px; padding: 0; border: 1px solid #3C4E60;
            border-radius: 7px; background: #111820; color: #FFFFFF;
            box-shadow: 0 2px 7px rgba(0,0,0,.24); text-decoration: none;
            font: 800 18px/1 Verdana, Arial, sans-serif; cursor: pointer;
        }}
        .telemetry-action:hover {{ background: #274A6B; }}
        .telemetry-table-wrap {{ height: 243px; overflow: auto; border: 1px solid {ertza}; border-radius: 7px; }}
        table {{ width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 13px; }}
        thead {{ position: sticky; top: 0; z-index: 2; background: {telemetria_goiburua}; }}
        th {{ height: 32px; padding: 3px 8px; text-align: center; font-weight: 800; line-height: 1; }}
        th:first-child, td:first-child {{ text-align: left; }}
        th small {{ display: block; margin-top: 5px; font-size: 10px; }}
        td {{ height: 31px; padding: 3px 8px; border-bottom: 1px solid {ertza}; text-align: right; white-space: nowrap; }}
        td:last-child {{ text-align: left; }}
        tbody tr:hover {{ background: {telemetria_hover}; }}
        tr.telemetria-akatsa {{ background: {telemetria_akatsa}; }}
        tr.telemetria-abisua {{ background: {telemetria_abisua}; }}
        .higadura-marka {{ display:inline-block; min-width:31px; padding:3px 5px; border-radius:4px; color:#FFF; text-align:center; }}
        .higadura-handia {{ background:{telemetria_gorria}; }} .higadura-ertaina {{ background:{telemetria_horia}; }} .higadura-txikia {{ background:{telemetria_berdea}; }}
        .egoera-marka {{ display:inline-block; margin-right:4px; font-weight:900; }}
        .egoera-akatsa {{ color:{telemetria_gorri_testua}; }} .egoera-abisua {{ color:{telemetria_hori_testua}; }} .egoera-normala {{ color:{telemetria_berde_testua}; }}
        #telemetry-root:fullscreen {{ padding: 24px; background: {panela}; }}
        #telemetry-root:fullscreen .telemetry-table-wrap {{ height: calc(100vh - 105px); }}
    </style></head><body>
    <div id="telemetry-root">
        <div class="telemetry-title">▣ Makinak · Telemetria</div>
        <div class="telemetry-subtitle">50 makinen neurketak</div>
        <div class="telemetry-actions">
            <button class="telemetry-action" type="button" title="Pantaila osoan ikusi"
                    aria-label="Pantaila osoan ikusi"
                    onclick="document.getElementById('telemetry-root').requestFullscreen()">&#x26F6;</button>
            <a class="telemetry-action" href="data:text/csv;base64,{csv_base64}"
               download="makinen_telemetria.csv" title="CSV deskargatu"
               aria-label="CSV deskargatu">&#x2B07;</a>
        </div>
        <div class="telemetry-table-wrap">
        <table>
            <thead><tr>
                <th>CNC</th><th>Tenp.<small>(°C)</small></th><th>RPM</th>
                <th>Higadura<small>(min)</small></th><th>Torque</th><th>Egoera</th>
            </tr></thead>
            <tbody>{''.join(errenkadak_html)}</tbody>
        </table>
        </div>
    </div>
    </body></html>
    """, height=320, scrolling=False)


def historiko_grafikoa():
    panel_izenburua(
        f"📉 {kodea} · Tenperatura, momentua eta higaduraren bilakaera"
    )

    aldagaiak = [
        ("Prozesu-tenperatura (°C)", "#2EA885", "Tenp. °C"),
        ("Bihurdura-momentua (Nm)", "#E5A636", "Momentua Nm"),
        ("Erremintaren higadura (min)", "#E56F7C", "Higadura min")
    ]

    sns.set_style("whitegrid")
    plt.rcParams.update({
        "font.family": "Verdana",
        "font.size": 11,
        "font.weight": "bold",
        "axes.labelweight": "bold",
    })
    fig, axes = plt.subplots(
        3, 1, figsize=(9, 4.5), sharex=True
    )

    fig.patch.set_facecolor(grafiko_atzeko_planoa)

    for ax, (eremua, kolorea, etiketa) in zip(
        axes, aldagaiak
    ):
        ax.set_facecolor(grafiko_atzeko_planoa)

        sns.lineplot(
            data=historikoa,
            x="Ordua",
            y=eremua,
            ax=ax,
            color=kolorea,
            marker="o",
            linewidth=2
        )

        ax.set_ylabel(
            etiketa,
            fontsize=10,
            color=testua,
            rotation=90,
            ha="center",
            va="center",
        )
        ax.yaxis.set_label_coords(-0.075, 0.5)
        ax.set_xlabel("")
        ax.tick_params(
            colors=testua, labelsize=10
        )
        ax.grid(True, linestyle="--", alpha=0.6, color=ertza)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["bottom", "left"]].set_color(ertza)

    axes[-1].tick_params(
        axis="x", rotation=0
    )
    fig.align_ylabels(axes)
    plt.tight_layout(pad=0.65)
    fig.subplots_adjust(
        left=0.09,
        right=0.985,
        top=0.98,
        bottom=0.12,
        hspace=0.18
    )
    irudi_bufferra = io.BytesIO()
    fig.savefig(
        irudi_bufferra,
        format="png",
        dpi=160,
        bbox_inches="tight",
        facecolor=grafiko_atzeko_planoa,
    )
    irudi_base64 = base64.b64encode(irudi_bufferra.getvalue()).decode("ascii")

    components.html(
        f"""
        <!doctype html>
        <html lang="eu">
        <head>
        <style>
            html, body {{ margin: 0; width: 100%; height: 100%; overflow: hidden; }}
            #chart-root {{
                position: relative; width: 100%; height: 100%;
                display: flex; flex-direction: column; align-items: stretch;
                justify-content: center;
                background: {grafiko_atzeko_planoa};
                font-family: Verdana, Arial, sans-serif;
            }}
            .chart-legend {{
                display: flex; align-items: center; justify-content: center;
                gap: 20px; flex: 0 0 auto; margin: 2px 58px 3px 8px;
                padding: 6px 10px; border: 1px solid {ertza}; border-radius: 8px;
                background: {azalera_leuna}; color: {testua};
                font-size: 11px; font-weight: 700; line-height: 1;
            }}
            .chart-legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
            .chart-legend i {{ width: 10px; height: 10px; border-radius: 50%; }}
            .chart-image-wrap {{ flex: 1 1 auto; min-height: 0; }}
            .chart-image-wrap img {{ width: 100%; height: 100%; object-fit: contain; }}
            .chart-actions {{
                position: absolute; top: 6px; right: 6px; z-index: 5;
                display: flex; gap: 7px; opacity: 0; pointer-events: none;
                transition: opacity .15s ease;
            }}
            #chart-root:hover .chart-actions,
            .chart-actions:focus-within {{ opacity: 1; pointer-events: auto; }}
            .chart-action {{
                display: inline-flex; align-items: center; justify-content: center;
                width: 36px; height: 36px; padding: 0;
                border: 1px solid #3C4E60; border-radius: 7px;
                background: #111820; color: #FFFFFF;
                box-shadow: 0 2px 7px rgba(0,0,0,.24);
                font: 800 18px/1 Verdana, Arial, sans-serif;
                text-decoration: none; cursor: pointer;
            }}
            .chart-action:hover {{ background: #274A6B; }}
            #chart-root:fullscreen {{ padding: 24px; box-sizing: border-box; }}
            #chart-root:fullscreen .chart-actions {{ opacity: 1; }}
        </style>
        </head>
        <body>
          <div id="chart-root">
            <div class="chart-legend" aria-label="Grafikoko koloreen azalpena">
              <span><i style="background:#2EA885"></i>Berdea: prozesu-tenperatura</span>
              <span><i style="background:#E5A636"></i>Laranja: momentua</span>
              <span><i style="background:#E56F7C"></i>Gorria: erremintaren higadura</span>
            </div>
            <div class="chart-image-wrap">
              <img src="data:image/png;base64,{irudi_base64}"
                   alt="{kodea} tenperatura, momentua eta higaduraren bilakaera">
            </div>
            <div class="chart-actions">
              <button class="chart-action" type="button"
                      title="Pantaila osoan ikusi" aria-label="Pantaila osoan ikusi"
                      onclick="document.getElementById('chart-root').requestFullscreen()">⛶</button>
              <a class="chart-action"
                 href="data:image/png;base64,{irudi_base64}"
                 download="{kodea}_erregistroen_bilakaera.png"
                 title="PNG deskargatu" aria-label="PNG deskargatu">↓</a>
            </div>
          </div>
        </body>
        </html>
        """,
        height=(310 if st.session_state.orria == "Datuak" else 285),
        scrolling=False,
    )
    plt.close(fig)


def azken_neurketak():
    panel_izenburua(
        f"📈 {kodea} · Azken neurketa"
    )

    elementuak = [
        ("Higadura", uneko_makina["higadura"], 300, "min"),
        ("Torque", uneko_makina["torque"], 100, "Nm"),
        ("RPM", uneko_makina["rpm"], 2000, ""),
        ("Tenp.", uneko_makina["tenperatura"], 50, "°C")
    ]

    for izenburua, balioa, erreferentzia, unitatea in elementuak:
        proportzioa = min(
            balioa / erreferentzia * 100, 100
        )

        kolorea = (
            "#E5B652" if izenburua == "Higadura"
            else "#48C2A5"
        )

        st.markdown(f"""
        <div class="sensor-row">
            <div class="sensor-heading">
                <span>{izenburua}</span>
                <strong>{balioa:g} {unitatea}</strong>
            </div>
            <div class="sensor-track">
                <div class="sensor-fill"
                     style="width:{proportzioa}%;
                            background:{kolorea};">
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.caption(
        "Barrak: demoko erreferentziekiko proportzioa "
        "(ez arrisku eredua)"
    )

    if uneko_makina["egoera"] == "Akatsa":
        st.html('<div style="background:#FFF1F2; border:1.5px solid #FDA4AF; color:#BE123C; border-radius:10px; padding:11px 14px; font-weight:800; font-size:12px; display:flex; align-items:center; justify-content:center; text-align:center; gap:8px; margin-top:10px;"><span>⚠️</span><span>Akats aktiboa — Berehalako berrikuspena</span></div>')
        pass
        pass
        pass
        pass
    elif uneko_makina["egoera"] == "Berrikusteko":
        st.html('<div style="background:#FFF7E6; border:1.5px solid #FDE68A; color:#B45309; border-radius:10px; padding:11px 14px; font-weight:800; font-size:12px; display:flex; align-items:center; justify-content:center; text-align:center; gap:8px; margin-top:10px;"><span>⚠️</span><span>Makina hau berrikusteko dago</span></div>')
    else:
        st.html('<div style="background:#F0FDF4; border:1.5px solid #86EFAC; color:#15803D; border-radius:10px; padding:11px 14px; font-weight:800; font-size:12px; display:flex; align-items:center; justify-content:center; text-align:center; gap:8px; margin-top:10px;"><span>✓</span><span>Makina egoera normalean</span></div>')


def makina_sarea():
    with st.container(key="machine_panel"):
        panel_izenburua(
            "Lantegiko mapa operatiboa",
            "Konfiguratutako kokapenak · 5 lerro · "
            "10 makina lerro bakoitzeko"
        )

        st.markdown("""
        <div class="machine-map-top">
            <strong>SARRERA / HARRERA</strong>
            <strong>BIDALKETA-EREMUA →</strong>
        </div>
        """, unsafe_allow_html=True)

        for errenkada in range(5):
            zutabeak = st.columns([0.78] + [1] * 10, gap="small")

            with zutabeak[0]:
                st.markdown(f"""
                <div class="machine-line-label">
                    <strong>{chr(65 + errenkada)} LERROA</strong>
                    <small>10 CNC</small>
                </div>
                """, unsafe_allow_html=True)

            for zutabea in range(10):
                indizea = errenkada * 10 + zutabea
                makina = makinak[indizea]
                zenbakia = makina["zenbakia"]
                makina_id = makina["id"]

                egoera = makina["egoera"]

                if egoera == "Akatsa":
                    klasea = "emergency"
                elif egoera == "Berrikusteko":
                    if makina["higadura"] >= 210:
                        klasea = "accelerated"
                    elif makina["higadura"] >= 160:
                        klasea = "necessary"
                    else:
                        klasea = "recommended"
                else:
                    klasea = "normal"

                hautatuta = (
                    makina_id ==
                    st.session_state.hautatutako_makina
                )

                with zutabeak[zutabea + 1]:
                    with st.container(
                        key=(
                            f"machine_{klasea}_{zenbakia}"
                            f"{'_selected' if hautatuta else ''}"
                        )
                    ):
                        etiketa = f"{zenbakia:02d}"

                        if st.button(
                            etiketa,
                            key=f"machine_button_{zenbakia}",
                            use_container_width=True,
                            help=f"{makina_id}: {egoera}"
                        ):
                            st.session_state.hautatutako_makina = (
                                makina_id
                            )
                            st.rerun()

        st.markdown(f"""
        <div class="machine-legend">
            <span><i class="state-normal"></i> Normala</span>
            <span><i class="state-recommended"></i> Gomendatua</span>
            <span><i class="state-necessary"></i> Beharrezkoa</span>
            <span><i class="state-accelerated"></i> Bizkortua</span>
            <span><i class="state-emergency"></i> Larrialdia</span>
            <span><i class="state-nodata"></i> Daturik gabe</span>
            <strong>Hautatua: {kodea}</strong>
        </div>
        """, unsafe_allow_html=True)


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
    st.caption(
        "Makina bakoitzaren azken berrikuspenetik "
        "kalkulatutako proposamena"
    )
    egutegi_taula()


def egutegia():
    izenburu_zutabea, zabaldu_zutabea, deskargatu_zutabea = st.columns(
        [3.5, 0.25, 0.25], gap="small"
    )

    with izenburu_zutabea:
        st.markdown(
            '<div class="calendar-heading">'
            '<strong>Aste honetako berrikuspen-egutegia</strong>'
            '<small>Makina bakoitzaren azken berrikuspenetik '
            'kalkulatutako proposamena</small></div>',
            unsafe_allow_html=True
        )

    with zabaldu_zutabea:
        ireki = st.button(
            "⛶",
            key="calendar_open",
            help="Asteko egutegia ireki"
        )

    with deskargatu_zutabea:
        egutegi_csv = (
            "Eguna,Ordua,Makina,Lana,Iraupena,Lehentasuna\n"
            "Larunbata,08:00,CNC-007,Ikuskapen mekanikoa,2 ordu,Bizkortua\n"
            "Larunbata,10:00,CNC-038,Erreminta,1 ordu,Beharrezkoa\n"
            "Larunbata,11:00,CNC-028,Prebentzioa,3 ordu,Teknikariaren berrikuspena\n"
            "Igandea,08:00,CNC-014,Berrikuspen termikoa,2 ordu,Gomendatua\n"
            "Igandea,10:00,CNC-042,Ikuskapena,1 ordu,Gomendatua\n"
            "Igandea,11:00,,Libre,,Erabilgarri\n"
        )
        st.download_button(
            "⬇",
            data=egutegi_csv.encode("utf-8-sig"),
            file_name="asteko_berrikuspen_egutegia.csv",
            mime="text/csv",
            key="calendar_download",
            help="Egutegia CSV formatuan deskargatu",
        )

    egutegi_taula()

    if ireki:
        asteko_egutegia_ireki()


def egoera_zerbitzuak():
    testua = (
        "Datu-zerbitzua konektatuta"
        if api_aktibo
        else "Datu lokal simulatuak"
    )

    st.markdown(f"""
    <div class="status-bar">
        <strong>🛠 ZERBITZUEN EGOERA</strong>
        <span>
            ● {testua} 50 CNC 
            {kpis['akatsak']} akats aktibo · {ordua}
        </span>
    </div>
    """, unsafe_allow_html=True)


# =============================
# ORRI NAGUSIA
# =============================

orria = st.session_state.orria

if orria == "Hasiera":
    st.html('<span class="hasiera-page-marker" aria-hidden="true"></span>')
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
    st.html('<span class="makinak-page-marker" aria-hidden="true"></span>')
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
    st.html('<span class="datuak-page-marker" aria-hidden="true"></span>')
    datuak_orria = importlib.reload(datuak_orria)
    datuak_orria.datuak_erakutsi(
        makina=uneko_makina,
        makinak=makinak,
        historikoen_kargatzailea=aldiko_historikoak_lortu,
    )

elif orria == "Abisuak":
    abisuak_orria = importlib.reload(abisuak_orria)
    abisuak_orria.abisuak_erakutsi(makinak)


elif orria == "Ezarpenak":
    st.subheader("Ezarpenak")
    st.info(
        "Uneko datuak simulatuak dira. "
        "CNC sentsoreekiko behin betiko konexioa "
        "aurrerago egingo da."
    )

    st.write("API:", FASTAPI_HELBIDEA)
    st.write(
        "Uneko gaia:",
        "Iluna" if iluna else "Argia"
    )
    st.write("Konfiguratutako makinak:", len(makinak))
