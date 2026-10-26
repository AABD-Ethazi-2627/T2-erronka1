"""Datuen analisi teknikorako osagai osagarriak."""

import streamlit as st


OSASUN_MAILAK = (
    ("CNC-004", 19, "#E86B86"),
    ("CNC-012", 44, "#E5AE50"),
    ("CNC-021", 72, "#4DA9DC"),
    ("CNC-035", 96, "#49BE98"),
)


def osasun_mailak_erakutsi() -> None:
    """Makinen osasun-mailak barra horizontaletan erakutsi."""
    errenkadak = []
    for makina_id, ehunekoa, kolorea in OSASUN_MAILAK:
        errenkadak.append(f"""
        <div class="health-row">
            <div class="health-row-heading">
                <strong>{makina_id}</strong><span>{ehunekoa}%</span>
            </div>
            <div class="health-track" role="progressbar"
                 aria-label="{makina_id} osasun-maila"
                 aria-valuemin="0" aria-valuemax="100" aria-valuenow="{ehunekoa}">
                <div class="health-fill"
                     style="width:{ehunekoa}%; background:{kolorea};"></div>
            </div>
        </div>
        """)

    st.html(f"""
    <style>
    .machine-health-panel {{
        margin-top: 12px;
        padding: 14px 16px 13px;
        border: 1px solid var(--panel-border, #D9E3EC);
        border-radius: 14px;
        background: var(--panel-bg, #FFFFFF);
        color: var(--main-text, #142A40);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
    }}
    .health-panel-heading {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 11px;
    }}
    .health-panel-heading strong {{ font-size: 15px; font-weight: 800; }}
    .health-panel-heading span {{
        color: var(--secondary-text, #526578); font-size: 10px;
    }}
    .health-row {{ margin-bottom: 10px; }}
    .health-row:last-child {{ margin-bottom: 0; }}
    .health-row-heading {{
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 5px;
        font-size: 11px;
    }}
    .health-row-heading strong,
    .health-row-heading span {{
        color: var(--main-text, #142A40); font-weight: 800;
    }}
    .health-track {{
        width: 100%;
        height: 8px;
        overflow: hidden;
        border-radius: 999px;
        background: var(--surface-muted, #E6ECF1);
    }}
    .health-fill {{ height: 100%; border-radius: inherit; }}
    </style>
    <section class="machine-health-panel">
        <div class="health-panel-heading">
            <strong>Makinen osasun-maila</strong><span>Adibidea</span>
        </div>
        {''.join(errenkadak)}
    </section>
    """)
