import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components

# --- [1. 설정 및 데이터 정의] ---
st.set_page_config(page_title="전북 극한호우 감시 & HRI 2.1 시뮬레이터", layout="wide")

st.markdown("""<style>
    .block-container { padding-top: 2rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; color: #1E88E5; }
</style>""", unsafe_allow_html=True)

API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# 과거 사례 데이터 (HRI 2.1 검증용)
PAST_RECORDS = {
    "2025-09-07 군산 (152.2mm)": {"pwat": 65.5, "cape": 4500, "v850": 20.0, "updiv": 40.2, "ki": 38.0, "img": "https://img.kma.go.kr"},
    "2024-07-10 익산 (125.5mm)": {"pwat": 64.5, "cape": 3800, "v850": 23.5, "updiv": 18.3, "ki": 37.0, "img": "https://img.kma.go.kr"},
    "2012-08-13 군산 (110.0mm)": {"pwat": 68.2, "cape": 4200, "v850": 19.8, "updiv": 30.1, "ki": 40.0, "img": "https://img.kma.go.kr"}
}

LOCATIONS = {
    "전주": {"nx": 63, "ny": 89, "lat": 35.824, "lon": 127.148}, "군산": {"nx": 56, "ny": 92, "lat": 35.967, "lon": 126.736},
    "익산": {"nx": 60, "ny": 91, "lat": 35.948, "lon": 126.957}, "정읍": {"nx": 58, "ny": 83, "lat": 35.569, "lon": 126.856},
    "남원": {"nx": 68, "ny": 80, "lat": 35.416, "lon": 127.390}, "김제": {"nx": 59, "ny": 88, "lat": 35.803, "lon": 126.880},
    "완주": {"nx": 63, "ny": 91, "lat": 35.904, "lon": 127.162}, "진안": {"nx": 68, "ny": 88, "lat": 35.791, "lon": 127.424},
    "무주": {"nx": 72, "ny": 93, "lat": 36.006, "lon": 127.660}, "장수": {"nx": 70, "ny": 85, "lat": 35.647, "lon": 127.521},
    "임실": {"nx": 66, "ny": 84, "lat": 35.617, "lon": 127.289}, "순창": {"nx": 63, "ny": 79, "lat": 35.374, "lon": 127.137},
    "고창": {"nx": 54, "ny": 80, "lat": 35.435, "lon": 126.702}, "부안": {"nx": 56, "ny": 87, "lat": 35.731, "lon": 126.733}
}

# --- [2. 핵심 엔진: HRI 2.1 보정 공식] ---
def get_hri_21(pwat, cape, v850, updiv=15.0, ki=32.0):
    """100mm 이상 시 95점 이상이 나오도록 보정된 공식"""
    # 연료항: 기준값 2100으로 하향 (민감도 상승)
    fuel = (pwat * ki) / 2100 * 30
    # 폭발항: 기준값 3500으로 하향 (전북 극한호우 평균 반영)
    explosive = (cape / 3500) * 35
    # 펌프항: 기준값 600으로 하향 (상하층 시너지 강조)
    pump = (v850 * updiv) / 600 * 35
    
    # 최종 보정 계수 1.1 적용
    score = (fuel + explosive + pump) * 1.1
    return min(100.0, round(score, 1))

@st.cache_data(ttl=600)
def fetch_weather(nx, ny):
    now = datetime.now(KST)
    for i in range(1, 4):
        t = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        url = f"http://apis.data.go.kr{API_KEY}&dataType=JSON&base_date={t.strftime('%Y%m%d')}&base_time={t.strftime('%H00')}&nx={nx}&ny={ny}"
        try:
            res = requests.get(url, timeout=5).json()
            if res['response']['header']['resultCode'] == '00':
                items = res['response']['body']['items']['item']
                return {'T1H': float(next(i['obsrValue'] for i in items if i['category'] == 'T1H')),
                        'REH': float(next(i['obsrValue'] for i in items if i['category'] == 'REH')),
                        'WSD': float(next(i['obsrValue'] for i in items if i['category'] == 'WSD')),
                        'RN1': float(next(i['obsrValue'] for i in items if i['category'] == 'RN1')), 'base': t.strftime("%m/%d %H시")}
        except: continue
    return None

