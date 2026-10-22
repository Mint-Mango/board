
import json
import re

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# --------------------------------------------------
# 페이지 설정
# --------------------------------------------------
st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

POPULATION_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/"
    "contents/main/population_ts_yearly_gender.zip"
)
GEOJSON_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/"
    "contents/main/sigungu_kr.geojson"
)

YEAR = 2026


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------
@st.cache_data(show_spinner="인구 데이터와 행정구역 경계를 불러오는 중...")
def load_data():
    # 압축 CSV는 pandas가 URL에서 직접 읽도록 처리
    population = pd.read_csv(
        POPULATION_URL,
        compression="zip",
        dtype={"코드": "string"},
        encoding="utf-8",
        low_memory=False,
    )

    # GeoJSON은 requests로 다운로드 후 JSON으로 읽기
    response = requests.get(GEOJSON_URL, timeout=60)
    response.raise_for_status()
    geojson = response.json()

    return population, geojson


# --------------------------------------------------
# 고령화율 계산
# --------------------------------------------------
def calculate_aging_rate(population):
    required_columns = {"연도", "코드"}
    missing = required_columns - set(population.columns)

    if missing:
        raise ValueError(
            f"인구 데이터에 필수 열이 없습니다: {sorted(missing)}"
        )

    df = population.copy()

    # 코드는 문자열로 처리하고 앞의 5자리로 시군구 코드 생성
    df["코드"] = (
        df["코드"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    df["시군구코드"] = df["코드"].str[:5]

    # 2026년 자료만 사용
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.loc[df["연도"] == YEAR].copy()

    if df.empty:
        raise ValueError("인구 데이터에서 2026년 자료를 찾지 못했습니다.")

    # 계_로 시작하는 열만 사용 (남_ 및 여_ 열 제외)
    total_columns = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    if not total_columns:
        raise ValueError("'계_'로 시작하는 인구 열이 없습니다.")

    # 65세 이상 열: 계_65세 ~ 계_99세, 계_100세 이상
    elderly_columns = [
        col for col in total_columns
        if (
            re.fullmatch(r"계_(?:[6-9]\d|100)세", col)
            or col == "계_100세 이상"
        )
        and int(re.search(r"\d+", col).group()) >= 65
    ]

    if not elderly_columns:
        raise ValueError("65세 이상 인구 열을 찾지 못했습니다.")

    # 인구 열을 숫자로 변환
    for col in total_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 동별 고령 인구와 전체 인구 계산
    df["65세이상인구"] = df[elderly_columns].sum(axis=1)
    df["전체인구"] = df[total_columns].sum(axis=1)

    # 시군구 코드별로 집계
    grouped = (
        df.groupby("시군구코드", as_index=False)
        .agg(
            고령인구=("65세이상인구", "sum"),
            전체인구=("전체인구", "sum"),
        )
    )

    # 전체 인구가 0인 지역은 비율 계산에서 제외
    grouped = grouped.loc[grouped["전체인구"] > 0].copy()

    grouped["고령화율"] = (
        grouped["고령인구"] / grouped["전체인구"] * 100
    )

    return grouped


# --------------------------------------------------
# GeoJSON 속성 확인 및 코드 기준 결합
# --------------------------------------------------
def prepare_geojson(geojson, aging):
    features = geojson.get("features", [])

    if not features:
        raise ValueError("GeoJSON에 행정구역 feature가 없습니다.")

    # GeoJSON의 코드도 문자열로 통일
    for feature in features:
        properties = feature.get("properties", {})
        code = properties.get("코드")

        if code is not None:
            properties["코드"] = str(code).strip().zfill(5)

    # 경계 파일의 코드와 인구 데이터 코드를 비교
    geo_codes = {
        feature.get("properties", {}).get("코드")
        for feature in features
    }
    population_codes = set(aging["시군구코드"].astype(str))

    matched_codes = geo_codes & population_codes

    if not matched_codes:
        raise ValueError(
            "인구 데이터와 GeoJSON의 코드가 일치하지 않습니다. "
            "코드 형식과 데이터 연도를 확인하세요."
        )

    # 데이터가 없는 지역은 지도에서 제외
    filtered_features = [
        feature
        for feature in features
        if feature.get("properties", {}).get("코드") in matched_codes
    ]

    geojson_filtered = {
        "type": "FeatureCollection",
        "features": filtered_features,
    }

    # 지도 데이터 역시 코드 문자열 기준으로 일치시킴
    map_df = aging.loc[
        aging["시군구코드"].isin(matched_codes)
    ].copy()

    # GeoJSON의 공식 시군구 이름을 코드로 연결
    name_by_code = {
        feature["properties"]["코드"]:
            feature["properties"].get("시군구", "")
        for feature in filtered_features
    }

    map_df["시군구"] = map_df["시군구코드"].map(name_by_code)

    return map_df, geojson_filtered, len(matched_codes)


# --------------------------------------------------
# 앱 실행
# --------------------------------------------------
st.title("전국 고령화 단계구분도")
st.caption(
    "2026년 6월 기준 · 시군구별 65세 이상 인구 비율"
)

try:
    population, geojson = load_data()

    aging = calculate_aging_rate(population)
    map_df, geojson_filtered, matched_count = prepare_geojson(
        geojson, aging
    )

    # 주요 통계
    col1, col2, col3 = st.columns(3)

    col1.metric("표시 시군구 수", f"{matched_count:,}개")

    national_elderly = aging["고령인구"].sum()
    national_population = aging["전체인구"].sum()

    national_rate = (
        national_elderly / national_population * 100
        if national_population > 0 else 0
    )

    col2.metric("전국 고령화율", f"{national_rate:.2f}%")
    col3.metric(
        "시군구 최고 고령화율",
        f"{map_df['고령화율'].max():.2f}%",
    )

    # Plotly 단계구분도
    fig = px.choropleth(
        map_df,
        geojson=geojson_filtered,
        locations="시군구코드",
        featureidkey="properties.코드",
        color="고령화율",
        color_continuous_scale="YlOrRd",
        hover_name="시군구",
        hover_data={
            "시군구코드": False,
            "고령화율": ":.2f",
        },
        labels={"고령화율": "고령화율 (%)"},
        title="시군구별 65세 이상 인구 비율",
    )

    # 배경 지도 및 타일 없이 경계만 표시
    fig.update_geos(
        visible=False,
        fitbounds="locations",
        showcountries=False,
        showcoastlines=False,
        showland=False,
        showframe=False,
    )

    fig.update_traces(
        marker_line_color="white",
        marker_line_width=0.5,
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "고령화율: %{z:.2f}%"
            "<extra></extra>"
        ),
    )

    fig.update_layout(
        height=800,
        margin=dict(l=0, r=0, t=60, b=0),
        coloraxis_colorbar=dict(
            title="고령화율 (%)",
            ticksuffix="%",
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    # 시군구별 상세 표
    with st.expander("시군구별 고령화율 표 보기"):
        table = map_df[
            ["시군구코드", "시군구", "고령인구", "전체인구", "고령화율"]
        ].copy()

        table = table.rename(
            columns={
                "시군구코드": "코드",
                "고령인구": "65세 이상 인구",
                "전체인구": "전체 인구",
                "고령화율": "고령화율 (%)",
            }
        )

        table = table.sort_values(
            "고령화율 (%)", ascending=False
        )

        st.dataframe(
            table.style.format({"고령화율 (%)": "{:.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

except Exception as exc:
    st.error(f"데이터 처리 중 오류가 발생했습니다: {exc}")
    st.info(
        "원본 데이터의 열 이름, 2026년 자료 존재 여부, "
        "시군구 코드 형식을 확인해 주세요."
    )
