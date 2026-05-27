from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from data import REGIONS
import math

app = FastAPI(title="SmartIndustry API")

class UserInput(BaseModel):
    volume: int                     # тыс. м² в год
    employees: int
    budget: int                     # млн руб
    railway: bool
    max_highway: int                # км
    arch_priority: str
    landscaping: List[str] = []     # до 3 пунктов
    housing_pct: float              # 0, 0.3, 0.5, 0.7
    housing_type: str               # "общежитие" / "квартиры"
    kindergarten_per_100: int       # мест на 100 сотрудников
    sports: List[str] = []          # до 2 пунктов

def score_region(region, inp: UserInput) -> float:
    # Фильтрация
    if inp.railway and not region["railway_available"]:
        return -1
    if region["highway_distance_km"] > inp.max_highway:
        return -1
    # Требуемая мощность (примем 500 кВА для любого объёма)
    required_power = 500
    if region["substation_free_power_kva"] < required_power:
        return -1
    # Бюджет на подключение (переводим млн руб в рубли)
    connection_cost = (required_power * region["connection_cost_rub_per_kw"]) / 1_000_000
    if connection_cost > inp.budget:
        return -1

    # Нормировка и взвешивание (веса выбраны экспертно)
    scores = {}
    # Логистика сырья (чем ближе, тем лучше)
    scores["steel"] = max(0, 1 - region["steel_distance_km"] / 1000) * 0.15
    scores["insulation"] = max(0, 1 - region["insulation_distance_km"] / 1000) * 0.10
    # Экономика
    scores["tax"] = 0.2 if region["tax_incentives"] else 0
    scores["insurance"] = 0.15 if region["has_reduced_insurance"] else 0
    scores["tariff"] = max(0, 1 - region["energy_tariff"] / 10) * 0.15
    scores["salary"] = max(0, 1 - region["average_salary"] / 100_000) * 0.05
    # Сети
    scores["gas"] = 0.1 if region["gas_available"] else 0
    scores["power"] = min(1.0, region["substation_free_power_kva"] / 2000) * 0.05
    scores["connect_cost"] = max(0, 1 - region["connection_cost_rub_per_kw"] / 20000) * 0.05
    # Социалка (для привлечения кадров)
    scores["env"] = min(1.0, region["urban_env_index"] / 300) * 0.05
    scores["kids"] = min(1.0, region["kindergartens_per_100"] / 100) * 0.03
    scores["colleges"] = min(1.0, region["vocational_colleges"] / 20) * 0.02

    total = sum(scores.values())
    return round(total, 4)

@app.post("/rank_regions")
def rank_regions(inp: UserInput):
    results = []
    for reg in REGIONS:
        score = score_region(reg, inp)
        if score >= 0:
            results.append({
                "name": reg["name"],
                "lat": reg["lat"],
                "lon": reg["lon"],
                "score": score,
                "energy_tariff": reg["energy_tariff"],
                "gas": reg["gas_available"],
                "tax_incentives": reg["tax_incentives"],
                "avg_rent": reg["avg_rent_1room"],
                "steel_km": reg["steel_distance_km"],
                "connection_cost_rub": reg["connection_cost_rub_per_kw"] * 500,
                "profile": reg["cultural_profile"]
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:3]

@app.post("/generate_report")
def generate_report(inp: UserInput, region_name: str):
    reg = next((r for r in REGIONS if r["name"] == region_name), None)
    if not reg:
        return {"error": "Регион не найден"}

    # Расчёт площадей (раздел 6 ТЗ)
    vol = inp.volume
    emp = inp.employees
    area_ceil = vol * 0.4          # цех
    area_sklad = area_ceil * 0.35
    area_abk = area_ceil * 0.02
    area_park = emp * 0.5 * 25
    area_roads = (area_ceil + area_sklad) * 0.25
    # Жильё
    if inp.housing_pct > 0:
        coef = 25 if inp.housing_type == "общежитие" else 40
        area_zhil = emp * inp.housing_pct * coef
    else:
        area_zhil = 0
    # Детский сад
    area_sad = (emp / 100) * inp.kindergarten_per_100 * 15
    area_stolovaya = emp * 0.5
    area_med = max(emp * 0.1, 20)

    total_land = area_ceil + area_sklad + area_abk + area_park + area_roads + area_zhil + area_sad + area_stolovaya + area_med

    # Смета (руб)
    cost_ceil_sklad = (area_ceil + area_sklad) * 35_000
    cost_abk = area_abk * 55_000
    cost_zhil = area_zhil * (70_000 if inp.housing_type == "общежитие" else 90_000)
    cost_sad = area_sad * 50_000
    cost_stol = area_stolovaya * 35_000
    cost_med = area_med * 45_000
    cost_roads_park = (area_roads + area_park) * 5_000
    cost_blag = total_land * 2_000  # благоустройство всей территории
    # Спортивные объекты
    sport_cost = 0
    for s in inp.sports:
        if s == "Стадион": sport_cost += 5_000_000
        elif s == "Бассейн": sport_cost += 8_000_000
        elif s == "Спортзал": sport_cost += 3_000_000
        elif s == "Хоккейная коробка": sport_cost += 2_000_000
        elif s in ("Уличные тренажёры", "Уличные тренажеры"):
            sport_cost += 500_000  # примерная оценка
    total_cost = (cost_ceil_sklad + cost_abk + cost_zhil + cost_sad +
                  cost_stol + cost_med + cost_roads_park + cost_blag + sport_cost)

    report = {
        "region": reg["name"],
        "social": {
            "urban_env_index": reg["urban_env_index"],
            "kindergartens_per_100": reg["kindergartens_per_100"],
            "colleges": reg["vocational_colleges"],
            "avg_rent_1room": reg["avg_rent_1room"]
        },
        "economic": {
            "tax_incentives": reg["tax_incentives"],
            "reduced_insurance": reg["has_reduced_insurance"],
            "energy_tariff": reg["energy_tariff"],
            "avg_salary": reg["average_salary"]
        },
        "networks": {
            "gas_available": reg["gas_available"],
            "free_power_kva": reg["substation_free_power_kva"],
            "connection_cost_per_kw": reg["connection_cost_rub_per_kw"],
            "total_connection_rub": reg["connection_cost_rub_per_kw"] * 500
        },
        "logistics": {
            "steel_supplier_km": reg["steel_distance_km"],
            "insulation_supplier_km": reg["insulation_distance_km"],
            "highway_km": reg["highway_distance_km"],
            "railway": reg["railway_available"]
        },
        "areas": {
            "цех": round(area_ceil, 1),
            "склад": round(area_sklad, 1),
            "АБК": round(area_abk, 1),
            "парковка": round(area_park, 1),
            "дороги": round(area_roads, 1),
            "жильё": round(area_zhil, 1),
            "детский сад": round(area_sad, 1),
            "столовая": round(area_stolovaya, 1),
            "медпункт": round(area_med, 1),
            "общая площадь участка": round(total_land, 1)
        },
        "cost_million_rub": round(total_cost / 1_000_000, 2)
    }
    return report