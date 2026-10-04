import streamlit as st

def render_day_card(day):
    st.subheader(f"Day {day['day']} - {day['date']} - {day['location']}")
    weather = day.get('weather') or {}
    if weather.get('success'):
        st.write(f"Weather: {weather.get('temperature')} C, {weather.get('condition') or 'condition unavailable'}")
        if weather.get('rain_probability') is not None:
            st.write('Rain probability: '+weather['rain_probability'])
    else:
        st.info('Weather unavailable')
    if not any(day.get(period) for period in ('morning', 'afternoon', 'evening')):
        st.info('No verified schedule is available for this day.')
    for period in ('morning','afternoon','evening'):
        st.write(period.title())
        for item in day.get(period,[]):
            st.write(item['name'])
    for category in ('places','food','temples'):
        if day.get(category):
            st.write(category.title())
            for item in day[category]:
                st.markdown(f"[{item['name']}]({item['url']})")
                st.caption(item.get('description',''))
    for warning in day.get('warnings',[]):
        st.warning(warning)
