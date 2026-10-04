import streamlit as st

def render_budget_section(budget, warnings, agent_activity=None):
    st.subheader('Budget')
    known_prices = any(entry.get('amount') is not None for entry in budget['entries'])
    st.metric('Known subtotal (INR)', f"{budget['known_subtotal']:,.2f}" if known_prices else 'Unavailable')
    if not known_prices:
        st.info('No prices were retrieved. This does not mean the trip costs zero.')
    st.write('Status: '+budget['status'])
    display_entries = [{**entry, 'amount': 'Unavailable' if entry.get('amount') is None else f"{entry['amount']:,.2f}"} for entry in budget['entries']]
    st.dataframe(display_entries,use_container_width=True)
    for warning in warnings:
        st.warning(warning)
    with st.expander('Tool execution trace'):
        st.json(agent_activity or [])
