
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
    "first2022-cyber/contents/main/population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/"
    "first2022-cyber/contents/main/sigungu_kr.geojson"
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
