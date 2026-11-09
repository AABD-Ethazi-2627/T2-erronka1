"""Source-preserving gallery, adapted from feat/dashboard 04d1bb1."""

from base64 import b64encode
from html import escape
from pathlib import Path

import streamlit as st
from domain import gallery_machine

from orriak.shared import fmt, measurements, pause_live_reads, provenance


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


@st.dialog("Makinen datuak", width="large")
def _makina_xehetasunak_modal(datuak):
    st.subheader(datuak["id"])
    measurements(datuak)
    st.caption("Uneko inferentzia · ez da etorkizuneko probabilitatea")
    st.write("Score [0,1]:", fmt(datuak.get("failure_score")))
    st.write("Alerta:", datuak.get("alert_level") or "Ez dago daturik")
    st.info(
        "Osasuna, bibrazioa, korrontea, mantentzea eta aurreikuspena: ez dago daturik."
    )
    provenance(datuak)


def makinak_erakutsi(makinak, uneko_makina, **kwargs):
    _estiloak_txertatu()
    st.caption("Uneko maila inferituak · ez dira behatutako matxurak")
    for col, state in zip(st.columns(3), ("Normala", "Berrikusteko", "Akatsa")):
        col.metric(state, sum(m["egoera"] == state for m in makinak))
    left, right = st.columns([1.52, 1])
    with left:
        query = st.text_input("Bilatu", key="makina_bilaketa")
        states = st.multiselect(
            "Maila inferitua",
            ["Normala", "Berrikusteko", "Akatsa"],
            default=["Normala", "Berrikusteko", "Akatsa"],
        )
        rows = [
            m for m in makinak if query.upper() in m["id"] and m["egoera"] in states
        ]
        if not rows:
            st.info("Ez da makinarik aurkitu.")
        cards = []
        theme = "iluna" if st.session_state.get("gai_iluna") else "argia"
        for row in rows:
            m = gallery_machine(row)
            picture = (
                Path(__file__).resolve().parents[1]
                / "assets/images/cnc"
                / f"cnc-{m['zenbakia']:03d}.webp"
            )
            image = ""
            if picture.exists():
                uri = b64encode(picture.read_bytes()).decode("ascii")
                image = f'<img class="cnc-card-thumb" src="data:image/webp;base64,{uri}" alt="Irudi ilustratiboa"/>'
            values = "".join(
                f'<div class="cnc-card-metric-row"><span>{label}</span><span>{escape(fmt(m.get(key)))}</span></div>'
                for key, label in (
                    ("tenperatura", "Prozesua °C"),
                    ("rpm", "RPM"),
                    ("torque", "Nm"),
                    ("higadura", "min"),
                )
            )
            cards.append(
                f'<a class="cnc-item-card card-{m["klasea"]}" href="?orria=Makinak&makina={m["id"]}&gaia={theme}" target="_self"><div class="cnc-card-top">{image}<strong>{m["id"]}</strong><span>{m["egoera"]}</span></div>{values}<small>Maila inferitua · irudi ilustratiboa</small></a>'
            )
        st.html(
            '<div class="gallery-outer-card"><div class="gallery-scroll-list"><div class="gallery-cards-grid">'
            + "".join(cards)
            + "</div></div></div>"
        )
    with right:
        st.subheader(uneko_makina["id"])
        measurements(uneko_makina)
        st.write("Kokapena:", uneko_makina.get("kokapena") or "Ez dago daturik")
        if st.button("Xehetasunak", key="machine_details", on_click=pause_live_reads):
            _makina_xehetasunak_modal(uneko_makina)
        provenance(uneko_makina)
