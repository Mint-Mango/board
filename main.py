
import re
import json

import pandas as pd
import requests
import plotly.graph_objects as go
import streamlit as st


# =========================================================
# 1. 페이지 설정 및 데이터 주소
# =========================================================
st.set_page_config(
    page_title="전국 인구구조 단계구분도",
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

MIN_YEAR = 2015
MAX_YEAR = 2026

# 지표별 색상 구간 경계값은 연도가 바뀌어도 고정
INDICATORS = {
    "고령화율 (65세 이상)": {
        "numerator": "elderly",
        "label": "고령화율",
        "unit": "%",
        "thresholds": [19, 23, 28, 38],
        "zmin": 0,
        "zmax": 50,
        "tickvals": [0, 19, 23, 28, 38, 50],
        "ticktext": ["0", "19", "23", "28", "38", "50+"],
        "description": "65세 이상 인구 ÷ 전체 인구 × 100",
    },
    "유소년 비율 (0~14세)": {
        "numerator": "youth",
        "label": "유소년 비율",
        "unit": "%",
        "thresholds": [8, 10, 12, 14],
        "zmin": 0,
        "zmax": 20,
        "tickvals": [0, 8, 10, 12, 14, 20],
        "ticktext": ["0", "8", "10", "12", "14", "20+"],
        "description": "0~14세 인구 ÷ 전체 인구 × 100",
    },
}

# 낮은 비율에서 높은 비율 순서
BIN_COLORS = [
    "#fff7bc",  # 가장 낮음
    "#fec44f",
    "#fe9929",
    "#ec7014",
    "#993404",  # 가장 높음
]

MISSING_COLOR = "#d3d3d3"


# =========================================================
# 2. 공통 유틸리티
# =========================================================
def normalize_code(value):
    """행정구역 코드를 문자열로 통일하고 알려진 개편 코드를 보정."""
    if pd.isna(value):
        return None

    code = str(value).strip()

    # 숫자형 CSV 값이 문자열로 변환되며 생기는 .0 제거
    code = re.sub(r"\.0$", "", code)

    if not code or code.lower() in {"nan", "none"}:
        return None

    # 특정 군위군 코드 우선 보정
    if code.startswith("47720"):
        code = "27720" + code[5:]

    # 과거 시도 코드 보정
    if code.startswith("42"):
        code = "51" + code[2:]
    elif code.startswith("45"):
        code = "52" + code[2:]

    return code


def sigungu_code(value):
    """읍면동 코드에서 시군구 코드 5자리를 추출."""
    code = normalize_code(value)

    if code is None:
        return None

    return code[:5].zfill(5)


def geo_code(value):
    """GeoJSON의 시군구 코드를 문자열 5자리로 통일."""
    if value is None:
        return None

    code = str(value).strip()
    code = re.sub(r"\.0$", "", code)

    if not code or code.lower() in {"nan", "none"}:
        return None

    return code.zfill(5)


def age_from_column(column):
    """계_65세 같은 열 이름에서 나이를 추출."""
    match = re.fullmatch(r"계_(\d+)세", column)

    if match:
        return int(match.group(1))

    if column == "계_100세 이상":
        return 100

    return None


# =========================================================
# 3. 원본 데이터 로딩
# =========================================================
@st.cache_data(show_spinner="인구 데이터와 시군구 경계를 불러오는 중...")
def load_data():
    # 압축 CSV 다운로드 및 읽기
    population = pd.read_csv(
        POPULATION_URL,
        compression="zip",
        dtype={"코드": "string"},
        encoding="utf-8",
        low_memory=False,
    )

    # GeoJSON은 requests로 다운로드하고 JSON으로 파싱
    response = requests.get(GEOJSON_URL, timeout=60)
    response.raise_for_status()
    geojson = response.json()

    if "features" not in geojson:
        raise ValueError("GeoJSON에 features가 없습니다.")

    # 경계 파일의 코드를 문자열로 통일
    for feature in geojson["features"]:
        properties = feature.setdefault("properties", {})
        properties["코드"] = geo_code(properties.get("코드"))

    return population, geojson


# =========================================================
# 4. 연도별 시군구 인구 지표 계산
# =========================================================
def calculate_indicator(population, year):
    required_columns = {"연도", "코드"}
    missing = required_columns - set(population.columns)

    if missing:
        raise ValueError(
            f"인구 데이터 필수 열이 없습니다: {sorted(missing)}"
        )

    df = population.copy()

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.loc[df["연도"] == year].copy()

    if df.empty:
        return pd.DataFrame(
            columns=[
                "코드", "고령인구", "유소년인구",
                "전체인구", "고령화율", "유소년 비율"
            ]
        )

    # 읍면동 코드를 보정한 다음 앞 5자리로 시군구 집계
    df["코드"] = df["코드"].map(normalize_code)
    df["시군구코드"] = df["코드"].map(sigungu_code)

    df = df.loc[df["시군구코드"].notna()].copy()

    # 전체 인구: 계_로 시작하는 열만 사용
    total_columns = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    if not total_columns:
        raise ValueError("'계_'로 시작하는 인구 열을 찾지 못했습니다.")

    # 나이별 인구 열 추출
    age_columns = {
        col: age_from_column(col)
        for col in total_columns
    }

    elderly_columns = [
        col for col, age in age_columns.items()
        if age is not None and age >= 65
    ]

    youth_columns = [
        col for col, age in age_columns.items()
        if age is not None and 0 <= age <= 14
    ]

    if not elderly_columns:
        raise ValueError("65세 이상 인구 열을 찾지 못했습니다.")

    if not youth_columns:
        raise ValueError("0~14세 인구 열을 찾지 못했습니다.")

    # 모든 계_ 열을 숫자로 변환
    for col in total_columns:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    # 남_ 및 여_ 열은 집계에 사용하지 않음
    df["전체인구"] = df[total_columns].sum(axis=1)
    df["고령인구"] = df[elderly_columns].sum(axis=1)
    df["유소년인구"] = df[youth_columns].sum(axis=1)

    # 시군구별 인구 합계
    result = (
        df.groupby("시군구코드", as_index=False)
        .agg(
            전체인구=("전체인구", "sum"),
            고령인구=("고령인구", "sum"),
            유소년인구=("유소년인구", "sum"),
        )
        .rename(columns={"시군구코드": "코드"})
    )

    # 전체 인구가 0인 지역은 비율을 계산하지 않음
    valid = result["전체인구"] > 0

    result["고령화율"] = float("nan")
    result["유소년 비율"] = float("nan")

    result.loc[valid, "고령화율"] = (
        result.loc[valid, "고령인구"]
        / result.loc[valid, "전체인구"] * 100
    )

    result.loc[valid, "유소년 비율"] = (
        result.loc[valid, "유소년인구"]
        / result.loc[valid, "전체인구"] * 100
    )

    return result


# =========================================================
# 5. GeoJSON과 인구 데이터 결합
# =========================================================
def merge_map_data(geojson, indicator_df, selected_province):
    features = geojson["features"]

    # 시도 필터
    if selected_province != "전국":
        features = [
            feature for feature in features
            if feature.get("properties", {}).get("시도")
            == selected_province
        ]

    # 선택된 시도의 경계만 포함하는 GeoJSON
    filtered_geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    # 경계 파일을 기준으로 LEFT JOIN:
    # 인구 데이터에 없는 지역도 지도에 남겨 회색으로 표시
    geo_rows = []

    for feature in features:
        properties = feature.get("properties", {})
        code = geo_code(properties.get("코드"))

        geo_rows.append({
            "코드": code,
            "시군구": properties.get("시군구", "이름 없음"),
            "시도": properties.get("시도", ""),
        })

    boundary_df = pd.DataFrame(geo_rows)

    map_df = boundary_df.merge(
        indicator_df,
        on="코드",
        how="left",
        validate="one_to_one",
    )

    # 매칭 여부와 관계없이 경계 파일의 모든 지역을 유지
    matched = (
        map_df["전체인구"].notna()
        & map_df["전체인구"].gt(0)
    )

    return map_df, filtered_geojson, matched


# =========================================================
# 6. 고정 구간 색상 스케일 생성
# =========================================================
def make_discrete_colorscale(thresholds, zmin, zmax):
    """
    경계값에서 색이 즉시 바뀌도록 계단형 색상표를 생성.
    연도별 자동 정규화를 하지 않아 연도 간 비교 가능.
    """
    boundaries = [zmin] + list(thresholds) + [zmax]
    colorscale = []

    for i, color in enumerate(BIN_COLORS):
        left = (boundaries[i] - zmin) / (zmax - zmin)
        right = (boundaries[i + 1] - zmin) / (zmax - zmin)

        colorscale.append([left, color])
        colorscale.append([right, color])

    return colorscale


# =========================================================
# 7. 지도 그리기
# =========================================================
def draw_map(map_df, geojson, metric, year):
    config = INDICATORS[metric]
    value_column = config["label"]
    thresholds = config["thresholds"]

    colorscale = make_discrete_colorscale(
        thresholds,
        config["zmin"],
        config["zmax"],
    )

    # GeoJSON의 모든 지역 코드를 순서대로 사용
    all_codes = map_df["코드"].tolist()

    # 먼저 모든 지역을 회색으로 그려 미매칭 지역의 경계를 유지
    fig = go.Figure()

    fig.add_trace(
        go.Choropleth(
            geojson=geojson,
            locations=all_codes,
            z=[0] * len(all_codes),
            featureidkey="properties.코드",
            colorscale=[
                [0, MISSING_COLOR],
                [1, MISSING_COLOR],
            ],
            zmin=0,
            zmax=1,
            showscale=False,
            marker_line_color="white",
            marker_line_width=0.5,
            hoverinfo="skip",
            name="자료 없음",
        )
    )

    # 유효한 인구 데이터가 있는 지역만 색칠
    valid_df = map_df.loc[
        map_df[value_column].notna()
        & map_df["전체인구"].gt(0)
    ].copy()

    if not valid_df.empty:
        fig.add_trace(
            go.Choropleth(
                geojson=geojson,
                locations=valid_df["코드"],
                z=valid_df[value_column],
                featureidkey="properties.코드",
                colorscale=colorscale,
                zmin=config["zmin"],
                zmax=config["zmax"],
                zauto=False,
                colorbar=dict(
                    title=dict(text=f"{config['label']} (%)"),
                    tickmode="array",
                    tickvals=config["tickvals"],
                    ticktext=config["ticktext"],
                    ticks="outside",
                    len=0.75,
                ),
                marker_line_color="white",
                marker_line_width=0.5,
                customdata=valid_df[
                    ["시군구", "코드", "전체인구"]
                ].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    f"{config['label']}: "
                    "%{z:.2f}%<br>"
                    "코드: %{customdata[1]}<br>"
                    "전체 인구: %{customdata[2]:,.0f}명"
                    "<extra></extra>"
                ),
                name=config["label"],
            )
        )

    fig.update_geos(
        visible=False,
        fitbounds="locations",
        showcountries=False,
        showcoastlines=False,
        showland=False,
        showframe=False,
        bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        title=dict(
            text=f"{year}년 {config['label']} 단계구분도",
            x=0.02,
            xanchor="left",
        ),
        height=760,
        margin=dict(l=0, r=0, t=65, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h"),
    )

    return fig


# =========================================================
# 8. 앱 UI
# =========================================================
st.title("전국 인구구조 단계구분도")
st.caption(
    "연도별 인구 자료를 이용해 시군구의 고령화율과 "
    "유소년 비율을 비교합니다."
)

try:
    population, geojson = load_data()

    # -----------------------------------------------------
    # 컨트롤
    # -----------------------------------------------------
    st.subheader("분석 조건")

    control1, control2, control3 = st.columns([1, 2, 2])

    with control1:
        year = st.slider(
            "기준 연도",
            min_value=MIN_YEAR,
            max_value=MAX_YEAR,
            value=2026,
            step=1,
        )

    with control2:
        metric = st.selectbox(
            "분석 지표",
            options=list(INDICATORS.keys()),
            index=0,
        )

    with control3:
        provinces = sorted({
            str(feature.get("properties", {}).get("시도"))
            for feature in geojson["features"]
            if feature.get("properties", {}).get("시도")
        })

        selected_province = st.selectbox(
            "시도 선택",
            options=["전국"] + provinces,
            index=0,
        )

    config = INDICATORS[metric]
    value_column = config["label"]

    st.caption(
        f"산출 기준: {config['description']} · "
        f"색상 구간: "
        + " / ".join(
            [
                f"{config['zmin']}~{config['thresholds'][0]}%",
                f"{config['thresholds'][0]}~{config['thresholds'][1]}%",
                f"{config['thresholds'][1]}~{config['thresholds'][2]}%",
                f"{config['thresholds'][2]}~{config['thresholds'][3]}%",
                f"{config['thresholds'][3]}% 이상",
            ]
        )
    )

    # -----------------------------------------------------
    # 해당 연도의 지표 계산
    # -----------------------------------------------------
    indicator_df = calculate_indicator(population, year)

    if indicator_df.empty:
        st.warning(f"{year}년 인구 자료가 없습니다.")
        st.stop()

    # -----------------------------------------------------
    # 전국 통계: 시도 선택과 관계없이 전국 기준으로 계산
    # -----------------------------------------------------
    national_valid = indicator_df.loc[
        indicator_df["전체인구"] > 0
    ].copy()

    national_population = national_valid["전체인구"].sum()

    if metric == "고령화율 (65세 이상)":
        national_numerator = national_valid["고령인구"].sum()
    else:
        national_numerator = national_valid["유소년인구"].sum()

    national_rate = (
        national_numerator / national_population * 100
        if national_population > 0 else float("nan")
    )

    ranked = national_valid.dropna(
        subset=[value_column]
    ).copy()

    # 경계 파일의 시군구명을 코드 기준으로 연결
    geo_name_by_code = {
        feature["properties"]["코드"]:
            feature["properties"].get("시군구", "")
        for feature in geojson["features"]
        if feature.get("properties", {}).get("코드")
    }

    ranked["시군구"] = ranked["코드"].map(geo_name_by_code)
    ranked = ranked.loc[ranked["시군구"].notna()]

    # -----------------------------------------------------
    # 지도에 표시할 지역 데이터
    # -----------------------------------------------------
    map_df, map_geojson, matched = merge_map_data(
        geojson,
        indicator_df,
        selected_province,
    )

    # -----------------------------------------------------
    # 지표 카드 3장
    # -----------------------------------------------------
    if not ranked.empty:
        highest = ranked.loc[ranked[value_column].idxmax()]
        lowest = ranked.loc[ranked[value_column].idxmin()]

        highest_name = highest["시군구"]
        highest_rate = highest[value_column]

        lowest_name = lowest["시군구"]
        lowest_rate = lowest[value_column]
    else:
        highest_name = "자료 없음"
        highest_rate = float("nan")
        lowest_name = "자료 없음"
        lowest_rate = float("nan")

    st.subheader("전국 주요 지표")

    card1, card2, card3 = st.columns(3)

    card1.metric(
        f"전국 {config['label']}",
        f"{national_rate:.2f}%" if pd.notna(national_rate) else "자료 없음",
        help=config["description"],
    )

    card2.metric(
        "가장 높은 시군구",
        highest_name,
        f"{highest_rate:.2f}%" if pd.notna(highest_rate) else None,
    )

    card3.metric(
        "가장 낮은 시군구",
        lowest_name,
        f"{lowest_rate:.2f}%" if pd.notna(lowest_rate) else None,
    )

    # -----------------------------------------------------
    # 단계구분도
    # -----------------------------------------------------
    st.subheader(
        "전국 지도" if selected_province == "전국"
        else f"{selected_province} 단계구분도"
    )

    fig = draw_map(
        map_df,
        map_geojson,
        metric,
        year,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displaylogo": False,
            "scrollZoom": True,
            "responsive": True,
        },
    )

    # -----------------------------------------------------
    # 코드 미매칭 안내
    # -----------------------------------------------------
    unmatched_df = map_df.loc[~matched].copy()
    unmatched_count = len(unmatched_df)

    if unmatched_count:
        st.warning(
            f"회색 지역 {unmatched_count}곳은 해당 연도의 인구 자료와 "
            "시군구 경계 코드가 일치하지 않거나 유효한 전체 인구가 "
            "없어 지표를 계산하지 못한 지역입니다. "
            "회색 지역은 비율이 0%라는 뜻이 아닙니다."
        )

        with st.expander("자료가 연결되지 않은 지역 확인"):
            st.dataframe(
                unmatched_df[["코드", "시도", "시군구"]],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.caption("현재 지도 범위에서 코드 미매칭 지역이 없습니다.")

    # -----------------------------------------------------
    # 상세 데이터 표
    # -----------------------------------------------------
    with st.expander("시군구별 상세 데이터"):
        detail = map_df[
            [
                "코드",
                "시도",
                "시군구",
                "전체인구",
                "고령인구",
                "고령화율",
                "유소년인구",
                "유소년 비율",
            ]
        ].copy()

        detail = detail.rename(
            columns={
                "코드": "시군구 코드",
                "시도": "시도",
                "시군구": "시군구",
                "전체인구": "전체 인구",
                "고령인구": "65세 이상 인구",
                "고령화율": "고령화율 (%)",
                "유소년인구": "0~14세 인구",
                "유소년 비율": "유소년 비율 (%)",
            }
        )

        detail = detail.sort_values(
            value_column,
            ascending=False,
            na_position="last",
        )

        st.dataframe(
            detail.style.format(
                {
                    "전체 인구": "{:,.0f}",
                    "65세 이상 인구": "{:,.0f}",
                    "고령화율 (%)": "{:.2f}",
                    "0~14세 인구": "{:,.0f}",
                    "유소년 비율 (%)": "{:.2f}",
                },
                na_rep="-",
            ),
            use_container_width=True,
            hide_index=True,
        )

except requests.RequestException as exc:
    st.error(f"원본 데이터를 다운로드하지 못했습니다: {exc}")

except Exception as exc:
    st.error(f"앱 실행 중 오류가 발생했습니다: {exc}")
    st.exception(exc)
