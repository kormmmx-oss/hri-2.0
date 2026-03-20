import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components

# --- [1. 기본 설정 및 과거 사례 데이터 정의] ---
st.set_page_config(page_title="전북 극한호우 실시간 감시", layout="wide")

# 과거 극한호우 통계 데이터 (제공해주신 25년치 자료 핵심 요약)
PAST_RECORDS = {
    "2025-09-07 군산 (152.2mm)": {"pwat": 65.5, "cape": 4500, "v850": 20.0, "updiv": 40.2, "ki": 38.0},
    "2024-07-10 익산 (125.5mm)": {"pwat": 64.5, "cape": 3800, "v850": 23.5, "updiv": 18.3, "ki": 37.0},
    "2024-08-26 남원 (110.0mm)": {"pwat": 62.0, "cape": 3200, "v850": 18.0, "updiv": 25.0, "ki": 36.5},
    "2022-08-11 군산 (100.0mm)": {"pwat": 59.7, "cape": 1500, "v850": 21.0, "updiv": 15.2, "ki": 35.8},
    "2020-07-30 완주 (100.5mm)": {"pwat": 60.5, "cape": 1850, "v850": 12.7, "updiv": 7.9, "ki": 36.0},
    "2012-08-13 군산 (110.0mm)": {"pwat": 68.2, "cape": 4200, "v850": 19.8, "updiv": 30.1, "ki": 40.0}
}

# --- [2. 핵심 엔진: 유사도 계산 함수 추가] ---
def get_similarity(current, past):
    # 각 변수별 차이를 계산하여 유사도(%) 산출
    diff = (
        abs(current['pwat'] - past['pwat'])/70 + 
        abs(current['cape'] - past['cape'])/7000 + 
        abs(current['v850'] - past['v850'])/40 + 
        abs(current['updiv'] - past['updiv'])/50
    ) / 4
    return round(max(0, (1 - diff) * 100), 1)

# (중략: fetch_weather, get_hri 함수는 기존과 동일)

# --- [3. 화면 구성: 과거 사례 비교 섹션 보강] ---
# ... (상단 타이틀, 지도, 순위표 코드 유지) ...

st.divider()
st.subheader("🔍 상세 분석 및 과거 사례 비교")
b1, b2, b3 = st.columns(3)

with b1:
    target = st.selectbox("🎯 분석 지역 선택", list(LOCATIONS.keys()))
    w = all_data[target]
    sc = get_hri(w)
    
    # 실시간 데이터 기반 추정치 (비교용)
    curr_params = {
        'pwat': w['REH']*0.65+10 if w else 0,
        'cape': w['T1H']*100 if w else 0,
        'v850': w['WSD']*2.5 if w else 0,
        'updiv': 15.0 # 추정치
    }
    
    # 가장 유사한 과거 사례 찾기
    best_match = ""
    max_sim = 0
    if w:
        for name, data in PAST_RECORDS.items():
            sim = get_similarity(curr_params, data)
            if sim > max_sim:
                max_sim = sim
                best_match = name
    
    if max_sim > 80:
        st.warning(f"⚠️ 현재 상황이 **{best_match}** 때와 **{max_sim}%** 유사합니다!")
    else:
        st.info(f"💡 가장 유사한 사례: {best_match} ({max_sim}%)")

with b2:
    # 게이지 차트 (기존과 동일)
    fig = go.Figure(go.Indicator(mode="gauge+number", value=sc, 
        gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#E8F5E9"}, ...]} )) # 생략
    st.plotly_chart(fig, use_container_width=True)

with b3:
    # 과거 25년 통계 데이터 요약표 표출
    with st.expander("📚 전북 극한호우 히스토리 보기"):
        st.table(pd.DataFrame(PAST_RECORDS).T.iloc[:, :3]) # 주요 3개 변수만 표출
