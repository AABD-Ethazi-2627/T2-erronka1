"""Kostuen taula ofiziala: alertak eta emaitza baieztatuak bereizita."""
from datetime import datetime, UTC
import streamlit as st
from operating_costs import official_alert_budget


def render_costs(machines):
    st.subheader('Alerta aktiboen kostu operatibo estimatua')
    st.caption('Makina bakoitzaren azken AVISO/CRITICA behaketa. Alerta ez da matxura baieztatua. Datuak freskatzean berriz kalkulatzen da; ez da gastua metatzen.')
    with st.expander('Kostuen taula ofiziala eta indarraldia'):
        st.table([{'Kasua': 'FN', 'Kostua (€)': 5000}, {'Kasua': 'FP', 'Kostua (€)': 200}, {'Kasua': 'TP', 'Kostua (€)': 300}, {'Kasua': 'TN', 'Kostua (€)': 0}])
        freshness = st.number_input('Behaketaren gehieneko adina (min)', min_value=1.0, value=30.0, key='cost_freshness')
        st.caption('FNren 5.000 €-ek geldialdia eta konponketa barne hartzen dituzte: ez dira 3 × 1.200 € berriro gehitzen. Indarraldia panelaren parametroa da.')
    cutoff = st.session_state.get('read_as_of', datetime.now(UTC).isoformat())
    try:
        result = official_alert_budget(machines, cutoff, freshness)
    except (ValueError, OverflowError):
        st.error('Ezin da kostua kalkulatu: berrikusi datuak.')
        return
    cols = st.columns(3)
    cols[0].metric('Alerta aktiboak', result['active'])
    cols[1].metric('Alerten kostu-tartea', f"{result['minimum']:,.0f}–{result['maximum']:,.0f} €")
    cols[2].metric('Emaitza baieztatuen kostua', 'E/D')
    st.caption('Beheko muga: alerta guztiak FP balira. Goikoa: guztiak TP balira. Alerta bakoitzeko esku-hartze bakarra suposatzen da. Ez da espero den galera edo lantegi osoaren gehieneko kostua: FNak ez dira alerta-zerrendan ikusten.')
    if result['stale'] or result['invalid']:
        st.warning(f"Kalkulutik kanpo: {result['stale']} makina datu zaharrekin eta {result['invalid']} behaketa baliogabe. Tarteak jasotako alertak soilik hartzen ditu.")
    if result['rows']:
        st.dataframe(result['rows'], hide_index=True, width='stretch')
    st.caption(f"UTC ebaketa: {cutoff}. Emaitzak baieztatzean: kostua = 5.000 × FN + 200 × FP + 300 × TP. AVISO/CRITICA koloreek ez dute FP/TP zehazten.")
