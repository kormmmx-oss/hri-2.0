import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# 1. 페이지 설정 (모바일 최적화)
st.set_page_config(page_title="전북 극한호우 HRI 2.0 감시", layout="centered")

# 2. 과거 사례 데이터 정의 (제공해주신 25년 통계 자료 기반)
past_cases = {
    "2025년 군산 (152.2mm)": {"pwat": 65.5, "cape": 4500, "v850": 20.0, "upper_div": 40.2, "k_index": 38.0},
    "2024년 익산 (125.5mm)": {"pwat": 64.5, "cape": 3800, "v850": 23.5, "upper_div": 18.3, "k_index": 37.0},
    "2022년 군산 (100.0mm)": {"pwat": 59.7, "cape": 1500, "v850": 21.0, "upper_div": 15.2, "k_index": 35.8},
    "2012년 군산 (110.0mm)": {"pwat": 68.2, "cape": 4200, "v850": 19.8, "upper_div": 30.1, "k_index": 40.0}
}

# 3. HRI 2.0 지수 및 유사도 계산 함수
def calculate_hri_2(pwat, cape, v850, upper_div, k_index):
    # 연료항(30) + 폭발항(35) + 펌프항(35) 구조
    fuel = (pwat * k_index) / 2500 * 30
    explosive = (cape / 5000) * 35
    pump = (v850 * upper_div) / 800 * 35
    return min(100, round(fuel + explosive + pump, 1))

def get_best_match(current):
    best_name = ""
    max_sim = -1
    
    for name, data in past_cases.items():
        # 각 변수별 차이의 가중 평균으로 유사도 산출
        score = 1 - (
            abs(current['pwat'] - data['pwat'])/75 * 0.2 +
            abs(current['cape'] - data['cape'])/7000 * 0.2 +
            abs(current['v850'] - data['v850'])/40 * 0.2 +
            abs(current['upper_div'] - data['upper_div'])/50 * 0.2 +
            abs(current['k_index'] - data['k_index'])/50 * 0.2
        )
        sim_percent = round(max(0, score * 100), 1)
        if sim_percent > max_sim:
            max_sim = sim_percent
            best_name = name
    return best_name, max_sim

# 4. 사이드바: 실시간 데이터 입력
st.sidebar.header("📍 실시간 기상 관측값 (전북)")
location = st.sidebar.selectbox("감시 지역", ["군산", "전주", "익산", "부안", "남원"])
pwat = st.sidebar.slider("PWAT (수증기량)", 30.0, 75.0, 60.0)
cape = st.sidebar.slider("CAPE (대류불안정)", 0, 7000, 2000)
v850 = st.sidebar.slider("V850 (850hPa 풍속)", 0.0, 40.0, 15.0)
upper_div = st.sidebar.slider("Upper Div (200hPa 발산)", -10.0, 50.0, 10.0)
k_index = st.sidebar.slider("K-Index", 10.0, 50.0, 30.0)

# 현재 입력값 정리
current_weather = {'pwat': pwat, 'cape': cape, 'v850': v850, 'upper_div': upper_div, 'k_index': k_index}

# 지수 및 유사도 계산 실행
hri_score = calculate_hri_2(pwat, cape, v850, upper_div, k_index)
match_name, match_percent = get_best_match(current_weather)

# 5. 메인 화면 UI
st.title(f"🌊 {location} 극한호우 실시간 감시")
st.write(f"분석 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 게이지 차트
fig = go.Figure(go.Indicator(
    mode = "gauge+number",
    value = hri_score,
    domain = {'x': [0, 1], 'y': [0, 1]},
    title = {'text': "HRI 2.0 위험 지수"},
    gauge = {
        'axis': {'range': [0, 100]},
        'steps': [
            {'range': [0, 60], 'color': "#E8F5E9"},
            {'range': [60, 80], 'color': "#FFF59D"},
            {'range': [80, 95], 'color': "#FFCC80"},
            {'range': [95, 100], 'color': "#EF9A9A"}],
        'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}
    }
))
st.plotly_chart(fig, use_container_width=True)

# 위험 단계 메시지
if hri_score >= 95:
    st.error(f"🚨 [심각] 시간당 100mm 이상 극한호우 발생 가능성 매우 높음 (지수: {hri_score})")
elif hri_score >= 80:
    st.warning(f"⚠️ [경계] 집중호우 발달 가능성 (지수: {hri_score})")
else:
    st.success(f"✅ [정상] 현재 기상 조건은 안정적입니다. (지수: {hri_score})")

# 6. 동적 유사 사례 분석 (슬라이더 연동됨)
st.subheader("📊 과거 유사 사례 분석")
st.info(f"현재 기상 조건은 과거 **{match_name}** 사례와 **{match_percent}%** 일치합니다.")

# 7. 위험 요인 분석 그래프
st.subheader("🔍 HRI 2.0 구성 요인")
fuel_val = (pwat * k_index) / 2500 * 30
exp_val = (cape / 5000) * 35
pump_val = (v850 * upper_div) / 800 * 35

contrib_df = pd.DataFrame({
    '요인': ['연료(수증기)', '폭발(불안정)', '펌프(상하층연결)'],
    '기여도 점수': [fuel_val, exp_val, pump_val]
})
st.bar_chart(data=contrib_df, x='요인', y='기여도 점수')

st.caption("※ 본 지수는 전북지역 25년 극한호우 통계 데이터를 기반으로 산출된 연구용 지표입니다.")
