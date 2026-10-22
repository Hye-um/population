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
