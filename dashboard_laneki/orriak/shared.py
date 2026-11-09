"""Common rendering keeps raw readings and provenance separate from decoration."""

import math

import streamlit as st

SENSORS = {
    "tenperatura": "Prozesu-tenperatura (°C)",
    "giro_tenperatura": "Giro-tenperatura (°C)",
    "rpm": "Abiadura (RPM)",
    "torque": "Bihurdura-momentua (Nm)",
    "higadura": "Erremintaren higadura (min)",
}


def fmt(value):
    if value is None:
        return "Ez dago daturik"
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return f"{value:g}" if math.isfinite(value) else "Ez dago daturik"
    return str(value)


def measurements(machine):
    st.write("Maila inferitua:", machine["egoera"])
    for key, label in SENSORS.items():
        st.metric(label, fmt(machine.get(key)))


def provenance(machine):
    st.caption("Akatsa: uneko alerta inferitua, ez behatutako matxura")
    st.caption(
        f"Behaketa (UTC): {fmt(machine.get('timestamp'))} · "
        f"Adina (s): {fmt(machine.get('age_seconds'))}"
    )
    with st.expander("Jatorria eta identitatea"):
        for key, label in (
            ("event_id", "Gertaera"),
            ("event_key", "Gertaera-gako kanonikoa"),
            ("timestamp", "Behaketa (UTC)"),
            ("scored_at", "Inferentzia (UTC)"),
            ("as_of", "Kontsultaren ebaketa (UTC)"),
            ("age_seconds", "Adina (s)"),
            ("prediction_scope", "Eremua"),
            ("score_semantics", "Scorearen esanahia"),
        ):
            st.write(label + ":", fmt(machine.get(key)))
        st.json(machine)


def pause_live_reads():
    """Widget callback runs before app widgets, preserving inspection cutoffs."""
    if "live_updates" in st.session_state:
        st.session_state.live_updates = False
