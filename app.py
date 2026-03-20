import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components

# --- [1. 설정 및 데이터 정의] ---
st.set_page_config(page_title="전북 극한호우 실시간 감시 & 시뮬레이터", layout="wide")

st.html("""<style>
    .block-container { padding-top: 4rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; color: #1E88E5; }
</style>""")

API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# 7대 극한호우 사례 데이터
PAST_RECORDS = {
    "2025-09-07 군산 (152.2mm)": {"pwat": 65.5, "cape": 4500, "v850": 20.0, "updiv": 40.2, "ki": 38.0, "img": "https://img.kma.go.kr"},
    "2024-07-10 익산 (125.5mm)": {"pwat": 64.5, "cape": 3800, "v850": 23.5, "updiv": 18.3, "ki": 37.0, "img": "https://img.kma.go.kr"},
    "2024-08-26 남원 (110.0mm)": {"pwat": 62.0, "cape": 3200, "v850": 18.0, "updiv": 25.0, "ki": 36.5, "img": "https://img.kma.go.kr"},
    "2022-08-11 군산 (100.0mm)": {"pwat": 59.7, "cape": 1500, "v850": 21.0, "updiv": 15.2, "ki": 35.8, "img": "https://img.kma.go.kr"},
    "2020-07-30 완주 (100.5mm)": {"pwat": 60.5, "cape": 1850, "v850": 12.7, "updiv": 7.9, "ki": 36.0, "img": "https://img.kma.go.kr"},
    "2017-07-15 군산 (93.5mm)": {"pwat": 58.2, "cape": 2100, "v850": 15.5, "updiv": 12.0, "ki": 35.5, "img": "https://img.kma.go.kr"},
    "2012-08-13 군산 (110.0mm)": {"pwat": 68.2, "cape": 4200, "v850": 19.8, "updiv": 30.1, "ki": 40.0, "img": "https://img.kma.go.kr"}
}

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

# --- [2. 핵심 엔진: HRI 2.1 분리형 공식] ---
def get_hri_21(pwat, cape, v850, loc_name, rain_1h=0, updiv=15.0, ki=32.0, is_sim=False):
    # 실시간 모드: 강수량이 없으면 지수 억제 (맑은 날 100점 방지)
    if not is_sim:
        if rain_1h <= 0.0:
            stability_factor = 0.3 # 평상시 20~30점 유지
        elif rain_1h < 5.0:
            stability_factor = 0.6
        else:
            stability_factor = 1.1 # 강수 시 민감도 상승
    else:
        # 시뮬레이션 모드: 과거 사례 수치 그대로 반영
        stability_factor = 1.0

    fuel = (pwat * ki) / 2300 * 30
    explosive = (cape / 4000) * 35
    pump = (v850 * updiv) / 750 * 35
    
    mod = LOCATIONS[loc_name]["mod"]
    score = (fuel + explosive + pump) * 1.02 * mod * stability_factor
    return min(100.0, round(score, 1))

@st.cache_data(ttl=600)
def fetch_weather(nx, ny):
    now = datetime.now(KST)
    for i in range(1, 5): 
        t = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        url = f"http://apis.data.go.kr{API_KEY}&dataType=JSON&base_date={t.strftime('%Y%m%d')}&base_time={t.strftime('%H00')}&nx={nx}&ny={ny}"
        try:
            res = requests.get(url, timeout=5).json()
            items = res['response']['body']['items']['item']
            def clean_val(cat):
                v = next(i['obsrValue'] for i in items if i['category'] == cat)
                return float(v) if float(v) > -50 else 0.0
            return {'T1H': clean_val('T1H'), 'REH': clean_val('REH'), 'WSD': clean_val('WSD'), 'RN1': clean_val('RN1'), 'base': t.strftime("%m/%d %H시")}
        except: continue
    return None

# --- [3. 메인 UI 및 데이터 분리 로직] ---
t1, t2 = st.columns([7, 3])
with t1:
    st.subheader("⚠️ 전북 극한호우 실시간 감시 & 시뮬레이터")
with t2:
    components.html("""<div id="clock" style="text-align:right; font-size:18px; font-weight:bold; color:#1E88E5; font-family:sans-serif;">⏱️ 로딩 중...</div>
    <script>function updateClock(){var now=new Date(); var kst=new Date(now.getTime()+(now.getTimezoneOffset()*60000)+(9*3600000));
    document.getElementById('clock').innerHTML="⏱️ "+kst.toLocaleString('ko-KR');} setInterval(updateClock,1000); updateClock();</script>""", height=40)

