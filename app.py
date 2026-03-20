import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components

# --- [1. 기본 설정 및 상단 여백 수정] ---
st.set_page_config(page_title="전북 극한호우 실시간 감시", layout="wide")

# CSS: 상단 padding을 대폭 늘려 잘림 방지 및 메트릭 폰트 최적화
st.markdown("""
    <style>
    /* 상단 여백 확보 */
    .block-container { 
        padding-top: 4rem !important; 
        padding-bottom: 0rem !important; 
    }
    /* 타이틀 폰트 크기 및 간격 조정 */
    h2 { margin-top: -1rem; padding-bottom: 1rem; }
    /* 메트릭 값 크기 조정 */
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; color: #1E88E5; }
    </style>
    """, unsafe_allow_html=True)

API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# --- [2. 핵심 엔진] ---
@st.cache_data(ttl=600)
def fetch_weather(nx, ny):
    now = datetime.now(KST)
    for i in range(1, 4):
        target_time = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        base_date = target_time.strftime("%Y%m%d")
        base_time = target_time.strftime("%H00")
        url = f"http://apis.data.go.kr{API_KEY}&dataType=JSON&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
        try:
            res = requests.get(url, timeout=5).json()
            if res['response']['header']['resultCode'] == '00':
                items = res['response']['body']['items']['item']
                return {
                    'T1H': float(next(i['obsrValue'] for i in items if i['category'] == 'T1H')),
                    'REH': float(next(i['obsrValue'] for i in items if i['category'] == 'REH')),
                    'WSD': float(next(i['obsrValue'] for i in items if i['category'] == 'WSD')),
                    'RN1': float(next(i['obsrValue'] for i in items if i['category'] == 'RN1')),
                    'base': f"{base_date} {base_time}"
                }
        except: continue
    return None

def get_hri(w):
    if not w: return 0.0
    pwat, v850, cape = w['REH']*0.65+10, w['WSD']*2.5, w['T1H']*100
    score = (pwat*32)/2500*30 + (cape/5000)*35 + (v850*15)/800*35
    return min(100, round(score, 1))

# --- [3. 메인 화면 구성] ---
# 상단 헤더: 타이틀과 실시간 시계
t_col1, t_col2 = st.columns(2)
with t_col1:
    st.subheader("🌊 전북 14개 시군 극한호우 실시간 감시 (HRI 2.0)")
with t_col2:
    components.html(f"""
        <div style="text-align:right; font-family:sans-serif; padding-right:10px;">
            <div id="clock" style="font-size:18px; font-weight:bold; color:#1E88E5;">⏱️ 로딩 중...</div>
            <div style="font-size:11px; color:gray;">전북특별자치도 방재 연구용</div>
        </div>
        <script>
            function updateClock() {{
                var now = new Date();
                var kst = new Date(now.getTime() + (now.getTimezoneOffset() * 60000) + (9 * 3600000));
                document.getElementById('clock').innerHTML = "⏱️ " + kst.toLocaleString('ko-KR');
            }}
            setInterval(updateClock, 1000); updateClock();
        </script>
    """, height=50)

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

all_data = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}

# 1행: 지도 및 순위 현황
m1, m2 = st.columns(2)
with m1:
    m = folium.Map(location=[35.7, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        sc = get_hri(all_data[name])
        folium.CircleMarker([info['lat'], info['lon']], radius=10, 
                            color="red" if sc>=95 else "orange" if sc>=80 else "green", 
                            fill=True, fill_opacity=0.7, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=380, returned_objects=[])

with m2:
    summary = [{"지역": name, "HRI": get_hri(all_data[name]), 
                "상태": "🔴 위험" if get_hri(all_data[name])>=95 else "🟠 주의" if get_hri(all_data[name])>=80 else "🟢 정상"} 
               for name in LOCATIONS.keys()]
    df_sum = pd.DataFrame(summary).sort_values("HRI", ascending=False)
    st.dataframe(df_sum, hide_index=True, use_container_width=True, height=380)

# 2행: 상세 분석
st.divider()
b1, b2, b3 = st.columns(3)

with b1:
    target = st.selectbox("🎯 상세 분석 지역", list(LOCATIONS.keys()))
    w = all_data[target]
    sc = get_hri(w)
    if sc >= 95: st.error("🚨 극한호우 경보")
    elif sc >= 80: st.warning("⚠️ 집중호우 주의")
    else: st.success("✅ 기상 안정")
    if w: st.caption(f"📡 수신 시각: {w['base']}")

with b2:
    fig = go.Figure(go.Indicator(mode="gauge+number", value=sc, domain={'x': [0, 1], 'y': [0, 1]},
        gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#E8F5E9"}, {'range': [40, 80], 'color': "#FFF59D"}, 
                                                  {'range': [80, 95], 'color': "#FFCC80"}, {'range': [95, 100], 'color': "#EF9A9A"}],
               'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}}))
    fig.update_layout(height=220, margin=dict(l=10, r=10, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

with b3:
    if w:
        st.metric("🌡️ 현재 기온", f"{w['T1H']}°C")
        st.metric("🌧️ 1시간 강수량", f"{w['RN1']}mm")
        st.write(f"💧 습도: {w['REH']}% | 💨 풍속: {w['WSD']}m/s")
    else: st.info("데이터 수신 대기 중")
