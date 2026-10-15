import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go


# =========================================================
# 1. 기본 설정
# =========================================================

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

    .intro {
        color: #795548;
        font-size: 17px;
        line-height: 1.7;
    }

    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #F0DCCB;
        padding: 16px;
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# 2. 데이터 불러오기
# =========================================================

DATA_URL = (
    "https://raw.githubusercontent.com/"
    "greatsong/modudata/main/data/population_yearly.csv.gz"
)


@st.cache_data
def load_data():
    # pandas는 .gz 압축 CSV 파일을 직접 읽을 수 있습니다.
    df = pd.read_csv(DATA_URL, compression="gzip")

    # 앞뒤 공백으로 인해 열 이름을 찾지 못하는 문제를 방지합니다.
    df.columns = df.columns.astype(str).str.strip()

    # 연도는 숫자로 변환합니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")

    # 연도가 없는 행은 제외합니다.
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 데이터에 포함된 가장 최신 연도만 사용합니다.
    latest_year = df["연도"].max()
    df = df[df["연도"] == latest_year].copy()

    # 지역 이름의 앞뒤 공백을 제거합니다.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].astype("string").str.strip()

    return df, latest_year


st.title("🏘️ 동네별 인구 피라미드")
st.markdown(
    '<p class="intro">'
    '우리 동네에는 연령대별로 얼마나 많은 사람이 살고 있을까요? '
    '시도, 시군구, 동을 선택해 남녀 인구 구성을 살펴보세요.'
    '</p>',
    unsafe_allow_html=True
)

try:
    with st.spinner("인구 데이터를 불러오는 중입니다..."):
        df, latest_year = load_data()

except Exception as e:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
    st.caption(f"오류 내용: {e}")
    st.stop()


if df.empty:
    st.warning("최신 연도에 해당하는 데이터가 없습니다.")
    st.stop()


# =========================================================
# 3. 지역 선택: 시도 → 시군구 → 동
# =========================================================

st.subheader("📍 우리 동네 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째 드롭다운: 시도
with col1:
    sido_list = sorted(df["시도"].dropna().unique().tolist())

    if not sido_list:
        st.warning("선택할 시도 데이터가 없습니다.")
        st.stop()

    selected_sido = st.selectbox(
        "① 시도",
        options=sido_list
    )

# 선택한 시도에 속하는 자료만 남깁니다.
sido_df = df[df["시도"] == selected_sido].copy()

# 두 번째 드롭다운: 시군구
with col2:
    sigungu_list = sorted(
        sido_df["시군구"].dropna().unique().tolist()
    )

    if not sigungu_list:
        st.warning("선택한 시도에 시군구 데이터가 없습니다.")
        st.stop()

    selected_sigungu = st.selectbox(
        "② 시군구",
        options=sigungu_list
    )

# 선택한 시군구에 속하는 자료만 남깁니다.
sigungu_df = sido_df[
    sido_df["시군구"] == selected_sigungu
].copy()

# 세 번째 드롭다운: 동
with col3:
    dong_list = sorted(
        sigungu_df["동"].dropna().unique().tolist()
    )

    if not dong_list:
        st.warning("선택한 시군구에 동 데이터가 없습니다.")
        st.stop()

    selected_dong = st.selectbox(
        "③ 동",
        options=dong_list
    )


# =========================================================
# 4. 선택한 동네의 인구 데이터 찾기
# =========================================================

# 지역 조건이 모두 일치하는 행만 선택합니다.
selected_df = df[
    (df["시도"] == selected_sido)
    & (df["시군구"] == selected_sigungu)
    & (df["동"] == selected_dong)
].copy()

if selected_df.empty:
    st.warning("선택한 지역의 인구 자료가 없습니다.")
    st.stop()

if len(selected_df) > 1:
    st.warning(
        "같은 지역에 여러 행이 있습니다. "
        "데이터의 중복 여부를 확인해 주세요."
    )

# 연도별 최신 자료만 남겼으므로 보통 지역당 한 행입니다.
# 혹시 같은 지역이 여러 행이면 연령별 인구를 합산합니다.
row = selected_df.iloc[0]


# =========================================================
# 5. 나이별 남녀 인구 계산
# =========================================================

# 0세부터 99세까지, 마지막은 100세 이상입니다.
ages = list(range(101))

age_labels = [
    f"{age}세" for age in range(100)
] + ["100세 이상"]

male_columns = [
    f"남_{age}세" for age in range(100)
] + ["남_100세 이상"]

female_columns = [
    f"여_{age}세" for age in range(100)
] + ["여_100세 이상"]


# 데이터에 해당 열이 없거나 값이 비어 있으면 0으로 처리합니다.
def get_population(row, column):
    if column not in row.index:
        return 0

    value = pd.to_numeric(row[column], errors="coerce")

    if pd.isna(value):
        return 0

    return max(0, int(value))


male_population = [
    get_population(row, col)
    for col in male_columns
]

female_population = [
    get_population(row, col)
    for col in female_columns
]

# 남자는 왼쪽에 표시하기 위해 음수로 변환합니다.
male_left = [-value for value in male_population]

# 여자는 오른쪽에 표시하므로 양수를 유지합니다.
female_right = female_population

total_male = sum(male_population)
total_female = sum(female_population)
total_population = total_male + total_female


# =========================================================
# 6. 주요 인구 정보 표시
# =========================================================

st.divider()

st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)

