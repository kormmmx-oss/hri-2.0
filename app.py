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

# 상단 여백 및 UI 최적화
st.html("""<style>
    .block-container { padding-top: 4rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; color: #1E88E5; }
</style>""")

API_KEY = "Tt8x4uYTSKufMeLmE-ir3Q"
KST = pytz.timezone('Asia/Seoul')

# 7대 극한호우 사례 (논문 기반 고정 데이터)
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

# --- [2. 핵심 엔진: HRI 2.1 보정 공식] ---
def get_hri_21(pwat, cape, v850, loc_name, updiv=15.0, ki=32.0, is_sim=False):
    # 실시간 모드에서 평시(비 안올 때) 지수 과잉 산출 방지 로직
    if not is_sim:
        if pwat < 45 or cape < 800: # 대기 안정 시 지수 하향 보정
            stability_factor = 0.6
        else:
            stability_factor = 1.0
    else:
        stability_factor = 1.0 # 시뮬레이션은 사례값 그대로 적용

    fuel = (pwat * ki) / 2300 * 30
    explosive = (cape / 4000) * 35
    pump = (v850 * updiv) / 750 * 35
    
    mod = LOCATIONS[loc_name]["mod"]
    score = (fuel + explosive + pump) * 1.02 * mod * stability_factor
    return min(100.0, round(score, 1))

@st.cache_data(ttl=600)
def fetch_weather(nx, ny):
    now = datetime.now(KST)
    for i in range(1, 5): # 4시간 전까지 데이터 탐색
        t = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        url = f"http://apis.data.go.kr{API_KEY}&dataType=JSON&base_date={t.strftime('%Y%m%d')}&base_time={t.strftime('%H00')}&nx={nx}&ny={ny}"
        try:
            res = requests.get(url, timeout=5).json()
            if res['response']['header']['resultCode'] == '00':
                items = res['response']['body']['items']['item']
                
                # 데이터 유효성 검사 (이상치 -999 제거)
                def clean_val(cat):
                    v = next(i['obsrValue'] for i in items if i['category'] == cat)
                    return float(v) if float(v) > -50 else None

                t1h = clean_val('T1H')
                reh = clean_val('REH')
                wsd = clean_val('WSD')
                rn1 = clean_val('RN1')

                if t1h is not None and reh is not None:
                    return {'T1H': t1h, 'REH': reh, 'WSD': wsd if wsd else 0, 'RN1': rn1 if rn1 else 0, 'base': t.strftime("%m/%d %H시")}
        except: continue
    return None

# --- [3. 메인 UI] ---
tab1, tab2 = st.tabs(["📡 실시간 극한호우 감시", "🧪 7대 사례 시뮬레이터"])

with tab1:
    st.subheader("⚠️ 전북 실시간 극한호우 가능성 감시 (HRI 2.1)")
    weather_source = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}
    is_simulation = False

with tab2:
    st.subheader("📅 과거 7대 극한호우 사례 재현")
    sim_case = st.selectbox("분석할 사례를 선택하세요", list(PAST_RECORDS.keys()))
    cd = PAST_RECORDS[sim_case]
    weather_source = {}
    for name in LOCATIONS.keys():
        v = 1 + (hash(name) % 8 - 4) / 100 # 지역별 미세 변동
        weather_source[name] = {'T1H': (cd['cape']*v)/100, 'REH': ((cd['pwat']*v)-10)/0.65, 'WSD': (cd['v850']*v)/2.5, 'RN1': 100.0, 'sim': True, 'up': cd['updiv'], 'ki': cd['ki']}
    with st.expander("🖼️ 당시 지상 일기도 확인"):
        st.image(cd['img'], use_container_width=True)
    is_simulation = True

# 공통 레이아웃 (지도 & 순위)
m1, m2 = st.columns([6, 4])
with m1:
    m = folium.Map(location=[35.75, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = weather_source[name]
        if w:
            pwat = w['REH']*0.65+10
            cape = w['T1H']*100
            wsd = w['WSD']*2.5
            sc = get_hri_21(pwat, cape, wsd, name, w.get('up', 15.0), w.get('ki', 32.0), is_sim=is_simulation)
            folium.CircleMarker([info['lat'], info['lon']], radius=10, color="red" if sc>=95 else "orange" if sc>=80 else "green", fill=True, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=380, returned_objects=[])

with m2:
    st.write(f"📊 **{ '실시간' if not is_simulation else '시뮬레이션' } 위험도 순위**")
    summary = []
    for n in LOCATIONS.keys():
        w = weather_source[n]
        if w:
            sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, n, w.get('up', 15.0), w.get('ki', 32.0), is_sim=is_simulation)
        else: sc = 0
        summary.append({"지역": n, "가능성 지수": sc, "1h 강수": w['RN1'] if w else 0})
    st.dataframe(pd.DataFrame(summary).sort_values("가능성 지수", ascending=False), hide_index=True, use_container_width=True, height=350)

# 상세 지표 & 강수 분포
st.divider()
target = st.selectbox("🎯 집중 분석 지역 선택", list(LOCATIONS.keys()))
tw = weather_source[target]
if tw:
    tsc = get_hri_21(tw['REH']*0.65+10, tw['T1H']*100, tw['WSD']*2.5, target, tw.get('up', 15.0), tw.get('ki', 32.0), is_sim=is_simulation)
else: tsc = 0

b1, b2, b3 = st.columns([3, 3.5, 3.5])
with b1:
    fig_g = go.Figure(go.Indicator(mode="gauge+number", value=tsc, title={'text': f"{target} 위험도"},
        gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#E8F5E9"}, {'range': [40, 80], 'color': "#FFF59D"}, 
                                                  {'range': [80, 95], 'color': "#FFCC80"}, {'range': [95, 100], 'color': "#EF9A9A"}],
               'threshold': {'line': {'color': "red", 'width': 4}, 'value': 95}}))
    fig_g.update_layout(height=230, margin=dict(l=10, r=10, t=50, b=0))
    st.plotly_chart(fig_g, use_container_width=True)

with b2:
    st.write(f"📊 **전북 시군별 1시간 강수량 현황**")
    rain_df = pd.DataFrame([{"지역": k, "강수": v['RN1'] if v else 0} for k, v in weather_source.items()])
    fig_bar = go.Figure(go.Bar(x=rain_df['지역'], y=rain_df['강수'], marker_color='skyblue'))
    fig_bar.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

with b3:
    st.write(f"📈 **{target} 관측 세부 데이터**")
    if tw:
        st.metric("기온", f"{tw['T1H']:.1f}°C")
        st.metric("습도", f"{tw['REH']:.1f}%")
        if not is_simulation: st.caption(f"📡 데이터 기준: {tw['base']}")
        else: st.error("🧪 시뮬레이션 데이터 적용 중")
