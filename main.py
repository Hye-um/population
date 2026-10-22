
import io
import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 전국 고령화 단계구분도")
st.caption("연도별 전국 시군구 인구 구조를 지도에서 비교합니다.")


POPULATION_URL = (
    "https://raw.githubusercontent.com/"
    "Hye-um/population/main/population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/"
    "first2022-cyber/contents//main/sigungu_kr.geojson"
)


def clean_code(value, length):
    if pd.isna(value):
        return None

    code = re.sub(r"\.0$", "", str(value).strip())

    if not code or not code.isdigit():
        return None

    return code.zfill(length)


def correct_sigungu_code(code):
    if code is None:
        return None

    if code == "47720":
        return "27720"

    if code.startswith("42"):
        return "51" + code[2:]

    if code.startswith("45"):
        return "52" + code[2:]

    return code


def age_number(column):
    match = re.fullmatch(r"계_(\d+)세", str(column))

    if match:
        return int(match.group(1))

    if str(column) == "계_100세 이상":
        return 100

    return None


@st.cache_data(ttl=3600)
def load_data():
    # 인구 데이터 다운로드 및 읽기
    response = requests.get(POPULATION_URL, timeout=120)
    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        compression="zip",
        low_memory=False,
    )

    df.columns = df.columns.astype(str).str.strip()

    if "연도" not in df.columns or "코드" not in df.columns:
        raise ValueError("인구 데이터에 '연도' 또는 '코드' 열이 없습니다.")

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["코드"] = df["코드"].apply(lambda x: clean_code(x, 10))

    total_cols = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    elderly_cols = [
        col for col in total_cols
        if age_number(col) is not None and age_number(col) >= 65
    ]

    youth_cols = [
        col for col in total_cols
        if age_number(col) is not None
        and 0 <= age_number(col) <= 14
    ]

    if not total_cols or not elderly_cols or not youth_cols:
        raise ValueError("나이별 인구 열을 확인할 수 없습니다.")

    for col in total_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # GeoJSON 읽기
    geo_response = requests.get(GEOJSON_URL, timeout=60)
    geo_response.raise_for_status()
    geojson = geo_response.json()

    if geojson.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON 형식이 올바르지 않습니다.")

    features = []

    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        code = clean_code(props.get("코드"), 5)

        if code is None:
            continue

        props["코드"] = code
        feature["properties"] = props
        features.append(feature)

    if not features:
        raise ValueError("GeoJSON에서 시군구 경계를 찾을 수 없습니다.")

    geojson["features"] = features

    provinces = sorted({
        str(f["properties"].get("시도", "")).strip()
        for f in features
        if str(f["properties"].get("시도", "")).strip()
    })

    # 모든 연도의 읍면동 자료를 시군구 단위로 합산
    results = []

    for year in sorted(df["연도"].dropna().unique()):
        year_df = df[df["연도"] == year].copy()
        year_df = year_df.dropna(subset=["코드"])

        year_df["시군구코드"] = (
            year_df["코드"].str[:5].apply(correct_sigungu_code)
        )

        year_df["전체인구"] = year_df[total_cols].sum(axis=1)
        year_df["65세이상인구"] = year_df[elderly_cols].sum(axis=1)
        year_df["유소년인구"] = year_df[youth_cols].sum(axis=1)

        # 딕셔너리 방식으로 합산
        grouped = (
            year_df.groupby("시군구코드", as_index=False)
            .agg({
                "전체인구": "sum",
                "65세이상인구": "sum",
                "유소년인구": "sum",
            })
        )

        grouped["연도"] = int(year)

        denominator = grouped["전체인구"].where(
            grouped["전체인구"] > 0
        )

        grouped["고령화율"] = (
            grouped["65세이상인구"] / denominator * 100
        )

        grouped["유소년비율"] = (
            grouped["유소년인구"] / denominator * 100
        )

        results.append(grouped)

    if not results:
        raise ValueError("인구 데이터가 비어 있습니다.")

    return pd.concat(results, ignore_index=True), geojson, provinces


def make_colorscale(boundaries, colors, maximum):
    scale = [[0.0, colors[0]]]

    for i, boundary in enumerate(boundaries):
        position = boundary / maximum
        scale.append([position, colors[i]])
        scale.append([position, colors[i + 1]])

    scale.append([1.0, colors[-1]])
    return scale


