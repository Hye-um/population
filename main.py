```python
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
    layout="wide"
)

# 따뜻한 색감의 화면 디자인
st.markdown("""
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
""", unsafe_allow_html=True)


# --------------------------------------------------
# 2. 데이터 불러오기
# --------------------------------------------------
DATA_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/"
    "contents/main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="전국 인구 데이터를 불러오는 중입니다...")
def load_data():
    # URL이 .zip으로 끝나므로 pandas가 압축을 자동으로 처리합니다.
    df = pd.read_csv(DATA_URL, compression="zip")

    # 열 이름 앞뒤에 혹시 들어 있는 공백을 제거합니다.
    df.columns = df.columns.astype(str).str.strip()

    # 연도는 숫자로 변환합니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")

    # 시도, 시군구, 동 이름은 문자열로 통일합니다.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # 나이별 남녀 인구 열을 숫자로 변환합니다.
    age_labels = [f"{age}세" for age in range(101)]
    age_labels[-1] = "100세 이상"

    for age in age_labels:
        for gender in ["남", "여"]:
            col = f"{gender}_{age}"

            if col in df.columns:
                # 쉼표가 들어간 숫자도 처리할 수 있도록 합니다.
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", "", regex=False),
                    errors="coerce"
                ).fillna(0)

    # 연도가 없는 행은 제외합니다.
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    return df, age_labels


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
    sido_list = sorted(
        latest_df["시도"].unique().tolist()
    )
    selected_sido = st.selectbox(
        "① 시도",
        sido_list,
        key="sido"
    )

# 선택한 시도에 해당하는 시군구만 보여 줍니다.
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
        key="sigungu"
    )

# 선택한 시도와 시군구에 해당하는 동만 보여 줍니다.
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
        key="dong"
    )


# --------------------------------------------------
# 5. 선택한 동네의 인구 데이터 가져오기
# --------------------------------------------------
selected_df = latest_df[
    (latest_df["시도"] == selected_sido)
    & (latest_df["시군구"] == selected_sigungu)
    & (latest_df["동"] == selected_dong)
]

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없습니다.")
    st.stop()

# 같은 지역이 여러 행으로 존재하면 나이별 인구를 합산합니다.
male_columns = [f"남_{age}" for age in age_labels]
female_columns = [f"여_{age}" for age in age_labels]

missing_columns = [
    col for col in male_columns + female_columns
    if col not in selected_df.columns
]

if missing_columns:
    st.error(
        "데이터에서 필요한 인구 열을 찾을 수 없습니다: "
        + ", ".join(missing_columns[:10])
    )
    st.stop()

male_population = (
    selected_df[male_columns].sum(axis=0).to_numpy(dtype=float)
)
female_population = (
    selected_df[female_columns].sum(axis=0).to_numpy(dtype=float)
)

# 남자는 왼쪽으로 향하도록 음수로 바꿉니다.
male_left = -male_population

# 전체 인구를 계산합니다.
total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# --------------------------------------------------
# 6. 주요 인구 정보 표시
# --------------------------------------------------
st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "전체 인구",
    f"{total_population:,}명"
)

metric2.metric(
    "남자 인구",
    f"{total_male:,}명"
)

metric3.metric(
    "여자 인구",
    f"{total_female:,}명"
)


# --------------------------------------------------
# 7. 인구 피라미드 그리기
# --------------------------------------------------
fig = go.Figure()

# 남자 인구: 음수이므로 중앙의 왼쪽에 표시됩니다.
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=male_left,
        name="남자",
        orientation="h",
        marker_color="#7198C8",
        hovertemplate=(
            "나이: %{y}<br>"
            "남자 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
        customdata=male_population
    )
)

# 여자 인구: 양수이므로 중앙의 오른쪽에 표시됩니다.
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=female_population,
        name="여자",
        orientation="h",
        marker_color="#E89A91",
        hovertemplate=(
            "나이: %{y}<br>"
            "여자 인구: %{x:,}명"
            "<extra></extra>"
        )
    )
)

# 좌우 막대 길이를 동일하게 맞춰 피라미드 모양을 비교하기 쉽게 합니다.
max_population = max(
    float(male_population.max()) if len(male_population) else 0,
    float(female_population.max()) if len(female_population) else 0,
    1
)
axis_limit = max_population * 1.12

# 음수인 남자 인구는 눈금에 절댓값을 표시합니다.
tick_step = max(1, int(np.ceil(axis_limit / 5)))
tick_end = int(np.ceil(axis_limit / tick_step)) * tick_step
tick_values_positive = list(range(0, tick_end + 1, tick_step))
tick_values = [-v for v in tick_values_positive[::-1]] + [
    v for v in tick_values_positive if v != 0
]
tick_text = [f"{abs(v):,}" for v in tick_values]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 인구 피라미드 ({latest_year}년)",
        "x": 0.5,
        "xanchor": "center"
    },
    barmode="overlay",
    bargap=0.12,
    height=1000,
    paper_bgcolor="#FFF9F2",
    plot_bgcolor="#FFF9F2",
    font={
        "family": "Malgun Gothic, Apple SD Gothic Neo, sans-serif",
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
        "title": "인구 수 (명)",
        "range": [-axis_limit, axis_limit],
        "tickmode": "array",
        "tickvals": tick_values,
        "ticktext": tick_text,
        "zeroline": True,
        "zerolinewidth": 2,
        "zerolinecolor": "#BCA38E",
        "gridcolor": "#EADFD4"
    },
    yaxis={
        "title": "나이",
        # 나이 라벨을 0세부터 100세 이상까지 직접 고정합니다.
        # categoryorder='array'로 숫자나 가나다순 자동 정렬을 막습니다.
        "categoryorder": "array",
        "categoryarray": age_labels,
        # 이 옵션은 사용하지 않습니다: autorange='reversed'
        # age_labels의 첫 항목이 맨 아래에 오도록 순서를 명시합니다.
        "autorange": False,
        "range": [-0.5, len(age_labels) - 0.5],
        "tickmode": "array",
        "tickvals": age_labels,
        "ticktext": age_labels,
        "gridcolor": "#EADFD4"
    },
    margin={
        "l": 100,
        "r": 40,
        "t": 100,
        "b": 70
    }
)

# 축 범위와 카테고리 순서가 의도대로 설정되었는지 확인할 수 있도록
# 마지막에 세로축 순서를 한 번 더 명시합니다.
fig.update_yaxes(
    categoryorder="array",
    categoryarray=age_labels,
    autorange=False,
    range=[-0.5, len(age_labels) - 0.5],
    tickmode="array",
    tickvals=age_labels,
    ticktext=age_labels
)

st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# 8. 그래프 읽는 방법
# --------------------------------------------------
with st.expander("💡 인구 피라미드 읽는 방법"):
    st.markdown("""
    - **왼쪽 파란색:** 남자 인구
    - **오른쪽 분홍색:** 여자 인구
    - **막대가 길수록:** 해당 나이의 인구가 많음
    - **가로축 가운데:** 인구가 0명인 기준선
    - **세로축 아래:** 0세
    - **세로축 위:** 100세 이상

    남자 인구는 그래프 왼쪽에 표시하기 위해 계산할 때 음수로 바꾸었지만,
    실제 인구 수와 화면에 표시되는 숫자는 양수입니다.
    """)

st.caption(
    f"데이터 출처: "
    f"[GitHub CSV 원본]({DATA_URL}) · 기준 연도: {latest_year}년"
)
```
