"""Committed history and separately identified offline binary evaluation."""

import altair as alt
import pandas as pd
import streamlit as st
from read_contracts import COLUMNS, evaluation, history

from orriak.shared import measurements, pause_live_reads


def show_history(payload, aggregate=False):
    try:
        frame = history(payload)
    except (ValueError, TypeError, OverflowError):
        st.warning(
            "Historikoa degradatuta edo ez dago eskuragarri; ez da simulaziorik sortu."
        )
        return
    st.caption(
        "Predikzio-erregistroen batezbesteko agregatuak · n eta azken erreferentzia metadatuetan"
        if aggregate
        else "Artxibatutako predikzio-erregistroen banakako laginak"
    )
    st.write("Estaldura, UTC mugak eta jatorria")
    st.json(frame.attrs["metadata"])
    if frame.empty:
        st.info("Ez dago laginik leiho honetan.")
    else:
        st.dataframe(frame, hide_index=True)
        for name in COLUMNS[1:]:
            if frame[name].notna().any():
                st.altair_chart(
                    alt.Chart(frame)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("Ordua:T", title="Ordua (UTC)"),
                        y=alt.Y(f"{name}:Q", title=name),
                        tooltip=["Ordua:T", alt.Tooltip(f"{name}:Q")],
                    ),
                    width="stretch",
                )
    if frame.attrs["next_cursor"]:
        st.warning("Orrialde partziala · emaitza gehiago daude; ez da leiho osoa.")


def datuak_erakutsi(machine, fetch, mode):
    st.subheader(f"{machine['id']} · Datuak")
    with st.expander("Azken neurketa", expanded=True):
        measurements(machine)
    label = (
        st.segmented_control(
            "Denbora-tartea",
            ["Laginak", "Astea", "Hilabetea", "Sei hilabete"],
            default="Astea",
            key="datuak_periodoa",
        )
        or "Astea"
    )
    if mode == "api":
        if label == "Laginak":
            # Page explicitly; never imply that the first 1000 rows cover all events.
            cursor_key = f"history_cursor_{machine['id']}"
            cursor = st.session_state.get(cursor_key)
            from urllib.parse import urlencode

            endpoint = f"historikoa/{machine['id']}" + (
                "?" + urlencode({"cursor": cursor}) if cursor else ""
            )
            payload = fetch(endpoint)
            show_history(payload)
            next_cursor = (
                payload.get("next_cursor") if isinstance(payload, dict) else None
            )
            if next_cursor or cursor:
                st.caption("Orrialdez aldatzean zuzeneko eguneratzea pausatzen da.")
            if next_cursor and st.button(
                "Hurrengo orrialdea", on_click=pause_live_reads
            ):
                st.session_state[cursor_key] = next_cursor
                st.rerun()
            if cursor and st.button("Lehen orrialdea", on_click=pause_live_reads):
                st.session_state.pop(cursor_key, None)
                st.rerun()
        else:
            periods = fetch(f"historikoa/{machine['id']}/periodoak")
            key = {
                "Astea": "astea",
                "Hilabetea": "hilabetea",
                "Sei hilabete": "sei_hilabete",
            }[label]
            show_history(
                periods.get(key) if isinstance(periods, dict) else None, aggregate=True
            )
    else:
        st.info("DEMO · ez dago artxibatutako historiko egiaztaturik.")
    st.subheader("Ereduaren offline ebaluazio bitarra")
    st.caption(
        "Ez da makinaren uneko ebaluazioa. Balidazioa atalasea doitzeko berrerabili bada, ez da azken testa."
    )
    payload = fetch("model-evaluation") if mode == "api" else None
    try:
        metrics = evaluation(payload, machine)
    except (ValueError, TypeError, OverflowError) as exc:
        st.info(f"Ebaluazioa ez dago eskuragarri edo bateraezina da: {exc}")
        return
    st.write("Ebaluatutako erabaki-araua:", payload["decision_rule"])
    st.write("Ebaluazioaren atalase zehatza:", payload["threshold"])
    st.caption(
        "AVISO / CRITICA aurkezpen-mailak (0.15 / 0.70) bereiziak dira; matrize hau goiko erabaki-arauari dagokio."
    )
    st.dataframe(
        pd.DataFrame(
            payload["confusion_matrix"],
            index=["Benetakoa 0", "Benetakoa 1"],
            columns=["Inferitua 0", "Inferitua 1"],
        )
    )
    st.write(metrics)
    st.json(payload)
