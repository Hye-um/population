
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏡",
    layout="wide",
)

# 따뜻한 색감의 화면 디자인
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFF9F2;
    }
    h1, h2, h3 {
        color: #754C38;
    }
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #F0D9C5;
        border-radius: 12px;
        padding: 15px;
    }
    div[data-testid="stSelectbox"] label {
        color: #754C38;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# 2. 데이터 불러오기
# --------------------------------------------------
DATA_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/"
    "contents/main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="전국 인구 데이터를 불러오는 중입니다...")
def load_data():
    # pandas가 ZIP 압축 파일을 직접 읽습니다.
    df = pd.read_csv(DATA_URL, compression="zip")

    # 열 이름의 앞뒤 공백 제거
    df.columns = df.columns.astype(str).str.strip()

    # 연도 변환
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 지역 이름을 문자열로 통일
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # 나이 라벨: 0세부터 100세 이상까지
    ages = [f"{age}세" for age in range(101)]
    ages[-1] = "100세 이상"

    # 남녀 나이별 인구 열을 숫자로 변환
    for age in ages:
        for gender in ["남", "여"]:
            col = f"{gender}_{age}"

            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(
                        ",", "", regex=False
                    ),
                    errors="coerce",
                ).fillna(0)

    return df, ages


try:
    df, age_labels = load_data()
except Exception as e:
    st.error("인구 데이터를 불러오지 못했습니다.")
    st.info(
        "인터넷 연결과 CSV 주소를 확인해 주세요. "
        "데이터의 열 이름이 안내된 형식인지도 확인해 주세요."
    )
    st.exception(e)
    st.stop()


# --------------------------------------------------
# 3. 가장 최신 연도의 데이터만 선택
# --------------------------------------------------
latest_year = int(df["연도"].max())
latest_df = df[df["연도"] == latest_year].copy()

st.title("🏡 동네별 인구 피라미드")

st.markdown(
    f"우리 동네의 연령별 인구 구조를 살펴보세요. "
    f"현재 데이터 기준 최신 연도는 **{latest_year}년**입니다."
)

st.caption(
    "왼쪽은 남자 인구, 오른쪽은 여자 인구입니다. "
    "막대가 길수록 해당 연령의 인구가 많습니다."
)


# --------------------------------------------------
# 4. 시도 → 시군구 → 동 선택
# --------------------------------------------------
st.subheader("📍 우리 동네 선택")

col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(latest_df["시도"].unique().tolist())
    selected_sido = st.selectbox(
        "① 시도",
        sido_list,
        key="sido",
    )

# 선택한 시도에 해당하는 시군구만 표시
sigungu_df = latest_df[
    latest_df["시도"] == selected_sido
]

with col2:
    sigungu_list = sorted(
        sigungu_df["시군구"].unique().tolist()
    )
    selected_sigungu = st.selectbox(
        "② 시군구",
        sigungu_list,
        key="sigungu",
    )

# 선택한 시도와 시군구에 해당하는 동만 표시
dong_df = sigungu_df[
    sigungu_df["시군구"] == selected_sigungu
]

with col3:
    dong_list = sorted(
        dong_df["동"].unique().tolist()
    )
    selected_dong = st.selectbox(
        "③ 동",
        dong_list,
        key="dong",
    )


# --------------------------------------------------
# 5. 선택한 동네의 인구 데이터 계산
# --------------------------------------------------
selected_df = latest_df[
    (latest_df["시도"] == selected_sido)
    & (latest_df["시군구"] == selected_sigungu)
    & (latest_df["동"] == selected_dong)
]

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없습니다.")
    st.stop()

male_columns = [f"남_{age}" for age in age_labels]
female_columns = [f"여_{age}" for age in age_labels]

# 필요한 인구 열이 모두 존재하는지 확인
missing_columns = [
    col
    for col in male_columns + female_columns
    if col not in selected_df.columns
]

if missing_columns:
    st.error(
        "데이터에서 필요한 인구 열을 찾을 수 없습니다: "
        + ", ".join(missing_columns[:10])
    )
    st.stop()

# 같은 지역이 여러 행이면 나이별 인구를 합산
male_population = (
    selected_df[male_columns]
    .sum(axis=0)
    .to_numpy(dtype=float)
)

female_population = (
    selected_df[female_columns]
    .sum(axis=0)
    .to_numpy(dtype=float)
)

# 남녀 합계 인구를 나이별로 계산
total_by_age = male_population + female_population

total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# --------------------------------------------------
# 6. 평균연령과 고령화율 계산
# --------------------------------------------------

# 평균연령 계산
# 100세 이상은 계산 편의를 위해 100세로 간주
age_numbers = np.arange(101, dtype=float)

average_age = (
    float(np.dot(total_by_age, age_numbers) / total_population)
    if total_population > 0
    else 0.0
)

# 65세 이상 인구와 고령화율
elderly_population = float(total_by_age[65:].sum())

aging_rate = (
    elderly_population / total_population * 100
    if total_population > 0
    else 0.0
)

# 아이 인구는 0~14세로 계산
children_population = float(total_by_age[:15].sum())

children_rate = (
    children_population / total_population * 100
    if total_population > 0
    else 0.0
)

elderly_rate = aging_rate


# --------------------------------------------------
# 7. 지표 카드 3개
# --------------------------------------------------
st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        "👥 총인구",
        f"{total_population:,}명",
    )

with card2:
    st.metric(
        "🎂 평균연령",
        f"{average_age:.1f}세",
    )

with card3:
    st.metric(
        "🌳 고령화율",
        f"{aging_rate:.1f}%",
    )

    # 고령화율이 20%를 초과하면 주의 표시
    if aging_rate > 20:
        st.warning("⚠️ 고령화율 20% 초과")


