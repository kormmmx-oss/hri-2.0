import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- [1. 설정 및 API 정보] ---
st.set_page_config(page_title="전북 극한호우 실시간 감시 시스템", layout="wide")
API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"

# 전북 주요 지점 정보 (nx, ny: 기상청 격자, lat, lon: 위경도)
LOCATIONS = {
    "군산": {"nx": 56, "ny": 92, "lat": 35.967, "lon": 126.736},
    "전주": {"nx": 63, "ny": 89, "lat": 35.824, "lon": 127.148},
    "익산": {"nx": 60, "ny": 91, "lat": 35.948, "lon": 126.957},
    "부안": {"nx": 56, "ny": 87, "lat": 35.731, "lon": 126.733},
    "남원": {"nx": 68, "ny": 80, "lat": 35.416, "lon": 127.390}
}

# --- [2. 핵심 함수 정의] ---
@st.cache_data(ttl=600)
def fetch_weather(nx, ny):
    """기상청 API 실시간 호출"""
    now = datetime.now() - timedelta(minutes=60) # 안전하게 1시간 전 데이터 호출
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H00")
    
    url = "http://apis.data.go.kr"
    params = {'serviceKey': API_KEY, 'dataType': 'JSON', 'base_date': base_date, 'base_time': base_time, 'nx': nx, 'ny': ny}
    
    try:
        res = requests.get(url, params=params, timeout=5).json()
        items = res['response']['body']['items']['item']
        return {
            'T1H': float(next(i['obsrValue'] for i in items if i['category'] == 'T1H')),
            'REH': float(next(i['obsrValue'] for i in items if i['category'] == 'REH')),
            'WSD': float(next(i['obsrValue'] for i in items if i['category'] == 'WSD')),
            'RN1': float(next(i['obsrValue'] for i in items if i['category'] == 'RN1'))
        }
    except: return None

def get_hri_score(w):
    """HRI 2.0 지수 산출 로직 (추정치 기반)"""
    if not w: return 50.0
    pwat = w['REH'] * 0.65 + 10
    v850 = w['WSD'] * 2.5
    cape = w['T1H'] * 100
    updiv, ki = 15.0, 32.0 # 고정 추정치
    
    score = (pwat * ki)/2500*30 + (cape/5000)*35 + (v850*updiv)/800*35
    return min(100, round(score, 1))

def get_color(score):
    if score >= 95: return "red"
    if score >= 80: return "orange"
    if score >= 60: return "yellow"
    return "green"

# --- [3. 메인 대시보드 레이아웃] ---
st.title("🌊 전북지역 극한호우 실시간 감시 (HRI 2.0)")

# 전 지역 데이터 미리 로드
all_data = {}
for name, info in LOCATIONS.items():
    all_data[name] = fetch_weather(info['nx'], info['ny'])

# 상단: 지도와 요약 정보 (컬럼 구분)
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📍 전북 실시간 위험 지도")
    m = folium.Map(location=[35.7, 127.1], zoom_start=9)
    for name, info in LOCATIONS.items():
        score = get_hri_score(all_data[name])
        folium.CircleMarker(
            location=[info['lat'], info['lon']],
            radius=15, color=get_color(score), fill=True, fill_opacity=0.7,
            popup=f"<b>{name}</b><br>HRI: {score}"
        ).add_to(m)
    st_folium(m, width=700, height=450)

with col2:
    st.subheader("📋 지역별 요약")
    selected_name = st.selectbox("상세 분석 지역", list(LOCATIONS.keys()))
    current_w = all_data[selected_name]
    current_hri = get_hri_score(current_w)
    
    st.metric("현재 HRI 지수", f"{current_hri}점")
    if current_hri >= 95: st.error("🚨 극한호우 경보")
    elif current_hri >= 80: st.warning("⚠️ 집중호우 주의")
    else: st.success("✅ 기상 안정")

# 하단: 게이지 차트 및 상세 지표
st.divider()
c1, c2 = st.columns(2)

with c1:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=current_hri,
        gauge={'axis': {'range': [0, 100]},
               'steps': [{'range': [0, 60], 'color': "#E8F5E9"}, {'range': [60, 80], 'color': "#FFF59D"},
                         {'range': [80, 95], 'color': "#FFCC80"}, {'range': [95, 100], 'color': "#EF9A9A"}]}))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("🔍 실시간 관측 데이터")
    if current_w:
        st.write(f"🌡️ 기온: {current_w['T1H']}°C")
        st.write(f"💧 습도: {current_w['REH']}%")
        st.write(f"💨 풍속: {current_w['WSD']}m/s")
        st.write(f"🌧️ 강수(1h): {current_w['RN1']}mm")
    else:
        st.error("API 연동 대기 중...")
