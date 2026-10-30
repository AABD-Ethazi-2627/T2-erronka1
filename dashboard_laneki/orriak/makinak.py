"""Makinen informazioa, egoera-koloreak, sortutako argazkiak eta neurketak erakusteko orria."""

from base64 import b64encode
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import altair as alt
import streamlit as st
from PIL import Image

Osagaia = Callable[[], None]

ARGAZKI_DIREKTORIOA = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "images"
    / "cnc"
)

# 4 Egoera nagusiak: Larria, Ertaina, Arina, Normala
LARRIAK_ID = {4, 9, 17, 28}
ERTAINAK_ID = {3, 12, 15, 21, 35, 40, 47}
ARINAK_ID = {7, 16, 20, 24, 27, 31, 38, 39, 41, 43, 46, 48}


def _joera_diagrama(
    balioak: list[float], kolorea: str, unitatea: str, gai_iluna: bool
) -> alt.LayerChart:
    """FastAPIko serieekin zuzenean eguneratzeko Altair diagrama interaktiboa."""
    orduak = ["12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00",
              "19:00", "20:00", "21:00", "22:00", "23:00", "00:00", "01:00",
              "02:00", "03:00", "04:00", "05:00", "06:00", "07:00", "08:00",
              "09:00", "10:00", "11:00", "12:00"]
    datuak = [
        {"indizea": i, "ordua": orduak[i], "balioa": float(balioa)}
        for i, balioa in enumerate(balioak)
    ]
    testua = "#DCE8F3" if gai_iluna else "#425B73"
    sareta = "#385169" if gai_iluna else "#D9E5EF"
    atzeko_planoa = "#172A3B" if gai_iluna else "#F8FAFC"
    kolore_ilunak = {
        "#EF476F": "#FF7D98",
        "#F2A51A": "#FFC857",
        "#16B66A": "#52D99A",
    }
    marra_kolorea = kolore_ilunak.get(kolorea, kolorea) if gai_iluna else kolorea
    ardatz_x = alt.X(
        "indizea:Q", title=None,
        axis=alt.Axis(
            values=[0, 4, 8, 12, 16, 20, 24],
            labelExpr="{0:'12:00',4:'16:00',8:'20:00',12:'00:00',16:'04:00',20:'08:00',24:'12:00'}[datum.value]",
            labelColor=testua, labelFontSize=9, tickSize=0, grid=True,
            gridColor=sareta, domain=False,
        ),
    )
    ardatz_y = alt.Y(
        "balioa:Q", title=None, scale=alt.Scale(zero=False),
        axis=alt.Axis(labelColor=testua, labelFontSize=9, tickSize=0,
                      grid=True, gridColor=sareta, domain=False),
    )
    oinarria = alt.Chart(alt.Data(values=datuak)).encode(
        x=ardatz_x,
        y=ardatz_y,
        tooltip=[alt.Tooltip("ordua:N", title="Ordua"),
                 alt.Tooltip("balioa:Q", title=unitatea, format=".1f")],
    )
    return (
        oinarria.mark_area(color=marra_kolorea, opacity=0.16 if gai_iluna else 0.12)
        + oinarria.mark_line(
            color=marra_kolorea, strokeWidth=2.5, interpolate="monotone"
        )
        + oinarria.mark_circle(color=marra_kolorea, size=18, opacity=0)
    ).properties(height=180, background=atzeko_planoa).configure_view(
        stroke=None, fill=atzeko_planoa
    )


@st.dialog("Makinen datuak", width="large")
def _makina_xehetasunak_modal(datuak: dict[str, Any]) -> None:
    """Hautatutako CNCaren analisi prediktibo osoa erakutsi."""
    zenbakia = datuak["zenbakia"]
    orain = datetime.now(timezone.utc)
    modal_data = orain.strftime("%Y-%m-%d")
    modal_ordua = orain.strftime("%H:%M UTC")
    modal_tenperatura = float(datuak.get("giro_tenperatura", 27.3))
    faktorea = {"Larria": 1.0, "Ertaina": 0.72, "Arina": 0.42, "Normala": 0.16}[datuak["egoera_mota"]]
    arriskua = max(3, min(97, round((100 - datuak["osasuna"]) * 0.86 + faktorea * 18)))
    bibrazioa = round(1.1 + faktorea * 2.1 + (zenbakia % 5) * 0.08, 1)
    korrontea = round(8.4 + faktorea * 5.7 + (zenbakia % 7) * 0.2, 1)
    egoera_tonua = {
        "Larria": "red", "Ertaina": "amber", "Arina": "blue", "Normala": "green"
    }[datuak["egoera_mota"]]
    bibrazio_tonua = "red" if bibrazioa >= 3 else "amber" if bibrazioa >= 2 else "green"
    tenperatura_tonua = "red" if datuak["tenperatura"] >= 75 else "amber" if datuak["tenperatura"] >= 60 else "green"
    korronte_tonua = "amber" if korrontea >= 12 else "green"
    bibrazio_mezua = "↗ Ohikotik gora" if bibrazioa >= 2 else "✓ Tarte egokian"

    if datuak["egoera_mota"] == "Larria":
        ekintza_laburra, arrisku_testua = "Berehalako berrikuspena", "Arrisku handia"
        ekintza_azalpena = "Mantentze-taldeak berehala aztertu behar du"
    elif datuak["egoera_mota"] == "Ertaina":
        ekintza_laburra, arrisku_testua = "Berrikuspena planifikatu", "Arrisku ertaina"
        ekintza_azalpena = "Hurrengo geldialdian ikuskapena egin"
    elif datuak["egoera_mota"] == "Arina":
        ekintza_laburra, arrisku_testua = "Jarraipena egin", "Arrisku arina"
        ekintza_azalpena = "Bilakaera eguneroko txandan kontrolatu"
    else:
        ekintza_laburra, arrisku_testua = "Ohiko jarraipena", "Arrisku txikia"
        ekintza_azalpena = "Ez da aparteko mantentze-lanik behar"

    bibrazio_seriea = [
        round(bibrazioa * (0.55 + i * 0.017) + ((i + zenbakia) % 4) * 0.055 + (0.24 if i in (18, 22) else 0), 2)
        for i in range(25)
    ]
    tenperatura_seriea = [
        round(datuak["tenperatura"] * (0.78 + i * 0.008) + ((i + zenbakia) % 5) * 0.55 + (3.4 if i == 13 else 0), 1)
        for i in range(25)
    ]
    korronte_seriea = [
        round(korrontea * (0.68 + i * 0.012) + ((i * zenbakia) % 5) * 0.28 + (korrontea * 0.55 if i in (7, 17) else 0), 1)
        for i in range(25)
    ]
    joera = "Igotzen" if datuak["egoera_mota"] != "Normala" else "Egonkorra"
    alarma = f"SP-{3 + zenbakia % 8:02d}" if datuak["egoera_mota"] != "Normala" else "Ez dago"
    gai_iluna = bool(st.session_state.get("gai_iluna", False))
    modal_theme_class = " theme-iluna" if gai_iluna else ""
    ikonoak = {
        "egoera": "icon-egoera",
        "osasuna": "icon-osasuna",
        "arriskua": "icon-arriskua",
        "ekintza": "icon-ekintza",
        "bibrazioa": "icon-bibrazioa",
        "korrontea": "icon-korrontea",
        "tenperatura": "icon-tenperatura",
    }

    st.html(f"""
    <div class="predictive-modal-top{modal_theme_class}">
      <div class="predictive-page-head">
        <small>CNC Prediktiboa</small>
        <div class="header-datetime modal-header-datetime">
          <span class="header-data-item header-date">
            <span class="header-data-icon" aria-hidden="true">▦</span>{modal_data}
          </span>
          <span class="header-data-item header-time">
            <span class="header-data-icon" aria-hidden="true">◷</span>{modal_ordua}
          </span>
          <span class="header-data-item header-temperature">
            <span class="header-data-icon" aria-hidden="true">🌡</span>{modal_tenperatura:.1f} °C
          </span>
        </div>
      </div>
      <div class="predictive-title">{datuak['id']} · Analisi prediktiboa</div>
      <div class="predictive-summary">
        <div class="predictive-kpi tone-{egoera_tonua}"><i class="modal-icon {ikonoak['egoera']}"></i><div><small>Egoera</small><strong>{datuak['egoera_mota']}</strong><p>Uneko makinaren egoera</p></div></div>
        <div class="predictive-kpi tone-blue"><i class="modal-icon {ikonoak['osasuna']}"></i><div><small>Osasun-maila</small><strong>{datuak['osasuna']}%</strong><p>Osasun-indize orokorra</p></div></div>
        <div class="predictive-kpi tone-amber"><i class="modal-icon {ikonoak['arriskua']}"></i><div><small>Arrisku-maila</small><strong>{arriskua}%</strong><p>Matxura-arriskua, hurrengo 7 egunetan</p></div></div>
        <div class="predictive-kpi tone-green"><i class="modal-icon {ikonoak['ekintza']}"></i><div><small>Hurrengo ekintza</small><strong class="action-text">{ekintza_laburra}</strong><p>{ekintza_azalpena}</p></div></div>
      </div>
      <div class="predictive-signals">
        <div class="signal-card tone-{bibrazio_tonua}"><i class="modal-icon {ikonoak['bibrazioa']}"></i><div><small>Bibrazio RMS</small><strong>{bibrazioa:.1f} mm/s</strong><em>{bibrazio_mezua}</em></div><aside><small>Balio maximoa</small><b>{bibrazioa * 1.65:.1f} mm/s</b></aside></div>
        <div class="signal-card tone-{korronte_tonua}"><i class="modal-icon {ikonoak['korrontea']}"></i><div><small>Ardatzaren korrontea</small><strong>{korrontea:.1f} A</strong><em>{'⚠ Aztertu' if korrontea >= 12 else '✓ Tarte egokian'}</em></div><aside><small>Piko balioa</small><b>{korrontea * 1.23:.1f} A</b></aside></div>
        <div class="signal-card tone-{tenperatura_tonua}"><i class="modal-icon {ikonoak['tenperatura']}"></i><div><small>Ardatzaren tenperatura</small><strong>{datuak['tenperatura']:.1f} °C</strong><em>{'⚠ Ohikotik gora' if datuak['tenperatura'] >= 60 else '✓ Tarte egokian'}</em></div><aside><small>Balio normala</small><b>&lt; 60 °C</b></aside></div>
      </div>
    </div>
    """)

    grafiko_zutabea, ondorio_zutabea = st.columns([3.25, 1.0], gap="small")
    with grafiko_zutabea, st.container(key="predictive_charts", border=True):
        st.html('<h3 class="native-trends-title">↗ Azken 24 orduko joerak</h3>')
        grafikoak = (
            ("Bibrazio RMS (mm/s)", bibrazio_seriea, "#EF476F", "mm/s", bibrazioa, f"±{bibrazioa * .28:.1f}"),
            ("Ardatzaren tenperatura (°C)", tenperatura_seriea, "#F2A51A", "°C", datuak["tenperatura"], f"±{datuak['tenperatura'] * .08:.1f} °C"),
            ("Ardatzaren korrontea (A)", korronte_seriea, "#16B66A", "A", korrontea, f"±{korrontea * .22:.1f} A"),
        )
        for zutabea, grafikoa in zip(st.columns(3, gap="small"), grafikoak):
            izenburua, seriea, kolorea, unitatea, batezbestekoa, aldakortasuna = grafikoa
            with zutabea, st.container(key=f"chart_{unitatea}_{zenbakia}", border=True):
                st.html(f'<div class="native-chart-title">{izenburua}</div>')
                st.altair_chart(
                    _joera_diagrama(seriea, kolorea, unitatea, gai_iluna),
                    width="stretch", theme=None,
                    key=f"altair_{unitatea}_{zenbakia}",
                )
                st.html(f"""<div class="native-chart-footer">
                    <span>Batez bestekoa<strong>{batezbestekoa:.1f} {unitatea}</strong></span>
                    <span>Joera<strong>{joera}</strong></span>
                    <span>Aldakortasuna<strong>{aldakortasuna}</strong></span>
                </div>""")

    with ondorio_zutabea:
        st.html(f"""<section class="predictive-panel conclusions-panel native-conclusions{modal_theme_class}"><h3>☀ Ondorio azkarra</h3>
          <div class="conclusion-row"><b>1</b><div><strong>{datuak['abisua']}</strong><small>Azken orduetan joera adierazgarria hauteman da.</small></div></div>
          <div class="conclusion-row"><b>2</b><div><strong>Tenperatura: {datuak['tenperatura']:.1f} °C</strong><small>Balioa makinaren ohiko tartearekin alderatu da.</small></div></div>
          <div class="conclusion-row"><b>3</b><div><strong>Osasun-maila: %{datuak['osasuna']}</strong><small>Sentsoreen neurketa guztiak kontuan hartuta.</small></div></div>
          <div class="risk-result tone-{egoera_tonua}"><strong>⚠ {arrisku_testua}</strong><span>Matxura gertatzeko probabilitatea: %{arriskua}</span></div>
        </section>""")

    st.html(f"""
      <div class="predictive-bottom predictive-bottom-native{modal_theme_class}">
        <section class="predictive-panel"><h3>⚙ Mekanizazio-baldintzak</h3><dl><div><dt>Materiala</dt><dd>Altzairua</dd></div><div><dt>Erreminta</dt><dd>Fresa Ø12</dd></div><div><dt>Aurrerapena</dt><dd>{1200 + zenbakia * 7} mm/min</dd></div></dl></section>
        <section class="predictive-panel"><h3>▣ Alarmak eta mantentzea</h3><dl><div><dt>Alarma-kodea</dt><dd>{alarma}</dd></div><div><dt>Azken matxura</dt><dd>{datuak['azken_matxura']}</dd></div><div><dt>Osagai kaltetua</dt><dd>{datuak['huts_egindako_osagaia']}</dd></div></dl></section>
        <section class="predictive-panel recommended-panel"><h3>◎ Gomendatutako mantentze-ekintzak</h3>
          <div class="recommended-actions">
            <div><b>1</b><p><strong>{ekintza_laburra}</strong><small>Makinaren egoera mekanikoa aztertu.</small></p></div>
            <div><b>2</b><p><strong>{datuak['ekintza']}</strong><small>Parametro nagusiak egiaztatu.</small></p></div>
            <div><b>3</b><p><strong>Hurrengo txandan mantentzea</strong><small>{datuak['hurrengo_berrikuspena']} egunerako planifikatu.</small></p></div>
          </div>
        </section>
      </div>
    """)


