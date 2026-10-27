"""Makinen galeria, egoera-koloreak, sortutako argazkiak eta neurketak erakusteko orria."""

from base64 import b64encode
from collections.abc import Callable
from pathlib import Path
from typing import Any

import streamlit as st
from domain import gallery_machine

Osagaia = Callable[[], None]

ARGAZKI_DIREKTORIOA = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "images"
    / "cnc"
)

@st.cache_data(show_spinner=False)
def _makinaren_uri_datuak(zenbakia: int) -> str:
    """Makina baten argazkia base64 URI moduan prestatu."""
    argazki_bidea = ARGAZKI_DIREKTORIOA / f"cnc-{zenbakia:03d}.webp"
    if argazki_bidea.exists():
        edukia = b64encode(argazki_bidea.read_bytes()).decode("ascii")
        return f"data:image/webp;base64,{edukia}"
    return ""


def _makina_datuak(makina: dict[str, Any]) -> dict[str, Any]:
    """Iturriaren neurketak eta egoera aldatu gabe aurkeztu."""
    return gallery_machine(makina)


def _estiloak_txertatu() -> None:
    """Makinen orrirako CSS estilo zehatzak injektatu."""
    st.html("""
    <style>
    /* KPI Txartelak goialdean */
    .makina-kpi-container {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }
    .makina-kpi-box {
        background: var(--panel-bg, #ffffff);
        border: 1px solid var(--panel-border, #E2E8F0);
        border-radius: 14px;
        padding: 14px 18px;
        position: relative;
        overflow: hidden;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .makina-kpi-box:nth-child(1) {
        background: var(--pastel-slate, #E5EDF5);
        border-color: #9FB3C8;
    }
    .makina-kpi-box:nth-child(2) {
        background: var(--state-red-bg, #FFF1F2);
        border-color: #FCA5A5;
    }
    .makina-kpi-box:nth-child(3) {
        background: var(--state-amber-bg, #FFF7E6);
        border-color: #FBBF24;
    }
    .makina-kpi-box:nth-child(4) {
        background: var(--state-blue-bg, #EFF6FF);
        border-color: #93C5FD;
    }
    .makina-kpi-box:nth-child(5) {
        background: var(--state-green-bg, #F0FDF4);
        border-color: #86EFAC;
    }
    .makina-kpi-box .kpi-label {
        font-size: 0.95rem;
        font-weight: 800;
        color: var(--secondary-text, #64748B);
        margin-bottom: 4px;
    }
    .makina-kpi-box .kpi-number {
        width: 100%;
        font-size: 2.3rem;
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 4px;
        text-align: center;
    }
    .makina-kpi-box .kpi-sub {
        font-size: 0.88rem;
        color: var(--secondary-text, #94A3B8);
        font-weight: 700;
    }
    .kpi-accent-circle {
        display: none;
    }

    /* Galeria (Ezkerreko zutabea) */
    .gallery-outer-card {
        background: transparent;
        border: 0;
        padding: 8px 4px 0;
        box-shadow: none;
        margin: 0;
    }
    .st-key-makina_gallery_panel {
        background: var(--panel-bg, #FFFFFF) !important;
        border: 1px solid var(--panel-border, #E2E8F0) !important;
        border-radius: 14px !important;
        padding: 14px 16px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
        min-height: calc(100vh - 40px) !important;
    }
    .gallery-head-row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 2px;
    }
    .gallery-head-title {
        font-size: 1.25rem;
        font-weight: 800;
        color: var(--main-text, #0F172A);
    }
    .gallery-head-count {
        font-size: 0.86rem;
        color: var(--secondary-text, #64748B);
        font-weight: 600;
    }
    .gallery-head-sub {
        font-size: 0.82rem;
        color: var(--secondary-text, #64748B);
        margin-bottom: 12px;
    }

    /* Txartelen zerrenda scrollable */
    .gallery-scroll-list {
        height: calc(100vh - 390px);
        min-height: 480px;
        max-height: none;
        overflow-y: auto;
        padding-right: 6px;
        margin: 10px 0;
    }
    .gallery-scroll-list::-webkit-scrollbar {
        width: 6px;
    }
    .gallery-scroll-list::-webkit-scrollbar-thumb {
        background: #CBD5E1;
        border-radius: 4px;
    }

    .gallery-cards-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
    }

    /* Ezkerreko makina-txartela */
    .cnc-item-card {
        display: block;
        text-decoration: none !important;
        border-radius: 10px;
        padding: 12px 14px;
        transition: all 0.18s ease-in-out;
        cursor: pointer;
        position: relative;
        background: #ffffff;
    }
    .cnc-item-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(0,0,0,0.07);
    }
    .cnc-item-card.hautatuta {
        outline: 2.5px solid #2563EB !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.22), 0 6px 14px rgba(0,0,0,0.08) !important;
    }

    /* Ezkerreko txartelen egoera-koloreak */
    .cnc-item-card.card-larria {
        border: 1.5px solid #FCA5A5 !important;
        background: var(--state-red-bg, #FFF1F2) !important;
        border-left: 4px solid #DE4651 !important;
    }
    .cnc-item-card.card-ertaina {
        border: 1.5px solid #FDE68A !important;
        background: var(--state-amber-bg, #FFF7E6) !important;
        border-left: 4px solid #D97706 !important;
    }
    .cnc-item-card.card-arina {
        border: 1.5px solid #BFDBFE !important;
        background: var(--state-blue-bg, #EFF6FF) !important;
        border-left: 4px solid #2563EB !important;
    }
    .cnc-item-card.card-normala {
        border: 1.5px solid #BBF7D0 !important;
        background: var(--state-green-bg, #F0FDF4) !important;
        border-left: 4px solid #16A34A !important;
    }

    .cnc-card-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .cnc-card-id-box {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .cnc-card-thumb {
        width: 38px;
        height: 38px;
        border-radius: 6px;
        object-fit: cover;
        border: 1px solid rgba(0,0,0,0.08);
        background: #F1F5F9;
    }
    .cnc-card-title {
        font-size: 0.98rem;
        font-weight: 800;
        color: var(--semantic-text, #0F172A);
    }
    .cnc-card-badge {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 5px;
    }

    .cnc-card-metric-row {
        display: flex;
        justify-content: space-between;
        font-size: 0.78rem;
        color: var(--semantic-muted, #475569);
        margin-bottom: 3px;
    }
    .cnc-card-metric-row span:last-child {
        font-weight: 800;
        color: var(--semantic-text, #0F172A);
    }

    .cnc-card-alert {
        font-size: 0.76rem;
        font-weight: 700;
        margin-top: 6px;
        margin-bottom: 2px;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .cnc-card-loc {
        font-size: 0.72rem;
        color: var(--semantic-muted, #64748B);
        font-weight: 500;
    }

    /* Eskuin-panela: hautatutako makina */
    .makina-detail-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 12px 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
        margin-bottom: 0;
        box-sizing: border-box;
        color: var(--semantic-text, #0F172A);
    }

    /* Eskuin-panelaren egoera-koloreak */
    .makina-detail-card.detail-larria {
        border: 2px solid #DE4651 !important;
        background: var(--state-red-bg, #FFF1F2) !important;
        box-shadow: 0 4px 20px rgba(222, 70, 81, 0.14) !important;
    }
    .makina-detail-card.detail-ertaina {
        border: 2px solid #D97706 !important;
        background: var(--state-amber-bg, #FFF7E6) !important;
        box-shadow: 0 4px 20px rgba(217, 119, 6, 0.14) !important;
    }
    .makina-detail-card.detail-arina {
        border: 2px solid #2563EB !important;
        background: var(--state-blue-bg, #EFF6FF) !important;
        box-shadow: 0 4px 20px rgba(37, 99, 235, 0.14) !important;
    }
    .makina-detail-card.detail-normala {
        border: 2px solid #16A34A !important;
        background: var(--state-green-bg, #F0FDF4) !important;
        box-shadow: 0 4px 20px rgba(22, 163, 74, 0.14) !important;
    }

    .detail-tag {
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        color: #2563EB;
        margin-bottom: 2px;
    }
    .detail-heading-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .detail-title {
        font-size: 1.85rem;
        font-weight: 800;
        color: var(--semantic-text, #0F172A);
        line-height: 1.1;
    }
    .detail-badge {
        font-size: 0.8rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 6px;
    }

    /* Argazki nagusia (sortutako WebP) */
    .detail-photo-wrapper {
        width: 100%;
        background: var(--detail-surface, #F8FAFC);
        border: 1px solid var(--detail-border, #E2E8F0);
        border-radius: 12px;
        padding: 6px;
        text-align: center;
        margin-bottom: 6px;
    }
    .detail-photo-img {
        width: 100%;
        max-height: 145px;
        object-fit: contain;
        border-radius: 8px;
        display: block;
        margin: 0 auto;
    }

    .detail-loc-box {
        margin-bottom: 7px;
    }
    .detail-loc-box strong {
        font-size: 0.85rem;
        color: var(--semantic-text, #1E293B);
    }
    .detail-loc-box small {
        display: block;
        font-size: 0.76rem;
        color: var(--semantic-muted, #64748B);
        margin-top: 1px;
    }

    /* 4 Metrika (2x2) */
    .detail-metrics-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 7px;
        margin-bottom: 7px;
    }
    .detail-metric-card {
        background: var(--detail-surface, #F8FAFC);
        border: 1px solid var(--detail-border, #E2E8F0);
        border-radius: 10px;
        padding: 7px 10px;
    }
    .detail-metric-header {
        font-size: 0.72rem;
        color: var(--semantic-muted, #64748B);
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 4px;
        margin-bottom: 2px;
    }
    .detail-metric-val {
        font-size: 1.25rem;
        font-weight: 800;
        color: var(--semantic-text, #0F172A);
    }

    /* Informazio-fitxa (2x2) */
    .detail-info-title {
        font-size: 0.88rem;
        font-weight: 800;
        color: var(--semantic-text, #0F172A);
        margin-bottom: 6px;
    }
    .detail-info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        margin-bottom: 7px;
    }
    .detail-info-card {
        background: var(--detail-surface, #F8FAFC);
        border: 1px solid var(--detail-border, #E2E8F0);
        border-radius: 8px;
        padding: 6px 9px;
    }
    .detail-info-card:last-child:nth-child(odd) {
        grid-column: 1 / -1;
    }
    .detail-info-card small {
        display: block;
        font-size: 0.7rem;
        color: var(--semantic-muted, #64748B);
        margin-bottom: 2px;
    }
    .detail-info-card strong {
        font-size: 0.82rem;
        color: var(--semantic-text, #0F172A);
    }

    /* Gomendioa / Lehentasuna */
    .detail-recom-box {
        border-radius: 10px;
        padding: 8px 12px;
        margin-bottom: 4px;
    }
    .detail-recom-title {
        font-size: 0.82rem;
        font-weight: 800;
        margin-bottom: 2px;
    }
    .detail-recom-desc {
        font-size: 0.76rem;
        color: var(--semantic-muted, #334155);
    }
    .detail-larria .detail-recom-box { background: var(--state-red-bg, #FFF1F2) !important; }
    .detail-ertaina .detail-recom-box { background: var(--state-amber-bg, #FFF7E6) !important; }
    .detail-arina .detail-recom-box { background: var(--state-blue-bg, #EFF6FF) !important; }
    .detail-normala .detail-recom-box { background: var(--state-green-bg, #F0FDF4) !important; }

    .footer-note {
        font-size: 0.72rem;
        color: var(--secondary-text, #94A3B8);
        margin-top: 8px;
    }

    /* Iragazkiak: gai argirako kolore argiak eta testu irakurgarria */
    .st-key-flt_guztiak button,
    .st-key-flt_larriak button,
    .st-key-flt_ertainak button,
    .st-key-flt_arinak button,
    .st-key-flt_normalak button {
        min-height: 42px !important;
        border-width: 1.5px !important;
        box-shadow: none !important;
    }
    .st-key-flt_guztiak button { background: var(--surface-muted, #F1F5F9) !important; border-color: var(--panel-border, #CBD5E1) !important; }
    .st-key-flt_larriak button { background: var(--state-red-bg, #FFF1F2) !important; border-color: #FDA4AF !important; }
    .st-key-flt_ertainak button { background: var(--state-amber-bg, #FFF7E6) !important; border-color: #FBBF24 !important; }
    .st-key-flt_arinak button { background: var(--state-blue-bg, #EFF6FF) !important; border-color: #93C5FD !important; }
    .st-key-flt_normalak button { background: var(--state-green-bg, #F0FDF4) !important; border-color: #86EFAC !important; }

    .st-key-flt_guztiak button p,
    .st-key-flt_larriak button p,
    .st-key-flt_ertainak button p,
    .st-key-flt_arinak button p,
    .st-key-flt_normalak button p {
        color: #0F172A !important;
        font-size: 0.94rem !important;
        font-weight: 800 !important;
    }
    .st-key-flt_larriak button p,
    .st-key-flt_ertainak button p,
    .st-key-flt_arinak button p,
    .st-key-flt_normalak button p { color: var(--semantic-text, #0F172A) !important; }
    .st-key-flt_guztiak button p { color: var(--main-text, #0F172A) !important; }

    .st-key-flt_guztiak button[kind="primary"],
    .st-key-flt_larriak button[kind="primary"],
    .st-key-flt_ertainak button[kind="primary"],
    .st-key-flt_arinak button[kind="primary"],
    .st-key-flt_normalak button[kind="primary"] {
        border-width: 2px !important;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.16) !important;
    }

    .st-key-makina_bilaketa input {
        min-height: 42px !important;
        background: var(--input-bg, #FFFFFF) !important;
        border: 1.5px solid var(--panel-border, #CBD5E1) !important;
        color: var(--main-text, #0F172A) !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
    }
    .st-key-makina_bilaketa input::placeholder {
        color: var(--secondary-text, #475569) !important;
        opacity: 1 !important;
        font-weight: 700 !important;
    }

    /* Beheko nabigazioa: aplikazioaren gai argi/ilunera egokitua. */
    .st-key-btn_aurrekoa button,
    .st-key-btn_hurrengoa button {
        min-height: 40px !important;
        background: var(--panel-bg, #FFFFFF) !important;
        border: 1.5px solid var(--panel-border, #CBD5E1) !important;
        color: var(--main-text, #0F172A) !important;
        box-shadow: none !important;
    }
    .st-key-btn_aurrekoa button p,
    .st-key-btn_hurrengoa button p {
        color: var(--main-text, #0F172A) !important;
        font-size: 0.92rem !important;
        font-weight: 800 !important;
    }
    .st-key-btn_aurrekoa button:hover,
    .st-key-btn_hurrengoa button:hover {
        background: var(--app-bg, #EAF0F5) !important;
        border-color: #3976BD !important;
    }
    @media (max-width: 900px) {
        .st-key-makina_gallery_panel,
        .makina-detail-card {
            min-height: auto !important;
        }
    }
    </style>
    """)


