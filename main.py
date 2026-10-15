
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide"
)

# 따뜻한 색감의 디자인
st.markdown("""
<style>
.stApp {
    background-color: #FFF9F2;
}
h1, h2, h3 {
    color: #70452F;
}
.intro-box {
    background-color: #F6E7D7;
    padding: 18px;
    border-radius: 14px;
    color: #70452F;
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. CSV 데이터 불러오기
# ==========================================
DATA_URL = (
    "https://raw.githubusercontent.com/Hye-um/population/"
    "main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="인구 데이터를 불러오는 중이에요...")
def load_data():
    # 일반 CSV 파일을 읽어요.
    # 압축파일 옵션인 compression="zip"은 사용하지 않아요.
    df = pd.read_csv(
        DATA_URL,
        encoding="utf-8-sig"
    )

    # 열 이름에 불필요한 공백이 있으면 제거해요.
    df.columns = df.columns.astype(str).str.strip()

    # 연도는 숫자로 변환해요.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 지역 이름이 비어 있는 경우를 처리해요.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # 0세부터 100세 이상까지 남녀 인구 열을 만들어요.
    age_columns = [
        f"{gender}_{age}세"
        for age in range(100)
        for gender in ["남", "여"]
    ]
    age_columns += ["남_100세 이상", "여_100세 이상"]

    # 인구 열을 숫자로 바꿔요.
    for col in age_columns:
        if col not in df.columns:
            df[col] = 0
        else:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce"
            ).fillna(0)

    return df


try:
    df = load_data()
except Exception as e:
    st.error("데이터를 불러오지 못했어요.")
    st.warning(
        "일반 CSV 주소가 맞는지 확인해 주세요. "
        "GitHub 주소가 ZIP 파일을 반환한다면 CSV 주소가 필요해요."
    )
    st.exception(e)
    st.stop()


# ==========================================
# 3. 가장 최신 연도 선택
# ==========================================
latest_year = int(df["연도"].max())
latest_df = df[df["연도"] == latest_year].copy()

if latest_df.empty:
    st.error("최신 연도 데이터가 없어요.")
    st.stop()


# ==========================================
# 4. 제목과 안내
# ==========================================
st.title("🏘️ 동네별 인구 피라미드")

st.markdown(f"""
<div class="intro-box">
<strong>우리 동네에는 어떤 연령대가 많이 살고 있을까요?</strong><br>
시도 → 시군구 → 동을 선택하면 남녀별 인구 분포를 확인할 수 있어요.<br>
현재 표시하는 최신 연도: <strong>{latest_year}년</strong>
</div>
""", unsafe_allow_html=True)

st.write("")


# ==========================================
# 5. 지역 선택 드롭다운 3개
# ==========================================
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째: 시도
sido_list = sorted(
    x for x in latest_df["시도"].unique() if x
)

if not sido_list:
    st.error("시도 데이터가 없어요.")
    st.stop()

with col1:
    selected_sido = st.selectbox(
        "① 시도",
        sido_list,
        key="sido"
    )

# 두 번째: 시군구
sido_df = latest_df[
    latest_df["시도"] == selected_sido
]

sigungu_list = sorted(
    x for x in sido_df["시군구"].unique() if x
)

if not sigungu_list:
    st.warning("시군구 데이터가 없어요.")
    st.stop()

with col2:
    selected_sigungu = st.selectbox(
        "② 시군구",
        sigungu_list,
        key="sigungu"
    )

# 세 번째: 동
sigungu_df = sido_df[
    sido_df["시군구"] == selected_sigungu
]

dong_list = sorted(
    x for x in sigungu_df["동"].unique() if x
)

if not dong_list:
    st.warning("동 데이터가 없어요.")
    st.stop()

with col3:
    selected_dong = st.selectbox(
        "③ 동",
        dong_list,
        key="dong"
    )


# ==========================================
# 6. 선택한 동의 인구 계산
# ==========================================
selected_rows = sigungu_df[
    sigungu_df["동"] == selected_dong
]

age_labels = [
    f"{age}세" for age in range(100)
] + ["100세 이상"]

male_columns = [
    f"남_{age}세" for age in range(100)
] + ["남_100세 이상"]

female_columns = [
    f"여_{age}세" for age in range(100)
] + ["여_100세 이상"]

# 같은 지역에 행이 여러 개 있으면 인구를 합산해요.
male_population = (
    selected_rows[male_columns]
    .sum(axis=0)
    .to_numpy(dtype=float)
)

female_population = (
    selected_rows[female_columns]
    .sum(axis=0)
    .to_numpy(dtype=float)
)

# 남성은 왼쪽에 그리기 위해 음수로 바꿔요.
male_negative = -male_population

total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# ==========================================
# 7. 인구 요약
# ==========================================
st.divider()

st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)

m1, m2, m3 = st.columns(3)

m1.metric("전체 인구", f"{total_population:,}명")
m2.metric("남성 인구", f"{total_male:,}명")
m3.metric("여성 인구", f"{total_female:,}명")


# ==========================================
# 8. 인구 피라미드
# ==========================================
fig = go.Figure()

# 남성: 음수이므로 왼쪽
fig.add_trace(go.Bar(
    y=age_labels,
    x=male_negative,
    name="남성",
    orientation="h",
    marker_color="#7297B8",
    customdata=male_population,
    hovertemplate=(
        "나이: %{y}<br>"
        "남성 인구: %{customdata:,.0f}명"
        "<extra></extra>"
    )
))

# 여성: 양수이므로 오른쪽
fig.add_trace(go.Bar(
    y=age_labels,
    x=female_population,
    name="여성",
    orientation="h",
    marker_color="#D98F87",
    hovertemplate=(
        "나이: %{y}<br>"
        "여성 인구: %{x:,.0f}명"
        "<extra></extra>"
    )
))

# 좌우 눈금 범위를 대칭으로 만들어요.
max_population = max(
    float(male_population.max()),
    float(female_population.max()),
    1.0
)

axis_limit = max_population * 1.15
tick_step = max(1, int(np.ceil(axis_limit / 5)))
tick_limit = int(np.ceil(axis_limit / tick_step) * tick_step)

tick_values = list(
    range(-tick_limit, tick_limit + tick_step, tick_step)
)
tick_text = [
    f"{abs(v):,}" for v in tick_values
]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 남녀 인구",
        "x": 0.5,
        "xanchor": "center"
    },
    barmode="relative",
    bargap=0.12,
    height=1050,
    paper_bgcolor="#FFF9F2",
    plot_bgcolor="#FFF9F2",
    font={
        "family": "Arial, sans-serif",
        "color": "#5D4638",
        "size": 12
    },
    legend={
        "title": "성별",
        "orientation": "h",
        "y": 1.02,
        "x": 0.5,
        "xanchor": "center"
    },
    xaxis={
        "title": "인구수 (명)",
        "range": [-axis_limit, axis_limit],
        "tickmode": "array",
        "tickvals": tick_values,
        "ticktext": tick_text,
        "zeroline": True,
        "zerolinecolor": "#A58B76",
        "zerolinewidth": 2,
        "gridcolor": "#EADFD3"
    },
    yaxis={
        "title": "나이",
        # 나이 순서를 직접 고정해요.
        # 아래쪽 0세, 위쪽 100세 이상이 되도록 설정해요.
        "categoryorder": "array",
        "categoryarray": age_labels,
        "gridcolor": "#F0E5DA",
        "automargin": True
    },
    margin={
        "l": 85,
        "r": 35,
        "t": 100,
        "b": 70
    }
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={"displayModeBar": True}
)


# ==========================================
# 9. 그래프 읽는 방법
# ==========================================
st.divider()
st.subheader("💡 그래프 읽는 방법")

left, right = st.columns(2)

with left:
    st.markdown("""
    **🔵 왼쪽은 남성**

    남성 인구를 음수로 표시했어요.
    막대가 왼쪽으로 길수록 해당 연령의 남성 인구가 많아요.
    """)

with right:
    st.markdown("""
    **🌸 오른쪽은 여성**

    여성 인구를 양수로 표시했어요.
    막대가 오른쪽으로 길수록 해당 연령의 여성 인구가 많아요.
    """)

st.caption(
    f"자료: GitHub 인구 데이터 | 기준 연도: {latest_year}년"
)