@st.cache_data(show_spinner=False)
def _makinaren_uri_datuak(zenbakia: int) -> str:
    """Makina baten argazkia base64 URI moduan prestatu."""
    argazki_bidea = ARGAZKI_DIREKTORIOA / f"cnc-{zenbakia:03d}.webp"
    if argazki_bidea.exists():
        edukia = b64encode(argazki_bidea.read_bytes()).decode("ascii")
        return f"data:image/webp;base64,{edukia}"
    return ""


@st.cache_data(show_spinner=False)
def _makinaren_thumbnail_uri_datuak(zenbakia: int) -> str:
    """Galeriako miniatura arina sortu, 50 txartelak osorik kargatzeko."""
    argazki_bidea = ARGAZKI_DIREKTORIOA / f"cnc-{zenbakia:03d}.webp"
    if not argazki_bidea.exists():
        return ""

    with Image.open(argazki_bidea) as irudia:
        irudia.thumbnail((64, 64), Image.Resampling.LANCZOS)
        bufferra = BytesIO()
        irudia.save(bufferra, format="WEBP", quality=82, method=6)

    edukia = b64encode(bufferra.getvalue()).decode("ascii")
    return f"data:image/webp;base64,{edukia}"


def _makina_datuak(makina: dict[str, Any]) -> dict[str, Any]:
    """Makinaren sailkapen zehatza, koloreak, alertak eta metrikak lortu."""
    zenbakia = int(makina.get("zenbakia", int(makina["id"].replace("CNC-", ""))))

    # 1. LARRIA (Gorria - 4 makina)
    if zenbakia in LARRIAK_ID:
        egoera_mota = "Larria"
        klasea = "larria"
        kolorea = "#DE4651"
        bg_kolorea = "#FFF5F5"
        border_kolorea = "#F87171"
        badge_bg = "#FEE2E2"
        badge_text = "#DC2626"
        abisu_ikonoa = "⚠"

        if zenbakia == 4:
            tenp, rpm, torque, higadura = 90.3, 1212, 47.6, 246
            abisua = "Tenperatura kritikoa"
            kokapena = "D lerroa · 10. kokapena"
            ekintza = "Tenperatura kritikoa. Berehalako arreta behar du."
        elif zenbakia == 9:
            tenp, rpm, torque, higadura = 80.3, 1577, 46.2, 235
            abisua = "Bibrazio handiegia"
            kokapena = "A lerroa · 1. kokapena"
            ekintza = "Ardatz nagusiaren bibrazio-anomalia detektatu da."
        elif zenbakia == 17:
            tenp, rpm, torque, higadura = 91.3, 1471, 48.0, 240
            abisua = "Bibrazio handiegia"
            kokapena = "A lerroa · 1. kokapena"
            ekintza = "Kojineteak berrikusi eta abiadura mugatu berehala."
        else:  # 28
            tenp, rpm, torque, higadura = 78.3, 1584, 45.8, 228
            abisua = "Tenperatura kritikoa"
            kokapena = "D lerroa · 10. kokapena"
            ekintza = "Hozte-sistemaren presioa jaitsi da."

    # 2. ERTAINA (Laranja - 7 makina)
    elif zenbakia in ERTAINAK_ID:
        egoera_mota = "Ertaina"
        klasea = "ertaina"
        kolorea = "#D97706"
        bg_kolorea = "#FFF7E6"
        border_kolorea = "#FBBF24"
        badge_bg = "#FEF3C7"
        badge_text = "#D97706"
        abisu_ikonoa = "⚠"

        if zenbakia == 3:
            tenp, rpm, torque, higadura = 68.2, 1139, 44.5, 180
            abisua = "Lubrifikazio-oharra"
            kokapena = "C lerroa · 7. kokapena"
            ekintza = "Lubrifikazio-oharra. Mantentze-lana lehenetsi."
        elif zenbakia == 12:
            tenp, rpm, torque, higadura = 69.2, 1106, 43.8, 175
            abisua = "Abiadura irregularra"
            kokapena = "D lerroa · 10. kokapena"
            ekintza = "Bihurdura-momentuaren gorabeherak kontrolatu."
        elif zenbakia == 15:
            tenp, rpm, torque, higadura = 65.2, 1325, 51.5, 115
            abisua = "Lubrifikazio-oharra"
            kokapena = "C lerroa · 7. kokapena"
            ekintza = "Lubrifikazio-oharra. Mantentze-lana lehenetsi."
        elif zenbakia == 21:
            tenp, rpm, torque, higadura = 67.4, 1280, 42.1, 160
            abisua = "Abiadura irregularra"
            kokapena = "B lerroa · 1. kokapena"
            ekintza = "Txanda honetan ikuskapena egitea gomendatzen da."
        elif zenbakia == 35:
            tenp, rpm, torque, higadura = 66.8, 1310, 43.0, 155
            abisua = "Lubrifikazio-oharra"
            kokapena = "D lerroa · 5. kokapena"
            ekintza = "Lubrifikazio-maila minimoaren azpitik dago."
        elif zenbakia == 40:
            tenp, rpm, torque, higadura = 64.9, 1295, 41.5, 148
            abisua = "Presio-gorabehera"
            kokapena = "D lerroa · 10. kokapena"
            ekintza = "Hurrengo geldialdian sistema hidraulikoa aztertu."
        else:  # 47
            tenp, rpm, torque, higadura = 68.0, 1340, 44.0, 165
            abisua = "Lubrifikazio-oharra"
            kokapena = "E lerroa · 7. kokapena"
            ekintza = "Kargaren egonkortasuna eta tenperatura kontrolatu."

    # 3. ARINA (Urdina - 12 makina)
    elif zenbakia in ARINAK_ID:
        egoera_mota = "Arina"
        klasea = "arina"
        kolorea = "#2563EB"
        bg_kolorea = "#F8FAFF"
        border_kolorea = "#93C5FD"
        badge_bg = "#DBEAFE"
        badge_text = "#2563EB"
        abisu_ikonoa = "ℹ"

        tenp = round(48.0 + (zenbakia * 1.7) % 8, 1)
        rpm = 1300 + (zenbakia * 23) % 280
        torque = round(32.0 + (zenbakia * 1.3) % 7, 1)
        higadura = 80 + (zenbakia * 9) % 55
        abisua = "Higadura jarraipena" if zenbakia % 2 == 0 else "Ikuskapen arrunta"
        kokapena = f"{chr(65 + (zenbakia - 1) // 10)} lerroa · {(zenbakia - 1) % 10 + 1}. kokapena"
        ekintza = "Jarraipena egin. Ohiko mantentze-lanen egutegian integratu."

    # 4. NORMALA (Berdea - 27 makina)
    else:
        egoera_mota = "Normala"
        klasea = "normala"
        kolorea = "#16A34A"
        bg_kolorea = "#F8FDFB"
        border_kolorea = "#86EFAC"
        badge_bg = "#DCFCE7"
        badge_text = "#16A34A"
        abisu_ikonoa = "✓"

        tenp = round(31.5 + (zenbakia * 1.1) % 6, 1)
        rpm = 1420 + (zenbakia * 19) % 360
        torque = round(23.0 + (zenbakia * 1.4) % 10, 1)
        higadura = 40 + (zenbakia * 6) % 45
        abisua = "Funtzionamendu normala"
        kokapena = f"{chr(65 + (zenbakia - 1) // 10)} lerroa · {(zenbakia - 1) % 10 + 1}. kokapena"
        ekintza = "Parametro guztiak tarte egokian daude. Ez da ekintzarik behar."

    # Mantentze-historiala
    if zenbakia == 15:
        azken_berrikuspena = "2026-07-19"
        fabrikazio_urtea = "2025"
        azken_matxura = "2026-10-16"
        teknikariaren_bisita = "2026-10-16"
        hurrengo_berrikuspena = "2026-11-03"
        huts_egindako_osagaia = "Lubrifikazio-ponpa"
        geldialdiaren_iraupena = "3 ordu 25 min"
    else:
        erreferentzia = date(2026, 10, 23)
        azken_berrikuspena = (erreferentzia - timedelta(days=12 + (zenbakia * 13) % 140)).isoformat()
        fabrikazio_urtea = str(2017 + (zenbakia * 3) % 9)
        azken_matxura = (erreferentzia - timedelta(days=6 + (zenbakia * 9) % 90)).isoformat()
        teknikariaren_bisita = (erreferentzia - timedelta(days=4 + (zenbakia * 7) % 45)).isoformat()
        hurrengo_berrikuspena = (
            erreferentzia + timedelta(days=10 + (zenbakia * 5) % 50)
        ).isoformat()
        osagaiak = (
            "Ardatz nagusiko errodamendua",
            "Hozte-sistemako ponpa",
            "Abiadura-sentsorea",
            "Sistema hidraulikoko balbula",
            "Lubrifikazio-ponpa",
        )
        huts_egindako_osagaia = osagaiak[(zenbakia - 1) % len(osagaiak)]
        geldialdiaren_iraupena = (
            f"{1 + (zenbakia * 3) % 7} ordu "
            f"{(zenbakia * 11) % 60:02d} min"
        )

    # Erabilera-datuak: FastAPIk bidalitako balioak lehenetsi eta, bitartean,
    # makina bakoitzerako simulazio egonkorra erakutsi.
    funtzionamendu_orduak = makina.get(
        "funtzionamendu_orduak", 2_400 + (zenbakia * 317) % 9_600
    )
    mantentzetik_orduak = makina.get(
        "mantentzetik_orduak", 35 + (zenbakia * 29) % 620
    )
    mantentzetik_zikloak = makina.get(
        "mantentzetik_zikloak", 180 + (zenbakia * 137) % 4_800
    )
    kargapeko_orduak = makina.get(
        "kargapeko_orduak", round(funtzionamendu_orduak * (0.58 + (zenbakia % 7) * 0.04))
    )

    # FastAPIko osasun-indizea lehenetsi; simulazioan egoerarekin koherentea den
    # ehunekoa erabili.
    osasun_berezia = {4: 19, 12: 44, 21: 72, 35: 96}
    if egoera_mota == "Larria":
        osasun_lehenetsia = 18 + (zenbakia * 3) % 15
    elif egoera_mota == "Ertaina":
        osasun_lehenetsia = 40 + (zenbakia * 5) % 21
    elif egoera_mota == "Arina":
        osasun_lehenetsia = 68 + (zenbakia * 3) % 15
    else:
        osasun_lehenetsia = 86 + (zenbakia * 2) % 13
    osasuna = int(makina.get("osasuna", osasun_berezia.get(zenbakia, osasun_lehenetsia)))
    osasuna = max(0, min(100, osasuna))
    osasun_kolorea = (
        "#E86B86" if osasuna < 35 else
        "#E5AE50" if osasuna < 60 else
        "#4DA9DC" if osasuna < 85 else
        "#49BE98"
    )

    # Makina bakoitzaren ohiko tarteak FastAPItik jaso daitezke. Simulazioak
    # balio lehenetsi hauek erabiltzen ditu.
    tarte_normalak = makina.get("tarte_normalak", {})
    tenperatura_tartea = tarte_normalak.get("tenperatura", "30–59 °C")
    rpm_tartea = tarte_normalak.get("rpm", "1.100–1.900 RPM")
    torque_tartea = tarte_normalak.get("torque", "20–49,9 Nm")
    higadura_tartea = tarte_normalak.get("higadura", "0–149 min")

    def metrika_alerta(balioa: float, ohartarazpena: float, kritikoa: float) -> tuple[str, str]:
        if balioa >= kritikoa:
            return "metric-fault", "AKATSA"
        if balioa >= ohartarazpena:
            return "metric-warning", "KONTUZ"
        return "", ""

    tenperatura_klasea, tenperatura_marka = metrika_alerta(tenp, 60, 75)
    higadura_klasea, higadura_marka = metrika_alerta(higadura, 150, 220)
    torque_klasea, torque_marka = metrika_alerta(torque, 50, 55)
    if rpm < 900 or rpm > 2200:
        rpm_klasea, rpm_marka = "metric-fault", "AKATSA"
    elif rpm < 1100 or rpm > 1900:
        rpm_klasea, rpm_marka = "metric-warning", "KONTUZ"
    else:
        rpm_klasea, rpm_marka = "", ""

    return {
        "id": makina["id"],
        "zenbakia": zenbakia,
        "egoera_mota": egoera_mota,
        "klasea": klasea,
        "kolorea": kolorea,
        "bg_kolorea": bg_kolorea,
        "border_kolorea": border_kolorea,
        "badge_bg": badge_bg,
        "badge_text": badge_text,
        "abisu_ikonoa": abisu_ikonoa,
        "tenperatura": tenp,
        "rpm": rpm,
        "torque": torque,
        "higadura": higadura,
        "abisua": abisua,
        "ekintza": ekintza,
        "kokapena": kokapena,
        "azken_berrikuspena": azken_berrikuspena,
        "fabrikazio_urtea": fabrikazio_urtea,
        "azken_matxura": azken_matxura,
        "teknikariaren_bisita": teknikariaren_bisita,
        "hurrengo_berrikuspena": hurrengo_berrikuspena,
        "huts_egindako_osagaia": huts_egindako_osagaia,
        "geldialdiaren_iraupena": geldialdiaren_iraupena,
        "funtzionamendu_orduak": funtzionamendu_orduak,
        "mantentzetik_orduak": mantentzetik_orduak,
        "mantentzetik_zikloak": mantentzetik_zikloak,
        "kargapeko_orduak": kargapeko_orduak,
        "osasuna": osasuna,
        "osasun_kolorea": osasun_kolorea,
        "tenperatura_tartea": tenperatura_tartea,
        "rpm_tartea": rpm_tartea,
        "torque_tartea": torque_tartea,
        "higadura_tartea": higadura_tartea,
        "tenperatura_klasea": tenperatura_klasea,
        "tenperatura_marka": tenperatura_marka,
        "rpm_klasea": rpm_klasea,
        "rpm_marka": rpm_marka,
        "torque_klasea": torque_klasea,
        "torque_marka": torque_marka,
        "higadura_klasea": higadura_klasea,
        "higadura_marka": higadura_marka,
    }


