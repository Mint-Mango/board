# ─────────────────────────────────────────────────────────
# 동네별 인구 피라미드 (Streamlit 앱)
# 실행 방법(내 컴퓨터):  streamlit run main.py
# ─────────────────────────────────────────────────────────
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# 페이지 기본 설정 (브라우저 탭 제목, 아이콘, 넓은 화면)
st.set_page_config(page_title="동네별 인구 피라미드", page_icon="🏡", layout="wide")

# 데이터 주소 (zip 압축 CSV지만 pandas가 바로 읽을 수 있어요)
DATA_URL = "https://raw.githubusercontent.com/Mint-Mango/board/blob/main/population_ts_yearly_gender.zip"

# 따뜻한 색 (남자: 따뜻한 주황 / 여자: 따뜻한 분홍)
COLOR_MALE = "#E8833A"
COLOR_FEMALE = "#E86A7A"
BG_CREAM = "#FFF8EC"
TEXT_BROWN = "#5D4037"

# ─────────────────────────────────────────────────────────
# 화면 꾸미기 (크림색 배경, 갈색 글씨)
# ─────────────────────────────────────────────────────────
st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {BG_CREAM}; }}
    h1, h2, h3, p, label, span {{ color: {TEXT_BROWN}; }}
    div[data-testid="stMetric"] {{
        background: #FFFFFF;
        border: 2px solid #F6D58E;
        border-radius: 16px;
        padding: 12px 16px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────
# 1. 데이터 읽기
#    @st.cache_data : 한 번 읽은 데이터를 기억해 두어서
#                     드롭다운을 바꿀 때마다 다시 내려받지 않아요.
# ─────────────────────────────────────────────────────────
@st.cache_data(show_spinner="인구 데이터를 불러오는 중이에요... 잠시만 기다려 주세요 ⏳")
def load_data(url):
    # 글자 인코딩이 utf-8이 아니면 cp949(한글 윈도우 방식)로 다시 시도해요.
    try:
        df = pd.read_csv(url, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(url, encoding="cp949")

    # 열 이름 앞뒤에 공백이 있으면 지워요.
    df.columns = [str(c).strip() for c in df.columns]

    # 가장 최신 연도만 남겨요.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    latest_year = int(df["연도"].max())
    df = df[df["연도"] == latest_year].copy()

    # 시도·시군구·동 글자 앞뒤 공백 정리
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].astype(str).str.strip()

    return df, latest_year


def age_number(label):
    """'0세' → 0, '100세 이상' → 100 처럼 나이 라벨에서 숫자만 꺼내요."""
    return int(re.search(r"\d+", label).group())


def get_age_labels(df):
    """
    표의 열 이름('남_0세', '남_1세', ..., '남_100세 이상')에서
    나이 라벨만 뽑아 0세 → 100세 이상 순서로 정렬해요.
    (열 순서가 섞여 있어도 숫자 기준으로 바르게 정렬됩니다.)
    """
    labels = [c[len("남_"):] for c in df.columns if c.startswith("남_")]
    labels = [lab for lab in labels if f"여_{lab}" in df.columns]  # 남·여 둘 다 있는 나이만
    return sorted(labels, key=age_number)


def to_number(series):
    """'1,234' 같은 글자도 숫자 1234로 바꾸고, 빈칸은 0으로 채워요."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", "").str.strip(), errors="coerce"
    ).fillna(0)


# ─────────────────────────────────────────────────────────
# 2. 제목
# ─────────────────────────────────────────────────────────
st.title("🏡 동네별 인구 피라미드")

try:
    data, year = load_data(DATA_URL)
except Exception as e:
    st.error(f"데이터를 불러오지 못했어요 😢\n\n오류 내용: {e}")
    st.stop()

st.write(f"**{year}년** 전국 읍·면·동 인구 자료예요. 아래에서 동네를 골라 보세요!")

# ─────────────────────────────────────────────────────────
# 3. 드롭다운 3개 (시도 → 시군구 → 동)
#    앞에서 고른 값에 맞는 목록만 다음 드롭다운에 나와요.
# ─────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(data["시도"].unique())
    sido = st.selectbox("① 시·도", sido_list)

with col2:
    sigungu_list = sorted(data.loc[data["시도"] == sido, "시군구"].unique())
    sigungu = st.selectbox("② 시·군·구", sigungu_list)

with col3:
    dong_list = sorted(
        data.loc[(data["시도"] == sido) & (data["시군구"] == sigungu), "동"].unique()
    )
    dong = st.selectbox("③ 읍·면·동", dong_list)

# 고른 동네의 행만 꺼내요. (같은 동이 여러 줄이면 합쳐요)
area = data[(data["시도"] == sido) & (data["시군구"] == sigungu) & (data["동"] == dong)]

# ─────────────────────────────────────────────────────────
# 4. 그래프에 쓸 표 만들기
#    나이 | 남자 | 여자   (0세부터 100세 이상까지 순서대로)
# ─────────────────────────────────────────────────────────
age_labels = get_age_labels(data)  # ['0세', '1세', ..., '100세 이상']

male = [to_number(area[f"남_{lab}"]).sum() for lab in age_labels]
female = [to_number(area[f"여_{lab}"]).sum() for lab in age_labels]

pyramid = pd.DataFrame({"나이": age_labels, "남자": male, "여자": female})

# 요약 숫자 카드
total_m = int(pyramid["남자"].sum())
total_f = int(pyramid["여자"].sum())
m1, m2, m3 = st.columns(3)
m1.metric("👨 남자", f"{total_m:,}명")
m2.metric("👩 여자", f"{total_f:,}명")
m3.metric("🏠 전체", f"{total_m + total_f:,}명")

# ─────────────────────────────────────────────────────────
# 5. 인구 피라미드 그리기 (plotly 가로 막대)
#    남자는 왼쪽(음수), 여자는 오른쪽(양수)
# ─────────────────────────────────────────────────────────
fig = go.Figure()

fig.add_trace(go.Bar(
    y=pyramid["나이"],
    x=-pyramid["남자"],                 # 음수로 바꿔서 왼쪽으로!
    orientation="h",
    name="남자",
    marker_color=COLOR_MALE,
    customdata=pyramid["남자"],         # 마우스를 올리면 양수로 보여 주기 위해
    hovertemplate="%{y} 남자: %{customdata:,}명<extra></extra>",
))

fig.add_trace(go.Bar(
    y=pyramid["나이"],
    x=pyramid["여자"],                  # 양수 그대로 오른쪽으로!
    orientation="h",
    name="여자",
    marker_color=COLOR_FEMALE,
    hovertemplate="%{y} 여자: %{x:,}명<extra></extra>",
))

# 가로축 눈금: 왼쪽도 '-100'이 아니라 '100'처럼 양수로 보이게 해요.
max_val = max(pyramid["남자"].max(), pyramid["여자"].max(), 1)
step = max(1, int(max_val / 4))
ticks = [i * step for i in range(-4, 5)]

fig.update_layout(
    title=f"{sido} {sigungu} {dong} 인구 피라미드 ({year}년)",
    barmode="relative",                 # 남·여 막대를 가운데 0을 기준으로 양쪽에
    bargap=0.1,
    height=900,
    plot_bgcolor="#FFFFFF",
    paper_bgcolor=BG_CREAM,
    font=dict(color=TEXT_BROWN, size=14),
    legend=dict(orientation="h", x=0.5, xanchor="center", y=1.03),
    xaxis=dict(
        title="인구 (명)",
        tickvals=ticks,
        ticktext=[f"{abs(t):,}" for t in ticks],
        range=[-max_val * 1.1, max_val * 1.1],
        gridcolor="#F3E3C3",
        zeroline=True,
        zerolinecolor=TEXT_BROWN,
    ),
    yaxis=dict(
        title="나이",
        # ★ 세로축 순서 고정 ★
        # type="category"      : 나이를 '글자 라벨'로 다뤄요.
        # categoryorder="array": 아래 categoryarray에 적은 순서 그대로 쓰라는 뜻이에요.
        # categoryarray         : 0세, 1세, ..., 100세 이상 (정렬된 순서 그대로)
        # plotly의 세로 범주축은 목록의 첫 번째 값을 '맨 아래'에 놓기 때문에
        # 0세가 맨 아래, 100세 이상이 맨 위에 그려져요.
        # (축 뒤집기 옵션이나 값 크기순 정렬 옵션은 쓰지 않았어요.)
        type="category",
        categoryorder="array",
        categoryarray=age_labels,
        # 101개 라벨이 다 나오면 빽빽하니 10살 간격으로만 글자를 보여 줘요.
        tickmode="array",
        tickvals=[lab for lab in age_labels if age_number(lab) % 10 == 0],
    ),
)

st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────
# 6. 숫자 표도 펼쳐서 볼 수 있게 (위가 100세 이상, 아래가 0세 → 그래프와 같은 방향)
# ─────────────────────────────────────────────────────────
with st.expander("📋 나이별 인구 숫자 표 보기"):
    st.dataframe(pyramid.iloc[::-1].reset_index(drop=True), use_container_width=True)

st.caption("자료: Mint-Mango/contents 저장소의 연도별·성별 인구 데이터")