# 탭을 통해 데이터 소스를 완전히 분리
tab1, tab2 = st.tabs(["📡 실시간 극한호우 감시", "🧪 7대 사례 시뮬레이터"])

with tab1:
    # 실시간 탭 클릭 시에만 API 데이터 소스 사용
    weather_source = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}
    is_sim_mode = False

with tab2:
    # 시뮬레이션 탭 클릭 시 과거 사례 데이터 소스 생성
    sim_case = st.selectbox("분석할 과거 사례를 선택하세요", list(PAST_RECORDS.keys()))
    cd = PAST_RECORDS[sim_case]
    weather_source = {}
    for name in LOCATIONS.keys():
        v = 1 + (hash(name) % 8 - 4) / 100 
        weather_source[name] = {'T1H': (cd['cape']*v)/100, 'REH': ((cd['pwat']*v)-10)/0.65, 'WSD': (cd['v850']*v)/2.5, 'RN1': 100.0, 'sim': True, 'up': cd['updiv'], 'ki': cd['ki']}
    with st.expander("🖼️ 당시 지상 일기도 확인"):
        st.image(cd['img'], use_container_width=True)
    is_sim_mode = True

# --- [4. 공통 출력 레이아웃 (지도 & 현황판)] ---
m1, m2 = st.columns([6, 4])
with m1:
    m = folium.Map(location=[35.75, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = weather_source[name]
        if w:
            # 탭 상태(is_sim_mode)에 따라 다른 계산 로직 적용
            sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, name, rain_1h=w['RN1'], updiv=w.get('up', 15.0), ki=w.get('ki', 32.0), is_sim=is_sim_mode)
            folium.CircleMarker([info['lat'], info['lon']], radius=10, color="red" if sc>=95 else "orange" if sc>=80 else "green", fill=True, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=380, returned_objects=[])

with m2:
    st.write(f"📊 **{ '실시간' if not is_sim_mode else '시뮬레이션' } 위험도 순위**")
    summary = []
    for n in LOCATIONS.keys():
        w = weather_source[n]
        if w:
            sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, n, rain_1h=w['RN1'], updiv=w.get('up', 15.0), ki=w.get('ki', 32.0), is_sim=is_sim_mode)
        else: sc = 0
        summary.append({"지역": n, "지수": sc, "1h 강수": w['RN1'] if w else 0})
    st.dataframe(pd.DataFrame(summary).sort_values("지수", ascending=False), hide_index=True, use_container_width=True, height=350)

# 상세 분석 하단 섹션
st.divider()
target = st.selectbox("🎯 상세 분석 지역 선택", list(LOCATIONS.keys()))
tw = weather_source[target]
tsc = get_hri_21(tw['REH']*0.65+10, tw['T1H']*100, tw['WSD']*2.5, target, rain_1h=tw['RN1'] if tw else 0, updiv=tw.get('up', 15.0), ki=tw.get('ki', 32.0), is_sim=is_sim_mode) if tw else 0

b1, b2, b3 = st.columns([3, 3.5, 3.5])
with b1:
    fig_g = go.Figure(go.Indicator(mode="gauge+number", value=tsc, title={'text': f"{target} 가능성"},
        gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 60], 'color': "#E8F5E9"}, {'range': [60, 80], 'color': "#FFF59D"}, 
                                                  {'range': [80, 95], 'color': "#FFCC80"}, {'range': [95, 100], 'color': "#EF9A9A"}]}))
    fig_g.update_layout(height=230, margin=dict(l=10, r=10, t=50, b=0))
    st.plotly_chart(fig_g, use_container_width=True)

with b2:
    st.write(f"📊 **전북 시군별 1시간 강수량 현황**")
    rain_df = pd.DataFrame([{"지역": k, "강수": v['RN1'] if v else 0} for k, v in weather_source.items()])
    st.bar_chart(rain_df.set_index("지역"), height=230)

with b3:
    if tw:
        st.metric("기온(사례)", f"{tw['T1H']:.1f}°C")
        st.metric("1h 강수량", f"{tw['RN1']:.1f} mm")
        if is_sim_mode: st.error("🧪 시뮬레이션 모드 활성")
        else: st.caption(f"📡 API 데이터 기준: {tw['base']}")
