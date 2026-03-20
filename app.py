# (상단 설정 및 데이터 정의 부분은 기존과 동일)

# --- [2. 핵심 엔진: 지역별 보정 계수 추가] ---
# 지형적 특성에 따른 가중치 (1.0 기준)
LOCATION_MODIFIERS = {
    "군산": 1.05, "부안": 1.03, "고창": 1.02, # 서해안 (수증기 유입 관문)
    "전주": 1.0, "익산": 1.0, "김제": 1.0, "완주": 0.98, # 내륙 평야
    "정읍": 0.97, "임실": 0.95, "순창": 0.94, # 중남부 내륙
    "무주": 0.92, "진안": 0.91, "장수": 0.90  # 동부 산악 (사례에 따라 상승 기류 보정 가능)
}

def get_hri_21(pwat, cape, v850, loc_name, updiv=15.0, ki=32.0):
    fuel = (pwat * ki) / 2300 * 30
    explosive = (cape / 4000) * 35
    pump = (v850 * updiv) / 750 * 35
    
    # 지역별 보정 계수 적용 (지형 특성 반영)
    modifier = LOCATION_MODIFIERS.get(loc_name, 1.0)
    score = (fuel + explosive + pump) * 1.02 * modifier
    return min(100.0, round(score, 1))

# --- [3. 메인 UI 및 시뮬레이션 로직 수정] ---
# ... (모드 선택 부분 동일) ...

if mode == "실시간 감시":
    weather_source = {name: fetch_weather(info['nx'], info['ny']) for name, info in LOCATIONS.items()}
else:
    sim_case = st.selectbox("📅 시뮬레이션 사례 선택", list(PAST_RECORDS.keys()))
    cd = PAST_RECORDS[sim_case]
    
    # 핵심 수정: 지역별로 미세한 랜덤 변동과 지형 보정 적용
    weather_source = {}
    for name in LOCATIONS.keys():
        # 사례 대푯값에 지역별 미세 변동(±5%) 추가하여 리얼리티 부여
        rand_var = 1 + (hash(name) % 10 - 5) / 100 
        weather_source[name] = {
            'T1H': (cd['cape'] * rand_var) / 100,
            'REH': ((cd['pwat'] * rand_var) - 10) / 0.65,
            'WSD': (cd['v850'] * rand_var) / 2.5,
            'RN1': 100.0 * rand_var,
            'sim': True, 'up': cd['updiv'], 'ki': cd['ki']
        }
    with st.expander("🖼️ 당시 지상 일기도 확인"):
        st.image(cd['img'], use_container_width=True)

# --- [4. 지도 및 순위표 출력 부분] ---
m1, m2 = st.columns(2)
with m1:
    m = folium.Map(location=[35.7, 127.1], zoom_start=8, tiles="cartodbpositron")
    for name, info in LOCATIONS.items():
        w = weather_source[name]
        if w:
            # 수정된 get_hri_21 함수 호출 (지역명 name 전달)
            sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, name, w.get('up', 15.0), w.get('ki', 32.0))
            folium.CircleMarker([info['lat'], info['lon']], radius=10, color="red" if sc>=95 else "orange" if sc>=80 else "green", fill=True, popup=f"{name}: {sc}").add_to(m)
    st_folium(m, width="100%", height=350, returned_objects=[])

with m2:
    summary = []
    for n in LOCATIONS.keys():
        w = weather_source[n]
        # 수정된 get_hri_21 함수 호출 (지역명 n 전달)
        sc = get_hri_21(w['REH']*0.65+10, w['T1H']*100, w['WSD']*2.5, n, w.get('up', 15.0), w.get('ki', 32.0)) if w else 0
        summary.append({"지역": n, "HRI": sc, "상태": "🔴 위험" if sc>=95 else "🟠 주의" if sc>=80 else "🟢 정상"})
    st.dataframe(pd.DataFrame(summary).sort_values("HRI", ascending=False), hide_index=True, use_container_width=True, height=350)
