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

st.html("""<style>
    .block-container { padding-top: 4rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; color: #1E88E5; }
</style>""")

API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

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

# --- [2. 핵심 엔진] ---
@st.cache_data(ttl=600)
def fetch_realtime_data(nx, ny):
    now = datetime.now(KST)
    for i in range(0, 6):
        t = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        base_date = t.strftime("%Y%m%d")
        base_time = t.strftime("%H00")
        url = f"http://apis.data.go.kr{API_KEY}&dataType=JSON&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
        try:
            res = requests.get(url, timeout=5).json()
            if res['response']['header']['resultCode'] == '00':
                items = res['response']['body']['items']['item']
                def clean_val(cat):
                    v = next(i['obsrValue'] for i in items if i['category'] == cat)
                    return float(v) if float(v) > -50 else 0.0
                return {'T1H': clean_val('T1H'), 'REH': clean_val('REH'), 'WSD': clean_val('WSD'), 'RN1': clean_val('RN1'), 'base': t.strftime("%m/%d %H시")}
        except: continue
    return None

def get_hri_21(pwat, cape, v850, loc_name, rain_1h=0, is_sim=False):
    stability = 0.3 if (not is_sim and rain_1h <= 0) else 1.0
    mod = LOCATIONS[loc_name]["mod"]
    score = ((pwat*32)/2300*30 + (cape/4000)*35 + (v850*15)/750*35) * 1.02 * mod * stability
    return min(100.0, round(score, 1))

# --- [3. 메인 UI] ---
t1, t2 = st.columns(2)
with t1:
    st.subheader("⚠️ 전북 극한호우 실시간 감시 & 시뮬레이터")
with t2:
    components.html("""<div id="clock" style="text-align:right; font-size:18px; font-weight:bold; color:#1E88E5; font-family:sans-serif;"></div>
    <script>function updateClock(){var now=new Date(); var kst=new Date(now.getTime()+(now.getTimezoneOffset()*60000)+(9*3600000));
    document.getElementById('clock').innerHTML="⏱️ "+kst.toLocaleString('ko-KR');} setInterval(updateClock,1000); updateClock();</script>""", height=40)

tab1, tab2 = st.tabs(["📡 실시간 극한호우 감시", "🧪 7대 사례 시뮬레이터"])

with tab1:
    realtime_weather = {name: fetch_realtime_data(info['nx'], info['ny']) for name, info in LOCATIONS.items()}
    source = realtime_weather
    is_sim_mode = False

with tab2:
    PAST_RECORDS = {
        "2025-09-07 군산 (152.2mm)": {"pwat": 65.5, "cape": 4500, "v850": 20.0, "up": 40.2, "ki": 38.0, "rn1": 152.2},
        "2024-07-10 익산 (125.5mm)": {"pwat": 64.5, "cape": 3800, "v850": 23.5, "up": 18.3, "ki": 37.0, "rn1": 125.5}
    }
    sim_case = st.selectbox("분석할 과거 사례 선택", list(PAST_RECORDS.keys()))
    cd = PAST_RECORDS[sim_case]
    sim_weather = {name: {'T1H': cd['cape']/100, 'REH': (cd['pwat']-10)/0.65, 'WSD': cd['v850']/2.5, 'RN1': cd['rn1'], 'up': cd['up'], 'ki': cd['ki']} for name in LOCATIONS.keys()}
    if st.button("🧪 시뮬레이션 적용"):
        source = sim_weather
        is_sim_mode = True
    else:
        source = realtime_weather
        is_sim_mode = False

# 지도 & 순위표
m1, m2 = st.columns(2)
with m1:
    m = folium.Map(location=[35.75, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = source.get(name)
        if w:
            sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, name, rain_1h=w['RN1'], is_sim=is_sim_mode)
            folium.CircleMarker([info['lat'], info['lon']], radius=10, color="red" if sc>=95 else "orange" if sc>=80 else "green", fill=True, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=380)

with m2:
    st.write(f"📊 **{ '시뮬레이션' if is_sim_mode else '실시간' } 위험도 순위**")
    summary = []
    for n in LOCATIONS.keys():
        w = source.get(n)
        sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, n, rain_1h=w['RN1'] if w else 0, is_sim=is_sim_mode) if w else 0
        summary.append({"지역": n, "지수": sc, "1h 강수": w['RN1'] if w else 0})
    st.dataframe(pd.DataFrame(summary).sort_values("지수", ascending=False), hide_index=True, use_container_width=True, height=350)

st.divider()

# --- [하단 상세 분석 및 강수량 분포도 섹션] ---
b1, b2, b3 = st.columns([3, 3.5, 3.5])

with b1:
    target = st.selectbox("🎯 상세 분석 지역 선택", list(LOCATIONS.keys()))
    tw = source.get(target)
    tsc = get_hri_21(tw['REH']*0.65+10, tw['T1H']*100, tw['WSD']*2.5, target, rain_1h=tw['RN1'] if tw else 0, is_sim=is_sim_mode) if tw else 0
    
    fig = go.Figure(go.Indicator(mode="gauge+number", value=tsc, title={'text': f"{target} 위험도"},
        gauge={'axis': {'range': [0, 100]}, 
               'steps': [{'range': [0, 40], 'color': "#E8F5E9"}, 
                         {'range': [40, 80], 'color': "#FFF59D"}, 
                         {'range': [80, 95], 'color': "#FFCC80"}, 
                         {'range': [95, 100], 'color': "#EF9A9A"}],
               'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}}))
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=50, b=0))
    st.plotly_chart(fig, use_container_width=True)

with b2:
    st.write(f"📊 **전북 시군별 1시간 강수량 현황**")
    rain_data = pd.DataFrame([{"지역": k, "강수": v['RN1'] if v else 0} for k, v in source.items()])
    fig_bar = go.Figure(go.Bar(x=rain_data['지역'], y=rain_data['강수'], marker_color='skyblue'))
    fig_bar.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="mm")
    st.plotly_chart(fig_bar, use_container_width=True)

with b3:
    st.write(f"📈 **{target} 상세 관측 데이터**")
    if tw:
        st.metric("기온 (추정/실측)", f"{tw['T1H']:.1f}°C")
        st.metric("1시간 강수량", f"{tw['RN1']:.1f} mm")
        if not is_sim_mode: st.caption(f"📡 API 데이터 기준: {tw['base']}")
        else: st.error("🧪 시뮬레이션 모드 활성 중")
