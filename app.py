import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components

# --- [1. 기본 설정 및 데이터 정의] ---
st.set_page_config(page_title="전북 극한호우 감시 & 시뮬레이터", layout="wide")

# UI 스타일 최적화
st.markdown("""<style>
    .block-container { padding-top: 2rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; color: #1E88E5; }
    .stAlert { padding: 0.5rem; margin-bottom: 0.5rem; }
</style>""", unsafe_allow_html=True)

API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# 과거 25년 주요 사례 데이터 및 기압배치도 이미지 URL (예시)
PAST_RECORDS = {
    "2025-09-07 군산 (152.2mm)": {"pwat": 65.5, "cape": 4500, "v850": 20.0, "updiv": 40.2, "ki": 38.0, "img": "https://img.kma.go.kr"},
    "2024-07-10 익산 (125.5mm)": {"pwat": 64.5, "cape": 3800, "v850": 23.5, "updiv": 18.3, "ki": 37.0, "img": "https://img.kma.go.kr"},
    "2012-08-13 군산 (110.0mm)": {"pwat": 68.2, "cape": 4200, "v850": 19.8, "updiv": 30.1, "ki": 40.0, "img": "https://img.kma.go.kr"}
}

LOCATIONS = {
    "전주": {"nx": 63, "ny": 89, "lat": 35.824, "lon": 127.148}, "군산": {"nx": 56, "ny": 92, "lat": 35.967, "lon": 126.736},
    "익산": {"nx": 60, "ny": 91, "lat": 35.948, "lon": 126.957}, "부안": {"nx": 56, "ny": 87, "lat": 35.731, "lon": 126.733}
}

# --- [2. 핵심 엔진] ---
@st.cache_data(ttl=600)
def fetch_weather(nx, ny):
    now = datetime.now(KST)
    for i in range(1, 3):
        t = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        url = f"http://apis.data.go.kr{API_KEY}&dataType=JSON&base_date={t.strftime('%Y%m%d')}&base_time={t.strftime('%H00')}&nx={nx}&ny={ny}"
        try:
            res = requests.get(url, timeout=5).json()
            if res['response']['header']['resultCode'] == '00':
                items = res['response']['body']['items']['item']
                return {'T1H': float(next(i['obsrValue'] for i in items if i['category'] == 'T1H')),
                        'REH': float(next(i['obsrValue'] for i in items if i['category'] == 'REH')),
                        'WSD': float(next(i['obsrValue'] for i in items if i['category'] == 'WSD')),
                        'RN1': float(next(i['obsrValue'] for i in items if i['category'] == 'RN1')), 'base': t.strftime("%m/%d %H:00")}
        except: continue
    return None

def get_hri(pwat, cape, v850, updiv=15.0, ki=32.0):
    score = (pwat*ki)/2500*30 + (cape/5000)*35 + (v850*updiv)/800*35
    return min(100, round(score, 1))

# --- [3. 메인 화면 구성] ---
# 상단 모드 선택 및 시계
h1, h2 = st.columns([7, 3])
with h1:
    mode = st.radio("📡 시스템 모드 선택", ["실시간 감시", "과거 사례 시뮬레이션"], horizontal=True)
with h2:
    components.html("""<div style="text-align:right;"><div id="clock" style="font-size:18px; font-weight:bold; color:#1E88E5;"></div></div>
    <script>function updateClock(){var now=new Date(); var kst=new Date(now.getTime()+(now.getTimezoneOffset()*60000)+(9*3600000));
    document.getElementById('clock').innerHTML="⏱️ "+kst.toLocaleString('ko-KR');} setInterval(updateClock,1000); updateClock();</script>""", height=40)

# 모드별 데이터 설정
if mode == "실시간 감시":
    st.subheader("🌊 전북 실시간 기상 감시 모드")
    weather_source = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}
else:
    st.subheader("🧪 과거 극한호우 사례 시뮬레이션 모드")
    sim_case = st.selectbox("📅 분석할 과거 사례를 선택하세요", list(PAST_RECORDS.keys()))
    case_data = PAST_RECORDS[sim_case]
    # 전체 지역에 과거 시뮬레이션 수치 적용
    weather_source = {name: {'T1H': case_data['cape']/100, 'REH': (case_data['pwat']-10)/0.65, 'WSD': case_data['v850']/2.5, 'RN1': 100.0, 'is_sim': True} for name in LOCATIONS.keys()}
    
    # 팝업 형태의 기압배치도 이미지
    with st.expander("🖼️ 당시 기압배치도 확인 (클릭)", expanded=True):
        st.image(case_data['img'], caption=f"{sim_case} 지상 일기도", use_container_width=True)

# 1행: 지도 및 순위표
m1, m2 = st.columns([6, 4])
with m1:
    m = folium.Map(location=[35.75, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = weather_source[name]
        sc = get_hri(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5) if w else 0
        folium.CircleMarker([info['lat'], info['lon']], radius=12, color="red" if sc>=95 else "orange" if sc>=80 else "green",
                            fill=True, fill_opacity=0.7, popup=f"{name}: {sc}점").add_to(m)
    st_folium(m, width="100%", height=350, returned_objects=[])

with m2:
    sum_list = [{"지역": n, "HRI": get_hri(weather_source[n]['REH']*0.65+10, weather_source[n]['T1H']*100, weather_source[n]['WSD']*2.5) if weather_source[n] else 0} for n in LOCATIONS.keys()]
    st.dataframe(pd.DataFrame(sum_list).sort_values("HRI", ascending=False), hide_index=True, use_container_width=True, height=350)

# 2행: 상세 게이지 및 데이터
st.divider()
b1, b2, b3 = st.columns(3)
target = b1.selectbox("🎯 상세 분석 시군", list(LOCATIONS.keys()))
tw = weather_source[target]
tsc = get_hri(tw['REH']*0.65+10, tw['T1H']*100, tw['WSD']*2.5) if tw else 0

with b2:
    fig = go.Figure(go.Indicator(mode="gauge+number", value=tsc, title={'text': f"{target} 위험 지수"},
        gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#E8F5E9"}, {'range': [40, 80], 'color': "#FFF59D"}, 
                                                  {'range': [80, 95], 'color': "#FFCC80"}, {'range': [95, 100], 'color': "#EF9A9A"}],
               'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}}))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

with b3:
    if tw:
        st.metric("🌡️ 기온(추정)", f"{tw['T1H']:.1f}°C")
        st.metric("🌧️ 강수량(실측/사례)", f"{tw['RN1']:.1f}mm")
        if mode == "실시간 감시": st.caption(f"📡 API 데이터 기준: {tw['base']}")
        else: st.error("🧪 시뮬레이션 데이터가 적용됨")
