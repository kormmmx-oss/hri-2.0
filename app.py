import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components

# --- [1. 설정 및 UI 최적화] ---
st.set_page_config(page_title="전북 극한호우 감시 & HRI 2.1", layout="wide")

# 상단 잘림 방지 및 여백 설정 (5rem 확보)
st.html("""
    <style>
    .block-container { padding-top: 5rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; color: #1E88E5; }
    </style>
""")

API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# 과거 사례 데이터 (사례별 변별력 부여)
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

# --- [2. 핵심 엔진: HRI 2.1 변별력 보정] ---
def get_hri_21(pwat, cape, v850, updiv=15.0, ki=32.0):
    fuel = (pwat * ki) / 2300 * 30
    explosive = (cape / 4000) * 35
    pump = (v850 * updiv) / 750 * 35
    score = (fuel + explosive + pump) * 1.02 # 사례 간 변별력을 위해 보정치 하향
    return min(100.0, round(score, 1))

@st.cache_data(ttl=600)
def fetch_weather(nx, ny):
    now = datetime.now(KST)
    for i in range(1, 4):
        t = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        url = f"http://apis.data.go.kr{API_KEY}&dataType=JSON&base_date={t.strftime('%Y%m%d')}&base_time={t.strftime('%H00')}&nx={nx}&ny={ny}"
        try:
            res = requests.get(url, timeout=5).json()
            items = res['response']['body']['items']['item']
            return {'T1H': float(next(i['obsrValue'] for i in items if i['category'] == 'T1H')),
                    'REH': float(next(i['obsrValue'] for i in items if i['category'] == 'REH')),
                    'WSD': float(next(i['obsrValue'] for i in items if i['category'] == 'WSD')),
                    'RN1': float(next(i['obsrValue'] for i in items if i['category'] == 'RN1')), 'base': t.strftime("%m/%d %H시")}
        except: continue
    return None

# --- [3. 메인 UI] ---
t1, t2 = st.columns(2)
with t1:
    mode = st.radio("📡 모드", ["실시간 감시", "과거 사례 시뮬레이션"], horizontal=True)
    st.subheader("전북 극한호우 실시간 감시 (HRI 2.1)")
with t2:
    components.html("""<div id="clock" style="text-align:right; font-size:18px; font-weight:bold; color:#1E88E5; font-family:sans-serif;"></div>
    <script>function updateClock(){var now=new Date(); var kst=new Date(now.getTime()+(now.getTimezoneOffset()*60000)+(9*3600000));
    document.getElementById('clock').innerHTML="⏱️ "+kst.toLocaleString('ko-KR');} setInterval(updateClock,1000); updateClock();</script>""", height=45)

if mode == "실시간 감시":
    weather_source = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}
else:
    sim_case = st.selectbox("📅 시뮬레이션 사례 선택", list(PAST_RECORDS.keys()))
    cd = PAST_RECORDS[sim_case]
    weather_source = {name: {'T1H': cd['cape']/100, 'REH': (cd['pwat']-10)/0.65, 'WSD': cd['v850']/2.5, 'RN1': 100.0, 'sim': True, 'up': cd['updiv'], 'ki': cd['ki']} for name in LOCATIONS.keys()}
    with st.expander("🖼️ 당시 지상 일기도 확인"):
        st.image(cd['img'], use_container_width=True)

m1, m2 = st.columns(2)
with m1:
    m = folium.Map(location=[35.7, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = weather_source[name]
        if w:
            sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, w.get('up', 15.0), w.get('ki', 32.0))
            folium.CircleMarker([info['lat'], info['lon']], radius=10, color="red" if sc>=95 else "orange" if sc>=80 else "green", fill=True, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=350, returned_objects=[])

with m2:
    summary = []
    for n in LOCATIONS.keys():
        w = weather_source[n]
        sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, w.get('up', 15.0), w.get('ki', 32.0)) if w else 0
        summary.append({"지역": n, "HRI": sc, "상태": "🔴 위험" if sc>=95 else "🟠 주의" if sc>=80 else "🟢 정상"})
    st.dataframe(pd.DataFrame(summary).sort_values("HRI", ascending=False), hide_index=True, use_container_width=True, height=350)

st.divider()
b1, b2, b3 = st.columns(3)
target = b1.selectbox("🎯 상세 분석 지역", list(LOCATIONS.keys()))
tw = weather_source[target]
tsc = get_hri_21(tw['REH']*0.65+10, tw['T1H']*100, tw['WSD']*2.5, tw.get('up', 15.0), tw.get('ki', 32.0)) if tw else 0

with b2:
    # SyntaxError 해결: 모든 range 및 steps 값을 숫자로 정확히 입력
    fig = go.Figure(go.Indicator(mode="gauge+number", value=tsc, title={'text': f"{target} HRI 2.1"},
        gauge={'axis': {'range': [0, 100]}, 
               'steps': [{'range': [0, 60], 'color': "#E8F5E9"}, 
                         {'range': [60, 80], 'color': "#FFF59D"}, 
                         {'range': [80, 95], 'color': "#FFCC80"}, 
                         {'range': [95, 100], 'color': "#EF9A9A"}],
               'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}}))
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

with b3:
    if tw:
        if mode == "실시간 감시":
            st.metric("🌡️ 현재 기온", f"{tw['T1H']:.1f}°C")
            st.metric("🌧️ 1h 강수량", f"{tw['RN1']:.1f}mm")
        else:
            st.metric("🧬 사례 CAPE 환산치", f"{tw['T1H']*100:.0f} J/kg")
            st.metric("🌊 사례 수증기량(PWAT)", f"{tw['REH']*0.65+10:.1f} mm")
            st.error("🧪 시뮬레이션 모드 활성")