# --------------------------------------------------
# 8. 인구 피라미드 그리기
# --------------------------------------------------

# 나이를 0~100의 숫자 위치로 사용합니다.
# 이렇게 하면 나이 순서를 숫자로 정확히 고정할 수 있습니다.
y_positions = list(range(101))

# 남자는 음수로 바꿔 왼쪽에 표시
male_left = -male_population

fig = go.Figure()

# 남자 인구 막대
fig.add_trace(
    go.Bar(
        y=y_positions,
        x=male_left,
        name="남자",
        orientation="h",
        marker_color="#7198C8",
        customdata=np.column_stack(
            [
                male_population,
                np.array(age_labels, dtype=object),
            ]
        ),
        hovertemplate=(
            "나이: %{customdata[1]}<br>"
            "남자 인구: %{customdata[0]:,.0f}명"
            "<extra></extra>"
        ),
    )
)

# 여자 인구 막대
fig.add_trace(
    go.Bar(
        y=y_positions,
        x=female_population,
        name="여자",
        orientation="h",
        marker_color="#E89A91",
        customdata=np.column_stack(
            [
                female_population,
                np.array(age_labels, dtype=object),
            ]
        ),
        hovertemplate=(
            "나이: %{customdata[1]}<br>"
            "여자 인구: %{customdata[0]:,.0f}명"
            "<extra></extra>"
        ),
    )
)

# 남녀 좌우 축의 크기를 같게 설정
max_population = max(
    float(male_population.max()),
    float(female_population.max()),
    1.0,
)

axis_limit = max_population * 1.12

# 가로축 눈금 계산
tick_step = max(
    1,
    int(np.ceil(axis_limit / 5)),
)

tick_end = (
    int(np.ceil(axis_limit / tick_step))
    * tick_step
)

positive_ticks = list(
    range(0, tick_end + 1, tick_step)
)

tick_values = (
    [-v for v in positive_ticks[:0:-1]]
    + positive_ticks
)

# 남자 인구는 음수여도 눈금에는 양수로 표시
tick_text = [
    f"{abs(v):,}"
    for v in tick_values
]

fig.update_layout(
    title={
        "text": (
            f"{selected_dong} 연령별 인구 피라미드 "
            f"({latest_year}년)"
        ),
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=1000,
    paper_bgcolor="#FFF9F2",
    plot_bgcolor="#FFF9F2",
    font={
        "family": (
            "Malgun Gothic, Apple SD Gothic Neo, sans-serif"
        ),
        "color": "#5D4638",
        "size": 12,
    },
    legend={
        "title": "성별",
        "orientation": "h",
        "y": 1.02,
        "x": 0.5,
        "xanchor": "center",
    },
    xaxis={
        "title": "인구 수 (명)",
        "range": [-axis_limit, axis_limit],
        "tickmode": "array",
        "tickvals": tick_values,
        "ticktext": tick_text,
        "zeroline": True,
        "zerolinewidth": 2,
        "zerolinecolor": "#BCA38E",
        "gridcolor": "#EADFD4",
    },
    yaxis={
        "title": "나이",
        # 0~100 숫자 위치를 그대로 사용합니다.
        # 범위를 뒤집지 않아 0세가 아래, 100세 이상이 위에 옵니다.
        "tickmode": "array",
        "tickvals": y_positions,
        "ticktext": age_labels,
        "range": [-0.5, 100.5],
        "dtick": 5,
        "gridcolor": "#EADFD4",
    },
    margin={
        "l": 100,
        "r": 40,
        "t": 100,
        "b": 70,
    },
)

# 그래프 표시
st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------
# 9. 동네 특징 자동 설명
# --------------------------------------------------
st.subheader("🔎 이 동네의 인구 특징")

if children_rate > elderly_rate:
    summary = (
        f"이 동네는 0~14세 인구 비율({children_rate:.1f}%)이 "
        f"65세 이상 인구 비율({elderly_rate:.1f}%)보다 높아, "
        "상대적으로 아이 인구의 비중이 큰 편입니다."
    )

elif children_rate < elderly_rate:
    summary = (
        f"이 동네는 65세 이상 인구 비율({elderly_rate:.1f}%)이 "
        f"0~14세 인구 비율({children_rate:.1f}%)보다 높아, "
        "상대적으로 어르신 인구의 비중이 큰 편입니다."
    )

else:
    summary = (
        f"이 동네는 0~14세와 65세 이상 인구 비율이 "
        f"모두 {children_rate:.1f}%로 같습니다."
    )

st.info("💬 " + summary)


# --------------------------------------------------
# 10. 그래프 읽는 방법
# --------------------------------------------------
with st.expander("💡 인구 피라미드 읽는 방법"):
    st.markdown(
        """
        - **왼쪽 파란색:** 남자 인구
        - **오른쪽 분홍색:** 여자 인구
        - **막대가 길수록:** 해당 나이의 인구가 많음
        - **세로축 아래:** 0세
        - **세로축 위:** 100세 이상
        - **평균연령:** 나이별 인구를 고려해 계산한 평균 나이
        - **고령화율:** 전체 인구 중 65세 이상 인구의 비율

        참고:
        - 평균연령 계산에서 '100세 이상'은 100세로 간주합니다.
        - 아이와 어르신 비교는 0~14세와 65세 이상 인구 비율을 기준으로 합니다.
        """
    )

st.caption(
    f"데이터 출처: [GitHub CSV 원본]({DATA_URL}) "
    f"· 기준 연도: {latest_year}년"
)
