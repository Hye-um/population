        hovertemplate=(
            "나이: %{customdata[1]}<br>"
            "여자 인구: %{customdata[0]:,.0f}명<extra></extra>"
        ),
    )
)

# 좌우 축의 크기를 같게 만들어 남녀 인구를 쉽게 비교합니다.
max_population = max(
    float(male_population.max()) if len(male_population) else 0,
    float(female_population.max()) if len(female_population) else 0,
    1.0,
)
axis_limit = max_population * 1.12
tick_step = max(1, int(np.ceil(axis_limit / 5)))
tick_end = int(np.ceil(axis_limit / tick_step)) * tick_step

positive_ticks = list(range(0, tick_end + 1, tick_step))
tick_values = [-v for v in positive_ticks[:0:-1]] + positive_ticks
tick_text = [f"{abs(v):,}" for v in tick_values]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 인구 피라미드 ({latest_year}년)",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=1000,
    paper_bgcolor="#FFF9F2",
    plot_bgcolor="#FFF9F2",
    font={
        "family": "Malgun Gothic, Apple SD Gothic Neo, sans-serif",
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
        # 숫자 위치 0~100을 그대로 사용하므로 0세가 아래, 100세 이상이 위입니다.
        # 축을 뒤집거나 인구수 기준으로 정렬하지 않습니다.
        "tickmode": "array",
        "tickvals": y_positions,
        "ticktext": age_labels,
        "range": [-0.5, 100.5],
        "dtick": 5,
        "gridcolor": "#EADFD4",
    },
    margin={"l": 100, "r": 40, "t": 100, "b": 70},
)

st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# 8. 동네 특징 자동 설명
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

        참고: 평균연령 계산에서 '100세 이상'은 100세로 간주합니다.
        아이와 어르신 비교는 0~14세와 65세 이상 인구 비율을 기준으로 합니다.
        """
    )

st.caption(
    f"데이터 출처: [GitHub CSV 원본]({DATA_URL}) · 기준 연도: {latest_year}년"
)