# --- [3. 메인 UI] ---
h1, h2 = st.columns([7, 3])
with h1:
    mode = st.radio("📡 시스템 모드", ["실시간 감시", "과거 사례 시뮬레이션"], horizontal=True)
with h2:
    components.html("""<div id="clock" style="text-align:right; font-size:18px; font-weight:bold; color:#1E88E5; font-family:sans-serif;"></div>
    <script>function updateClock(){var now=new Date(); var kst=new Date(now.getTime()+(now.getTimezoneOffset()*60000)+(9*3600000));
    document.getElementById('clock').innerHTML="⏱️ "+kst.toLocaleString('ko-KR');} setInterval(updateClock,1000); updateClock();</script>""", height=40)

if mode == "실시간 감시":
    weather_source = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}
    st.caption(f"📡 API 데이터 기준: {list(weather_source.values())[0]['base'] if any(weather_source.values()) else '데이터 대기 중'}")
else:
    sim_case = st.selectbox("📅 시뮬레이션 사례 선택", list(PAST_RECORDS.keys()))
    cd = PAST_RECORDS[sim_case]
    weather_source = {name: {'T1H': cd['cape']/100, 'REH': (cd['pwat']-10)/0.65, 'WSD': cd['v850']/2.5, 'RN1': 100.0, 'sim': True, 'up': cd['updiv'], 'ki': cd['ki']} for name in LOCATIONS.keys()}
    with st.expander("🖼️ 당시 기압배치도 확인", expanded=False):
        st.image(cd['img'], use_container_width=True)

# 지도 & 순위표
m1, m2 = st.columns([6, 4])
with m1:
    m = folium.Map(location=[35.7, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = weather_source[name]
        if w:
            sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, w.get('up', 15.0), w.get('ki', 32.0))
            folium.CircleMarker([info['lat'], info['lon']], radius=10, color="red" if sc>=95 else "orange" if sc>=80 else "green", fill=True, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=380, returned_objects=[])

with m2:
    st.write("📊 **위험도 순위 (HRI 2.1)**")
    summary = []
    for n in LOCATIONS.keys():
        w = weather_source[n]
        sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, w.get('up', 15.0), w.get('ki', 32.0)) if w else 0
        summary.append({"지역": n, "HRI": sc, "상태": "🔴 위험" if sc>=95 else "🟠 주의" if sc>=80 else "🟢 정상"})
    st.dataframe(pd.DataFrame(summary).sort_values("HRI", ascending=False), hide_index=True, use_container_width=True, height=350)

# 상세 분석
st.divider()
b1, b2, b3 = st.columns(3)
target = b1.selectbox("🎯 분석 지역 선택", list(LOCATIONS.keys()))
tw = weather_source[target]
tsc = get_hri_21(tw['REH']*0.65+10, tw['T1H']*100, tw['WSD']*2.5, tw.get('up', 15.0), tw.get('ki', 32.0)) if tw else 0

with b2:
    fig = go.Figure(go.Indicator(mode="gauge+number", value=tsc, title={'text': f"{target} 지수 (HRI 2.1)"},
        gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 60], 'color': "#E8F5E9"}, {'range': [60, 85], 'color': "#FFF59D"}, 
                                                  {'range': [85, 95], 'color': "#FFCC80"}, {'range': [95, 100], 'color': "#EF9A9A"}],
               'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}}))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

with b3:
    if tw:
        st.metric("🌡️ 기온(추정)", f"{tw['T1H']:.1f}°C")
        st.metric("🌧️ 1h 강수량", f"{tw['RN1']:.1f}mm")
        if mode == "과거 사례 시뮬레이션": st.error("🧪 시뮬레이션 데이터 적용 중")
