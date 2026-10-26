"""Makinen abisuak eta kostu-arriskua lehenesteko orria."""

from typing import Any

import streamlit as st


GALERA_ORDUKO = 1_200


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
        maila = "Lehentasun handia"
        klasea = "alert-high"
        ekintza = "Txanda honetan ikuskapena egin"
        ordena = 2_000 + higadura + momentua
    else:
        maila = "Berrikusteko"
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
    }


def abisuak_erakutsi(makinak: list[dict[str, Any]]) -> None:
    """Abisuak larritasunaren arabera eta kostuekin erakutsi."""

    abisuak = [
        _lehentasun_datuak(makina)
        for makina in makinak
        if makina["egoera"] in {"Akatsa", "Berrikusteko"}
    ]
    abisuak.sort(key=lambda datua: datua["ordena"], reverse=True)

    kritikoak = sum(
        datua["makina"]["egoera"] == "Akatsa"
        for datua in abisuak
    )
    berrikustekoak = len(abisuak) - kritikoak
    galera_egiaztatua = kritikoak * GALERA_ORDUKO
    balizko_galera = berrikustekoak * GALERA_ORDUKO
    gehieneko_esposizioa = len(abisuak) * GALERA_ORDUKO

    st.markdown(
        '<div class="alerts-page-title">Abisuak eta lehentasunak</div>'
        '<div class="alerts-page-subtitle">'
        'Egoera okerrenetik onenera ordenatuta · '
        'galera 1.200 €/h matxuratutako makina bakoitzeko'
        '</div>',
        unsafe_allow_html=True,
    )

    st.html(f"""
    <section class="alerts-summary">
        <div class="alerts-summary-card summary-red"><span>Akats kritikoak</span><strong>{kritikoak}</strong><small>Berehalako jarduketa</small></div>
        <div class="alerts-summary-card summary-amber"><span>Berrikusteko</span><strong>{berrikustekoak}</strong><small>Planifikatu beharrekoak</small></div>
        <div class="alerts-summary-card summary-money"><span>Uneko galera</span><strong>{galera_egiaztatua:,} €/h</strong><small>Matxuratutako makinengatik, orduko</small></div>
        <div class="alerts-summary-card summary-risk"><span>Balizko galera</span><strong>{balizko_galera:,} €/h</strong><small>Berrikusteko makinak matxuratuz gero</small></div>
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
            kostu_etiketa = (
                "Egiaztatutako galera"
                if makina["egoera"] == "Akatsa"
                else "Matxura-arriskua"
            )
            txartelak.append(f"""
            <article class="alert-machine-row {datua['klasea']}">
                <div class="alert-rank">{posizioa}</div>
                <div class="alert-machine-name"><strong>{makina['id']}</strong><span>{datua['lerroa']} lerroa · {datua['kokapena']}. kokapena</span></div>
                <div class="alert-level"><span>{datua['maila']}</span><small>{datua['ekintza']}</small></div>
                <div class="alert-readings"><span>{makina['tenperatura']:.1f} °C</span><span>{makina['rpm']} RPM</span><span>{makina['higadura']} min</span></div>
                <div class="alert-cost"><small>{kostu_etiketa}</small><strong>{GALERA_ORDUKO:,} €/h</strong></div>
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
            <strong>{galera_egiaztatua:,} €/h</strong>
            <small>Matxuratutako makinek ordu bakoitzean eragindako galera</small>
            <div class="cost-formula"><b>{kritikoak}</b> makina matxuratuta × <b>{GALERA_ORDUKO:,} €/h</b></div>
            <hr>
            <div class="cost-detail"><span>Ordubeteko galera</span><b>{galera_egiaztatua:,} €</b></div>
            <div class="cost-detail"><span>8 orduko txandako galera</span><b>{galera_egiaztatua * 8:,} €</b></div>
            <div class="cost-detail"><span>24 orduko galera</span><b>{galera_egiaztatua * 24:,} €</b></div>
            <div class="cost-detail"><span>Gehieneko arriskua orduko</span><b>{gehieneko_esposizioa:,} €/h</b></div>
            <p>Kalkulua: 1.200 €/h matxuratutako makina bakoitzeko. Berrikusteko makinen zenbatekoa balizko arriskua da.</p>
        </section>
        """)
