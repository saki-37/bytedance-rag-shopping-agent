#!/usr/bin/env python3
"""Build the first manually curated beauty enrichment layer."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "ecommerce_agent_dataset"
OUTPUT = ROOT / "data" / "enriched" / "beauty_products.jsonl"


ANNOTATIONS: dict[str, dict] = {
    "p_beauty_006": {
        "attributes": {
            "target_users": ["油皮", "混油皮", "通勤人群", "学生党"],
            "use_cases": ["日常通勤防晒", "短途户外", "妆前打底"],
            "selling_points": ["SPF50+ PA++++", "水感轻薄", "自然提亮", "200元以内"],
            "cautions": ["敏感肌先做耳后测试", "长时间户外需2-3小时补涂"],
            "avoid_for": ["长时间大量出汗场景", "对防晒剂敏感人群"],
            "suitable_for": ["油皮", "混油皮", "追求清爽肤感的人"],
            "tags": ["防晒", "油皮", "通勤", "轻薄", "200元以内"],
        },
        "beauty_attributes": {
            "skin_types": ["油皮", "混油皮"],
            "skin_concerns": ["出油", "防晒", "暗沉"],
            "product_effects": ["防晒", "修护", "提亮"],
            "key_ingredients": ["玻尿酸", "维生素E"],
            "texture": "水感轻薄",
            "spf": "SPF50+",
            "pa": "PA++++",
            "makeup_compatibility": "可叠加粉底或散粉",
            "sensitive_skin_note": "敏感肌需先做耳后测试",
            "avoid_conditions": ["大量出汗后不补涂", "眼周或破损肌肤"],
        },
        "card_reason": "SPF50+ PA++++，水感轻薄，适合油皮/混油皮通勤防晒，价格在200元以内。",
    },
    "p_beauty_010": {
        "attributes": {
            "target_users": ["户外活动人群", "需要防水防汗的人", "面部身体防晒需求"],
            "use_cases": ["海边", "爬山", "长时间户外", "运动防晒"],
            "selling_points": ["高倍防晒", "防水防汗", "户外适用"],
            "cautions": ["需要卸妆清洁", "敏感肌先测试", "户外仍需补涂"],
            "avoid_for": ["不喜欢成膜感的人", "只需要轻薄通勤的人"],
            "suitable_for": ["户外场景", "运动场景", "需要防水防汗的人"],
            "tags": ["防晒", "户外", "防水防汗", "高倍防晒"],
        },
        "beauty_attributes": {
            "skin_types": ["多数肤质"],
            "skin_concerns": ["防晒", "晒黑", "晒伤"],
            "product_effects": ["防晒", "防水", "防汗"],
            "key_ingredients": [],
            "texture": "成膜感较强",
            "spf": "高倍防晒",
            "pa": "",
            "makeup_compatibility": "更偏户外防护，不主打妆前轻薄",
            "sensitive_skin_note": "敏感肌需先做局部测试",
            "avoid_conditions": ["讨厌成膜感", "清洁不到位"],
        },
        "card_reason": "更适合长时间户外或运动防晒，防水防汗比轻薄通勤款更突出。",
    },
    "p_beauty_007": {
        "attributes": {
            "target_users": ["敏感肌", "屏障受损人群", "干痒泛红人群"],
            "use_cases": ["屏障修护", "换季维稳", "保湿舒缓"],
            "selling_points": ["舒敏保湿", "修护屏障", "舒缓干痒"],
            "cautions": ["严重敏感期建议先少量试用", "如持续刺痛应停止使用"],
            "avoid_for": ["只追求强功效抗老的人"],
            "suitable_for": ["敏感肌", "干敏肌", "屏障不稳定人群"],
            "tags": ["敏感肌", "修护", "保湿", "面霜", "屏障"],
        },
        "beauty_attributes": {
            "skin_types": ["敏感肌", "干敏肌"],
            "skin_concerns": ["屏障受损", "干痒", "泛红", "缺水"],
            "product_effects": ["舒缓", "保湿", "修护屏障"],
            "key_ingredients": [],
            "texture": "面霜",
            "spf": "",
            "pa": "",
            "makeup_compatibility": "适合护肤保湿步骤，不是底妆产品",
            "sensitive_skin_note": "敏感肌友好，但仍建议先局部测试",
            "avoid_conditions": ["急性红肿刺痛未缓解时大面积使用"],
        },
        "card_reason": "主打敏感肌舒缓保湿和屏障修护，适合屏障不稳定时作为温和选项。",
    },
    "p_beauty_012": {
        "attributes": {
            "target_users": ["敏感肌", "干皮", "需要滋润修护的人"],
            "use_cases": ["夜间修护", "换季保湿", "干皮滋润"],
            "selling_points": ["敏感肌适用", "滋润型", "修护屏障"],
            "cautions": ["油皮可能觉得厚重", "首次使用先局部测试"],
            "avoid_for": ["大油皮", "讨厌厚重肤感的人"],
            "suitable_for": ["干皮", "敏感肌", "屏障修护需求"],
            "tags": ["敏感肌", "干皮", "修护", "保湿", "面霜"],
        },
        "beauty_attributes": {
            "skin_types": ["干皮", "敏感肌"],
            "skin_concerns": ["干燥", "屏障脆弱", "泛红"],
            "product_effects": ["保湿", "舒缓", "修护"],
            "key_ingredients": [],
            "texture": "滋润型面霜",
            "spf": "",
            "pa": "",
            "makeup_compatibility": "更适合护肤修护，妆前需控制用量",
            "sensitive_skin_note": "敏感肌适用但仍需先测试",
            "avoid_conditions": ["油皮白天厚涂"],
        },
        "card_reason": "滋润修护取向更强，适合干皮或敏感肌做屏障修护。",
    },
    "p_beauty_018": {
        "attributes": {
            "target_users": ["油皮", "毛孔粗大人群", "预算有限的人"],
            "use_cases": ["控油", "平衡油脂", "提亮肤色", "入门功效精华"],
            "selling_points": ["烟酰胺", "平衡油脂", "淡化毛孔", "百元以内"],
            "cautions": ["高浓度烟酰胺可能刺激", "敏感肌需建立耐受"],
            "avoid_for": ["烟酰胺不耐受人群", "急性敏感肌"],
            "suitable_for": ["油皮", "预算有限", "想尝试控油提亮的人"],
            "tags": ["精华", "油皮", "提亮", "控油", "百元以内"],
        },
        "beauty_attributes": {
            "skin_types": ["油皮", "混油皮"],
            "skin_concerns": ["出油", "毛孔", "暗沉"],
            "product_effects": ["控油", "提亮", "平衡油脂"],
            "key_ingredients": ["烟酰胺", "锌"],
            "texture": "精华液",
            "spf": "",
            "pa": "",
            "makeup_compatibility": "护肤精华，妆前需等待吸收",
            "sensitive_skin_note": "敏感肌和烟酰胺不耐受者需谨慎",
            "avoid_conditions": ["屏障受损期", "烟酰胺刺痛"],
        },
        "card_reason": "价格低，适合预算有限且想控油提亮的人，但敏感肌要注意耐受。",
    },
    "p_beauty_020": {
        "attributes": {
            "target_users": ["油皮", "混油皮", "需要长时间持妆的人"],
            "use_cases": ["通勤底妆", "夏日控油", "持妆遮瑕"],
            "selling_points": ["持久遮瑕", "控油抗汗", "清透底妆"],
            "cautions": ["干皮可能拔干", "色号需试色", "敏感肌先测试"],
            "avoid_for": ["干皮", "混干皮", "不喜欢哑光妆效的人"],
            "suitable_for": ["油皮", "混油皮", "夏季底妆"],
            "tags": ["底妆", "控油", "油皮", "持妆", "粉底液"],
        },
        "beauty_attributes": {
            "skin_types": ["油皮", "混油皮"],
            "skin_concerns": ["出油", "脱妆", "遮瑕"],
            "product_effects": ["控油", "持妆", "遮瑕"],
            "key_ingredients": ["控油科技"],
            "texture": "清透粉底液",
            "spf": "SPF10",
            "pa": "PA",
            "makeup_compatibility": "底妆产品，可搭配清爽保湿妆前",
            "sensitive_skin_note": "敏感肌先做测试",
            "avoid_conditions": ["干皮直接上妆", "未做好保湿打底"],
        },
        "card_reason": "适合油皮/混油皮长时间持妆和控油需求，干皮可能拔干。",
    },
}


def main() -> None:
    raw_by_id = load_raw_by_id()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for product_id, annotation in ANNOTATIONS.items():
            if product_id not in raw_by_id:
                raise SystemExit(f"Raw product not found: {product_id}")
            row = {"raw_product_id": product_id, **annotation}
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Wrote {len(ANNOTATIONS)} rows to {OUTPUT}")


def load_raw_by_id() -> dict[str, dict]:
    products: dict[str, dict] = {}
    for path in sorted(RAW_ROOT.glob("*/data/*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        products[item["product_id"]] = item
    return products


if __name__ == "__main__":
    main()
