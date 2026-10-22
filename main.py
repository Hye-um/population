
import io
import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


# ==================================================
# 1. 페이지 설정
# ==================================================
st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 전국 고령화 단계구분도")
st.caption("전국 시군구별 인구 구조를 연도별 지도에서 비교해 보세요.")


# ==================================================
# 2. 데이터 주소
# ==================================================
POPULATION_URL = (
    "https://raw.githubusercontent.com/"
    "Hye-um/population/main/population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/"
    "first2022-cyber/contents//main/sigungu_kr.geojson"
)


# ==================================================
# 3. 코드 정리 함수
# ==================================================
def clean_code(value, length):
    """행정구역 코드를 숫자로 변환하지 않고 문자열로 정리."""
    if pd.isna(value):
        return None

    code = str(value).strip()
    code = re.sub(r"\.0$", "", code)

    if not code or not code.isdigit():
        return None

    return code.zfill(length)


def correct_sigungu_code(code):
    """과거 행정구역 코드를 현재 경계 코드에 맞게 보정."""
    if code is None:
        return None

    # 군위군: 47720 -> 27720
    if code == "47720":
        return "27720"

    # 옛 시도 코드 보정
    if code.startswith("42"):
        return "51" + code[2:]

    if code.startswith("45"):
        return "52" + code[2:]

    return code


def get_age_number(column):
    """계_0세 같은 열에서 나이 숫자를 추출."""
    match = re.fullmatch(r"계_(\d+)세", str(column))
    if match:
        return int(match.group(1))

    if str(column) == "계_100세 이상":
        return 100

    return None


# ==================================================
# 4. 인구 및 경계 데이터 불러오기
# ==================================================
@st.cache_data(ttl=3600, show_spinner="인구 데이터와 행정구역 지도를 불러오는 중...")
def load_data():
    # 인구 ZIP 파일 다운로드
    response = requests.get(POPULATION_URL, timeout=120)
    response.raise_for_status()

    population = pd.read_csv(
        io.BytesIO(response.content),
        compression="zip",
        low_memory=False,
    )

    population.columns = population.columns.astype(str).str.strip()

    required_columns = {"연도", "코드"}
    missing_columns = required_columns - set(population.columns)

    if missing_columns:
        raise ValueError(
            f"인구 데이터에 필요한 열이 없습니다: {', '.join(missing_columns)}"
        )

    population["연도"] = pd.to_numeric(
        population["연도"], errors="coerce"
    )

    # 연도와 코드는 문자열로 관리
    population["코드"] = population["코드"].apply(
        lambda x: clean_code(x, 10)
    )

    # 나이별 총계 열
    total_cols = [
        col for col in population.columns
        if col.startswith("계_")
    ]

    if not total_cols:
        raise ValueError("'계_'로 시작하는 나이별 인구 열을 찾을 수 없습니다.")

    # 숫자로 변환
    for col in total_cols:
        population[col] = pd.to_numeric(
            population[col], errors="coerce"
        ).fillna(0)

    # 65세 이상 열: 계_65세부터 계_100세 이상
    elderly_cols = [
        col for col in total_cols
        if (
            get_age_number(col) is not None
            and get_age_number(col) >= 65
        )
    ]

    # 유소년 열: 계_0세부터 계_14세
    youth_cols = [
        col for col in total_cols
        if (
            get_age_number(col) is not None
            and 0 <= get_age_number(col) <= 14
        )
    ]

    if not elderly_cols:
        raise ValueError("65세 이상 인구 열을 찾을 수 없습니다.")

    if not youth_cols:
        raise ValueError("0~14세 인구 열을 찾을 수 없습니다.")

    # GeoJSON 다운로드
    geo_response = requests.get(GEOJSON_URL, timeout=60)
    geo_response.raise_for_status()
    geojson = geo_response.json()

    if geojson.get("type") != "FeatureCollection":
        raise ValueError("행정구역 파일이 올바른 GeoJSON 형식이 아닙니다.")

    # GeoJSON 코드 및 속성 정리
    valid_features = []

    for feature in geojson.get("features", []):
        properties = feature.get("properties", {})

        code = clean_code(properties.get("코드"), 5)

        if code is None:
            continue

        properties["코드"] = code
        feature["properties"] = properties
        valid_features.append(feature)

    if not valid_features:
        raise ValueError("GeoJSON에서 유효한 시군구 코드를 찾을 수 없습니다.")

    geojson["features"] = valid_features

    # 시도 선택 목록 생성
    provinces = sorted({
        str(f["properties"].get("시도", "")).strip()
        for f in valid_features
        if str(f["properties"].get("시도", "")).strip()
    })

    # 모든 연도별 자료를 시군구 단위로 합산
    yearly_results = []

    for year in sorted(population["연도"].dropna().unique()):
        year_df = population[population["연도"] == year].copy()

        year_df = year_df.dropna(subset=["코드"])

        # 읍면동 코드 앞 5자리로 시군구 코드 생성 후 보정
        year_df["시군구코드"] = year_df["코드"].str[:5].apply(
            correct_sigungu_code
        )

        year_df["전체인구"] = year_df[total_cols].sum(axis=1)
        year_df["65세이상인구"] = year_df[elderly_cols].sum(axis=1)
        year_df["유소년인구"] = year_df[youth_cols].sum(axis=1)

        grouped = (
            year_df.groupby("시군구코드", as_index=False)
            .agg(
                전체인구=("전체인구", "sum"),
                65세이상인구=("65세이상인구", "sum"),
                유소년인구=("유소년인구", "sum"),
            )
        )

        grouped["연도"] = int(year)

        grouped["고령화율"] = (
            grouped["65세이상인구"]
            .div(grouped["전체인구"].where(grouped["전체인구"] > 0))
            * 100
        )

        grouped["유소년비율"] = (
            grouped["유소년인구"]
            .div(grouped["전체인구"].where(grouped["전체인구"] > 0))
            * 100
        )

        yearly_results.append(grouped)

    all_stats = pd.concat(yearly_results, ignore_index=True)

    return all_stats, geojson, provinces