def _estiloak_txertatu() -> None:
    """Makinen orrirako CSS estilo zehatzak injektatu."""
    st.html("""
    <style>
    /* KPI Txartelak goialdean */
    .makina-kpi-container {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 8px;
        margin-bottom: 8px;
    }
    .makina-kpi-box {
        background: var(--panel-bg, #ffffff);
        border: 1px solid var(--panel-border, #E2E8F0);
        border-radius: 12px;
        padding: 9px 13px;
        position: relative;
        overflow: hidden;
        display: grid;
        grid-template-columns: auto auto;
        grid-template-rows: auto auto;
        column-gap: 8px;
        row-gap: 5px;
        place-content: center;
        align-items: center;
        justify-items: center;
        min-height: 92px;
        height: 92px;
        text-align: center;
        box-shadow: 0 2px 5px rgba(20,42,64,0.04);
        box-sizing: border-box;
        font-family: var(--kpi-font-family, Verdana, Arial, sans-serif) !important;
    }
    .makina-kpi-box .kpi-label,
    .makina-kpi-box .kpi-number,
    .makina-kpi-box .kpi-sub {
        font-weight: 800 !important;
    }
    .makina-kpi-box .kpi-label,
    .makina-kpi-box .kpi-number {
        font-weight: 900 !important;
    }
    .makina-kpi-box:nth-child(1) {
        background: var(--pastel-slate, #E5EDF5);
        border-color: #9FB3C8;
    }
    .makina-kpi-box:nth-child(2) {
        background: var(--state-red-bg, #F8C1C1);
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
        grid-column: 1 / -1;
        width: 100%;
        text-align: center;
        font-family: var(--kpi-font-family, Verdana, Arial, sans-serif) !important;
        font-size: 15px;
        line-height: 1.25;
        font-weight: 800;
        color: var(--semantic-text, #142A40);
    }
    .makina-kpi-box .kpi-number {
        align-self: center;
        width: auto;
        font-family: var(--kpi-font-family, Verdana, Arial, sans-serif) !important;
        font-size: clamp(28px, 1.9vw, 34px);
        font-weight: 800;
        line-height: 1.05;
        letter-spacing: -1px;
        margin: 0;
        text-align: center;
    }
    .makina-kpi-box .kpi-sub {
        align-self: center;
        padding-bottom: 0;
        text-align: center;
        font-family: var(--kpi-font-family, Verdana, Arial, sans-serif) !important;
        font-size: 14px;
        line-height: 1.2;
        color: var(--semantic-muted, #475569);
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
        min-height: calc(100vh - 105px) !important;
        height: calc(100vh - 105px) !important;
        box-sizing: border-box !important;
        overflow: hidden !important;
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
        height: calc(100vh - 245px);
        min-height: 420px;
        max-height: none;
        overflow-y: scroll !important;
        overflow-x: hidden !important;
        scrollbar-gutter: stable;
        overscroll-behavior: contain;
        padding-right: 8px;
        margin: 10px 0;
    }
    .gallery-scroll-list::-webkit-scrollbar {
        width: 11px;
    }
    .gallery-scroll-list::-webkit-scrollbar-track {
        background: rgba(100, 116, 139, 0.16);
        border-radius: 6px;
    }
    .gallery-scroll-list::-webkit-scrollbar-thumb {
        background: #7890A6;
        border: 2px solid transparent;
        border-radius: 7px;
        background-clip: padding-box;
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
        background: var(--state-red-bg, #F8C1C1) !important;
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
        width: 50px;
        height: 50px;
        border-radius: 6px;
        object-fit: contain;
        border: 1px solid rgba(0,0,0,0.08);
        background: #F1F5F9;
        image-rendering: auto;
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
        padding: 8px 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
        margin-bottom: 0;
        box-sizing: border-box;
        color: var(--semantic-text, #0F172A);
        /* Utzi lekua beheko Aurrekoa/Hurrengoa nabigazioari. */
        min-height: calc(100vh - 150px);
        display: flex;
        flex-direction: column;
    }

    /* Eskuin-panelaren egoera-koloreak */
    .makina-detail-card.detail-larria {
        border: 2px solid #DE4651 !important;
        background: var(--state-red-bg, #F8C1C1) !important;
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
        margin-bottom: 5px;
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
        display: grid;
        grid-template-columns: minmax(210px, 1fr) minmax(230px, 1fr);
        gap: 10px;
        align-items: stretch;
    }
    .detail-machine-photo,
    .detail-health-box {
        min-width: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    .detail-photo-img {
        width: 225px;
        max-width: 100%;
        height: 225px;
        max-height: 225px;
        object-fit: contain;
        border-radius: 8px;
        display: block;
        margin: 0 auto;
        image-rendering: auto;
    }
    .detail-health-box {
        padding: 18px 16px;
        border: 1px solid var(--detail-border, #E2E8F0);
        border-radius: 10px;
        background: var(--panel-bg, #FFFFFF);
    }
    .detail-health-heading {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 28px;
        color: var(--semantic-text, #0F172A);
        font-size: 1rem;
        font-weight: 800;
        text-align: left;
    }
    .detail-health-row {
        width: 100%;
        margin-bottom: 7px;
    }
    .detail-health-actions {
        width: 100%;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-top: auto;
        padding-top: 12px;
    }
    .detail-health-actions .detail-recom-box {
        min-height: 39px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }
    .detail-health-action-space {
        min-height: 39px;
        anchor-name: --info-gehiago-kokalekua;
    }
    .detail-navigation-slots {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        width: 100%;
        margin-top: 8px;
    }
    .detail-navigation-prev,
    .detail-navigation-next {
        min-height: 40px;
    }
    .detail-navigation-prev {
        anchor-name: --aurrekoa-kokalekua;
    }
    .detail-navigation-next {
        anchor-name: --hurrengoa-kokalekua;
    }
    .detail-health-row-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 7px;
        color: var(--semantic-text, #0F172A);
        font-size: 0.94rem;
        font-weight: 800;
    }
    .detail-health-track {
        width: 100%;
        height: 10px;
        overflow: hidden;
        border-radius: 999px;
        background: var(--surface-muted, #E6ECF1);
    }
    .detail-health-fill {
        height: 100%;
        border-radius: inherit;
    }

    .detail-loc-box {
        margin-bottom: 4px;
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
        gap: 5px;
        margin-bottom: 5px;
    }
    .detail-metric-card {
        background: var(--detail-surface, #F8FAFC);
        border: 1px solid var(--detail-border, #E2E8F0);
        border-radius: 10px;
        padding: 5px 10px;
    }
    .detail-metric-card.metric-warning {
        background: var(--state-amber-bg, #FFF3CD) !important;
        border: 2px solid #E5A636 !important;
    }
    .detail-metric-card.metric-fault {
        background: var(--state-red-bg, #F5B8B8) !important;
        border: 2px solid #E94355 !important;
        box-shadow: 0 0 0 2px rgba(233, 67, 85, 0.10);
    }
    .detail-metric-header {
        justify-content: space-between;
    }
    .metric-alert-mark {
        margin-left: auto;
        padding: 2px 5px;
        border-radius: 4px;
        background: #E94355;
        color: #FFFFFF;
        font-size: 0.58rem;
        font-weight: 900;
        letter-spacing: 0.03em;
    }
    .metric-warning .metric-alert-mark {
        background: #D97706;
    }
    .detail-normal-ranges {
        margin: 0 0 7px;
        padding: 7px 10px;
        border: 1px solid #7BA7CF;
        border-radius: 9px;
        background: var(--state-blue-bg, #E8F2FC);
        color: var(--semantic-text, #0F172A);
    }
    .detail-normal-ranges strong {
        display: block;
        margin-bottom: 5px;
        font-size: 0.75rem;
        font-weight: 900;
    }
    .detail-normal-range-list {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 5px;
    }
    .detail-normal-range-list span {
        padding: 4px 5px;
        border-radius: 5px;
        background: var(--detail-surface, #F8FAFC);
        font-size: 0.67rem;
        font-weight: 700;
        text-align: center;
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
        font-size: 0.94rem;
        font-weight: 800;
        color: var(--semantic-text, #0F172A);
        margin-bottom: 7px;
    }
    .detail-info-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        grid-template-rows: repeat(3, minmax(52px, 1fr));
        gap: 7px;
        margin-bottom: 8px;
        flex: 1 1 auto;
    }
    .detail-info-card {
        background: var(--detail-surface, #F8FAFC);
        border: 1px solid var(--detail-border, #E2E8F0);
        border-radius: 9px;
        padding: 7px 9px;
        min-height: 52px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .detail-info-card:last-child:nth-child(odd) {
        grid-column: auto;
    }
    .detail-info-card small {
        display: block;
        font-size: 0.74rem;
        color: var(--semantic-muted, #64748B);
        line-height: 1.2;
        margin-bottom: 3px;
    }
    .detail-info-card strong {
        font-size: 0.88rem;
        color: var(--semantic-text, #0F172A);
    }

    /* Gomendioa / Lehentasuna */
    .detail-recom-box {
        border-radius: 10px;
        padding: 5px 12px;
        margin-bottom: 0;
        text-align: center;
    }
    .detail-actions-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 4px;
    }
    .st-key-btn_info_gehiago {
        width: calc(25% - 10px) !important;
        margin-top: -515px !important;
        margin-right: 17px !important;
        margin-bottom: 476px !important;
        margin-left: calc(75% + 3px) !important;
        position: relative !important;
        z-index: 6;
    }
    .st-key-btn_info_gehiago button {
        width: 100% !important;
        height: 39px !important;
        min-height: 39px !important;
        border: 1.5px solid #3976BD !important;
        border-radius: 10px !important;
        background: var(--panel-bg, #FFFFFF) !important;
        color: var(--main-text, #0F172A) !important;
        font-size: 0.82rem !important;
        font-weight: 900 !important;
    }
    .st-key-btn_info_gehiago button:hover {
        background: var(--state-blue-bg, #E8F2FC) !important;
        border-color: #2563EB !important;
    }
    /* Nabigatzaile modernoetan botoia osasun-panelaren hutsune zehatzean ainguratu. */
    @supports (position-anchor: --info-gehiago-kokalekua) {
        .st-key-btn_info_gehiago {
            position: absolute !important;
            position-anchor: --info-gehiago-kokalekua;
            top: anchor(top) !important;
            left: anchor(left) !important;
            width: anchor-size(width) !important;
            height: anchor-size(height) !important;
            margin: 0 !important;
            display: flex !important;
            align-items: center !important;
        }
        .st-key-btn_info_gehiago [data-testid="stButton"] {
            width: 100% !important;
            height: 100% !important;
            display: flex !important;
            align-items: center !important;
        }
        .st-key-btn_aurrekoa,
        .st-key-btn_hurrengoa {
            position: absolute !important;
            top: anchor(top) !important;
            left: anchor(left) !important;
            width: anchor-size(width) !important;
            height: anchor-size(height) !important;
            margin: 0 !important;
            z-index: 6;
        }
        .st-key-btn_aurrekoa {
            position-anchor: --aurrekoa-kokalekua;
        }
        .st-key-btn_hurrengoa {
            position-anchor: --hurrengoa-kokalekua;
        }
        .st-key-btn_aurrekoa button,
        .st-key-btn_hurrengoa button {
            height: 100% !important;
        }
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
    .detail-larria .detail-recom-box { background: var(--state-red-bg, #F8C1C1) !important; }
    .detail-ertaina .detail-recom-box { background: var(--state-amber-bg, #FFF7E6) !important; }
    .detail-arina .detail-recom-box { background: var(--state-blue-bg, #EFF6FF) !important; }
    .detail-normala .detail-recom-box { background: var(--state-green-bg, #F0FDF4) !important; }

    /* Xehetasunen leihoa: ia pantaila osoa eta atzeko plano lausotua. */
    div[data-testid="stDialog"] {
        backdrop-filter: blur(7px) !important;
        -webkit-backdrop-filter: blur(7px) !important;
    }
    div[data-testid="stDialog"] [role="dialog"] {
        position: fixed !important;
        inset: 50% auto auto 50% !important;
        transform: translate(-50%, -50%) !important;
        width: min(calc(100vw - 20px), 1780px) !important;
        max-width: min(calc(100vw - 20px), 1780px) !important;
        min-width: 0 !important;
        height: min(calc(100vh - 20px), 820px) !important;
        min-height: 0 !important;
        max-height: min(calc(100vh - 20px), 820px) !important;
        margin: 0 !important;
        padding: 8px 18px 10px !important;
        overflow: hidden !important;
        background: var(--panel-bg, #FFFFFF) !important;
        color: var(--main-text, #0F172A) !important;
        border: 1px solid var(--panel-border, #D9E3EC) !important;
        border-radius: 12px !important;
        box-sizing: border-box !important;
    }
    div[data-testid="stDialog"] button[aria-label="Close"] {
        color: var(--main-text, #0F172A) !important;
        background: var(--detail-surface, #F8FAFC) !important;
        border: 1px solid var(--panel-border, #D9E3EC) !important;
    }
    div[data-testid="stDialog"] [role="dialog"] > div,
    div[data-testid="stDialog"] [role="dialog"] [data-testid="stVerticalBlock"] {
        width: 100% !important;
        min-width: 0 !important;
        box-sizing: border-box !important;
        max-height: 100% !important;
        overflow: hidden !important;
    }
    .machine-modal-content {
        height: 100%; padding: 4px 6px 8px; box-sizing: border-box;
        color: var(--main-text, #0F172A); overflow: hidden;
    }
    .machine-modal-heading {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 18px; font-size: 1.5rem; font-weight: 900;
    }
    .machine-modal-alert {
        padding: 18px; border: 2px solid; border-radius: 12px; margin-bottom: 18px;
    }
    .machine-modal-alert.modal-larria {
        background: var(--state-red-bg, #F8C1C1); border-color: #D94343;
    }
    .machine-modal-alert.modal-ertaina {
        background: var(--state-amber-bg, #FFF7E6); border-color: #E5A636;
    }
    .machine-modal-alert.modal-arina {
        background: var(--state-blue-bg, #EFF6FF); border-color: #4DA9DC;
    }
    .machine-modal-alert.modal-normala {
        background: var(--state-green-bg, #F0FDF4); border-color: #49BE98;
    }
    .machine-modal-alert strong { font-size: 1.05rem; }
    .machine-modal-alert p { margin: 8px 0 0; font-weight: 700; }
    .machine-modal-grid {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
        margin-bottom: 18px;
    }
    .machine-modal-grid > div {
        padding: 14px; border: 1px solid var(--panel-border, #D9E3EC);
        border-radius: 10px; background: var(--detail-surface, #F8FAFC);
    }
    .machine-modal-grid small, .machine-modal-grid strong { display: block; }
    .machine-modal-grid small { margin-bottom: 6px; color: var(--semantic-muted, #64748B); }
    .machine-modal-reference {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
        padding: 14px; border-radius: 10px; background: var(--state-blue-bg, #E8F2FC);
    }
    .machine-modal-reference strong { grid-column: 1 / -1; }
    .machine-modal-reference span { font-size: 0.82rem; font-weight: 700; }

    /* Analisi prediktibo osoa */
    .predictive-modal {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        margin: 0 auto !important;
        height: calc(100vh - 64px); max-height: calc(100vh - 64px);
        overflow: hidden; box-sizing: border-box;
        display: grid;
        grid-template-rows: auto auto auto auto minmax(270px, 1fr) 160px;
        gap: 9px; padding: 0 4px 6px; color: var(--main-text, #0F172A);
        font-family: var(--kpi-font-family, Verdana, Arial, sans-serif);
    }
    .predictive-modal-top,
    .predictive-bottom-native {
        width: calc(100% - 8px) !important;
        max-width: 1680px !important;
        margin: 0 auto !important;
        box-sizing: border-box;
    }
    div[data-testid="stHorizontalBlock"]:has(.st-key-predictive_charts) {
        width: calc(100% - 8px) !important;
        max-width: 1680px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    .predictive-modal-top {
        display: grid; grid-template-rows: auto auto auto auto;
        gap: 5px; color: var(--main-text, #0F172A);
        font-family: var(--kpi-font-family, Verdana, Arial, sans-serif);
    }
    .st-key-predictive_charts {
        height: 292px !important; padding: 8px 10px !important;
        background: var(--panel-bg, #FFFFFF) !important;
        border-color: var(--panel-border, #D9E3EC) !important;
        overflow: hidden !important;
    }
    .st-key-predictive_charts [data-testid="stVegaLiteChart"] {
        margin: -4px 0 !important;
    }
    .native-trends-title {
        margin: 0 !important; font-size: .9rem; color: var(--main-text, #0F172A);
    }
    .native-chart-title {
        margin-bottom: -5px; font-size: .7rem; font-weight: 900;
        color: var(--main-text, #0F172A);
    }
    .native-chart-footer {
        display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 5px; margin-top: -7px;
    }
    .native-chart-footer span {
        padding: 5px 6px; border-radius: 6px;
        background: var(--surface-muted, #EEF3F7);
        color: var(--secondary-text, #64748B); font-size: .56rem;
    }
    .native-chart-footer strong {
        display: block; margin-top: 2px; color: var(--main-text, #0F172A);
        font-size: .67rem;
    }
    .native-chart-footer span:nth-child(2) strong { color: #E33D50; }
    .native-conclusions { height: 292px; box-sizing: border-box; }
    .predictive-page-head {
        display: flex; align-items: center; justify-content: space-between;
        color: var(--secondary-text, #64748B); font-size: .64rem; font-weight: 800;
    }
    .predictive-page-head small { font-size: .64rem; font-weight: 800; }
    .predictive-page-head span { color: var(--main-text, #0F172A); }
    .predictive-page-head .modal-header-datetime {
        flex: 0 0 auto;
        width: auto;
        margin-left: auto;
        font-size: 14px;
    }
    .predictive-page-head .modal-header-datetime .header-data-icon {
        color: #276FA6;
    }
    .predictive-page-head .modal-header-datetime .header-temperature .header-data-icon {
        color: #C65E36;
    }
    .predictive-title { font-size: 1.16rem; line-height: 1; font-weight: 900; }
    .predictive-summary {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.12fr);
        gap: 6px; min-width: 0;
    }
    .predictive-kpi, .signal-card {
        border: 1px solid var(--panel-border, #D9E3EC); border-radius: 11px;
        display: flex; align-items: center; min-width: 0; box-sizing: border-box;
    }
    .predictive-kpi > div, .signal-card > div {
        min-width: 0; overflow-wrap: anywhere;
    }
    .predictive-kpi { min-height: 46px; padding: 3px 6px; gap: 5px; }
    .predictive-kpi i, .signal-card i {
        width: 30px; height: 30px; flex: 0 0 30px; border-radius: 50%;
        display: grid; place-items: center; font-style: normal;
        background: color-mix(in srgb, currentColor 12%, transparent);
        box-shadow: inset 0 0 0 1px color-mix(in srgb, currentColor 18%, transparent);
    }
    .modal-icon::before {
        content: "";
        width: 18px; height: 18px; display: block;
        background: currentColor;
        -webkit-mask: var(--modal-icon) center / contain no-repeat;
        mask: var(--modal-icon) center / contain no-repeat;
    }
    .icon-egoera {
        --modal-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 2 1 21h22L12 2Zm1 16h-2v-2h2v2Zm0-4h-2V9h2v5Z'/%3E%3C/svg%3E");
    }
    .icon-osasuna {
        --modal-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 21 3.5 13A5.6 5.6 0 0 1 11.4 5l.6.6.6-.6a5.6 5.6 0 0 1 7.9 8L12 21Zm-5.8-9h3l1-2.2 2.2 5 1.2-2.8h4.2v-2h-5.5l-1.8-4-2.6 5.9H6.2V12Z'/%3E%3C/svg%3E");
    }
    .icon-arriskua {
        --modal-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 2 3 6v6c0 5.6 3.8 8.8 9 10 5.2-1.2 9-4.4 9-10V6l-9-4Zm1 15h-2v-2h2v2Zm0-4h-2V7h2v6Z'/%3E%3C/svg%3E");
    }
    .icon-ekintza {
        --modal-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M22 19.6 14.4 12a6 6 0 0 0-7.8-7.8l3.5 3.5-2.4 2.4-3.5-3.5A6 6 0 0 0 12 14.4l7.6 7.6L22 19.6ZM5.5 16 2 19.5 4.5 22 8 18.5 5.5 16Z'/%3E%3C/svg%3E");
    }
    .icon-bibrazioa {
        --modal-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M1 11h4l2-6 4 14 3-10 2 6h7v-2h-5.6L14 3l-3 10L7 0 3.6 9H1v2Z'/%3E%3C/svg%3E");
    }
    .icon-korrontea {
        --modal-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M13 1 3 14h7l-1 9 12-15h-8V1Z'/%3E%3C/svg%3E");
    }
    .icon-tenperatura {
        --modal-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M15 13.8V5a5 5 0 0 0-10 0v8.8A7 7 0 1 0 15 13.8ZM10 20a4 4 0 0 1-2-7.5V5a2 2 0 0 1 4 0v7.5A4 4 0 0 1 10 20Zm1-5.8V7H9v7.2a2.5 2.5 0 1 0 2 0Z'/%3E%3C/svg%3E");
    }
    .predictive-kpi small, .signal-card small { display: block; font-weight: 800; }
    .predictive-kpi strong { display: block; font-size: 1.12rem; line-height: 1; margin: 1px 0; }
    .predictive-kpi strong.action-text {
        font-size: .8rem; white-space: normal; overflow-wrap: anywhere;
    }
    .predictive-kpi p {
        margin: 0; color: var(--secondary-text, #64748B);
        font-size: .57rem; line-height: 1.1; font-weight: 700;
        white-space: normal; overflow-wrap: anywhere;
    }
    .tone-red { background: var(--state-red-bg, #F5B8B8); color: #B42323; border-color: #E86F6F; }
    .tone-amber { background: var(--state-amber-bg, #F7E2AE); color: #B96208; border-color: #E8BC52; }
    .tone-blue { background: var(--state-blue-bg, #C8DEF4); color: #1769A8; border-color: #87BCE7; }
    .tone-green { background: var(--state-green-bg, #C8EAD8); color: #0B9253; border-color: #7BD3A5; }
    .theme-iluna,
    .theme-iluna * {
        color: #FFFFFF !important;
    }
    .predictive-signals { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; min-width: 0; }
    .signal-card { min-height: 46px; padding: 3px 6px; gap: 5px; }
    .signal-card > div { min-width: 0; flex: 1; }
    .signal-card strong { display: block; font-size: 1.02rem; line-height: 1; margin: 1px 0; }
    .signal-card em { font-style: normal; font-size: .58rem; font-weight: 800; }
    .signal-card aside {
        padding-left: 8px; border-left: 1px solid currentColor;
        flex: 0 1 96px; min-width: 64px; max-width: 29%;
        overflow-wrap: anywhere; white-space: normal;
    }
    .signal-card aside small { line-height: 1.1; white-space: normal; }
    .signal-card aside b { display: block; margin-top: 3px; font-size: .84rem; }
    .predictive-middle { display: grid; grid-template-columns: minmax(0, 3.2fr) minmax(220px, 1fr); gap: 9px; min-width: 0; min-height: 0; }
    .predictive-panel {
        background: var(--panel-bg, #FFFFFF); border: 1px solid var(--panel-border, #D9E3EC);
        border-radius: 11px; padding: 9px 11px; min-width: 0; overflow: hidden;
    }
    .predictive-panel h3 { margin: 0 0 6px; font-size: .88rem; line-height: 1.1; }
    .trend-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; height: calc(100% - 25px); min-width: 0; }
    .trend-card {
        border: 1px solid var(--panel-border, #D9E3EC); border-radius: 8px;
        padding: 6px; display: grid; grid-template-rows: auto minmax(70px, 1fr) auto;
        background: var(--detail-surface, #F8FAFC); min-width: 0;
    }
    .trend-card > b { font-size: .7rem; }
    .predictive-spark { display: block; width: 100%; height: 100%; min-height: 74px; object-fit: fill; }
    .spark-grid { stroke: var(--panel-border, #D9E3EC); stroke-width: 1; stroke-dasharray: 3 3; }
    .trend-card footer {
        display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 5px;
    }
    .trend-card footer span {
        padding: 6px 7px; border-radius: 6px;
        background: var(--surface-muted, #EEF3F7);
        font-size: .57rem; color: var(--secondary-text, #64748B);
    }
    .trend-card footer strong { display: block; color: var(--main-text, #0F172A); font-size: .67rem; }
    .trend-card footer span:nth-child(2) strong { color: #E33D50; }
    .conclusions-panel { display: flex; flex-direction: column; }
    .conclusions-panel h3 { font-size: 1rem; margin-bottom: 10px; }
    .conclusions-panel ol, .action-list { margin: 0; padding-left: 25px; }
    .conclusions-panel li, .action-list li { margin: 5px 0; font-size: .69rem; font-weight: 700; }
    .conclusions-panel li::marker, .action-list li::marker { color: #E84759; font-weight: 900; }
    .conclusion-row {
        display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 9px;
        align-items: center; margin: 7px 0;
    }
    .conclusion-row > b {
        width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center;
        background: var(--state-red-bg, #F5B8B8); color: #B42323;
        font-size: .78rem; font-weight: 900;
    }
    .recommended-actions > div > b {
        width: 25px; height: 25px; border-radius: 50%; display: grid; place-items: center;
        background: var(--state-red-bg, #F5B8B8); color: #B42323;
        font-size: .68rem; font-weight: 900;
    }
    .conclusion-row strong, .conclusion-row small { display: block; }
    .conclusion-row strong { font-size: .86rem; line-height: 1.15; }
    .conclusion-row small {
        margin-top: 3px; color: var(--secondary-text, #64748B);
        font-size: .66rem; line-height: 1.2;
    }
    .risk-result {
        margin-top: auto; padding: 8px; border: 1px solid #EF6676; border-radius: 8px;
        text-align: center; background: var(--state-red-bg, #F5B8B8);
    }
    .risk-result strong, .risk-result span { display: block; }
    .risk-result span { margin-top: 2px; font-size: .62rem; }
    .risk-result.tone-amber { background: var(--state-amber-bg, #F7E2AE); border-color: #E8BC52; }
    .risk-result.tone-blue { background: var(--state-blue-bg, #C8DEF4); border-color: #87BCE7; }
    .risk-result.tone-green { background: var(--state-green-bg, #C8EAD8); border-color: #7BD3A5; }
    .predictive-bottom { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; min-width: 0; }
    .predictive-bottom { height: 160px; min-height: 160px; }
    .predictive-bottom .predictive-panel { height: 100%; min-height: 0; }
    .predictive-panel dl { margin: 0; }
    .predictive-panel dl > div {
        display: grid; grid-template-columns: 1fr 1.45fr; gap: 8px;
        padding: 5px 7px; background: var(--detail-surface, #F8FAFC);
        border-bottom: 1px solid var(--panel-border, #D9E3EC); font-size: .64rem;
    }
    .predictive-panel dt { color: var(--secondary-text, #64748B); font-weight: 700; }
    .predictive-panel dd { margin: 0; font-weight: 900; }
    .recommended-actions {
        height: calc(100% - 28px); padding: 7px 9px; border-radius: 8px;
        background: var(--state-red-bg, #F5B8B8); box-sizing: border-box;
    }
    .recommended-panel h3 {
        margin: 0 0 7px !important; color: var(--main-text, #142A40) !important;
        font-size: .9rem !important; font-weight: 900 !important;
        line-height: 1.15 !important; opacity: 1 !important;
    }
    .recommended-actions > div {
        display: grid; grid-template-columns: 27px minmax(0, 1fr); gap: 9px;
        align-items: center; min-height: 34px;
    }
    .recommended-actions > div > b {
        width: 27px; height: 27px; font-size: .75rem;
    }
    .recommended-actions p { margin: 0; min-width: 0; }
    .recommended-actions strong, .recommended-actions small { display: block; }
    .recommended-actions strong {
        color: var(--main-text, #142A40); white-space: normal;
        overflow-wrap: anywhere; line-height: 1.15; font-size: .72rem;
    }
    .recommended-actions small {
        color: var(--secondary-text, #64748B); font-size: .63rem;
        line-height: 1.15; overflow-wrap: anywhere;
    }
    @media (max-height: 760px) {
        .predictive-modal {
            height: calc(100vh - 58px);
            max-height: calc(100vh - 58px);
            grid-template-rows: auto auto auto auto minmax(205px, 1fr) 122px;
            gap: 6px;
        }
        .predictive-bottom { height: 122px; min-height: 122px; }
        .predictive-panel dl > div { padding: 3px 6px; }
        .conclusion-row { margin: 2px 0; }
    }

    .footer-note {
        font-size: 0.72rem;
        color: var(--secondary-text, #94A3B8);
        margin-top: 8px;
    }

    .st-key-makina_bilaketa {
        width: 290px !important;
        max-width: 100% !important;
        margin: 0 !important;
    }
    .st-key-makina_bilaketa input {
        height: 34px !important;
        min-height: 34px !important;
        background: var(--input-bg, #FFFFFF) !important;
        border: 0 !important;
        border-radius: 0 !important;
        color: var(--main-text, #0F172A) !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
    }
    .st-key-makina_bilaketa [data-baseweb="input"] {
        width: 100% !important;
        height: 34px !important;
        min-height: 34px !important;
        max-height: 34px !important;
        margin: 0 !important;
        overflow: hidden !important;
        background: var(--input-bg, #FFFFFF) !important;
        border: 1.5px solid var(--panel-border, #CBD5E1) !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }
    .st-key-makina_bilaketa input::placeholder {
        color: var(--secondary-text, #475569) !important;
        opacity: 1 !important;
        font-weight: 700 !important;
    }

    /* Iragazkiaren ikonoa eta testua gai argi/ilunaren arabera egokitu. */
    .st-key-makina_iragazkia button,
    .st-key-makina_iragazkia button span,
    .st-key-makina_iragazkia [data-testid="stIconMaterial"] {
        color: var(--main-text, #0F172A) !important;
    }
    .st-key-makina_iragazkia {
        width: 54px !important;
        min-width: 54px !important;
        margin: 0 !important;
    }
    .st-key-makina_iragazkia button {
        width: 54px !important;
        min-width: 54px !important;
        max-width: 54px !important;
        height: 44px !important;
        min-height: 44px !important;
        max-height: 44px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        position: relative !important;
        overflow: hidden !important;
        background: transparent !important;
        border: 1.5px solid #3976BD !important;
        border-radius: 9px !important;
        box-shadow: 0 2px 6px rgba(39, 96, 142, 0.12) !important;
    }
    .st-key-makina_iragazkia button:hover {
        background: transparent !important;
        border-color: #3976BD !important;
    }
    .st-key-makina_iragazkia [data-testid="stIconMaterial"] {
        display: none !important;
    }
    .st-key-makina_iragazkia button > * {
        display: none !important;
    }
    .st-key-makina_iragazkia button::before {
        content: "";
        display: block !important;
        position: absolute;
        left: 11px;
        top: 50%;
        width: 21px;
        height: 20px;
        background: currentColor;
        clip-path: polygon(0 0, 100% 0, 62% 46%, 62% 100%, 38% 84%, 38% 46%);
        transform: translateY(-50%);
    }
    .st-key-makina_iragazkia button::after {
        content: "⌄";
        display: block !important;
        position: absolute;
        right: 7px;
        top: 50%;
        color: currentColor;
        font-size: 16px;
        font-weight: 900;
        line-height: 1;
        transform: translateY(-58%);
    }
    .st-key-makina_iragazkia button[aria-expanded="true"]::after {
        content: "⌃";
        transform: translateY(-38%);
    }
    .st-key-makina_iragazkia button p {
        display: none !important;
    }
    .st-key-makina_iragazkia button svg {
        display: none !important;
    }
    .st-key-makina_bilaketa_tresnak {
        gap: 10px !important;
        align-items: center !important;
        min-height: 44px !important;
    }
    .st-key-makina_bilaketa_tresnak > div {
        align-self: center !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }

    /* Streamlit marrazten duen iragazki-panela ataritik kanpo dago;
       gai aktiboaren koloreak zuzenean aplikatu behar zaizkio. */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    [data-testid="stPopoverBody"] {
        background: var(--panel-bg, #FFFFFF) !important;
        color: var(--main-text, #0F172A) !important;
    }
    [data-testid="stPopoverBody"] {
        border: 1px solid var(--panel-border, #CBD5E1) !important;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18) !important;
    }
    [data-testid="stPopoverBody"] p,
    [data-testid="stPopoverBody"] label,
    [data-testid="stPopoverBody"] span {
        color: var(--main-text, #0F172A) !important;
    }
    .st-key-iragazki_arrisku_handia,
    .st-key-iragazki_arrisku_ertaina,
    .st-key-iragazki_arrisku_arina,
    .st-key-iragazki_arriskurik_ez {
        padding: 7px 9px !important;
        margin-bottom: 5px !important;
        border-radius: 8px !important;
        border: 1px solid var(--panel-border, #CBD5E1) !important;
    }
    .st-key-iragazki_arrisku_handia {
        background: var(--state-red-bg, #F5B8B8) !important;
    }
    .st-key-iragazki_arrisku_ertaina {
        background: var(--state-amber-bg, #F7E2AE) !important;
    }
    .st-key-iragazki_arrisku_arina {
        background: var(--state-blue-bg, #C8DEF4) !important;
    }
    .st-key-iragazki_arriskurik_ez {
        background: var(--state-green-bg, #C8EAD8) !important;
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
    .st-key-btn_aurrekoa,
    .st-key-btn_hurrengoa {
        margin-top: 5px !important;
        margin-bottom: 0 !important;
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
            height: auto !important;
        }
        .detail-info-grid {
            grid-template-columns: 1fr 1fr;
        }
        .detail-photo-wrapper {
            grid-template-columns: 1fr;
        }
        .st-key-btn_info_gehiago {
            position: static !important;
            width: 100% !important;
            margin: 6px 0 0 !important;
        }
    }
    </style>
    """)


