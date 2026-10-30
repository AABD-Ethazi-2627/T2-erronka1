"""Makinen abisuak eta kostu-arriskua lehenesteko orria."""

from typing import Any

import streamlit as st


GALERA_MAILAKA = {
    "alert-critical": 1_200,
    "alert-high": 800,
    "alert-review": 400,
}

PROBABILITATE_MAILAKA = {
    "alert-critical": 1.00,
    "alert-high": 0.72,
    "alert-review": 0.42,
}

GELDIALDI_ORDUAK_MAILAKA = {
    "alert-critical": 6.0,
    "alert-high": 4.0,
    "alert-review": 2.0,
}


def _lehentasun_datuak(makina: dict[str, Any]) -> dict[str, Any]:
    """Makinaren larritasuna eta gomendatutako ekintza kalkulatu."""

    higadura = int(makina["higadura"])
    tenperatura = float(makina["tenperatura"])
    momentua = float(makina["torque"])
    zenbakia = int(makina["zenbakia"])
    lerroa = chr(65 + (zenbakia - 1) // 10)
    kokapena = (zenbakia - 1) % 10 + 1

    if makina["egoera"] == "Akatsa":
        maila = "Kritikoa"
        klasea = "alert-critical"
        ekintza = "Makina gelditu eta berehala berrikusi"
        ordena = 3_000 + higadura
    elif higadura >= 200 or momentua >= 44:
        maila = "Altua"
        klasea = "alert-high"
        ekintza = "Txanda honetan ikuskapena egin"
        ordena = 2_000 + higadura + momentua
    else:
        maila = "Ertaina"
        klasea = "alert-review"
        ekintza = "Hurrengo geldialdian berrikusi"
        ordena = 1_000 + higadura + tenperatura

    galera_orduko = float(
        makina.get("geldialdi_kostua_orduko", GALERA_MAILAKA[klasea])
    )
    probabilitatea = float(
        makina.get("matxura_probabilitatea", makina.get("riesgo_fallo", PROBABILITATE_MAILAKA[klasea]))
    )
    if probabilitatea > 1:
        probabilitatea /= 100
    probabilitatea = max(0.0, min(1.0, probabilitatea))
    geldialdi_orduak = max(0.0, float(
        makina.get("aurreikusitako_geldialdia_ordu", GELDIALDI_ORDUAK_MAILAKA[klasea])
    ))
    galera_potentziala = galera_orduko * geldialdi_orduak
    galera_esperoa = galera_potentziala * probabilitatea

    return {
        "makina": makina,
        "maila": maila,
        "klasea": klasea,
        "ekintza": ekintza,
        "ordena": ordena,
        "lerroa": lerroa,
        "kokapena": kokapena,
        "galera_orduko": galera_orduko,
        "probabilitatea": probabilitatea,
        "geldialdi_orduak": geldialdi_orduak,
        "galera_potentziala": galera_potentziala,
        "galera_esperoa": galera_esperoa,
    }


@st.fragment
def abisuak_erakutsi(makinak: list[dict[str, Any]]) -> None:
    """Abisuak larritasunaren arabera eta kostuekin erakutsi."""

    abisuak = [
        _lehentasun_datuak(makina)
        for makina in makinak
        if makina["egoera"] in {"Akatsa", "Berrikusteko"}
    ]
    abisuak.sort(key=lambda datua: datua["ordena"], reverse=True)

    kritikoak = sum(d["klasea"] == "alert-critical" for d in abisuak)
    handiak = sum(d["klasea"] == "alert-high" for d in abisuak)
    ertainak = sum(d["klasea"] == "alert-review" for d in abisuak)
    galera_kritikoa = sum(d["galera_orduko"] for d in abisuak if d["klasea"] == "alert-critical")
    galera_handia = sum(d["galera_orduko"] for d in abisuak if d["klasea"] == "alert-high")
    galera_ertaina = sum(d["galera_orduko"] for d in abisuak if d["klasea"] == "alert-review")
    galera_guztira = sum(d["galera_orduko"] for d in abisuak)
    galera_potentziala = sum(d["galera_potentziala"] for d in abisuak)
    galera_esperoa = sum(d["galera_esperoa"] for d in abisuak)

    st.html(f"""
    <section class="alerts-summary">
        <div class="alerts-summary-card summary-red"><span>Kritikoa</span><strong>{kritikoak}</strong><small>{GALERA_MAILAKA['alert-critical']:,} €/h makina bakoitzeko</small></div>
        <div class="alerts-summary-card summary-high"><span>Altua</span><strong>{handiak}</strong><small>{GALERA_MAILAKA['alert-high']:,} €/h makina bakoitzeko</small></div>
        <div class="alerts-summary-card summary-medium"><span>Ertaina</span><strong>{ertainak}</strong><small>{GALERA_MAILAKA['alert-review']:,} €/h makina bakoitzeko</small></div>
        <div class="alerts-summary-card summary-risk"><span>Aurreikusitako galera</span><strong>{galera_esperoa:,.0f} €</strong><small>Arriskua eta geldialdi-denbora kontuan hartuta</small></div>
    </section>
    """)

    zerrenda_zutabea, kostu_zutabea = st.columns([2.35, 1], gap="small")

    with zerrenda_zutabea:
        st.markdown(
            '<div class="alerts-section-heading">'
            'Lehentasunezko jarduketa-zerrenda</div>',
            unsafe_allow_html=True,
        )

        txartelak = []
        for posizioa, datua in enumerate(abisuak, start=1):
            makina = datua["makina"]
            kostu_etiketa = "Aurreikusitako galera"
            txartelak.append(f"""
            <article class="alert-machine-row {datua['klasea']}">
                <div class="alert-rank">{posizioa}</div>
                <div class="alert-machine-name"><strong>{makina['id']}</strong><span>{datua['lerroa']} lerroa · {datua['kokapena']}. kokapena</span></div>
                <div class="alert-level"><span>{datua['maila']}</span><small>{datua['ekintza']}</small></div>
                <div class="alert-readings"><small>Neurketak</small><span>{makina['tenperatura']:.1f} °C</span><span>{makina['rpm']} RPM</span><span>{makina['higadura']} min</span></div>
                <div class="alert-cost"><small>{kostu_etiketa}</small><strong>{datua['galera_esperoa']:,.0f} €</strong><span>{datua['probabilitatea']:.0%} arriskua · {datua['geldialdi_orduak']:g} h · {datua['galera_orduko']:,.0f} €/h</span></div>
            </article>
            """)

        st.html(
            '<div class="alerts-list">'
            + "".join(txartelak)
            + '</div>'
        )

    with kostu_zutabea:
        st.html(f"""
        <section class="cost-panel">
            <div class="cost-panel-icon">€</div>
            <span>GALERA EKONOMIKO PREDIKTIBOAREN LABURPENA</span>
            <strong>{galera_esperoa:,.0f} €</strong>
            <small>Makina bakoitzaren arriskuaren arabera espero den galera</small>
            <div class="cost-formula">Probabilitatea × aurreikusitako geldialdi-orduak × orduko kostua</div>
            <hr>
            <div class="cost-detail"><span>Espero den galera</span><b>{galera_esperoa:,.0f} €</b></div>
            <div class="cost-detail"><span>Galera potentziala</span><b>{galera_potentziala:,.0f} €</b></div>
            <div class="cost-detail"><span>Orduko esposizioa</span><b>{galera_guztira:,.0f} €/h</b></div>
            <div class="cost-detail"><span>Kritikoen esposizioa / h</span><b>{galera_kritikoa:,} €</b></div>
            <div class="cost-detail"><span>Altuen esposizioa / h</span><b>{galera_handia:,} €</b></div>
            <div class="cost-detail"><span>Ertainen esposizioa / h</span><b>{galera_ertaina:,} €</b></div>
            <p>Simulazioan larritasunaren araberako balioak erabiltzen dira. Datu errealekin makina bakoitzak bere probabilitatea, geldialdi-denbora eta orduko kostua izango ditu.</p>
        </section>
        """)
