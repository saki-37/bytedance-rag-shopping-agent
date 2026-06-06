#!/usr/bin/env python3
"""Build a thin all-category enrichment layer from the official raw catalog.

The hand-curated beauty and apparel samples remain the deep enrichment layer.
This script fills the rest of the 100 official products with conservative,
source-bound structured fields so every raw product can enter retrieval, cards,
and evidence-aware generation without pretending all categories have equal depth.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "ecommerce_agent_dataset"
ENRICHED_DIR = ROOT / "data" / "enriched"
OUTPUT = ENRICHED_DIR / "thin_products.jsonl"

CATEGORY_TO_CANONICAL = {
    "美妆护肤": "beauty",
    "数码电子": "digital",
    "服饰运动": "apparel",
    "食品饮料": "food",
}

CATEGORY_BOUNDARIES = {
    "digital": "未在资料中明确的芯片、续航、兼容性、库存和优惠不做推断。",
    "apparel": "尺码、材质、防水和支撑表现只按资料描述表达；实际合身仍建议结合尺码表或试穿。",
    "food": "糖分、咖啡因、过敏原和健康影响只在资料明确说明时表达，不做治疗或减肥承诺。",
    "beauty": "肤质、成分和刺激风险只按资料明确内容表达；敏感场景建议先做局部测试。",
}

USE_CASE_TERMS = [
    "通勤",
    "办公",
    "网课",
    "做笔记",
    "学习",
    "剪视频",
    "拍照",
    "游戏",
    "出差",
    "旅行",
    "户外",
    "跑步",
    "健身",
    "徒步",
    "篮球",
    "瑜伽",
    "早餐",
    "下午茶",
    "提神",
    "送礼",
    "办公室",
    "火锅",
]

TARGET_USER_TERMS = [
    "学生党",
    "高校学生",
    "上班族",
    "职场",
    "打工人",
    "内容创作者",
    "运动党",
    "减脂人群",
    "控糖人群",
    "咖啡爱好者",
    "户外爱好者",
]

CATEGORY_KEYWORDS = {
    "digital": [
        "高刷",
        "续航",
        "快充",
        "轻薄",
        "多任务",
        "降噪",
        "拍照",
        "剪辑",
        "办公",
        "网课",
        "存储",
        "5G",
        "Wi-Fi",
    ],
    "apparel": [
        "速干",
        "透气",
        "防水",
        "防泼水",
        "抓地",
        "缓震",
        "纯棉",
        "棉感",
        "轻薄",
        "宽松",
        "保暖",
        "支撑",
    ],
    "food": [
        "0糖",
        "无糖",
        "低糖",
        "0脂",
        "0卡",
        "咖啡因",
        "便携",
        "独立小包装",
        "礼盒",
        "冻干",
        "提神",
        "解腻",
    ],
}

SEARCH_ALIASES = {
    "智能手机": ["手机", "拍照手机", "旗舰手机"],
    "笔记本电脑": ["笔记本", "电脑", "轻薄本", "办公本"],
    "平板电脑": ["平板", "学习平板", "办公平板", "网课平板"],
    "真无线耳机": ["耳机", "蓝牙耳机", "降噪耳机"],
    "短袖T恤": ["T恤", "短袖", "白T", "速干衣"],
    "速干T恤": ["速干衣", "跑步短袖", "训练T恤"],
    "运动短裤": ["短裤", "训练裤", "速干短裤"],
    "跑步鞋": ["慢跑鞋", "公路跑鞋", "缓震跑鞋"],
    "篮球鞋": ["实战篮球鞋", "球鞋"],
    "徒步鞋": ["登山鞋", "防水鞋", "户外鞋"],
    "背包": ["双肩包", "电脑包", "通勤包"],
    "咖啡": ["速溶咖啡", "冻干咖啡", "提神咖啡"],
    "茶饮": ["无糖茶", "瓶装茶"],
    "碳酸饮料": ["气泡水", "苏打水", "快乐水"],
    "功能饮料": ["能量饮料", "提神饮料"],
    "坚果/零食": ["零食", "下午茶", "坚果"],
    "方便食品": ["泡面", "速食", "方便面"],
}


def main() -> None:
    raw_products = load_raw_products()
    covered_ids = load_deep_enriched_ids()
    rows = [build_thin_row(item) for item in raw_products if item["product_id"] not in covered_ids]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["canonical_category"])] += 1
    print(f"Wrote {len(rows)} thin enriched products to {OUTPUT}: {dict(sorted(counts.items()))}")


def load_raw_products() -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for path in sorted(RAW_ROOT.glob("*/data/*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        item["_raw_path"] = str(path)
        products.append(item)
    return products


def load_deep_enriched_ids() -> set[str]:
    covered: set[str] = set()
    for path in sorted(ENRICHED_DIR.glob("*_products.jsonl")):
        if path == OUTPUT:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            covered.add(str(json.loads(line)["raw_product_id"]))
    return covered


def build_thin_row(raw: dict[str, Any]) -> dict[str, Any]:
    canonical = CATEGORY_TO_CANONICAL[str(raw["category"])]
    text = product_text(raw)
    dimensions = sku_dimensions(raw)
    use_cases = matched_terms(text, USE_CASE_TERMS)
    target_users = matched_terms(text, TARGET_USER_TERMS)
    keywords = matched_terms(text, CATEGORY_KEYWORDS.get(canonical, []))
    risks = review_risks(raw)
    boundary = CATEGORY_BOUNDARIES[canonical]
    tags = unique([raw["sub_category"], *keywords, *use_cases])[:5]
    selling_points = unique([first_sentence(raw["rag_knowledge"]["marketing_description"]), *keywords])[:5]

    return {
        "schema_version": "2.0-thin",
        "raw_product_id": raw["product_id"],
        "canonical_category": canonical,
        "source": build_source(raw, dimensions, keywords),
        "variants": {
            "variant_dimensions": build_variant_dimensions(dimensions),
            "raw_sku_summary": sku_summary(dimensions),
        },
        "display": {
            "card_reason": card_reason(raw, keywords, use_cases),
            "detail_highlights": detail_highlights(raw, selling_points, dimensions),
            "detail_cautions": unique([boundary, *risks])[:4],
            "comparison_summary": comparison_summary(raw, keywords, use_cases),
        },
        "attributes": {
            "target_users": target_users,
            "use_cases": use_cases,
            "selling_points": selling_points,
            "cautions": unique([boundary]),
            "avoid_for": [],
            "suitable_for": unique([*target_users, *use_cases])[:5],
            "tags": tags,
            "decision_factors": decision_factors(canonical),
            "quality_risks": risks,
            "care_or_usage_notes": usage_notes(raw, canonical),
            "specifications": specifications(raw, dimensions),
        },
        "category_attributes": category_attributes(raw, canonical, dimensions, keywords, use_cases, text),
        "retrieval": retrieval_fields(raw, canonical, dimensions, keywords, use_cases, risks),
        "graph": graph_fields(raw, canonical, keywords, use_cases),
    }


def product_text(raw: dict[str, Any]) -> str:
    knowledge = raw.get("rag_knowledge", {})
    faq_text = " ".join(
        f"{item.get('question', '')} {item.get('answer', '')}"
        for item in knowledge.get("official_faq", [])
        if isinstance(item, dict)
    )
    review_text = " ".join(
        str(item.get("content", ""))
        for item in knowledge.get("user_reviews", [])
        if isinstance(item, dict)
    )
    return " ".join(
        [
            str(raw.get("title", "")),
            str(raw.get("brand", "")),
            str(raw.get("category", "")),
            str(raw.get("sub_category", "")),
            str(knowledge.get("marketing_description", "")),
            faq_text,
            review_text,
        ]
    )


def sku_dimensions(raw: dict[str, Any]) -> dict[str, list[str]]:
    dimensions: dict[str, list[str]] = defaultdict(list)
    for sku in raw.get("skus", []):
        properties = sku.get("properties", {}) if isinstance(sku, dict) else {}
        if not isinstance(properties, dict):
            continue
        for key, value in properties.items():
            value_text = str(value).strip()
            if value_text and value_text not in dimensions[str(key)]:
                dimensions[str(key)].append(value_text)
    if not dimensions:
        dimensions["SKU"] = ["默认规格"]
    return dict(dimensions)


def build_variant_dimensions(dimensions: dict[str, list[str]]) -> list[dict[str, object]]:
    return [
        {"name": name, "values": values, "affects": affects_for_dimension(name)}
        for name, values in dimensions.items()
    ]


def affects_for_dimension(name: str) -> list[str]:
    if any(term in name for term in ["颜色", "配色"]):
        return ["style", "image", "sku"]
    if any(term in name for term in ["尺码", "鞋楦", "款型", "适用人群"]):
        return ["fit", "sku"]
    if any(term in name for term in ["存储", "内存", "容量"]):
        return ["capacity", "price", "sku"]
    if any(term in name for term in ["网络", "版本"]):
        return ["version", "price", "sku"]
    if any(term in name for term in ["口味", "包装", "数量"]):
        return ["preference", "package", "sku"]
    return ["sku"]


def sku_summary(dimensions: dict[str, list[str]]) -> str:
    return "；".join(f"{name}含{'、'.join(values[:8])}" for name, values in dimensions.items())


def build_source(raw: dict[str, Any], dimensions: dict[str, list[str]], keywords: list[str]) -> dict[str, object]:
    provenance: list[dict[str, str]] = [
        provenance_row("raw.category", "raw.category", str(raw["category"])),
        provenance_row("raw.sub_category", "raw.sub_category", str(raw["sub_category"])),
        provenance_row("raw.base_price", "raw.base_price", f"{raw['base_price']:g}"),
        provenance_row("raw.title", "raw.title", str(raw["title"])),
    ]
    for name, values in dimensions.items():
        provenance.append(
            provenance_row(
                "variants.variant_dimensions",
                f"raw.skus.properties.{name}",
                f"{name}: {'、'.join(values[:8])}",
            )
        )
    for keyword in keywords[:4]:
        provenance.append(
            provenance_row(
                "attributes.selling_points",
                "raw.rag_knowledge.marketing_description/faq/reviews",
                keyword,
            )
        )
    return {
        "source_docs": [
            "raw.title",
            "raw.brand",
            "raw.category",
            "raw.base_price",
            "raw.skus",
            "raw.rag_knowledge.marketing_description",
            "raw.rag_knowledge.official_faq",
            "raw.rag_knowledge.user_reviews",
        ],
        "attribute_provenance": provenance,
    }


def provenance_row(field: str, source_path: str, evidence: str) -> dict[str, str]:
    return {
        "field": field,
        "source_path": source_path,
        "evidence": evidence[:120],
        "confidence": "explicit",
    }


def card_reason(raw: dict[str, Any], keywords: list[str], use_cases: list[str]) -> str:
    signals = unique([*keywords, *use_cases])[:3]
    if signals:
        return f"{raw['sub_category']}商品，资料明确涉及{'、'.join(signals)}，数据源基础价格 ¥{raw['base_price']:g}。"
    return f"{raw['sub_category']}商品，基础价格 ¥{raw['base_price']:g}，可按标题、SKU、FAQ 和用户评价做资料内推荐。"


def detail_highlights(raw: dict[str, Any], selling_points: list[str], dimensions: dict[str, list[str]]) -> list[str]:
    highlights = [
        f"品牌：{raw['brand']}；类目：{raw['category']} / {raw['sub_category']}",
        f"数据源基础价格：¥{raw['base_price']:g}",
    ]
    if selling_points:
        highlights.append(selling_points[0])
    if dimensions:
        highlights.append(sku_summary(dimensions))
    return highlights[:4]


def comparison_summary(raw: dict[str, Any], keywords: list[str], use_cases: list[str]) -> str:
    focus = "、".join(unique([*keywords, *use_cases])[:3]) or "价格、规格和资料内卖点"
    return f"对比同类商品时，可优先看{focus}；未写明的参数不做推断。"


def decision_factors(canonical: str) -> list[str]:
    common = ["价格", "品牌", "子类目", "SKU规格", "用户评价风险"]
    category_specific = {
        "digital": ["使用场景", "性能/屏幕/存储资料", "生态兼容性"],
        "apparel": ["材质", "尺码", "运动或天气场景"],
        "food": ["口味", "包装规格", "糖分/咖啡因等资料内声明"],
        "beauty": ["肤质", "功效", "成分和注意事项"],
    }
    return [*common, *category_specific.get(canonical, [])]


def usage_notes(raw: dict[str, Any], canonical: str) -> list[str]:
    text = product_text(raw)
    notes: list[str] = []
    for term in ["阴凉", "避光", "开封", "冷水", "中性洗涤", "不要暴晒", "补涂", "充电", "热点"]:
        if term in text:
            notes.append(term)
    if canonical == "food" and not notes:
        notes.append("保存和饮用方式以商品资料为准。")
    return unique(notes)[:5]


def specifications(raw: dict[str, Any], dimensions: dict[str, list[str]]) -> list[dict[str, str]]:
    specs = [
        {"section": "基础信息", "name": "品牌", "value": str(raw["brand"])},
        {"section": "基础信息", "name": "类目", "value": f"{raw['category']} / {raw['sub_category']}"},
        {"section": "价格", "name": "基础价格", "value": f"¥{raw['base_price']:g}"},
    ]
    for name, values in dimensions.items():
        specs.append({"section": "SKU", "name": name, "value": "、".join(values[:12])})
    return specs


def category_attributes(
    raw: dict[str, Any],
    canonical: str,
    dimensions: dict[str, list[str]],
    keywords: list[str],
    use_cases: list[str],
    text: str,
) -> dict[str, object]:
    if canonical == "digital":
        return {"digital": digital_attributes(raw, dimensions, keywords, use_cases, text)}
    if canonical == "apparel":
        return {"apparel": apparel_attributes(raw, dimensions, keywords, use_cases, text)}
    if canonical == "food":
        return {"food": food_attributes(raw, dimensions, keywords, use_cases, text)}
    return {"beauty": {}}


def digital_attributes(raw: dict[str, Any], dimensions: dict[str, list[str]], keywords: list[str], use_cases: list[str], text: str) -> dict[str, object]:
    return {
        "device_type": raw["sub_category"],
        "usage_scenarios": use_cases,
        "performance_level": first_match(text, ["旗舰", "高性能", "入门", "生产力"]),
        "processor": first_regex(text, r"(A\d+\s*Pro|M\d+|骁龙\s*\w+|锐龙\w*)"),
        "memory_options": dimension_values(dimensions, ["内存"]),
        "storage_options": dimension_values(dimensions, ["存储"]),
        "screen_features": matched_terms(text, ["高刷", "2K", "120Hz", "OLED", "护眼", "大屏"]),
        "battery_level": "资料提到续航" if "续航" in text else "",
        "charging_features": matched_terms(text, ["快充", "无线充", "65W", "120W"]),
        "camera_features": matched_terms(text, ["拍照", "影像", "摄像", "长焦", "人像"]),
        "portability": first_match(text, ["轻薄", "便携", "重量"]),
        "ecosystem": matched_terms(text, ["鸿蒙", "华为", "Apple", "苹果", "小米"]),
        "connectivity": unique([*dimension_values(dimensions, ["网络", "版本"]), *matched_terms(text, ["5G", "Wi-Fi", "蓝牙"])]),
        "compatibility_notes": ["跨设备、生态和兼容性只按商品资料明确内容表达。"],
        "avoid_conditions": ["资料未明确的芯片、续航、兼容性、库存和优惠不做推断。"],
    }


def apparel_attributes(raw: dict[str, Any], dimensions: dict[str, list[str]], keywords: list[str], use_cases: list[str], text: str) -> dict[str, object]:
    return {
        "item_type": raw["sub_category"],
        "materials": matched_terms(text, ["纯棉", "棉", "聚酯纤维", "GORE-TEX", "牛津纺", "羊毛", "网布", "速干纤维"]),
        "material_notes": [],
        "fit": first_match(text, ["宽松", "修身", "标准", "高腰", "中帮", "低帮"]),
        "size_range": dimension_values(dimensions, ["尺码", "鞋楦", "款型"]),
        "size_notes": ["尺码建议以商品资料和实际试穿为准。"],
        "colors": dimension_values(dimensions, ["颜色", "配色"]),
        "season": matched_terms(text, ["夏天", "夏季", "春秋", "四季", "冬季"]),
        "style": matched_terms(text, ["通勤", "休闲", "基础", "户外", "训练", "运动"]),
        "sport_scenarios": matched_terms(text, ["跑步", "健身", "徒步", "篮球", "瑜伽", "训练", "登山"]),
        "weather_conditions": matched_terms(text, ["防水", "防泼水", "雨天", "炎热", "出汗", "湿滑"]),
        "breathability": "资料提到透气/速干" if any(term in text for term in ["透气", "速干", "导湿"]) else "",
        "warmth_level": first_match(text, ["保暖", "轻薄"]),
        "support_level": first_match(text, ["支撑", "缓震", "抓地"]),
        "waterproof_level": first_match(text, ["GORE-TEX", "防水", "防泼水"]),
        "durability_notes": review_risks(raw),
        "care_instructions": usage_notes(raw, "apparel"),
        "avoid_conditions": ["尺码、材质、防水和支撑表现只按资料描述表达。"],
    }


def food_attributes(raw: dict[str, Any], dimensions: dict[str, list[str]], keywords: list[str], use_cases: list[str], text: str) -> dict[str, object]:
    return {
        "food_type": raw["sub_category"],
        "flavors": dimension_values(dimensions, ["口味"]),
        "flavor_profile": matched_terms(text, ["白桃", "柑橘", "焦糖", "坚果", "清爽", "醇厚", "酸", "甜", "苦", "辣"]),
        "sugar_level": first_match(text, ["0糖", "无糖", "低糖", "赤藓糖醇"]),
        "caffeine": "资料提到咖啡因" if "咖啡因" in text else "",
        "package_type": "、".join(dimension_values(dimensions, ["包装"])) if dimension_values(dimensions, ["包装"]) else "",
        "count_or_weight": "、".join(dimension_values(dimensions, ["数量", "容量", "总袋数", "整箱盒数", "单盒容量"])) ,
        "eating_scenarios": use_cases,
        "storage_notes": matched_terms(text, ["阴凉", "避光", "冷藏", "开封", "尽快喝完", "干燥处"]),
        "dietary_preferences": matched_terms(text, ["0糖", "无糖", "低糖", "减脂", "控糖", "0脂", "0卡"]),
        "allergens": matched_terms(text, ["过敏原", "乳", "坚果", "小麦"]),
        "ingredient_highlights": matched_terms(text, ["阿拉比卡", "赤藓糖醇", "牛磺酸", "咖啡因", "有机奶源"]),
        "health_claim_cautions": ["食品健康、控糖、提神和过敏相关表达只能基于资料明确内容，不能替代专业建议。"],
        "avoid_conditions": ["资料未明确的过敏原、健康功效或适用禁忌不做推断。"],
    }


def retrieval_fields(
    raw: dict[str, Any],
    canonical: str,
    dimensions: dict[str, list[str]],
    keywords: list[str],
    use_cases: list[str],
    risks: list[str],
) -> dict[str, list[str]]:
    return {
        "hard_filter_facets": unique(
            [
                f"category:{raw['category']}",
                f"canonical_category:{canonical}",
                f"sub_category:{raw['sub_category']}",
                f"price_bucket:{price_bucket(float(raw['base_price']))}",
                *[f"{name}:{'、'.join(values[:4])}" for name, values in dimensions.items()],
            ]
        ),
        "soft_preference_facets": unique([*keywords, *use_cases]),
        "negative_facets": risks,
        "search_aliases": unique([raw["brand"], raw["sub_category"], *SEARCH_ALIASES.get(raw["sub_category"], [])]),
        "evidence_fields": [
            "raw.title",
            "raw.brand",
            "raw.base_price",
            "raw.skus",
            "raw.rag_knowledge",
            "attributes.specifications",
            f"category_attributes.{canonical}",
            "source.attribute_provenance",
        ],
    }


def graph_fields(raw: dict[str, Any], canonical: str, keywords: list[str], use_cases: list[str]) -> dict[str, list[dict[str, str]]]:
    nodes = [
        {"type": "product", "id": raw["product_id"]},
        {"type": "category", "id": canonical},
        {"type": "sub_category", "id": raw["sub_category"]},
    ]
    edges = [
        {"from": raw["product_id"], "relation": "belongs_to", "to": canonical},
        {"from": raw["product_id"], "relation": "has_sub_category", "to": raw["sub_category"]},
    ]
    for keyword in unique([*keywords, *use_cases])[:3]:
        nodes.append({"type": "facet", "id": keyword})
        edges.append({"from": raw["product_id"], "relation": "mentions", "to": keyword})
    return {"nodes": nodes, "edges": edges}


def review_risks(raw: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    for review in raw.get("rag_knowledge", {}).get("user_reviews", []):
        if not isinstance(review, dict):
            continue
        rating = int(review.get("rating", 5) or 5)
        content = str(review.get("content", "")).strip()
        if rating <= 3 and content:
            risks.append(f"用户评价提到：{content[:36]}")
    return unique(risks)[:3]


def dimension_values(dimensions: dict[str, list[str]], keys: list[str]) -> list[str]:
    values: list[str] = []
    for name, items in dimensions.items():
        if any(key in name for key in keys):
            values.extend(items)
    return unique(values)


def matched_terms(text: str, terms: list[str]) -> list[str]:
    return unique([term for term in terms if term and term in text])


def first_match(text: str, terms: list[str]) -> str:
    for term in terms:
        if term in text:
            return term
    return ""


def first_regex(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def first_sentence(text: str, limit: int = 84) -> str:
    sentence = re.split(r"[。！？!?]", str(text).strip())[0].strip()
    return sentence[:limit]


def price_bucket(price: float) -> str:
    if price <= 100:
        return "100元以内"
    if price <= 300:
        return "300元以内"
    if price <= 1000:
        return "1000元以内"
    if price <= 5000:
        return "5000元以内"
    return "5000元以上"


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        value = str(value).strip()
        if value and value not in result:
            result.append(value)
    return result


if __name__ == "__main__":
    main()
