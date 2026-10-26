"""Hasiera orriaren osaera."""

from collections.abc import Callable

import streamlit as st

Osagaia = Callable[[], None]


def hasiera_erakutsi(
    kpi_txartelak: Osagaia,
    egoera_zerbitzuak: Osagaia,
    telemetria_taula: Osagaia,
    historiko_grafikoa: Osagaia,
    azken_neurketak: Osagaia,
    makina_sarea: Osagaia,
    egutegia: Osagaia,
) -> None:
    """Hasierako dashboard osoa marraztu."""

    kpi_txartelak()
    egoera_zerbitzuak()

    telemetria_zutabea, historiko_zutabea, neurketa_zutabea = st.columns(
        [2.5, 2, 1.5],
        gap="small",
    )

    with telemetria_zutabea, st.container(key="telemetry_panel"):
        telemetria_taula()

    with historiko_zutabea, st.container(key="history_panel"):
        historiko_grafikoa()

    with neurketa_zutabea, st.container(key="measure_panel"):
        azken_neurketak()

    mapa_zutabea, egutegi_zutabea = st.columns(
        [1, 1.5],
        gap="small",
    )

    with mapa_zutabea:
        makina_sarea()

    with egutegi_zutabea, st.container(key="calendar_panel"):
        egutegia()
