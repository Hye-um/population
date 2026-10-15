
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==================================================
# 1. 기본 설정
# ==================================================
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide"
)

# 따뜻한 색감의 화면 디자인
st.markdown("""
<style>
    .stApp {
        background-color: #FFF9F2;
    }

    h1, h2, h3 {
        color: #70452F;
    }

    p, label, .stMarkdown {
        color: #5D4638;
    }

    div[data-baseweb="select"] {
        background-color: #FFFFFF;
    }

    .intro-box {
        background-color: #F6E7D7;
        padding: 18px 22px;
        border-radius: 14px;
        margin-bottom: 20px;
        color: #70452F;
    }
</style>
""", unsafe_allow_html=True)


# ==================================================
# 2. 데이터 불러오기
# ==================================================
DATA_URL = (
    "https://raw.githubusercontent.com/Hye-um/population/"
    "main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="전국 인구 데이터를 불러오는 중이에요...")
def load_data():
    # GitHub의 ZIP 파일을 pandas로 직접 읽어요.
    # ZIP 안에 CSV 파일이 하나 들어 있어야 해요.
    df = pd.read_csv(
        DATA_URL,
        compression="zip",
        encoding="utf-8-sig"
    )

    # 열 이름 앞뒤에 혹시 모를 공백이 있으면 제거해요.
    df.columns = df.columns.astype(str).str.strip()

    # 연도를 숫자로 바꿔서 최신 연도를 찾기 쉽게 만들어요.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 지역 이름이 비어 있으면 빈 문자열로 처리해요.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # 인구수 열은 숫자로 변환해요.
    # 쉼표가 들어 있는 문자열도 처리할 수 있어요.
    age_columns = [
        f"{gender}_{age}세"
        for age in range(100)
        for gender in ["남", "여"]
    ]
    age_columns += ["남_100세 이상", "여_100세 이상"]

    for col in age_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce"
            ).fillna(0)
        else:
            # 일부 연령 열이 없더라도 앱이 멈추지 않게 해요.
            df[col] = 0

    return df


try:
    df = load_data()
except Exception as e:
    st.error("인구 데이터를 불러오지 못했어요.")
    st.info(
        "인터넷 연결과 GitHub ZIP 주소를 확인해 주세요. "
        "ZIP 안의 CSV 파일과 열 이름도 확인해 주세요."
    )
    st.exception(e)
    st.stop()


# ==================================================
# 3. 가장 최신 연도만 선택
# ==================================================
latest_year = int(df["연도"].max())
latest_df = df[df["연도"] == latest_year].copy()

if latest_df.empty:
    st.error("최신 연도의 인구 데이터가 없어요.")
    st.stop()


# ==================================================
# 4. 화면 제목과 안내
# ==================================================
st.title("🏘️ 동네별 인구 피라미드")

st.markdown(f"""
<div class="intro-box">
    <strong>우리 동네에는 어떤 연령대가 많이 살고 있을까요?</strong><br>
    시도, 시군구, 동을 차례로 선택하면 남녀별 연령 분포를
    인구 피라미드로 확인할 수 있어요.<br>
    현재 데이터의 최신 연도는 <strong>{latest_year}년</strong>이에요.
</div>
""", unsafe_allow_html=True)


# ==================================================
# 5. 시도 → 시군구 → 동 드롭다운
# ==================================================
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째 드롭다운: 시도
sido_list = sorted([
    x for x in latest_df["시도"].unique()
    if x
])

if not sido_list:
    st.error("선택할 수 있는 시도 데이터가 없어요.")
    st.stop()

with col1:
    selected_sido = st.selectbox(
        "① 시도",
        options=sido_list,
        key="selected_sido"
    )

# 선택한 시도에 해당하는 시군구만 추려요.
sido_df = latest_df[
    latest_df["시도"] == selected_sido
].copy()

sigungu_list = sorted([
    x for x in sido_df["시군구"].unique()
    if x
])

if not sigungu_list:
    st.warning("선택한 시도에 시군구 데이터가 없어요.")
    st.stop()

with col2:
    selected_sigungu = st.selectbox(
        "② 시군구",
        options=sigungu_list,
        key="selected_sigungu"
    )

