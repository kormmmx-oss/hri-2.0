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
st.set_page_config(page_title="전북 극한호우 실시간 감시 & 시뮬레이터", layout="wide")

st.html("""<style>
    .block-container { padding-top: 4rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; color: #1E88E5; }
</style>""")

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

# --- [2. 핵심 엔진: HRI 2.1 실시간 보정 공식] ---
def get_hri_21(pwat, cape, v850, loc_name, rain_1h=0, updiv=15.0, ki=32.0, is_sim=False):
    # 실시간 모드에서 강수량이 없을 경우 지수 과잉 산출 강력 억제
    if not is_sim:
        if rain_1h <= 0: # 강수가 전혀 없는 맑은 날씨
            stability_factor = 0.3 # 지수를 평시 수준(20~30점)으로 강제 하향
        elif rain_1h < 10: # 약한 비
            stability_factor = 0.6
        else: # 강한 강수 시작
            stability_factor = 1.1 
    else:
        stability_factor = 1.0 # 시뮬레이션은 사례값 그대로

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
            if res['response']['header']['resultCode'] == '00':
                items = res['response']['body']['items']['item']
                
                def clean_val(cat):
                    v = next(i['obsrValue'] for i in items if i['category'] == cat)
                    return float(v) if float(v) > -50 else 0.0

                t1h = clean_val('T1H')
                reh = clean_val('REH')
                wsd = clean_val('WSD')
                rn1 = clean_val('RN1')

                return {'T1H': t1h, 'REH': reh, 'WSD': wsd, 'RN1': rn1, 'base': t.strftime("%m/%d %H시")}
        except: continue
    return None

# --- [3. 메인 UI 및 실시간 시계] ---
t1, t2 = st.columns([7, 3])
with t1:
    st.subheader("⚠️ 전북 실시간 극한호우 가능성 감시 (HRI 2.1)")
with t2:
    components.html("""<div id="clock" style="text-align:right; font-size:18px; font-weight:bold; color:#1E88E5; font-family:sans-serif;">⏱️ 로딩 중...</div>
    <script>function updateClock(){var now=new Date(); var kst=new Date(now.getTime()+(now.getTimezoneOffset()*60000)+(9*3600000));
    document.getElementById('clock').innerHTML="⏱️ "+kst.toLocaleString('ko-KR');} setInterval(updateClock,1000); updateClock();</script>""", height=45)

tab1, tab2 = st.tabs(["📡 실시간 극한호우 감시", "🧪 7대 사례 시뮬레이터"])

with tab1:
    weather_source = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}
    is_simulation = False

with tab2:
    sim_case = st.selectbox("분석할 과거 사례를 선택하세요", list(pd.read_csv('past_records.csv')['case'].unique()) if False else ["2025-09-07 군산 (152.2mm)"]) 
    # 과거 사례 데이터 하드코딩 (예시)
    PAST_RECORDS = {"2025-09-07 군산 (152.2mm)": {"pwat": 65.5, "cape": 4500, "v850": 20.0, "updiv": 40.2, "ki": 38.0}}
    cd = PAST_RECORDS[sim_case]
    weather_source = {name: {'T1H': cd['cape']/100, 'REH': (cd['pwat']-10)/0.65, 'WSD': cd['v850']/2.5, 'RN1': 152.2, 'sim': True, 'up': cd['updiv'], 'ki': cd['ki']} for name in LOCATIONS.keys()}
    is_simulation = True

# 지도 & 순위표
m1, m2 = st.columns([6, 4])
with m1:
    m = folium.Map(location=[35.75, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = weather_source[name]
        if w:
            sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, name, rain_1h=w['RN1'], updiv=w.get('up', 15.0), ki=w.get('ki', 32.0), is_sim=is_simulation)
            folium.CircleMarker([info['lat'], info['lon']], radius=10, color="red" if sc>=95 else "orange" if sc>=80 else "green", fill=True, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=380, returned_objects=[])

with m2:
    summary = []
    for n in LOCATIONS.keys():
        w = weather_source[n]
        sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, n, rain_1h=w['RN1'] if w else 0, is_sim=is_simulation) if w else 0
        summary.append({"지역": n, "가능성 지수": sc, "1h 강수(mm)": w['RN1'] if w else 0})
    st.dataframe(pd.DataFrame(summary).sort_values("가능성 지수", ascending=False), hide_index=True, use_container_width=True, height=350)

# 상세 정보
st.divider()
target = st.selectbox("🎯 상세 분석 시군", list(LOCATIONS.keys()))
tw = weather_source[target]
tsc = get_hri_21(tw['REH']*0.65+10, tw['T1H']*100, tw['WSD']*2.5, target, rain_1h=tw['RN1'] if tw else 0, is_sim=is_simulation) if tw else 0

b1, b2, b3 = st.columns([3, 3.5, 3.5])
with b1:
    fig_g = go.Figure(go.Indicator(mode="gauge+number", value=tsc, title={'text': f"{target} 위험도"},
        gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#E8F5E9"}, {'range': [40, 80], 'color': "#FFF59D"}, 
                                                  {'range': [80, 95], 'color': "#FFCC80"}, {'range': [95, 100], 'color': "#EF9A9A"}]}))
    fig_g.update_layout(height=230, margin=dict(l=10, r=10, t=50, b=0))
    st.plotly_chart(fig_g, use_container_width=True)

with b2:
    st.write(f"📊 **전북 시군별 1시간 강수 현황**")
    rain_df = pd.DataFrame([{"지역": k, "강수": v['RN1'] if v else 0} for k, v in weather_source.items()])
    st.bar_chart(rain_df.set_index("지역"), height=230)

with b3:
    if tw:
        st.metric("현재 기온", f"{tw['T1H']:.1f}°C")
        st.metric("1시간 강수량", f"{tw['RN1']:.1f} mm")
        if not is_simulation: st.caption(f"📡 API 데이터 기준: {tw['base']}")
