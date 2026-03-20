import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime
import pytz

# --- 1. 설정 및 지역 데이터 ---
st.set_page_config(page_title="전북 실시간 HRI 시스템 v2.1", layout="wide")

STATIONS = {
    "전주": "146", "군산": "140", "정읍": "245", 
    "남원": "248", "익산": "249", "고창": "251", "장수": "247", "임실": "244"
}

# --- 2. 시간대별 가중치 계산 함수 ---
def get_time_weight():
    # 한국 시간 기준 현재 시간 추출
    tz_korea = pytz.timezone('Asia/Seoul')
    now = datetime.now(tz_korea)
    current_hour = now.hour
    
    # 분석된 위험 시간대: 18시 ~ 다음날 10시
    if current_hour >= 18 or current_hour <= 10:
        return 1.2, "⚠️ 야간~오전 위험 시간대 (가중치 120% 적용)"
    else:
        return 1.0, "✅ 주간 평시 시간대 (가중치 100% 적용)"

# --- 3. 기상청 API 호출 함수 ---
def fetch_realtime_weather(stn_id):
    SERVICE_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
    url = "http://apis.data.go.kr/1360000/AsosObservationsService/getLatestObservation"
    params = {'serviceKey': SERVICE_KEY, 'numOfRows': '1', 'pageNo': '1', 'dataType': 'JSON', 'stnId': stn_id}
    
    try:
        response = requests.get(url, params=params, timeout=5)
        item = response.json()['response']['body']['items']['item'][0]
        return {
            "temp": float(item.get('ta', 25.0)),
            "pwat": float(item.get('hm', 75.0)),
            "v850": 25.0, # 기본값
            "theta_e": float(item.get('ta', 25.0)) + 315 # 간이 계산
        }
    except:
        return {"temp": 26.5, "pwat": 75.0, "v850": 25.0, "theta_e": 340.0}

# --- 4. 메인 UI ---
st.title("🌧️ 전북 극한호우 예측 시스템 v2.1 (시간 가중치 적용)")

# 시간 가중치 확인
time_weight, time_msg = get_time_weight()
st.subheader(time_msg)

selected_city = st.sidebar.selectbox("📍 관측 지역 선택", list(STATIONS.keys()))
real_data = fetch_realtime_weather(STATIONS[selected_city])

# 사이드바 입력
st.sidebar.header("📊 관측값 조정")
sst = st.sidebar.slider("해수면 온도 (SST, °C)", 20.0, 32.0, 27.5)
pwat = st.sidebar.slider("가용가강수량 (PWAT)", 30.0, 100.0, float(real_data["pwat"]))
v850 = st.sidebar.slider("하층제트 (V850)", 0.0, 50.0, float(real_data["v850"]))
theta_e = st.sidebar.slider("상당온위 (Theta-e)", 300.0, 360.0, float(real_data["theta_e"]))

# --- 5. 가중치 적용 계산 ---
s_sst = (sst - 20) / (32 - 20) * 100
s_pwat = (pwat - 30) / (100 - 30) * 100
s_v850 = (v850 - 0) / (50 - 0) * 100
s_theta = (theta_e - 300) / (360 - 300) * 100

# 기본 지수 계산
base_hri = (0.2 * s_sst) + (0.3 * s_pwat) + (0.2 * s_v850) + (0.3 * s_theta)

# 시간 가중치 반영 (최종 지수)
final_hri = base_hri * time_weight
if final_hri > 100: final_hri = 100 # 최대치 100 제한

# --- 6. 시각화 ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.metric(label="최종 HRI 지수 (시간 가중 반영)", value=f"{final_hri:.1f}점", delta=f"보정치 x{time_weight}")
    
    if final_hri >= 80: st.error("🚨 등급: [위험] 즉각적인 대비 필요")
    elif final_hri >= 60: st.warning("⚠️ 등급: [주의] 기상 추이 모니터링")
    else: st.success("✅ 등급: [보통] 현재 안정적")
    
    st.write(f"**현재 {selected_city} 기온:** {real_data['temp']}°C / **습도:** {real_data['pwat']}%")

with col2:
    fig = go.Figure(go.Scatterpolar(
        r=[s_sst, s_pwat, s_v850, s_theta],
        theta=['해수면온도', '가용수증기', '하층제트', '상당온위'],
        fill='toself'
    ))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