# 선택한 시군구에 해당하는 동만 추려요.
sigungu_df = sido_df[
    sido_df["시군구"] == selected_sigungu
].copy()

dong_list = sorted([
    x for x in sigungu_df["동"].unique()
    if x
])

if not dong_list:
    st.warning("선택한 시군구에 동 데이터가 없어요.")
    st.stop()

with col3:
    selected_dong = st.selectbox(
        "③ 동",
        options=dong_list,
        key="selected_dong"
    )


# ==================================================
# 6. 선택한 동네의 인구 데이터 찾기
# ==================================================
selected_rows = sigungu_df[
    sigungu_df["동"] == selected_dong
].copy()

if selected_rows.empty:
    st.warning("선택한 동네의 인구 자료가 없어요.")
    st.stop()

# 같은 지역에 행이 여러 개라면 연령별 인구를 합산해요.
age_labels = [
    f"{age}세" for age in range(100)
] + ["100세 이상"]

male_columns = [
    f"남_{age}세" for age in range(100)
] + ["남_100세 이상"]

female_columns = [
    f"여_{age}세" for age in range(100)
] + ["여_100세 이상"]

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

# 남성은 왼쪽에 표시하기 위해 음수로 바꿔요.
male_negative = -male_population

total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# ==================================================
# 7. 주요 인구 정보
# ==================================================
st.markdown("---")
st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong} 인구 현황"
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "전체 인구",
    f"{total_population:,}명"
)

metric2.metric(
    "남성 인구",
    f"{total_male:,}명"
)

metric3.metric(
    "여성 인구",
    f"{total_female:,}명"
)


# ==================================================
# 8. 인구 피라미드 가로 막대그래프
# ==================================================
fig = go.Figure()

# 남성: 음수이므로 가운데 기준선의 왼쪽에 나타나요.
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=male_negative,
        name="남성",
        orientation="h",
        marker_color="#7297B8",
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,.0f}명"
            "<extra></extra>"
        ),
        customdata=male_population
    )
)

# 여성: 양수이므로 가운데 기준선의 오른쪽에 나타나요.
fig.add_trace(
    go.Bar(
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
    )
)

# 좌우 축 범위를 대칭으로 맞추면 성별 비교가 쉬워요.
max_population = max(
    float(male_population.max()),
    float(female_population.max()),
    1
)
axis_limit = max_population * 1.15

# 좌우 축의 눈금은 음수 대신 양수 인구수로 보여 줘요.
tick_step = max(1, int(np.ceil(axis_limit / 5)))
tick_limit = int(np.ceil(axis_limit / tick_step) * tick_step)

tick_values = list(
    range(-tick_limit, tick_limit + tick_step, tick_step)
)
tick_text = [
    f"{abs(value):,}" for value in tick_values
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
        # 중요: 0세부터 100세 이상까지 순서를 직접 지정해요.
        # 이 순서가 아래쪽 0세 → 위쪽 100세 이상이 되도록
        # 카테고리 목록을 고정합니다.
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

# 그래프를 화면에 표시해요.
st.plotly_chart(
    fig,
    use_container_width=True,
    config={"displayModeBar": True}
)


# ==================================================
# 9. 그래프 읽는 방법
# ==================================================
st.markdown("---")
st.subheader("💡 그래프 읽는 방법")

guide1, guide2 = st.columns(2)

with guide1:
    st.markdown("""
    **🔵 왼쪽 — 남성**
    
    남성 인구는 음수로 표현해 왼쪽에 그렸어요.
    막대가 가운데에서 왼쪽으로 길수록 해당 나이의
    남성 인구가 많다는 뜻이에요.
    """)

with guide2:
    st.markdown("""
    **🌸 오른쪽 — 여성**
    
    여성 인구는 양수로 표현해 오른쪽에 그렸어요.
    막대가 가운데에서 오른쪽으로 길수록 해당 나이의
    여성 인구가 많다는 뜻이에요.
    """)

st.caption(
    f"자료: GitHub 인구 데이터 | 표시 연도: {latest_year}년"
)
