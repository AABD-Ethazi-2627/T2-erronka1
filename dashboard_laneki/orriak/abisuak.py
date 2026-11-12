"""Current alert levels and explicit business scenarios, never expected losses."""

import streamlit as st
from read_contracts import scenario
from orriak.costs import render_costs

from orriak.shared import measurements


def abisuak_erakutsi(makinak):
    render_costs(makinak)
    st.subheader("Uneko abisu inferituak")
    st.caption(
        "Maila inferitua ez da behatutako matxura edo etorkizuneko probabilitatea."
    )
    left, right = st.columns([2.35, 1])
    with left:
        for machine in sorted(
            makinak,
            key=lambda m: {"Akatsa": 0, "Berrikusteko": 1, "Normala": 2}[m["egoera"]],
        ):
            with st.expander(f"{machine['id']} · {machine['egoera']}", expanded=True):
                measurements(machine)
    with right:
        st.subheader("Kostu-eszenarioa")
        st.caption(
            "Suposizioak, ez neurketak. Makina bakarreko esposizioa; ez espero den galera."
        )
        inspection = st.number_input("Ikuskapen-kostua (€)", min_value=0.0, value=0.0)
        hours = st.number_input("Suposatutako geldialdia (h)", min_value=0.0, value=0.0)
        hourly = st.number_input(
            "Suposatutako orduko kostua (€/h)", min_value=0.0, value=0.0
        )
        try:
            st.metric(
                "Eszenarioaren esposizioa (€)",
                f"{scenario(inspection, hours, hourly):g}",
            )
        except ValueError:
            st.error("Eszenarioaren sarrerak baliogabeak dira.")
        st.caption("Ikuskapena + geldialdi-orduak × orduko kostua")
