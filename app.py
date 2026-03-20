import streamlit as st
import pandas as pd
import requests
import json
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- [1. 설정 및 API 정보] ---
st.set_page_config(page_title="전북 극한호우 실시간 감시 (HRI 2.0)", layout="centered")
API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"  # 제공해주신 인증키

# 전북 주요 지점 격자 좌표 (기상청 nx, ny)
LOCATIONS = {
    "군산": {"nx": 56, "ny": 92},
    "전주": {"nx": 63, "ny": 89},
    "익산": {"nx": 60, "ny": 91},
    "부안": {"nx": 56, "ny": 87},
    "남원": {"nx": 68, "ny": 80}
}

# 과거 사례 데이터 (유사도 계산용)
past_cases = {
    "2025년 군산 (152.2mm)": {"pwat": 65.5, "cape": 4500, "v850": 20.0, "upper_div": 40.2, "k_index": 38.0},
    "2024년 익산 (125.5mm)": {"pwat": 64.5, "cape": 3800, "v850": 23.5, "upper_div": 18.3, "k_index": 37.0},
    "2022년 군산 (100.0mm)": {"pwat": 59.7, "cape": 1500, "v850": 21.0, "upper_div": 15.2, "k_index": 35.8}
}

# --- [2. 데이터 수집 및 계산 함수] ---
@st.cache_data(ttl=600) # 10분간 데이터 캐싱 (API 호출 최적화)
def fetch_realtime_weather(nx, ny):
    now = datetime.now() - timedelta(minutes=40) # 데이터 생성 지연 고려
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H00")
    
    url = "http://apis.data.go.kr"
    params = {
        'serviceKey': API_KEY,
        'pageNo': '1', 'numOfRows': '1000', 'dataType': 'JSON',
        'base_date': base_date, 'base_time': base_time, 'nx': nx, 'ny': ny
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        res_json = response.json()
        items = res_json['response']['body']['items']['item']
        
        # 실제 API에서 가져오기 어려운 CAPE/PWAT 등은 실시간 지상 관측 기반 추정 로직 적용
        # 연구 목적상 실시간 수치 예보 모델(LDAPS) 연동 전까지는 관측값 기반 추정치 활용
        weather_data = {
            'temp': next(i['obsrValue'] for i in items if i['category'] == 'T1H'),
            'humi': next(i['obsrValue'] for i in items if i['category'] == 'REH'),
            'wind': next(i['obsrValue'] for i in items if i['category'] == 'WSD'),
            'rain': next(i['obsrValue'] for i in items if i['category'] == 'RN1')
        }
        return weather_data
    except:
        return None

def calculate_hri_2(pwat, cape, v850, upper_div, k_index):
    fuel = (pwat * k_index) / 2500 * 30
    explosive = (cape / 5000) * 35
    pump = (v850 * upper_div) / 800 * 35
    return min(100, round(fuel + explosive + pump, 1))

def get_best_match(current):
    best_name, max_sim = "", -1
    for name, data in past_cases.items():
        score = 1 - (abs(current['pwat'] - data['pwat'])/75 * 0.2 + abs(current['cape'] - data['cape'])/7000 * 0.2 + 
                     abs(current['v850'] - data['v850'])/40 * 0.2 + abs(current['upper_div'] - data['upper_div'])/50 * 0.2 + 
                     abs(current['k_index'] - data['k_index'])/50 * 0.2)
        sim = round(max(0, score * 100), 1)
        if sim > max_sim: max_sim, best_name = sim, name
    return best_name, max_sim

# --- [3. 메인 UI 및 로직] ---
st.title("🌊 전북 극한호우 실시간 감시 (HRI 2.0)")
selected_loc = st.selectbox("📍 감시 지역 선택", list(LOCATIONS.keys()))
weather = fetch_realtime_weather(LOCATIONS[selected_loc]['nx'], LOCATIONS[selected_loc]['ny'])

if weather:
    st.sidebar.success(f"✅ {selected_loc} 실시간 데이터 수신 중")
    # API 관측값을 기반으로 HRI 변수 추정 (실제 연구 시 LDAPS 데이터로 대체 권장)
    # 아래 값들은 현재 관측된 기온/습도를 바탕으로 극한호우 메커니즘을 시뮬레이션하기 위한 보정값입니다.
    pwat_est = float(weather['humi']) * 0.65 + 10 
    v850_est = float(weather['wind']) * 2.5
    cape_est = float(weather['temp']) * 100
    updiv_est = 15.0 # 상층 발산은 지상 관측 불가하므로 기본값 설정
    ki_est = 32.0    # K-Index 추정치
    
    current_weather = {'pwat': pwat_est, 'cape': cape_est, 'v850': v850_est, 'upper_div': updiv_est, 'k_index': ki_est}
    hri_score = calculate_hri_2(**current_weather)
    match_name, match_percent = get_best_match(current_weather)

    # 게이지 표시
        # 게이지 표시 (94번 줄 근처부터 교체)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", 
        value=hri_score, 
        title={'text': "HRI 2.0 위험 지수"},
        gauge={
            'axis': {'range': [0, 100]}, # 여기 숫자가 빠져있었습니다
            'steps': [
                {'range': [0, 40], 'color': "#E8F5E9"}, 
                {'range': [40, 80], 'color': "#FFF59D"}, 
                {'range': [80, 95], 'color': "#FFCC80"}, 
                {'range': [95, 100], 'color': "#EF9A9A"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4}, 
                'thickness': 0.75,
                'value': 95
            }
        }
    ))
    st.plotly_chart(fig, use_container_width=True)

    
    # 상세 관측값 표출
    cols = st.columns(3)
    cols.metric("기온", f"{weather['temp']}°C")
    cols.metric("습도", f"{weather['humi']}%")
    cols.metric("강수량(1h)", f"{weather['rain']}mm")
else:
    st.error("❌ 기상청 API 연결 실패. 인증키 활성화 대기 중이거나 점검 중일 수 있습니다.")
    st.info("Tip: API 키 발급 후 실제 데이터가 나오기까지 최대 1~2시간이 소요될 수 있습니다.")
