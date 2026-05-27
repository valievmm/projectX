import streamlit as st
import requests
import folium
from streamlit_folium import folium_static
import json

st.set_page_config(page_title="SmartIndustry", layout="wide")
st.title("🏭 Наследие индустрии: умный подбор локации для производства сэндвич-панелей")

# API URL
API = "http://localhost:8000"

# ===== Шаг 1: Форма 10 полей =====
with st.expander("📋 Параметры проекта", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        volume = st.number_input("Объём выпуска (тыс. м²/год)", 100, 1000, 500, step=50)
        employees = st.number_input("Количество сотрудников", 10, 200, 80, step=10)
        budget = st.slider("Бюджет на участок и подключение (млн руб)", 10, 300, 100, step=10)
    with col2:
        railway = st.checkbox("Необходима ж/д ветка", value=True)
        max_highway = st.slider("Макс. расстояние до трассы (км)", 1, 100, 30)
        arch_priority = st.selectbox("Архитектурный приоритет",
                                     ["Аутентичность региону", "Техно-стиль", "Экодизайн"])
    with col3:
        landscaping = st.multiselect("Благоустройство (до 3)",
                                     ["Аллея", "Сквер с фонтаном", "Беседки", "Сцена",
                                      "Тропа здоровья", "Пруд", "Арт-объект"],
                                     default=["Аллея", "Сквер с фонтаном"],
                                     max_selections=3)
        housing_pct = st.select_slider("Обеспечение жильём сотрудников",
                                       options=[0, 30, 50, 70], value=30) / 100
        housing_type = st.radio("Тип жилья", ["общежитие", "квартиры"], horizontal=True)
        kindergarten = st.selectbox("Мест в детсаду на 100 сотрудников", [0, 15, 30, 50], index=2)
        sports = st.multiselect("Спортобъекты (до 2)",
                                ["Уличные тренажёры", "Стадион", "Бассейн",
                                 "Спортзал", "Хоккейная коробка"],
                                default=["Спортзал"], max_selections=2)

# ===== Шаг 2: Поиск участков =====
if st.button("🔍 Найти участок"):
    payload = {
        "volume": volume,
        "employees": employees,
        "budget": budget,
        "railway": railway,
        "max_highway": max_highway,
        "arch_priority": arch_priority,
        "landscaping": landscaping,
        "housing_pct": housing_pct,
        "housing_type": housing_type,
        "kindergarten_per_100": kindergarten,
        "sports": sports
    }
    with st.spinner("Подбираем лучшие регионы..."):
        resp = requests.post(f"{API}/rank_regions", json=payload)
        if resp.status_code == 200:
            top3 = resp.json()
        else:
            st.error("Ошибка сервера")
            top3 = []

    if not top3:
        st.warning("Нет подходящих регионов под заданные условия.")
    else:
        st.success(f"Найдено {len(top3)} регионов")
        # Карта
        m = folium.Map(location=[top3[0]["lat"], top3[0]["lon"]], zoom_start=5)
        colors = ["green", "blue", "purple"]
        for i, reg in enumerate(top3):
            folium.Marker(
                [reg["lat"], reg["lon"]],
                popup=f"{i+1}. {reg['name']} (score: {reg['score']})",
                icon=folium.Icon(color=colors[i])
            ).add_to(m)
        st.subheader("📍 ТОП-3 региона на карте")
        folium_static(m, width=1000, height=500)

        # Таблица
        st.subheader("📊 Сравнительная аналитика")
        st.dataframe([{
            "Регион": r["name"],
            "Рейтинг": r["score"],
            "Э/э тариф": r["energy_tariff"],
            "Газ": "✅" if r["gas"] else "❌",
            "Льготы": "✅" if r["tax_incentives"] else "❌",
            "Аренда 1-к кв.": r["avg_rent"],
            "Расст. до стали": r["steel_km"],
            "Стоим. подключ.": f"{r['connection_cost_rub']:,.0f} руб"
        } for r in top3], use_container_width=True)

        # ===== Шаг 3: Аналитическая справка для выбранного региона =====
        st.subheader("📑 Полная аналитическая справка")
        selected_region = st.selectbox("Выберите регион для подробного отчёта",
                                       [r["name"] for r in top3])
        if st.button("Сформировать справку"):
            with st.spinner("Готовим справку и смету..."):
                rep = requests.post(f"{API}/generate_report",
                                    json={**payload, "region_name": selected_region}).json()
            if "error" not in rep:
                st.markdown(f"### 🏘 Социальный паспорт")
                st.write(f"- Индекс городской среды: {rep['social']['urban_env_index']}")
                st.write(f"- Обеспеченность детсадами: {rep['social']['kindergartens_per_100']} мест на 100 детей")
                st.write(f"- Профильные колледжи: {rep['social']['colleges']}")
                st.write(f"- Средняя аренда 1-к квартиры: {rep['social']['avg_rent_1room']} руб/мес")

                st.markdown("### 💰 Экономика")
                st.write(f"- Льготы (ТОР/ОЭЗ): {'Да' if rep['economic']['tax_incentives'] else 'Нет'}")
                st.write(f"- Пониженные страх. взносы: {'Да' if rep['economic']['reduced_insurance'] else 'Нет'}")
                st.write(f"- Энерготариф: {rep['economic']['energy_tariff']} руб/кВт·ч")
                st.write(f"- Средняя зарплата: {rep['economic']['avg_salary']} руб/мес")

                st.markdown("### 🔌 Сетевая инфраструктура")
                st.write(f"- Газ: {'Есть' if rep['networks']['gas_available'] else 'Нет'}")
                st.write(f"- Свободная мощность: {rep['networks']['free_power_kva']} кВА")
                st.write(f"- Стоимость подключения: {rep['networks']['connection_cost_per_kw']} руб/кВт")
                st.write(f"- Оценочная стоимость ТП: {rep['networks']['total_connection_rub']:,.0f} руб")

                st.markdown("### 🚛 Логистика")
                st.write(f"- До поставщика стали: {rep['logistics']['steel_supplier_km']} км")
                st.write(f"- До поставщика утеплителя: {rep['logistics']['insulation_supplier_km']} км")
                st.write(f"- До федеральной трассы: {rep['logistics']['highway_km']} км")
                st.write(f"- Ж/д ветка: {'Есть' if rep['logistics']['railway'] else 'Нет'}")

                st.markdown("### 📐 Расчёт площадей")
                areas = rep["areas"]
                df_areas = {"Объект": list(areas.keys()), "Площадь (м²)": list(areas.values())}
                st.table(df_areas)

                st.markdown(f"### 🏗 Предварительная смета строительства")
                st.metric("Общая стоимость (млн руб)", f'{rep["cost_million_rub"]} млн ₽')
                st.caption("Включает цех, склад, АБК, дороги, жильё, соцобъекты и благоустройство.")
            else:
                st.error("Не удалось сформировать отчёт")