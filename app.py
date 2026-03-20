import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import pytz

# --- [1. 기본 설정 및 14개 시군 좌표 정의] ---
st.set_page_config(page_title="전북 14개 시군 극한호우 실시간 감시", layout="wide")
API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# 시간 정의: 실황 데이터는 매시 40분 이후 안정적이므로 1시간 전 데이터 기준
now_kst = datetime.now(KST)
api_base_time = (now_kst - timedelta(minutes=60)).replace(minute=0, second=0, microsecond=0)

# 전북 14개 시군 상세 좌표
LOCATIONS = {
    "전주": {"nx": 63, "ny": 89, "lat": 35.824, "lon": 127.148},
    "군산": {"nx": 56, "ny": 92, "lat": 35.967, "lon": 126.736},
    "익산": {"nx": 60, "ny": 91, "lat": 35.948, "lon": 126.957},
    "정읍": {"nx": 58, "ny": 83, "lat": 35.569, "lon": 126.856},
    "남원": {"nx": 68, "ny": 80, "lat": 35.416, "lon": 127.390},
    "김제": {"nx": 59, "ny": 88, "lat": 35.803, "lon": 126.880},
    "완주": {"nx": 63, "ny": 91, "lat": 35.904, "lon": 127.162},
    "진안": {"nx": 68, "ny": 88, "lat": 35.791, "lon": 127.424},
    "무주": {"nx": 72, "ny": 93, "lat": 36.006, "lon": 127.660},
    "장수": {"nx": 70, "ny": 85, "lat": 35.647, "lon": 127.521},
    "임실": {"nx": 66, "ny": 84, "lat": 35.617, "lon": 127.289},
    "순창": {"nx": 63, "ny": 79, "lat": 35.374, "lon": 127.137},
    "고창": {"nx": 54, "ny": 80, "lat": 35.435, "lon": 126.702},
    "부안": {"nx": 56, "ny": 87, "lat": 35.731, "lon": 126.733}
}

# --- [2. 데이터 수집 및 HRI 2.0 엔진] ---
@st.cache_data(ttl=600)
def fetch_weather(nx, ny):
    base_date = api_base_time.strftime("%Y%m%d")
    base_time = api_base_time.strftime("%H00")
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
    if not w: return 0.0
    pwat, v850, cape = w['REH']*0.65+10, w['WSD']*2.5, w['T1H']*100
    updiv, ki = 15.0, 32.0
    score = (pwat*ki)/2500*30 + (cape/5000)*35 + (v850*updiv)/800*35
    return min(100, round(score, 1))

def get_color(score):
    if score >= 95: return "red"
    if score >= 80: return "orange"
    if score >= 60: return "yellow"
    return "green"

# --- [3. 메인 대시보드 레이아웃] ---
st.title("🌊 전북 14개 시군 극한호우 실시간 감시 (HRI 2.0)")

# 시간 정보
t_col1, t_col2 = st.columns(2)
t_col1.metric("현재 시각 (KST)", now_kst.strftime("%Y-%m-%d %H:%M:%S"))
t_col2.metric("API 데이터 기준", api_base_time.strftime("%Y-%m-%d %H시"))

# 데이터 로드
all_data = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}

# 상단: 지도와 요약 리스트
col1, col2 = st.columns()

with col1:
    st.subheader("📍 전북 전역 레이더 및 위험 지도")
    m = folium.Map(location=[35.7, 127.1], zoom_start=8, tiles="cartodbpositron")
    folium.WmsTileLayer(
        url="https://mesonet.agron.iastate.edu",
        layers="nexrad-n0r-900913", name="Radar", fmt="image/png",
        transparent=True, opacity=0.4, overlay=True
    ).add_to(m)
    for name, info in LOCATIONS.items():
        score = get_hri_score(all_data[name])
        folium.CircleMarker(
            location=[info['lat'], info['lon']], radius=10,
            color=get_color(score), fill=True, fill_opacity=0.7,
            popup=f"<b>{name}</b><br>HRI: {score}"
        ).add_to(m)
    st_folium(m, width=750, height=550)

with col2:
    st.subheader("📋 14개 시군 위험도 현황")
    summary_data = []
    for name in LOCATIONS.keys():
        score = get_hri_score(all_data[name])
        summary_data.append({"지역": name, "HRI 지수": score, "상태": "🔴 위험" if score >= 95 else "🟠 경계" if score >= 80 else "🟢 정상"})
    st.dataframe(pd.DataFrame(summary_data).sort_values("HRI 지수", ascending=False), hide_index=True, use_container_width=True)
    selected_name = st.selectbox("🎯 상세 분석 지역 선택", list(LOCATIONS.keys()))
    current_hri = get_hri_score(all_data[selected_name])

# 하단: 게이지 및 상세 데이터
st.divider()
c1, c2 = st.columns(2)

with c1:
    # SyntaxError 해결: range 및 steps 값을 숫자로 정확히 채움
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=current_hri,
        title={'text': f"{selected_name} 위험 지수"},
        gauge={
            'axis': {'range': [0, 100]},
            'steps': [
                {'range': [0, 40], 'color': "#E8F5E9"}, 
                {'range': [40, 80], 'color': "#FFF59D"}, 
                {'range': [80, 95], 'color': "#FFCC80"}, 
                {'range': [95, 100], 'color': "#EF9A9A"}
            ],
            'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}
        }
    ))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader(f"🔍 {selected_name} 실시간 관측값")
    w = all_data[selected_name]
    if w:
        st.write(f"🌡️ 기온: **{w['T1H']}°C** | 💧 습도: **{w['REH']}%**")
        st.write(f"💨 풍속: **{w['WSD']}m/s** | 🌧️ 1시간 강수: **{w['RN1']}mm**")
    else:
        st.warning("데이터 수신 대기 중...")
