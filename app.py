import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import pytz

# --- [1. 기본 설정 및 시간 정의] ---
st.set_page_config(page_title="전북 극한호우 실시간 감시 시스템", layout="wide")
API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# 현재 시각 및 API 조회 기준 시간 계산
now_kst = datetime.now(KST)
# 기상청 실황 API는 매시 40분 이후 안정적이므로, 1시간 전 데이터를 기준으로 호출 설정
api_base_time = (now_kst - timedelta(minutes=60)).replace(minute=0, second=0, microsecond=0)

LOCATIONS = {
    "군산": {"nx": 56, "ny": 92, "lat": 35.967, "lon": 126.736},
    "전주": {"nx": 63, "ny": 89, "lat": 35.824, "lon": 127.148},
    "익산": {"nx": 60, "ny": 91, "lat": 35.948, "lon": 126.957},
    "부안": {"nx": 56, "ny": 87, "lat": 35.731, "lon": 126.733},
    "남원": {"nx": 68, "ny": 80, "lat": 35.416, "lon": 127.390}
}

# --- [2. 데이터 수집 및 계산 함수] ---
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
    except Exception: return None

def get_hri_score(w):
    if not w: return 0.0
    pwat = w['REH'] * 0.65 + 10
    v850 = w['WSD'] * 2.5
    cape = w['T1H'] * 100
    updiv, ki = 15.0, 32.0
    score = (pwat * ki)/2500*30 + (cape/5000)*35 + (v850*updiv)/800*35
    return min(100, round(score, 1))

def get_color(score):
    if score >= 95: return "red"
    if score >= 80: return "orange"
    if score >= 60: return "yellow"
    return "green"

# --- [3. 메인 대시보드 레이아웃] ---
st.title("🌊 전북지역 극한호우 실시간 감시 (HRI 2.0)")

# 시간 정보 표시 섹션
t_col1, t_col2 = st.columns(2)
t_col1.metric("현재 시각 (KST)", now_kst.strftime("%Y-%m-%d %H:%M:%S"))
t_col2.metric("API 연동 기준 시각", api_base_time.strftime("%Y-%m-%d %H:00"))

# 데이터 로드
all_data = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}

# 상단: 지도와 요약 정보
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📍 실시간 레이더 영상 및 위험 지도")
    # 지도 초기화
    m = folium.Map(location=[35.75, 127.1], zoom_start=9, tiles="cartodbpositron")
    
    # 기상청 레이더 WMS 레이어 추가 (공공데이터 오픈 API 사용)
    # 레이더 합성이미지 조회 서비스 URL 예시 (활성화된 API 서비스에 맞춰 수정 가능)
    radar_url = "https://map.kma.go.kr"
    folium.WmsTileLayer(
        url="https://mesonet.agron.iastate.edu", # 예시용 글로벌 레이더 WMS (기상청 WMS 인증 필요시 대체)
        layers="nexrad-n0r-900913",
        name="Radar Overlay",
        fmt="image/png",
        transparent=True,
        opacity=0.5,
        overlay=True,
        control=True
    ).add_to(m)
    
    # 지점 마커 추가
    for name, info in LOCATIONS.items():
        score = get_hri_score(all_data[name])
        folium.CircleMarker(
            location=[info['lat'], info['lon']],
            radius=12, color=get_color(score), fill=True, fill_opacity=0.8,
            popup=f"<b>{name}</b><br>HRI: {score}"
        ).add_to(m)
    
    folium.LayerControl().add_to(m)
    st_folium(m, width=800, height=500)

with col2:
    st.subheader("📋 지역 상세 분석")
    selected_name = st.selectbox("분석 대상 시군", list(LOCATIONS.keys()))
    current_w = all_data[selected_name]
    current_hri = get_hri_score(current_w)
    
    st.write(f"### **{selected_name}** 상태")
    st.metric("HRI 지수", f"{current_hri}점")
    
    if current_hri >= 95: st.error("🚨 극한호우 경보: 즉각 대응 필요")
    elif current_hri >= 80: st.warning("⚠️ 집중호우 주의: 모니터링 강화")
    elif current_hri > 0: st.success("✅ 기상 안정: 현재 위험 낮음")
    else: st.info("ℹ️ 데이터 수신 대기 중...")

# 하단: 게이지 및 관측값
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
    st.subheader("🔍 {0} 실시간 관측값".format(selected_name))
    if current_w:
        res_cols = st.columns(2)
        res_cols[0].write(f"🌡️ 기온: **{current_w['T1H']}°C**")
        res_cols[0].write(f"💧 습도: **{current_w['REH']}%**")
        res_cols[1].write(f"💨 풍속: **{current_w['WSD']}m/s**")
        res_cols[1].write(f"🌧️ 강수: **{current_w['RN1']}mm/h**")
    else:
        st.warning("선택 지역의 실시간 관측 자료를 불러올 수 없습니다.")