# ==================================================
# 5. 지도 색상 구간
# ==================================================
def make_step_colorscale(boundaries, colors, maximum):
    """
    지정한 경계값에서 색이 단계적으로 바뀌는 색상표.
    boundaries 예: [19, 23, 28, 38]
    """
    scale = [[0.0, colors[0]]]

    for index, boundary in enumerate(boundaries):
        position = boundary / maximum
        scale.append([position, colors[index]])
        scale.append([position, colors[index + 1]])

    scale.append([1.0, colors[-1]])
    return scale


# ==================================================
# 6. 앱 실행
# ==================================================
try:
    all_stats, geojson, provinces = load_data()

    available_years = sorted(all_stats["연도"].unique())

    if not available_years:
        st.error("선택할 수 있는 연도 자료가 없습니다.")
        st.stop()

    # ----------------------------------------------
    # 입력 컨트롤
    # ----------------------------------------------
    st.subheader("🔎 지도 설정")

    control1, control2, control3 = st.columns([1.2, 1, 1.4])

    with control1:
        selected_year = st.slider(
            "연도 선택",
            min_value=int(min(available_years)),
            max_value=int(max(available_years)),
            value=int(max(available_years)),
            step=1,
        )

    with control2:
        indicator = st.selectbox(
            "표시할 지표",
            ["고령화율 (65세 이상)", "유소년 비율 (0~14세)"],
        )

    with control3:
        selected_province = st.selectbox(
            "표시할 시도",
            ["전국"] + provinces,
        )

    # 선택 연도 데이터
    year_stats = all_stats[
        all_stats["연도"] == selected_year
    ].copy()

    # ----------------------------------------------
    # 지도 경계 필터
    # ----------------------------------------------
    selected_features = []

    for feature in geojson["features"]:
        province = str(
            feature["properties"].get("시도", "")
        ).strip()

        if selected_province == "전국" or province == selected_province:
            selected_features.append(feature)

    selected_geojson = {
        "type": "FeatureCollection",
        "features": selected_features,
    }

    # ----------------------------------------------
    # 경계 코드 기준으로 결합
    # ----------------------------------------------
    boundary_codes = [
        f["properties"]["코드"]
        for f in selected_features
    ]

    year_stats["시군구코드"] = year_stats["시군구코드"].astype(str)

    map_df = pd.DataFrame({"시군구코드": boundary_codes})

    map_df = map_df.merge(
        year_stats,
        left_on="시군구코드",
        right_on="시군구코드",
        how="left",
    )

    # 경계 속성의 이름을 사용
    name_by_code = {
        f["properties"]["코드"]: f["properties"].get(
            "시군구", "이름 없음"
        )
        for f in selected_features
    }

    map_df["시군구명"] = map_df["시군구코드"].map(name_by_code)

    # 지표 선택
    if indicator == "고령화율 (65세 이상)":
        metric_column = "고령화율"
        metric_label = "고령화율"
        boundaries = [19, 23, 28, 38]
        colors = [
            "#fff7bc",
            "#fec44f",
            "#fe9929",
            "#ec7014",
            "#7f2704",
        ]
        maximum = 50
    else:
        metric_column = "유소년비율"
        metric_label = "유소년 비율"
        boundaries = [5, 8, 11, 14]
        colors = [
            "#f7fbff",
            "#c6dbef",
            "#6baed6",
            "#2171b5",
            "#08306b",
        ]
        maximum = 20

    # 선택 지표 열을 숫자로 정리
    map_df[metric_column] = pd.to_numeric(
        map_df[metric_column], errors="coerce"
    )

    matched_df = map_df.dropna(subset=[metric_column]).copy()
    unmatched_df = map_df[map_df[metric_column].isna()].copy()

    # ----------------------------------------------
    # 상단 지표 카드
    # ----------------------------------------------
    nationwide_stats = all_stats[
        all_stats["연도"] == selected_year
    ]

    nationwide_population = nationwide_stats["전체인구"].sum()
    nationwide_elderly = nationwide_stats["65세이상인구"].sum()
    nationwide_youth = nationwide_stats["유소년인구"].sum()

    nationwide_aging_rate = (
        nationwide_elderly / nationwide_population * 100
        if nationwide_population > 0 else 0
    )

    nationwide_youth_rate = (
        nationwide_youth / nationwide_population * 100
        if nationwide_population > 0 else 0
    )

    if metric_column == "고령화율":
        national_value = nationwide_aging_rate
    else:
        national_value = nationwide_youth_rate

    if not matched_df.empty:
        highest_row = matched_df.loc[
            matched_df[metric_column].idxmax()
        ]
        lowest_row = matched_df.loc[
            matched_df[metric_column].idxmin()
        ]

        highest_text = (
            f"{highest_row['시군구명']} · "
            f"{highest_row[metric_column]:.2f}%"
        )
        lowest_text = (
            f"{lowest_row['시군구명']} · "
            f"{lowest_row[metric_column]:.2f}%"
        )
    else:
        highest_text = "자료 없음"
        lowest_text = "자료 없음"

    card1, card2, card3 = st.columns(3)

    card1.metric(
        f"전국 {metric_label}",
        f"{national_value:.2f}%",
    )
    card2.metric(
        f"가장 높은 시군구 · {selected_province}",
        highest_text,
    )
    card3.metric(
        f"가장 낮은 시군구 · {selected_province}",
        lowest_text,
    )

    st.caption(
        f"{selected_year}년 기준 · "
        f"최고·최저 시군구는 현재 선택한 지도 범위에서 계산합니다."
    )

    # ----------------------------------------------
    # 단계구분도
    # ----------------------------------------------
    fig = go.Figure()

    # 자료가 연결되지 않은 지역은 회색으로 표시
    if not unmatched_df.empty:
        fig.add_trace(
            go.Choropleth(
                geojson=selected_geojson,
                featureidkey="properties.코드",
                locations=unmatched_df["시군구코드"],
                z=[1] * len(unmatched_df),
                zmin=0,
                zmax=1,
                colorscale=[
                    [0, "#bdbdbd"],
                    [1, "#bdbdbd"],
                ],
                showscale=False,
                marker_line_color="white",
                marker_line_width=0.4,
                customdata=unmatched_df[["시군구명"]].to_numpy(),
                hovertemplate=(
                    "%{customdata[0]}<br>"
                    "자료 연결 안 됨"
                    "<extra></extra>"
                ),
            )
        )

    # 자료가 연결된 지역은 선택한 지표에 따라 색칠
    if not matched_df.empty:
        fig.add_trace(
            go.Choropleth(
                geojson=selected_geojson,
                featureidkey="properties.코드",
                locations=matched_df["시군구코드"],
                z=matched_df[metric_column],
                zmin=0,
                zmax=maximum,
                colorscale=make_step_colorscale(
                    boundaries, colors, maximum
                ),
                colorbar={
                    "title": f"{metric_label} (%)",
                    "tickvals": boundaries,
                    "ticktext": [f"{x}%" for x in boundaries],
                    "ticks": "outside",
                },
                marker_line_color="white",
                marker_line_width=0.4,
                customdata=matched_df[
                    ["시군구명"]
                ].to_numpy(),
                hovertemplate=(
                    "%{customdata[0]}<br>"
                    f"{metric_label}: "
                    "%{z:.2f}%"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_geos(
        visible=False,
        showcountries=False,
        showcoastlines=False,
        showland=False,
        showframe=False,
        fitbounds="locations",
        bgcolor="white",
    )

    fig.update_layout(
        title={
            "text": (
                f"{selected_year}년 {selected_province} "
                f"{metric_label} 단계구분도"
            ),
            "x": 0.5,
            "xanchor": "center",
        },
        height=760,
        margin={"l": 0, "r": 0, "t": 65, "b": 0},
        paper_bgcolor="white",
        geo_bgcolor="white",
        legend={"orientation": "h"},
    )

    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------
    # 안내 문구
    # ----------------------------------------------
    if not unmatched_df.empty:
        unmatched_names = unmatched_df["시군구명"].dropna().tolist()

        st.warning(
            f"회색 지역 {len(unmatched_df)}곳은 인구 데이터와 "
            "경계 파일의 코드가 일치하지 않아 지표를 표시하지 못했습니다. "
            "행정구역 개편 또는 자료 누락이 원인일 수 있습니다."
        )

        with st.expander("코드가 일치하지 않은 지역 확인"):
            st.write(", ".join(unmatched_names))

    st.caption(
        "색상 구간은 연도가 바뀌어도 고정됩니다. "
        "회색은 해당 연도 인구 자료와 경계 코드를 연결하지 못한 지역입니다."
    )

    # ----------------------------------------------
    # 상세 표
    # ----------------------------------------------
    st.subheader("📊 시군구별 지표")

    table_df = map_df[
        [
            "시군구코드",
            "시군구명",
            "전체인구",
            "65세이상인구",
            "유소년인구",
            "고령화율",
            "유소년비율",
        ]
    ].copy()

    table_df = table_df.rename(
        columns={
            "시군구코드": "코드",
            "시군구명": "시군구",
            "전체인구": "전체 인구",
            "65세이상인구": "65세 이상 인구",
            "유소년인구": "0~14세 인구",
            "고령화율": "고령화율(%)",
            "유소년비율": "유소년 비율(%)",
        }
    )

    table_df["고령화율(%)"] = table_df["고령화율(%)"].round(2)
    table_df["유소년 비율(%)"] = table_df["유소년 비율(%)"].round(2)

    sort_column = (
        "고령화율(%)"
        if metric_column == "고령화율"
        else "유소년 비율(%)"
    )

    table_df = table_df.sort_values(
        sort_column,
        ascending=False,
        na_position="last",
    )

    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
    )

    csv_data = table_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "📥 시군구별 자료 CSV 다운로드",
        data=csv_data,
        file_name=f"시군구별_인구지표_{selected_year}.csv",
        mime="text/csv",
    )

    st.caption(
        "자료: 제공된 읍·면·동 인구 데이터 및 시군구 경계 GeoJSON"
    )

except Exception as error:
    st.error("앱을 실행하는 중 오류가 발생했습니다.")
    st.exception(error)