try:
    all_stats, geojson, provinces = load_data()

    years = sorted(all_stats["연도"].unique())

    if not years:
        st.error("사용할 수 있는 연도 자료가 없습니다.")
        st.stop()

    # 지도 설정
    st.subheader("🔎 지도 설정")

    c1, c2, c3 = st.columns(3)

    with c1:
        selected_year = st.slider(
            "연도",
            min_value=int(min(years)),
            max_value=int(max(years)),
            value=int(max(years)),
            step=1,
        )

    with c2:
        indicator = st.selectbox(
            "지표",
            ["고령화율 (65세 이상)", "유소년 비율 (0~14세)"],
        )

    with c3:
        selected_province = st.selectbox(
            "시도",
            ["전국"] + provinces,
        )

    year_stats = all_stats[
        all_stats["연도"] == selected_year
    ].copy()

    # 선택한 시도에 해당하는 경계만 선택
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

    name_by_code = {
        f["properties"]["코드"]: f["properties"].get(
            "시군구", "이름 없음"
        )
        for f in selected_features
    }

    boundary_codes = list(name_by_code.keys())

    # 코드 기준으로 경계와 인구 자료 결합
    map_df = pd.DataFrame({"시군구코드": boundary_codes})

    year_stats["시군구코드"] = year_stats[
        "시군구코드"
    ].astype(str)

    map_df = map_df.merge(
        year_stats,
        on="시군구코드",
        how="left",
    )

    map_df["시군구명"] = map_df["시군구코드"].map(name_by_code)

    # 지표에 따른 색상 구간
    if indicator == "고령화율 (65세 이상)":
        metric = "고령화율"
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
        metric = "유소년비율"
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

    map_df[metric] = pd.to_numeric(map_df[metric], errors="coerce")

    matched = map_df.dropna(subset=[metric]).copy()
    unmatched = map_df[map_df[metric].isna()].copy()

    # 지표 카드
    national_stats = all_stats[
        all_stats["연도"] == selected_year
    ]

    national_total = national_stats["전체인구"].sum()
    national_elderly = national_stats["65세이상인구"].sum()
    national_youth = national_stats["유소년인구"].sum()

    if metric == "고령화율":
        national_value = (
            national_elderly / national_total * 100
            if national_total else 0
        )
    else:
        national_value = (
            national_youth / national_total * 100
            if national_total else 0
        )

    if not matched.empty:
        highest = matched.loc[matched[metric].idxmax()]
        lowest = matched.loc[matched[metric].idxmin()]

        highest_text = (
            f"{highest['시군구명']} · {highest[metric]:.2f}%"
        )
        lowest_text = (
            f"{lowest['시군구명']} · {lowest[metric]:.2f}%"
        )
    else:
        highest_text = "자료 없음"
        lowest_text = "자료 없음"

    m1, m2, m3 = st.columns(3)

    m1.metric(f"전국 {metric_label}", f"{national_value:.2f}%")
    m2.metric("가장 높은 시군구", highest_text)
    m3.metric("가장 낮은 시군구", lowest_text)

    st.caption(
        f"{selected_year}년 기준. 최고·최저는 선택한 지도 범위 안에서 계산합니다."
    )

    # 지도 생성
    fig = go.Figure()

    # 코드 미매칭 지역은 회색
    if not unmatched.empty:
        fig.add_trace(
            go.Choropleth(
                geojson=selected_geojson,
                featureidkey="properties.코드",
                locations=unmatched["시군구코드"],
                z=[1] * len(unmatched),
                zmin=0,
                zmax=1,
                colorscale=[
                    [0, "#bdbdbd"],
                    [1, "#bdbdbd"],
                ],
                showscale=False,
                marker_line_color="white",
                marker_line_width=0.4,
                customdata=unmatched[["시군구명"]].to_numpy(),
                hovertemplate=(
                    "%{customdata[0]}<br>"
                    "자료 연결 안 됨"
                    "<extra></extra>"
                ),
            )
        )

    # 코드 매칭 지역은 지표에 따라 색칠
    if not matched.empty:
        fig.add_trace(
            go.Choropleth(
                geojson=selected_geojson,
                featureidkey="properties.코드",
                locations=matched["시군구코드"],
                z=matched[metric],
                zmin=0,
                zmax=maximum,
                colorscale=make_colorscale(
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
                customdata=matched[["시군구명"]].to_numpy(),
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
    )

    st.plotly_chart(fig, use_container_width=True)

    # 코드가 맞지 않은 지역 안내
    if not unmatched.empty:
        st.warning(
            f"회색 지역 {len(unmatched)}곳은 해당 연도 인구 데이터와 "
            "경계 파일의 코드가 일치하지 않아 색칠하지 못했습니다."
        )

        with st.expander("연결되지 않은 지역 확인"):
            st.write(", ".join(unmatched["시군구명"].dropna().tolist()))

    st.caption(
        "고령화율 색 구간: 19 · 23 · 28 · 38%. "
        "유소년 비율 색 구간: 5 · 8 · 11 · 14%. "
        "연도를 바꿔도 각 지표의 구간은 고정됩니다."
    )

    # 상세 표
    st.subheader("📊 시군구별 인구 지표")

    table = map_df[
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

    table.rename(
        columns={
            "시군구코드": "코드",
            "시군구명": "시군구",
            "전체인구": "전체 인구",
            "65세이상인구": "65세 이상 인구",
            "유소년인구": "0~14세 인구",
            "고령화율": "고령화율(%)",
            "유소년비율": "유소년 비율(%)",
        },
        inplace=True,
    )

    table["고령화율(%)"] = table["고령화율(%)"].round(2)
    table["유소년 비율(%)"] = table["유소년 비율(%)"].round(2)

    sort_col = (
        "고령화율(%)"
        if metric == "고령화율"
        else "유소년 비율(%)"
    )

    table = table.sort_values(
        sort_col,
        ascending=False,
        na_position="last",
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )

    csv_data = table.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "📥 CSV 다운로드",
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