@st.fragment
def makinak_erakutsi(
    makinak: list[dict[str, Any]],
    uneko_makina: dict[str, Any],
    makina_sarea: Osagaia | None = None,
    historiko_grafikoa: Osagaia | None = None,
    azken_neurketak: Osagaia | None = None,
) -> None:
    """Makinen informazioa"""

    _estiloak_txertatu()

    # URL query param bidez hautapena detektatu
    if "makina" in st.query_params:
        makina_param = st.query_params.get("makina")
        if makina_param and any(m["id"] == makina_param for m in makinak):
            if makina_param != st.session_state.hautatutako_makina:
                st.session_state.hautatutako_makina = makina_param
                uneko_makina = next(m for m in makinak if m["id"] == makina_param)

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
            <div class="kpi-sub">50 makina monitorizatuta</div>
            <div class="kpi-accent-circle" style="background:#EBF3FC;"></div>
        </div>
        <!-- 2. Larriak -->
        <div class="makina-kpi-box">
            <div class="kpi-label">Akats larriak</div>
            <div class="kpi-number" style="color:#DE4651;">{kopuru_larriak}</div>
            <div class="kpi-sub">Berehalako arreta</div>
            <div class="kpi-accent-circle" style="background:#FCE8E6;"></div>
        </div>
        <!-- 3. Ertainak -->
        <div class="makina-kpi-box">
            <div class="kpi-label">Akats ertainak</div>
            <div class="kpi-number" style="color:#D97706;">{kopuru_ertainak}</div>
            <div class="kpi-sub">Berrikuspena behar dute</div>
            <div class="kpi-accent-circle" style="background:#FEF3C7;"></div>
        </div>
        <!-- 4. Arinak -->
        <div class="makina-kpi-box">
            <div class="kpi-label">Akats arinak</div>
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
    # EZKERREKO ZUTABEA: MAKINEN INFORMAZIOA
    # ------------------------------------------
    with zutabe_ezkerra, st.container(key="makina_gallery_panel", border=False):
        st.html(f"""
        <div class="gallery-head-row">
            <span class="gallery-head-title">Makinen informazioa</span>
            <span class="gallery-head-count">{kopuru_guztira} makina</span>
        </div>
        <div class="gallery-head-sub">Hautatu makina bat datu osoak ikusteko</div>
        """)

        with st.container(
            key="makina_bilaketa_tresnak",
            horizontal=True,
            gap="small",
        ):
            bilaketa = st.text_input(
                "Bilatu",
                placeholder="⌕ Bilatu CNC-001...",
                label_visibility="collapsed",
                key="makina_bilaketa"
            )

            with st.popover(
                "Iragazkia",
                icon=":material/filter_alt:",
                use_container_width=True,
                key="makina_iragazkia",
            ):
                st.markdown("**Arrisku-maila**")
                arrisku_handia = st.checkbox(
                    "Arrisku handiko makinak", value=True,
                    key="iragazki_arrisku_handia"
                )
                arrisku_ertaina = st.checkbox(
                    "Arrisku ertaineko makinak", value=True,
                    key="iragazki_arrisku_ertaina"
                )
                arrisku_arina = st.checkbox(
                    "Arrisku arina", value=True,
                    key="iragazki_arrisku_arina"
                )
                arriskurik_ez = st.checkbox(
                    "Arriskurik ez", value=True,
                    key="iragazki_arriskurik_ez"
                )

        # Makinen zerrenda iragazi
        baimendutako_egoerak = {
            egoera
            for egoera, aktibo in (
                ("Larria", arrisku_handia),
                ("Ertaina", arrisku_ertaina),
                ("Arina", arrisku_arina),
                ("Normala", arriskurik_ez),
            )
            if aktibo
        }
        zerrenda = [
            makina for makina in guztiak_datuekin
            if makina["egoera_mota"] in baimendutako_egoerak
        ]

        if bilaketa.strip():
            hitza = bilaketa.strip().upper()
            zerrenda = [m for m in zerrenda if hitza in m["id"].upper()]

        # Mantendu xehetasun-panela eta nabigazioa ikusgai dagoen zerrendarekin
        # sinkronizatuta. Uneko makina iragazkitik kanpo geratzen bada,
        # iragazitako lehen makina hautatzen da.
        if zerrenda and not any(m["id"] == uneko_id for m in zerrenda):
            uneko_datuak = zerrenda[0]
            uneko_id = uneko_datuak["id"]
            st.session_state.hautatutako_makina = uneko_id
            st.query_params["makina"] = uneko_id

        # Txartelen HTML edukia sortu
        txartelak_html = []
        gai_parametroa = (
            "iluna" if st.session_state.get("gai_iluna", False) else "argia"
        )
        for m in zerrenda:
            hautatuta_klasea = " hautatuta" if m["id"] == uneko_id else ""
            argazki_uri = _makinaren_thumbnail_uri_datuak(m["zenbakia"])

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
        marka_html = {
            izena: (
                f'<span class="metric-alert-mark">{uneko_datuak[f"{izena}_marka"]}</span>'
                if uneko_datuak[f"{izena}_marka"] else ""
            )
            for izena in ("tenperatura", "rpm", "torque", "higadura")
        }
        tarte_normalen_html = ""
        if uneko_datuak["egoera_mota"] != "Normala":
            tarte_normalen_html = f"""
            <div class="detail-normal-ranges">
                <strong>Ohiko balioen erreferentzia</strong>
                <div class="detail-normal-range-list">
                    <span>Tenp.: {uneko_datuak['tenperatura_tartea']}</span>
                    <span>RPM: {uneko_datuak['rpm_tartea']}</span>
                    <span>Momentua: {uneko_datuak['torque_tartea']}</span>
                    <span>Higadura: {uneko_datuak['higadura_tartea']}</span>
                </div>
            </div>
            """
        gomendio_izenburua = {
            "Larria": "Lehentasunezko berrikuspena",
            "Ertaina": "Mantentze-berrikuspena",
            "Arina": "Jarraipena gomendatua",
            "Normala": "Makina egoera normalean",
        }[uneko_datuak["egoera_mota"]]

        st.html(f"""
        <div class="makina-detail-card detail-{uneko_datuak['klasea']}">
            <div class="detail-tag" style="color:{uneko_datuak['kolorea']};">HAUTATUTAKO MAKINA</div>
            <div class="detail-heading-row">
                <span class="detail-title">{uneko_datuak['id']}</span>
                <span class="detail-badge"
                      style="background:{uneko_datuak['badge_bg']}; color:{uneko_datuak['badge_text']}; border: 1px solid {uneko_datuak['border_kolorea']};">
                     {uneko_datuak['egoera_mota']}
                </span>
            </div>

            <!-- Sortutako WebP argazkia -->
            <div class="detail-photo-wrapper" style="border-color:{uneko_datuak['border_kolorea']};">
                <div class="detail-machine-photo">
                    <img class="detail-photo-img" src="{uneko_argazkia}" alt="{uneko_datuak['id']} makinaren argazkia" />
                </div>
                <div class="detail-health-box">
                    <div class="detail-health-heading">
                        <span>Makinen osasun-maila</span><small>Unekoa</small>
                    </div>
                    <div class="detail-health-row">
                        <div class="detail-health-row-heading">
                            <strong>{uneko_datuak['id']}</strong>
                            <span>{uneko_datuak['osasuna']}%</span>
                        </div>
                        <div class="detail-health-track" role="progressbar"
                             aria-label="{uneko_datuak['id']} osasun-maila"
                             aria-valuemin="0" aria-valuemax="100"
                             aria-valuenow="{uneko_datuak['osasuna']}">
                            <div class="detail-health-fill"
                                 style="width:{uneko_datuak['osasuna']}%; background:{uneko_datuak['osasun_kolorea']};"></div>
                        </div>
                    </div>
                    <div class="detail-health-actions">
                        <div class="detail-recom-box"
                             style="background:{uneko_datuak['bg_kolorea']}; border:1.5px solid {uneko_datuak['border_kolorea']};">
                            <div class="detail-recom-title" style="color:{uneko_datuak['kolorea']};">
                                {uneko_datuak['abisu_ikonoa']} {gomendio_izenburua}
                            </div>
                            <div class="detail-recom-desc">{uneko_datuak['ekintza']}</div>
                        </div>
                        <div class="detail-health-action-space" aria-hidden="true"></div>
                    </div>
                </div>
            </div>

            <div class="detail-loc-box">
                <strong>Enpresako kokapena:</strong> {uneko_datuak['kokapena']}<br/>
                <small>Produkzio-eremua · CNC gunea</small>
            </div>

            <!-- 4 Metrika nagusiak (2x2) -->
            <div class="detail-metrics-grid">
                <div class="detail-metric-card {uneko_datuak['tenperatura_klasea']}">
                    <div class="detail-metric-header">🌡 Tenperatura {marka_html['tenperatura']}</div>
                    <div class="detail-metric-val">{uneko_datuak['tenperatura']:.1f} °C</div>
                </div>
                <div class="detail-metric-card {uneko_datuak['rpm_klasea']}">
                    <div class="detail-metric-header">⚙ Abiadura {marka_html['rpm']}</div>
                    <div class="detail-metric-val">{uneko_datuak['rpm']} RPM</div>
                </div>
                <div class="detail-metric-card {uneko_datuak['torque_klasea']}">
                    <div class="detail-metric-header">⟳ Momentua {marka_html['torque']}</div>
                    <div class="detail-metric-val">{uneko_datuak['torque']:.1f} Nm</div>
                </div>
                <div class="detail-metric-card {uneko_datuak['higadura_klasea']}">
                    <div class="detail-metric-header">🕒 Higadura {marka_html['higadura']}</div>
                    <div class="detail-metric-val">{uneko_datuak['higadura']} min</div>
                </div>
            </div>

            {tarte_normalen_html}

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
                <div class="detail-info-card">
                    <small>Funtzionamendu-orduak guztira</small>
                    <strong>{uneko_datuak['funtzionamendu_orduak']:,} ordu</strong>
                </div>
                <div class="detail-info-card">
                    <small>Azken mantentze-lanetik igarotako orduak</small>
                    <strong>{uneko_datuak['mantentzetik_orduak']:,} ordu</strong>
                </div>
                <div class="detail-info-card">
                    <small>Azken mantentze-lanetik egindako zikloak</small>
                    <strong>{uneko_datuak['mantentzetik_zikloak']:,} ziklo</strong>
                </div>
                <div class="detail-info-card">
                    <small>Kargapean emandako denbora</small>
                    <strong>{uneko_datuak['kargapeko_orduak']:,} ordu</strong>
                </div>
            </div>

            <div class="detail-navigation-slots">
                <div class="detail-navigation-prev" aria-hidden="true"></div>
                <div class="detail-navigation-next" aria-hidden="true"></div>
            </div>

        </div>
        """)

        if st.button(
            "Info gehiago +",
            key="btn_info_gehiago",
            use_container_width=True,
        ):
            _makina_xehetasunak_modal(uneko_datuak)

        # Nabigazio botoiak: ← Aurrekoa  eta  Hurrengoa →
        col_prev, col_next = st.columns(2)
        uneko_indizea = next(
            (i for i, m in enumerate(zerrenda) if m["id"] == uneko_id),
            0
        )

        def nabigatu_makina(norabidea: int) -> None:
            indizea = (uneko_indizea + norabidea) % len(zerrenda)
            berria = zerrenda[indizea]["id"]
            st.session_state.hautatutako_makina = berria
            st.query_params["makina"] = berria

        with col_prev:
            st.button(
                "← Aurrekoa", key="btn_aurrekoa",
                use_container_width=True, disabled=not zerrenda,
                on_click=nabigatu_makina,
                args=(-1,),
            )

        with col_next:
            st.button(
                "Hurrengoa →", key="btn_hurrengoa",
                use_container_width=True, disabled=not zerrenda,
                on_click=nabigatu_makina,
                args=(1,),
            )

        st.html("""
        <div class="footer-note" style="text-align:center;">
            CNC bakoitzak bere informazio-fitxa du.
        </div>
        """)