def makinak_erakutsi(
    makinak: list[dict[str, Any]],
    uneko_makina: dict[str, Any],
    makina_sarea: Osagaia | None = None,
    historiko_grafikoa: Osagaia | None = None,
    azken_neurketak: Osagaia | None = None,
) -> None:
    """Makinen galeria modernoa, sortutako argazkiekin eta egoera-koloreekin."""

    _estiloak_txertatu()

    # Datu guztiak prestatu
    guztiak_datuekin = [_makina_datuak(m) for m in makinak]
    uneko_id = st.session_state.hautatutako_makina
    uneko_datuak = next(
        (m for m in guztiak_datuekin if m["id"] == uneko_id),
        guztiak_datuekin[0]
    )

    # Zenbaketak
    kopuru_guztira = len(guztiak_datuekin)
    kopuru_larriak = sum(m["egoera_mota"] == "Larria" for m in guztiak_datuekin)
    kopuru_ertainak = sum(m["egoera_mota"] == "Ertaina" for m in guztiak_datuekin)
    kopuru_arinak = sum(m["egoera_mota"] == "Arina" for m in guztiak_datuekin)
    kopuru_normalak = sum(m["egoera_mota"] == "Normala" for m in guztiak_datuekin)

    # ==========================================
    # 1. GOIKO KPI TXARTELAK (5 TXARTEL)
    # ==========================================
    st.html(f"""
    <div class="makina-kpi-container">
        <!-- 1. Guztira -->
        <div class="makina-kpi-box">
            <div class="kpi-label">Makina guztira</div>
            <div class="kpi-number" style="color:var(--main-text, #0F172A);">{kopuru_guztira}</div>
            <div class="kpi-sub">{kopuru_guztira} makina iturrian</div>
            <div class="kpi-accent-circle" style="background:#EBF3FC;"></div>
        </div>
        <!-- 2. Larriak -->
        <div class="makina-kpi-box">
            <div class="kpi-label">Akatsa</div>
            <div class="kpi-number" style="color:#DE4651;">{kopuru_larriak}</div>
            <div class="kpi-sub">Berehalako arreta</div>
            <div class="kpi-accent-circle" style="background:#FCE8E6;"></div>
        </div>
        <!-- 3. Ertainak -->
        <div class="makina-kpi-box">
            <div class="kpi-label">Berrikusteko</div>
            <div class="kpi-number" style="color:#D97706;">{kopuru_ertainak}</div>
            <div class="kpi-sub">Berrikuspena behar dute</div>
            <div class="kpi-accent-circle" style="background:#FEF3C7;"></div>
        </div>
        <!-- 4. Arinak -->
        <div class="makina-kpi-box">
            <div class="kpi-label">Beste egoerak</div>
            <div class="kpi-number" style="color:#2563EB;">{kopuru_arinak}</div>
            <div class="kpi-sub">Jarraipena</div>
            <div class="kpi-accent-circle" style="background:#E0E7FF;"></div>
        </div>
        <!-- 5. Normala -->
        <div class="makina-kpi-box">
            <div class="kpi-label">Egoera normala</div>
            <div class="kpi-number" style="color:#16A34A;">{kopuru_normalak}</div>
            <div class="kpi-sub">Arazorik gabe</div>
            <div class="kpi-accent-circle" style="background:#DCFCE7;"></div>
        </div>
    </div>
    """)

    # ==========================================
    # 2. ZUTABE NAGUSIAK (EZKERRA ETA ESKUINA)
    # ==========================================
    zutabe_ezkerra, zutabe_eskuina = st.columns([1.52, 1.0], gap="medium")

    # ------------------------------------------
    # EZKERREKO ZUTABEA: MAKINEN GALERIA
    # ------------------------------------------
    with zutabe_ezkerra, st.container(key="makina_gallery_panel", border=False):
        if "makina_iragazkia" not in st.session_state:
            st.session_state.makina_iragazkia = "Guztiak"

        # Iragazkien botoiak eta bilaketa
        c_f1, c_f2, c_f3, c_f4 = st.columns([1.1, 1.1, 1.1, 1.1])
        with c_f1:
            if st.button(
                f"Guztiak {kopuru_guztira}",
                key="flt_guztiak",
                width="stretch",
                type="primary" if st.session_state.makina_iragazkia == "Guztiak" else "secondary"
            ):
                st.session_state.makina_iragazkia = "Guztiak"
                st.rerun()
        with c_f2:
            if st.button(
                f"Larriak {kopuru_larriak}",
                key="flt_larriak",
                width="stretch",
                type="primary" if st.session_state.makina_iragazkia == "Larriak" else "secondary"
            ):
                st.session_state.makina_iragazkia = "Larriak"
                st.rerun()
        with c_f3:
            if st.button(
                f"Ertainak {kopuru_ertainak}",
                key="flt_ertainak",
                width="stretch",
                type="primary" if st.session_state.makina_iragazkia == "Ertainak" else "secondary"
            ):
                st.session_state.makina_iragazkia = "Ertainak"
                st.rerun()
        with c_f4:
            if st.button(
                f"Arinak {kopuru_arinak}",
                key="flt_arinak",
                width="stretch",
                type="primary" if st.session_state.makina_iragazkia == "Arinak" else "secondary"
            ):
                st.session_state.makina_iragazkia = "Arinak"
                st.rerun()

        c_f5, c_search = st.columns([1.2, 3.2])
        with c_f5:
            if st.button(
                f"● Normalak {kopuru_normalak}",
                key="flt_normalak",
                width="stretch",
                type="primary" if st.session_state.makina_iragazkia == "Normalak" else "secondary"
            ):
                st.session_state.makina_iragazkia = "Normalak"
                st.rerun()
        with c_search:
            bilaketa = st.text_input(
                "Bilatu",
                placeholder="⌕ Bilatu CNC-001...",
                label_visibility="collapsed",
                key="makina_bilaketa"
            )

        # Makinen zerrenda iragazi
        hautatutako_flt = st.session_state.makina_iragazkia
        zerrenda = guztiak_datuekin

        if hautatutako_flt == "Larriak":
            zerrenda = [m for m in zerrenda if m["egoera_mota"] == "Larria"]
        elif hautatutako_flt == "Ertainak":
            zerrenda = [m for m in zerrenda if m["egoera_mota"] == "Ertaina"]
        elif hautatutako_flt == "Arinak":
            zerrenda = [m for m in zerrenda if m["egoera_mota"] == "Arina"]
        elif hautatutako_flt == "Normalak":
            zerrenda = [m for m in zerrenda if m["egoera_mota"] == "Normala"]

        if bilaketa.strip():
            hitza = bilaketa.strip().upper()
            zerrenda = [m for m in zerrenda if hitza in m["id"].upper()]

        # Txartelen HTML edukia sortu
        txartelak_html = []
        gai_parametroa = (
            "iluna" if st.session_state.get("gai_iluna", False) else "argia"
        )
        for m in zerrenda:
            hautatuta_klasea = " hautatuta" if m["id"] == uneko_id else ""
            argazki_uri = _makinaren_uri_datuak(m["zenbakia"])

            txartelak_html.append(f"""
            <a href="?orria=Makinak&makina={m['id']}&gaia={gai_parametroa}" target="_self"
               class="cnc-item-card card-{m['klasea']}{hautatuta_klasea}">
                <div class="cnc-card-top">
                    <div class="cnc-card-id-box">
                        <img class="cnc-card-thumb" src="{argazki_uri}" alt="{m['id']}" loading="lazy"/>
                        <span class="cnc-card-title">{m['id']}</span>
                    </div>
                    <span class="cnc-card-badge"
                          style="background:{m['badge_bg']}; color:{m['badge_text']};">
                        {m['egoera_mota']}
                    </span>
                </div>
                <div class="cnc-card-metric-row">
                    <span>Tenperatura</span>
                    <span>{m['tenperatura']:.1f} °C</span>
                </div>
                <div class="cnc-card-metric-row">
                    <span>Abiadura</span>
                    <span>{m['rpm']} RPM</span>
                </div>
                <div class="cnc-card-alert" style="color:{m['kolorea']};">
                    <span>{m['abisu_ikonoa']}</span>
                    <span>{m['abisua']}</span>
                </div>
                <div class="cnc-card-loc">{m['kokapena']}</div>
            </a>
            """)

        cards_content = "".join(txartelak_html) if txartelak_html else "<p style='color:#64748B; padding:15px;'>Ez da makinarik aurkitu irizpide hauekin.</p>"

        st.html(f"""
        <div class="gallery-outer-card">
            <div class="gallery-head-row">
                <span class="gallery-head-title">Makinen galeria</span>
                <span class="gallery-head-count">{len(zerrenda)} makina</span>
            </div>
            <div class="gallery-head-sub">Hautatu makina bat datu osoak ikusteko</div>
            <div class="gallery-scroll-list">
                <div class="gallery-cards-grid">
                    {cards_content}
                </div>
            </div>
        </div>
        """)

    # ------------------------------------------
    # ESKUINEKO ZUTABEA: HAUTATUTAKO MAKINA
    # ------------------------------------------
    with zutabe_eskuina:
        uneko_argazkia = _makinaren_uri_datuak(uneko_datuak["zenbakia"])

        st.html(f"""
        <div class="makina-detail-card detail-{uneko_datuak['klasea']}">
            <div class="detail-tag" style="color:{uneko_datuak['kolorea']};">HAUTATUTAKO MAKINA</div>
            <div class="detail-heading-row">
                <span class="detail-title">{uneko_datuak['id']}</span>
                <span class="detail-badge"
                      style="background:{uneko_datuak['badge_bg']}; color:{uneko_datuak['badge_text']}; border: 1px solid {uneko_datuak['border_kolorea']};">
                    ▪ {uneko_datuak['egoera_mota']}
                </span>
            </div>

            <!-- Sortutako WebP argazkia -->
            <div class="detail-photo-wrapper" style="border-color:{uneko_datuak['border_kolorea']};">
                <img class="detail-photo-img" src="{uneko_argazkia}" alt="{uneko_datuak['id']} makinaren argazkia" />
            </div>

            <div class="detail-loc-box">
                <strong>Enpresako kokapena:</strong> {uneko_datuak['kokapena']}<br/>
                <small>Produkzio-eremua · CNC gunea</small>
            </div>

            <!-- 4 Metrika nagusiak (2x2) -->
            <div class="detail-metrics-grid">
                <div class="detail-metric-card">
                    <div class="detail-metric-header">🌡 Tenperatura</div>
                    <div class="detail-metric-val">{uneko_datuak['tenperatura']:.1f} °C</div>
                </div>
                <div class="detail-metric-card">
                    <div class="detail-metric-header">⚙ Abiadura</div>
                    <div class="detail-metric-val">{uneko_datuak['rpm']} RPM</div>
                </div>
                <div class="detail-metric-card">
                    <div class="detail-metric-header">⟳ Momentua</div>
                    <div class="detail-metric-val">{uneko_datuak['torque']:.1f} Nm</div>
                </div>
                <div class="detail-metric-card">
                    <div class="detail-metric-header">🕒 Higadura</div>
                    <div class="detail-metric-val">{uneko_datuak['higadura']} min</div>
                </div>
            </div>

            <!-- Informazio-fitxa (2x2) -->
            <div class="detail-info-title">Makinaren informazioa</div>
            <div class="detail-info-grid">
                <div class="detail-info-card">
                    <small>Azken matxura noiz gertatu zen</small>
                    <strong>{uneko_datuak['azken_matxura']}</strong>
                </div>
                <div class="detail-info-card">
                    <small>Huts egindako osagaia</small>
                    <strong>{uneko_datuak['huts_egindako_osagaia']}</strong>
                </div>
                <div class="detail-info-card">
                    <small>Geldialdiaren iraupena</small>
                    <strong>{uneko_datuak['geldialdiaren_iraupena']}</strong>
                </div>
                <div class="detail-info-card">
                    <small>Hurrengo berrikuspena</small>
                    <strong>{uneko_datuak['hurrengo_berrikuspena']}</strong>
                </div>
                <div class="detail-info-card">
                    <small>Fabrikazio-urtea</small>
                    <strong>{uneko_datuak['fabrikazio_urtea']}</strong>
                </div>
            </div>

            <!-- Gomendio-kutxa -->
            <div class="detail-recom-box"
                 style="background:{uneko_datuak['bg_kolorea']}; border: 1.5px solid {uneko_datuak['border_kolorea']};">
                <div class="detail-recom-title" style="color:{uneko_datuak['kolorea']};">
                    {uneko_datuak['abisu_ikonoa']} Lehentasunezko berrikuspena
                </div>
                <div class="detail-recom-desc">
                    {uneko_datuak['ekintza']}
                </div>
            </div>
        </div>
        """)

        # Nabigazio botoiak: ← Aurrekoa  eta  Hurrengoa →
        col_prev, col_next = st.columns(2)
        uneko_indizea = next(
            (i for i, m in enumerate(guztiak_datuekin) if m["id"] == uneko_id),
            0
        )

        with col_prev:
            if st.button("← Aurrekoa", key="btn_aurrekoa", width="stretch"):
                aurreko_idx = (uneko_indizea - 1) % len(guztiak_datuekin)
                berria = guztiak_datuekin[aurreko_idx]["id"]
                st.session_state.hautatutako_makina = berria
                st.query_params["makina"] = berria
                st.rerun()

        with col_next:
            if st.button("Hurrengoa →", key="btn_hurrengoa", width="stretch"):
                hurrengo_idx = (uneko_indizea + 1) % len(guztiak_datuekin)
                berria = guztiak_datuekin[hurrengo_idx]["id"]
                st.session_state.hautatutako_makina = berria
                st.query_params["makina"] = berria
                st.rerun()

        st.html("""
        <div class="footer-note" style="text-align:center;">
            CNC bakoitzak bere informazio-fitxa du.
        </div>
        """)
