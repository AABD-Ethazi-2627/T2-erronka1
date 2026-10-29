"""Makinen abisuak eta kostu-arriskua lehenesteko orria."""

from typing import Any

import streamlit as st


GALERA_MAILAKA = {
    "alert-critical": 1_200,
    "alert-high": 800,
    "alert-review": 400,
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

    return {
        "makina": makina,
        "maila": maila,
        "klasea": klasea,
        "ekintza": ekintza,
        "ordena": ordena,
        "lerroa": lerroa,
        "kokapena": kokapena,
        "galera_orduko": GALERA_MAILAKA[klasea],
    }


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
    galera_kritikoa = kritikoak * GALERA_MAILAKA["alert-critical"]
    galera_handia = handiak * GALERA_MAILAKA["alert-high"]
    galera_ertaina = ertainak * GALERA_MAILAKA["alert-review"]
    galera_guztira = sum(d["galera_orduko"] for d in abisuak)

    st.html(f"""
    <section class="alerts-summary">
        <div class="alerts-summary-card summary-red"><span>Kritikoa</span><strong>{kritikoak}</strong><small>{GALERA_MAILAKA['alert-critical']:,} €/h makina bakoitzeko</small></div>
        <div class="alerts-summary-card summary-high"><span>Altua</span><strong>{handiak}</strong><small>{GALERA_MAILAKA['alert-high']:,} €/h makina bakoitzeko</small></div>
        <div class="alerts-summary-card summary-medium"><span>Ertaina</span><strong>{ertainak}</strong><small>{GALERA_MAILAKA['alert-review']:,} €/h makina bakoitzeko</small></div>
        <div class="alerts-summary-card summary-risk"><span>Galera guztira</span><strong>{galera_guztira:,} €/h</strong><small>Gelditutako makina guztien batura</small></div>
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
            kostu_etiketa = "Makina honen galera"
            txartelak.append(f"""
            <article class="alert-machine-row {datua['klasea']}">
                <div class="alert-rank">{posizioa}</div>
                <div class="alert-machine-name"><strong>{makina['id']}</strong><span>{datua['lerroa']} lerroa · {datua['kokapena']}. kokapena</span></div>
                <div class="alert-level"><span>{datua['maila']}</span><small>{datua['ekintza']}</small></div>
                <div class="alert-readings"><small>Neurketak</small><span>{makina['tenperatura']:.1f} °C</span><span>{makina['rpm']} RPM</span><span>{makina['higadura']} min</span></div>
                <div class="alert-cost"><small>{kostu_etiketa}</small><strong>{datua['galera_orduko']:,} €/h</strong></div>
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
            <span>GALERA EKONOMIKOAREN LABURPENA</span>
            <strong>{galera_guztira:,} €/h</strong>
            <small>Gelditutako makina guztien orduko galera</small>
            <div class="cost-formula"><b>{kritikoak}</b> kritiko × 1.200 + <b>{handiak}</b> altu × 800 + <b>{ertainak}</b> ertain × 400</div>
            <hr>
            <div class="cost-detail"><span>Kritikoen galera / h</span><b>{galera_kritikoa:,} €</b></div>
            <div class="cost-detail"><span>Altuen galera / h</span><b>{galera_handia:,} €</b></div>
            <div class="cost-detail"><span>Ertainen galera / h</span><b>{galera_ertaina:,} €</b></div>
            <div class="cost-detail"><span>Ordubeteko galera guztira</span><b>{galera_guztira:,} €</b></div>
            <div class="cost-detail"><span>8 orduko txandako galera</span><b>{galera_guztira * 8:,} €</b></div>
            <div class="cost-detail"><span>24 orduko galera</span><b>{galera_guztira * 24:,} €</b></div>
            <p>Demo-kalkulua makina geldirik dagoela suposatuz: kritikoa 1.200 €/h, altua 800 €/h eta ertaina 400 €/h.</p>
        </section>
        """)
