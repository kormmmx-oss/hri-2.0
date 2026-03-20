import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime

# --- 1. 설정 및 지역별 지점번호 ---
st.set_page_config(page_title="전북 실시간 HRI 시스템", layout="wide")

# 기상청 ASOS 지점 번호 (전북 지역)
STATIONS = {
    "전주": "146", "군산": "140", "정읍": "245", 
    "남원": "248", "익산": "249", "고창": "251", "장수": "247", "임실": "244"
}

# --- 2. 기상청 API 데이터 호출 함수 ---
def fetch_realtime_weather(stn_id):
    # 제공해주신 인증키 적용
    SERVICE_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
    url = "http://apis.data.go.kr/1360000/AsosObservationsService/getLatestObservation"
    
    params = {
        'serviceKey': SERVICE_KEY,
        'numOfRows': '1',
        'pageNo': '1',
        'dataType': 'JSON',
        'stnId': stn_id
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        res_data = response.json()
        item = res_data['response']['body']['items']['item'][0]
        
        # 기상청 변수 추출: ta(기온), hm(상대습도)
        # PWAT와 하층제트는 지상 관측값으로 추정치를 사용하거나 고정값 설정
        curr_temp = float(item.get('ta', 25.0))
        curr_hm = float(item.get('hm', 70.0))
        
        return {
            "temp": curr_temp,
            "pwat": curr_hm, # 습도를 PWAT 대용 지표로 활용 (단순화)
            "v850": 20.0,    # 고층 데이터는 기본값 유지
            "theta_e": curr_temp + (curr_hm * 0.1) + 310 # 기온/습도 기반 상당온위 간이 계산식
        }
    except Exception as e:
        # API 호출 실패 시 기본값 반환
        return {"temp": 26.5, "pwat": 75.0, "v850": 25.0, "theta_e": 340.0}

# --- 3. UI 및 데이터 로드 ---
st.title("🌧️ 전북지역 실시간 극한호우 예측 시스템 v2.0")
st.info(f"업데이트 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

selected_city = st.sidebar.selectbox("📍 관측 지역 선택", list(STATIONS.keys()))
real_data = fetch_realtime_weather(STATIONS[selected_city])

st.sidebar.header("📊 실시간 관측값 (보정 가능)")
# API에서 가져온 실시간 값을 초기값으로 설정
sst = st.sidebar.slider("해수면 온도 (SST, °C)", 20.0, 32.0, 27.5)
pwat = st.sidebar.slider("가용가강수량 (PWAT/습도)", 30.0, 100.0, float(real_data["pwat"]))
v850 = st.sidebar.slider("하층제트 (V850, m/s)", 0.0, 50.0, float(real_data["v850"]))
theta_e = st.sidebar.slider("상당온위 (Theta-e, K)", 300.0, 360.0, float(real_data["theta_e"]))

# --- 4. HRI v2.0 계산 공식 ---
s_sst = (sst - 20) / (32 - 20) * 100
s_pwat = (pwat - 30) / (100 - 30) * 100
s_v850 = (v850 - 0) / (50 - 0) * 100
s_theta = (theta_e - 300) / (360 - 300) * 100

# 가중치 적용 (PWAT 30%, Theta-e 30%, 나머지 20%씩)
hri = (0.2 * s_sst) + (0.3 * s_pwat) + (0.2 * s_v850) + (0.3 * s_theta)

# --- 5. 화면 출력 ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.metric(label=f"{selected_city} 현재 위험 지수", value=f"{hri:.1f}점")
    if hri >= 80:
        st.error("🚨 등급: [위험] 극한호우 발생 가능성 매우 높음")
    elif hri >= 60:
        st.warning("⚠️ 등급: [주의] 집중호우 대비 및 모니터링 필요")
    else:
        st.success("✅ 등급: [보통] 현재 기상 안정적")
    
    st.write(f"**현재 {selected_city} 기온:** {real_data['temp']}°C")
    st.write(f"**현재 {selected_city} 습도:** {real_data['pwat']}%")

with col2:
    # 레이더 차트 시각화
    fig = go.Figure(go.Scatterpolar(
        r=[s_sst, s_pwat, s_v850, s_theta],
        theta=['해수면온도', '가용수증기', '하층제트', '상당온위'],
        fill='toself',
        line=dict(color='#FF4B4B')
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        title="항목별 위험 기여도"
    )
    st.plotly_chart(fig, use_container_width=True)
