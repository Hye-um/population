
import json
import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 전국 고령화 단계구분도")
st.caption("2026년 6월 기준 · 전국 시군구별 65세 이상 인구 비율")

POPULATION_URL = (
    "https://raw.githubusercontent.com/"
    "Hye-um/population/main/population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/"
    "first2022-cyber/contents//main/sigungu_kr.geojson"
)


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="인구 데이터와 지도를 불러오는 중...")
def load_data():
    # ZIP 주소를 pandas가 직접 읽음
    response = requests.get(POPULATION_URL, timeout=120)
    response.raise_for_status()

    from io import BytesIO

    df = pd.read_csv(BytesIO(response.content), compression="zip")

    # 열 이름의 앞뒤 공백 제거
    df.columns = df.columns.astype(str).str.strip()

    # 연도는 숫자로 변환
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")

    # 2026년 자료만 사용
    df = df[df["연도"] == 2026].copy()

    if df.empty:
        raise ValueError("인구 데이터에서 2026년 자료를 찾을 수 없습니다.")

    # 코드는 숫자로 바꾸지 않고 문자열로 유지
    df["코드"] = (
        df["코드"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(10)
    )

    # '계_'로 시작하는 인구 열만 선택
    total_cols = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    # 계_65세부터 계_100세 이상까지 선택
    elderly_cols = [
        col for col in total_cols
        if (
            (match := re.fullmatch(r"계_(\d+)세", col))
            and int(match.group(1)) >= 65
        ) or col == "계_100세 이상"
    ]

    if not total_cols:
        raise ValueError("'계_'로 시작하는 인구 열이 없습니다.")

    if not elderly_cols:
        raise ValueError("65세 이상 인구 열을 찾을 수 없습니다.")

    # 숫자가 아닌 값은 0으로 처리
    for col in total_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 동 코드 앞 5자리로 시군구 코드 생성
    df["시군구코드"] = df["코드"].str[:5]

    # 읍면동 자료를 시군구별로 합산
    df["전체인구"] = df[total_cols].sum(axis=1)
    df["65세이상인구"] = df[elderly_cols].sum(axis=1)

    stats = (
        df.groupby("시군구코드", as_index=False)
        .agg(
            전체인구=("전체인구", "sum"),
            **{"65세이상인구": ("65세이상인구", "sum")},
        )
    )

    stats["고령화율"] = (
        stats["65세이상인구"]
        .div(stats["전체인구"].replace(0, pd.NA))
        .mul(100)
    )

    # GeoJSON 다운로드
    geo_response = requests.get(GEOJSON_URL, timeout=60)
    geo_response.raise_for_status()
    geojson = geo_response.json()

    if geojson.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON 형식이 FeatureCollection이 아닙니다.")

    # 경계 파일의 코드도 문자열로 통일
    features = geojson.get("features", [])
    valid_features = []

    for feature in features:
        properties = feature.get("properties", {})
        code = properties.get("코드")

        if code is None:
            continue

        code = str(code).strip()

        # 숫자 코드가 12345.0 형태로 들어온 경우 정리
        code = re.sub(r"\.0$", "", code)

        if not code.isdigit():
            continue

        code = code.zfill(5)

        properties["코드"] = code
        feature["properties"] = properties
        valid_features.append(feature)

    geojson["features"] = valid_features

    # 이름이 아닌 시군구 코드로 정확하게 결합
    geo_codes = {
        feature["properties"]["코드"]
        for feature in valid_features
    }

    stats = stats[stats["시군구코드"].isin(geo_codes)].copy()

    # GeoJSON에 없는 코드는 지도에 표시하지 않음
    if stats.empty:
        raise ValueError(
            "인구 데이터와 경계 GeoJSON의 코드가 일치하지 않습니다. "
            "두 데이터의 코드 형식을 확인해 주세요."
        )

    return stats, geojson


# --------------------------------------------------
# 지도 그리기
# --------------------------------------------------
try:
    stats, geojson = load_data()

    # 상단 지표
    total_population = int(stats["전체인구"].sum())
    elderly_population = int(stats["65세이상인구"].sum())

    nationwide_rate = (
        elderly_population / total_population * 100
        if total_population > 0 else 0
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("지도에 포함된 시군구", f"{len(stats):,}곳")
    col2.metric("지도 기준 전체 인구", f"{total_population:,}명")
    col3.metric("지도 기준 고령화율", f"{nationwide_rate:.2f}%")

    st.info(
        "고령화율은 전체 인구 중 65세 이상 인구가 차지하는 비율입니다. "
        "지도에 포함된 시군구의 인구를 합산해 전국 지표를 계산합니다."
    )

    # 색상 값이 없는 지역을 숨기지 않고 별도 처리
    map_df = stats.dropna(subset=["고령화율"]).copy()

    fig = go.Figure(
        go.Choropleth(
            geojson=geojson,
            featureidkey="properties.코드",
            locations=map_df["시군구코드"].astype(str),
            z=map_df["고령화율"],
            customdata=map_df[["전체인구", "65세이상인구"]].to_numpy(),
            colorscale=[
                [0.0, "#fff7bc"],
                [0.2, "#fec44f"],
                [0.4, "#fe9929"],
                [0.6, "#ec7014"],
                [0.8, "#cc4c02"],
                [1.0, "#7f2704"],
            ],
            marker_line_color="#ffffff",
            marker_line_width=0.35,
            colorbar={
                "title": "고령화율 (%)",
                "ticksuffix": "%",
            },
            zmin=0,
            zmax=max(30, float(map_df["고령화율"].max())),
            hovertemplate=(
                "시군구 코드: %{location}<br>"
                "고령화율: %{z:.2f}%<br>"
                "전체 인구: %{customdata[0]:,.0f}명<br>"
                "65세 이상: %{customdata[1]:,.0f}명"
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
    )

    fig.update_layout(
        title={
            "text": "시군구별 65세 이상 인구 비율",
            "x": 0.5,
            "xanchor": "center",
        },
        height=780,
        margin={"l": 0, "r": 0, "t": 60, "b": 0},
        paper_bgcolor="white",
        geo_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True)

    # 시군구별 수치 표
    st.subheader("📊 시군구별 고령화율")

    display_df = stats.copy()
    display_df["고령화율(%)"] = display_df["고령화율"].round(2)
    display_df = display_df.sort_values(
        "고령화율(%)", ascending=False
    )

    # GeoJSON의 시군구 이름을 코드로 연결해 표시
    name_by_code = {
        feature["properties"]["코드"]: feature["properties"].get(
            "시군구", "이름 없음"
        )
        for feature in geojson["features"]
    }

    display_df["시군구"] = display_df["시군구코드"].map(name_by_code)
    display_df = display_df[
        [
            "시군구코드",
            "시군구",
            "전체인구",
            "65세이상인구",
            "고령화율(%)",
        ]
    ]

    display_df = display_df.rename(
        columns={
            "시군구코드": "코드",
            "전체인구": "전체 인구",
            "65세이상인구": "65세 이상 인구",
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "시군구별 결과 CSV 다운로드",
        data=csv_data,
        file_name="전국_고령화율_2026.csv",
        mime="text/csv",
    )

    st.caption(
        "자료: 제공된 2026년 인구 데이터 및 시군구 경계 GeoJSON. "
        "코드가 일치하는 시군구만 지도와 표에 표시합니다."
    )

except Exception as e:
    st.error("데이터를 불러오거나 지도를 만드는 중 오류가 발생했습니다.")
    st.exception(e)
