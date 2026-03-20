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
st.set_page_config(page_title="전북 극한호우 실시간 감시 시스템", layout="wide")

# 상단 잘림 방지 및 여백 설정
st.html("""
    <style>
    .block-container { padding-top: 4rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; color: #1E88E5; }
    .stDataFrame { font-size: 12px; }
    </style>
""")

API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# 14개 시군 좌표 및 지형 보정 계수
LOCATIONS = {
    "전주": {"nx": 63, "ny": 89, "lat": 35.824, "lon": 127.148, "mod": 1.0},
    "군산": {"nx": 56, "ny": 92, "lat": 35.967, "lon": 126.736, "mod": 1.05},
    "익산": {"nx": 60, "ny": 91, "lat": 35.948, "lon": 126.957, "mod": 1.0},
    "정읍": {"nx": 58, "ny": 83, "lat": 35.569, "lon": 126.856, "mod": 0.97},
    "남원": {"nx": 68, "ny": 80, "lat": 35.416, "lon": 127.390, "mod": 0.96},
    "김제": {"nx": 59, "ny": 88, "lat": 35.803, "lon": 126.880, "mod": 1.0},
    "완주": {"nx": 63, "ny": 91, "lat": 35.904, "lon": 127.162, "mod": 0.98},
    "진안": {"nx": 68, "ny": 88, "lat": 35.791, "lon": 127.424, "mod": 0.92},
    "무주": {"nx": 72, "ny": 93, "lat": 36.006, "lon": 127.660, "mod": 0.91},
    "장수": {"nx": 70, "ny": 85, "lat": 35.647, "lon": 127.521, "mod": 0.90},
    "임실": {"nx": 66, "ny": 84, "lat": 35.617, "lon": 127.289, "mod": 0.95},
    "순창": {"nx": 63, "ny": 79, "lat": 35.374, "lon": 127.137, "mod": 0.94},
    "고창": {"nx": 54, "ny": 80, "lat": 35.435, "lon": 126.702, "mod": 1.02},
    "부안": {"nx": 56, "ny": 87, "lat": 35.731, "lon": 126.733, "mod": 1.03}
}

# --- [2. 데이터 수집 및 엔진] ---
def get_hri_21(pwat, cape, v850, loc_name, updiv=15.0, ki=32.0):
    modifier = LOCATIONS[loc_name]["mod"]
    score = ((pwat*ki)/2300*30 + (cape/4000)*35 + (v850*updiv)/750*35) * 1.02 * modifier
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
            # PTY(강수형태), REH(습도), RN1(1시간강수), T1H(기온), WSD(풍속)
            return {
                'T1H': float(next(i['obsrValue'] for i in items if i['category'] == 'T1H')),
                'REH': float(next(i['obsrValue'] for i in items if i['category'] == 'REH')),
                'WSD': float(next(i['obsrValue'] for i in items if i['category'] == 'WSD')),
                'RN1': float(next(i['obsrValue'] for i in items if i['category'] == 'RN1')),
                'base': t.strftime("%m/%d %H시")
            }
        except: continue
    return None

# --- [3. 메인 화면 구성] ---
t1, t2 = st.columns([7, 3])
with t1:
    st.subheader("⚠️ 전북 실시간 극한호우 발생 가능성 감시")
with t2:
    components.html("""<div id="clock" style="text-align:right; font-size:18px; font-weight:bold; color:#1E88E5; font-family:sans-serif;"></div>
    <script>function updateClock(){var now=new Date(); var kst=new Date(now.getTime()+(now.getTimezoneOffset()*60000)+(9*3600000));
    document.getElementById('clock').innerHTML="⏱️ "+kst.toLocaleString('ko-KR');} setInterval(updateClock,1000); updateClock();</script>""", height=45)

# 전 지역 데이터 로드
all_data = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}

# 지도 & 실시간 위험도 리스트
m1, m2 = st.columns([6, 4])
with m1:
    m = folium.Map(location=[35.75, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = all_data[name]
        sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, name) if w else 0
        folium.CircleMarker([info['lat'], info['lon']], radius=10, color="red" if sc>=95 else "orange" if sc>=80 else "green", fill=True, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=380, returned_objects=[])

with m2:
    summary = []
    for n in LOCATIONS.keys():
        w = all_data[n]
        sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, n) if w else 0
        summary.append({"지역": n, "가능성 지수": sc, "1h 강수": w['RN1'] if w else 0})
    df_sum = pd.DataFrame(summary).sort_values("가능성 지수", ascending=False)
    st.dataframe(df_sum, hide_index=True, use_container_width=True, height=350)

# 상세 분석 & 강수 분포도
st.divider()
target = st.selectbox("🎯 집중 분석 지역", list(LOCATIONS.keys()))
tw = all_data[target]
tsc = get_hri_21(tw['REH']*0.65+10, tw['T1H']*100, tw['WSD']*2.5, target) if tw else 0

b1, b2, b3 = st.columns([3, 3.5, 3.5])

with b1:
    fig_g = go.Figure(go.Indicator(mode="gauge+number", value=tsc, title={'text': f"{target} 발생 가능성"},
        gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 60], 'color': "#E8F5E9"}, {'range': [60, 85], 'color': "#FFF59D"}, 
                                                  {'range': [85, 95], 'color': "#FFCC80"}, {'range': [95, 100], 'color': "#EF9A9A"}],
               'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}}))
    fig_g.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=0))
    st.plotly_chart(fig_g, use_container_width=True)

with b2:
    st.write(f"📊 **전북 주요지역 1시간 강수 현황**")
    rain_1h = pd.DataFrame([{"지역": k, "강수": v['RN1'] if v else 0} for k, v in all_data.items()])
    fig_bar = go.Figure(go.Bar(x=rain_1h['지역'], y=rain_1h['강수'], marker_color='skyblue'))
    fig_bar.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="mm")
    st.plotly_chart(fig_bar, use_container_width=True)

with b3:
    st.write(f"📈 **{target} 실시간 기상 지표**")
    if tw:
        c1, c2 = st.columns(2)
        c1.metric("기온", f"{tw['T1H']}°C")
        c2.metric("습도", f"{tw['REH']}%")
        st.write(f"💨 풍속: {tw['WSD']}m/s | 📡 기준: {tw['base']}")
        # 일강수량 분포 추정 (실황 1h 합산 기반)
        st.progress(min(tw['RN1']/100, 1.0), text=f"극한호우 임계 강도 대비 ({tw['RN1']}mm/h)")
    else: st.info("데이터 수신 대기 중")