st.caption(
    f"기준 연도: {latest_year}년 · 데이터에 포함된 최신 연도"
)

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric(
        "전체 인구",
        f"{total_population:,}명"
    )

with metric2:
    st.metric(
        "남자 인구",
        f"{total_male:,}명"
    )

with metric3:
    st.metric(
        "여자 인구",
        f"{total_female:,}명"
    )


# =========================================================
# 7. 인구 피라미드 그리기
# =========================================================

fig = go.Figure()

# 남자: 왼쪽 방향 막대
fig.add_trace(
    go.Bar(
        x=male_left,
        y=age_labels,
        orientation="h",
        name="남자",
        marker_color="#D9826B",
        customdata=male_population,
        hovertemplate=(
            "나이: %{y}<br>"
            "남자 인구: %{customdata:,}명"
            "<extra></extra>"
        )
    )
)

# 여자: 오른쪽 방향 막대
fig.add_trace(
    go.Bar(
        x=female_right,
        y=age_labels,
        orientation="h",
        name="여자",
        marker_color="#E9B66B",
        customdata=female_population,
        hovertemplate=(
            "나이: %{y}<br>"
            "여자 인구: %{customdata:,}명"
            "<extra></extra>"
        )
    )
)

# 남녀 막대가 가운데를 기준으로 나뉘도록 설정합니다.
# 좌우 축의 눈금은 절댓값으로 표시해 읽기 쉽게 만듭니다.
max_population = max(
    max(male_population, default=0),
    max(female_population, default=0),
    1
)

axis_limit = max_population * 1.1

tick_step = max(1, int(np.ceil(axis_limit / 5)))
tick_values_positive = list(
    range(0, int(axis_limit) + tick_step, tick_step)
)

# 축 범위 안에 마지막 눈금이 들어오도록 조정합니다.
tick_values_positive = [
    value for value in tick_values_positive
    if value <= axis_limit
]

if not tick_values_positive or tick_values_positive[0] != 0:
    tick_values_positive.insert(0, 0)

tick_values = (
    [-value for value in reversed(tick_values_positive) if value != 0]
    + [0]
    + [value for value in tick_values_positive if value != 0]
)

tick_text = [f"{abs(value):,}" for value in tick_values]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 남녀 인구",
        "x": 0.5,
        "xanchor": "center"
    },
    barmode="overlay",
    bargap=0.12,
    height=1000,
    plot_bgcolor="#FFFDF9",
    paper_bgcolor="#FFF9F2",
    font={
        "family": "Arial, sans-serif",
        "size": 12,
        "color": "#5D4037"
    },
    legend={
        "title": "성별",
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "center",
        "x": 0.5
    },
    xaxis={
        "title": "인구 (명)",
        "range": [-axis_limit, axis_limit],
        "tickmode": "array",
        "tickvals": tick_values,
        "ticktext": tick_text,
        "zeroline": True,
        "zerolinecolor": "#9E8A7C",
        "zerolinewidth": 1.5,
        "gridcolor": "#F0E4D8"
    },
    yaxis={
        "title": "나이",
        # 핵심: 라벨을 0세부터 100세 이상까지 명시적으로 고정합니다.
        "categoryorder": "array",
        "categoryarray": age_labels,
        # 축 전체를 뒤집지 않습니다.
        # categoryarray 순서대로 0세가 아래, 100세 이상이 위에 놓입니다.
        "autorange": True,
        "showgrid": False,
        "tickfont": {"size": 10}
    },
    margin={"l": 100, "r": 40, "t": 100, "b": 70}
)

# Streamlit 화면에 그래프를 표시합니다.
st.plotly_chart(
    fig,
    width="stretch",
    config={"displayModeBar": True}
)


# =========================================================
# 8. 연령별 인구 표
# =========================================================

with st.expander("📋 연령별 인구 표 보기"):
    population_table = pd.DataFrame({
        "나이": age_labels,
        "남자 인구": male_population,
        "여자 인구": female_population,
        "합계": [
            male_population[i] + female_population[i]
            for i in range(101)
        ]
    })

    st.dataframe(
        population_table,
        hide_index=True,
        width="stretch"
    )

st.caption(
    "자료: 제공된 연도별 읍·면·동 인구 CSV | "
    "남자는 왼쪽, 여자는 오른쪽에 표시됩니다."
)
  
