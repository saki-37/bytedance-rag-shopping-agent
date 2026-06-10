"""商品 RAG 检索核心：约束优先的混合检索（不是纯向量搜索）。

主入口 retrieve() 的流水线：
1. parse_query_intent：规则解析预算、类目、肤质/功效/场景 facet、
   否定排除词（"不要含酒精"）、商品指代和是否需要追问澄清。
2. 记忆合并：_apply_memory_profile 把用户/购买对象的硬约束并入 intent。
3. 硬过滤先于打分：预算上限、类目、品牌排除、排除词、必要功效/肤质
   不满足即剔除——违反硬约束的商品不能因为语义相似而被召回。
4. 多路召回打分：keyword 词命中 + facet 匹配 + Chroma 向量分
   （metadata filter 收窄）+ 轻量 graph 关系分 + 用途优先级，加权求和。
5. rerank 与选卡：_select_ranked_scored 控制多样性/对比顺序，
   生成 ProductCard（卡片字段全部来自数据源，不经过模型）。
6. RetrievalTrace 全程记录过滤原因、各通道命中、排序信号与来源证据，
   供 /api/debug/retrieve、评测脚本和答辩复验。

Chunking 口径：商品为最小检索单元（一商品一向量），向量文本由
data_loader.product_search_text 拼接标题/类目/卖点/适用人群等字段；
SKU/规格作为商品内 variants 展示，不单独成 chunk，避免召回碎片化。
"""

import contextlib
import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from app.data_loader import CATEGORY_TO_CANONICAL, product_search_text
from app.embeddings import sentence_model
from app.models import (
    ConstraintTrace,
    FilteredProduct,
    GuardrailChecks,
    ProductCard,
    ProductVariantCard,
    QueryIntent,
    RecipientProfile,
    UserMemoryProfile,
    RetrievalChannels,
    RetrievalHit,
    RetrievalTrace,
    SafetyTrace,
    SourceClaim,
    SourceTrace,
    UniversalConstraints,
)


@dataclass
class RetrievalResult:
    cards: list[ProductCard]
    context: str
    trace: RetrievalTrace
    clarification_question: str | None = None


@dataclass(frozen=True)
class SearchSlot:
    label: str
    category: str | None = None
    sub_categories: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    use_cases: tuple[str, ...] = ()


FACET_LEXICON: dict[str, dict[str, list[str]]] = {
    "skin_type": {
        "油皮": ["油皮", "大油皮", "混油", "混油皮", "出油"],
        "干皮": ["干皮", "混干", "混干皮", "干燥"],
        "敏感肌": ["敏感肌", "敏感", "屏障", "泛红", "刺痛"],
    },
    "effect": {
        "防晒": ["防晒", "spf", "pa", "晒黑", "晒伤"],
        "修护": ["修护", "屏障", "舒缓", "维稳"],
        "保湿": ["保湿", "补水", "滋润", "干燥"],
        "控油": ["控油", "油脂", "出油", "清爽"],
        "提亮": ["提亮", "亮肤", "美白", "暗沉"],
        "淡斑": ["淡斑", "斑点", "色斑", "痘印", "色沉", "色素"],
        "抗初老": ["抗初老", "抗老", "淡纹", "紧致", "抗皱"],
        "清洁": ["清洁", "毛孔污垢"],
        "洁面": ["洁面", "洗面奶", "泡沫洁面"],
        "卸妆": ["卸妆", "卸除", "防水彩妆"],
        "眼周护理": ["眼霜", "眼周", "干纹", "卡粉"],
        "底妆": ["底妆", "粉底", "粉底液", "遮瑕"],
        "定妆": ["定妆", "蜜粉", "散粉", "持妆"],
        "唇妆": ["唇釉", "口红", "唇妆", "显色", "沾杯"],
        "眉妆": ["眉笔", "画眉", "眉妆", "眉尾", "野生眉"],
    },
    "use_case": {
        "通勤": ["通勤", "上班", "日常"],
        "户外": ["户外", "海边", "爬山", "旅行", "三亚"],
        "运动": ["运动", "跑步", "健身", "防汗"],
        "妆前": ["妆前", "打底", "上妆"],
        "夜间": ["夜间", "晚上", "睡前"],
        "约会": ["约会", "聚会", "拍照", "妆造"],
        "出差": ["出差", "旅行装", "便携", "随身"],
        "提神": ["提神", "醒脑", "清醒", "犯困", "早八"],
    },
    "sub_category": {
        "防晒": ["防晒", "防晒霜"],
        "面霜": ["面霜", "霜", "特护霜"],
        "精华": ["精华", "精华液"],
        "卸妆": ["卸妆", "卸妆油"],
        "洁面": ["洁面", "洗面奶", "泡沫洁面"],
        "眼霜": ["眼霜"],
        "蜜粉": ["蜜粉", "散粉"],
        "唇釉": ["唇釉", "口红"],
        "眉笔": ["眉笔"],
        "短袖T恤": ["短袖", "T恤", "t恤", "白T", "基础T", "速干衣"],
        "跑步鞋": ["跑步鞋", "慢跑鞋", "公路跑鞋", "缓震跑鞋"],
        "徒步鞋": ["徒步鞋", "登山鞋", "防水鞋", "户外鞋"],
        "背包": ["背包", "双肩包", "电脑包", "通勤包"],
        "智能手机": ["手机", "智能手机", "拍照手机", "旗舰手机"],
        "笔记本电脑": ["笔记本", "笔记本电脑", "电脑", "轻薄本", "办公本"],
        "平板电脑": ["平板", "平板电脑", "学习平板", "办公平板", "网课平板"],
        "真无线耳机": ["耳机", "蓝牙耳机", "真无线耳机", "降噪耳机"],
        "运动长裤": ["运动长裤", "长裤", "收口裤"],
        "卫衣": ["卫衣", "连帽卫衣"],
        "篮球鞋": ["篮球鞋", "实战篮球鞋", "球鞋"],
        "瑜伽裤": ["瑜伽裤", "紧身裤"],
        "户外裤": ["户外裤", "软壳裤"],
        "帽子": ["帽子", "棒球帽", "鸭舌帽"],
        "速干T恤": ["速干T恤", "速干衣", "跑步短袖", "训练T恤"],
        "运动短裤": ["运动短裤", "短裤", "训练裤", "速干短裤"],
        "咖啡": ["咖啡", "速溶咖啡", "冻干咖啡", "提神咖啡"],
        "茶饮": ["茶饮", "无糖茶", "瓶装茶"],
        "碳酸饮料": ["碳酸饮料", "气泡水", "苏打水", "快乐水"],
        "功能饮料": ["功能饮料", "能量饮料", "提神饮料"],
        "牛奶": ["牛奶", "纯牛奶"],
        "酸奶": ["酸奶", "风味酸奶"],
        "坚果/零食": ["坚果", "零食", "下午茶", "每日坚果"],
        "方便食品": ["方便食品", "方便面", "泡面", "速食"],
        "调味品": ["调味品", "酱油", "生抽"],
    },
}

BEAUTY_TERMS = [
    "美妆",
    "护肤",
    "护肤品",
    "化妆品",
    "防晒",
    "面霜",
    "精华",
    "粉底",
    "底妆",
    "化妆水",
    "爽肤水",
    "洗面奶",
    "洁面",
    "卸妆",
    "定妆",
    "眼霜",
    "唇釉",
    "眉笔",
    "面膜",
    "蜜粉",
    "散粉",
]
APPAREL_TERMS = [
    "服饰",
    "运动类",
    "运动用品",
    "健身",
    "训练",
    "瑜伽",
    "穿搭",
    "搭配",
    "衣服",
    "衣物",
    "帽子",
    "棒球帽",
    "鸭舌帽",
    "防晒衣",
    "裤子",
    "长裤",
    "短裤",
    "户外裤",
    "运动短裤",
    "运动长裤",
    "软壳裤",
    "短袖",
    "t恤",
    "T恤",
    "白T",
    "速干",
    "棉感",
    "纯棉",
    "尺码",
    "版型",
    "跑步鞋",
    "慢跑鞋",
    "徒步鞋",
    "登山鞋",
    "防水鞋",
    "抓地",
    "背包",
    "双肩包",
    "电脑包",
]
DIGITAL_TERMS = [
    "数码",
    "电子",
    "手机",
    "智能手机",
    "平板",
    "平板电脑",
    "笔记本",
    "笔记本电脑",
    "电脑",
    "轻薄本",
    "办公本",
    "耳机",
    "蓝牙耳机",
    "降噪耳机",
    "网课",
    "做笔记",
    "剪辑",
    "拍照",
    "续航",
    "高刷",
]
FOOD_TERMS = [
    "食品",
    "饮料",
    "零食",
    "咖啡",
    "茶饮",
    "无糖茶",
    "气泡水",
    "苏打水",
    "功能饮料",
    "牛奶",
    "酸奶",
    "坚果",
    "方便面",
    "泡面",
    "速食",
    "调味品",
    "早八",
    "下午茶",
    "提神",
    "醒脑",
    "清醒",
    "犯困",
    "控糖",
    "减脂",
]
CATEGORY_TO_RAW = {
    "beauty": "美妆护肤",
    "apparel": "服饰运动",
    "digital": "数码电子",
    "food": "食品饮料",
}
RAW_TO_CATEGORY = {raw: category for category, raw in CATEGORY_TO_RAW.items()}
CATEGORY_NEGATION_PATTERNS = {
    "beauty": [
        r"(?:非|不是|不要|不看|别看|排除|避开|先不看|不想要|不太想要|不考虑).{0,6}(?:美妆|护肤|护肤品|化妆品)",
        r"(?:美妆|护肤|护肤品|化妆品).{0,10}(?:不要|不看|排除|避开|除外|以外|之外|不想要|不太想要|不考虑|不太行)",
    ],
}
ENERGY_PURPOSE_TERMS = ["提神", "醒脑", "清醒", "犯困", "困了", "很困", "犯迷糊"]
ENERGY_SUB_CATEGORIES = ["咖啡", "茶饮", "功能饮料"]
EARLY_ENERGY_CONTEXT_TERMS = ["早八", "早课", "早上", "上午", "上课", "上班", "通勤", "工位", "办公室"]
STRONG_ENERGY_CONTEXT_TERMS = ["熬夜", "通宵", "长途", "开车", "运动", "健身", "训练", "快速补能", "能量饮料", "功能饮料"]
CASUAL_RUNNING_CONTEXT_TERMS = ["偶尔慢跑", "慢跑", "走路", "近郊", "压马路", "日常跑", "入门跑"]
LIGHT_HIKING_CONTEXT_TERMS = ["徒步", "近郊", "郊野", "周末", "走路", "登山", "户外"]
PERFORMANCE_RUNNING_TERMS = ["竞速", "碳板", "马拉松", "全马", "破3", "进阶跑者", "冲速度"]
FOOD_SUB_CATEGORIES = {
    "咖啡",
    "茶饮",
    "碳酸饮料",
    "功能饮料",
    "牛奶",
    "酸奶",
    "坚果/零食",
    "方便食品",
    "调味品",
}

GENERIC_RECOMMEND_TERMS = ["推荐", "买什么", "护肤品", "化妆品", "随便", "看看"]
EXCLUDE_TERMS = ["酒精", "香精", "刺激", "刺痛", "太油", "油腻", "厚重", "拔干", "日系"]
SOFT_PREFERENCE_TERMS = [
    "便宜",
    "清爽",
    "轻薄",
    "温和",
    "自然",
    "滋润",
    "高倍",
    "防水",
    "防汗",
    "便携",
    "持久",
    "显色",
    "不沾杯",
    "不晕染",
    "防晕染",
    "办公",
    "学习",
    "网课",
    "续航",
    "高刷",
    "降噪",
    "控糖",
    "无糖",
    "低糖",
    "提神",
    "醒脑",
    "清醒",
    "犯困",
    "礼盒",
    "独立包装",
]
COMPARISON_TERMS = [
    "对比",
    "比较",
    "怎么选",
    "选哪个",
    "买哪个",
    "该买哪个",
    "哪个更",
    "哪款更",
    "更适合",
    "二选一",
    "还是",
    "区别",
]


def _query_terms(query: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{1,4}", query):
        token = token.strip().lower()
        if token:
            terms.add(token)
    return terms


def parse_query_intent(query: str) -> QueryIntent:
    referenced_product_ids = _extract_referenced_product_ids(query)
    budget = None if _relaxes_budget(query) else _hard_budget(query)
    facets = _extract_facets(query)
    _apply_purpose_facets(query, facets)
    exclude_terms = [] if _relaxes_exclusions(query) else _extract_exclude_terms(query)
    soft_preferences = _extract_soft_preferences(query)
    comparison_mode = _is_comparison_query(query)
    structured_categories = _structured_category_candidates(query)
    excluded_categories = set(category_exclusions(query))
    if structured_categories is None:
        category_candidates = _extract_category_candidates(query, facets, exclude_terms)
    else:
        category_candidates = [
            category for category in structured_categories
            if category not in excluded_categories
        ]
    hard_constraints: list[str] = []
    if budget is not None:
        hard_constraints.append(f"budget_max <= {budget:g}")
    hard_constraints.extend(f"referenced_product:{product_id}" for product_id in referenced_product_ids)
    hard_constraints.extend(f"exclude:{term}" for term in exclude_terms)

    signal_count = (
        len(referenced_product_ids)
        + len(exclude_terms)
        + len(soft_preferences)
        + sum(len(values) for values in facets.values())
        + (1 if budget is not None else 0)
    )
    needs_clarification = _needs_clarification(query, signal_count)
    confidence = min(0.95, 0.2 + signal_count * 0.15 + (0.1 if category_candidates else 0.0))
    return QueryIntent(
        category_candidates=category_candidates,
        referenced_product_ids=referenced_product_ids,
        universal_constraints=UniversalConstraints(budget_max=budget),
        facets=facets,
        hard_constraints=hard_constraints,
        soft_preferences=soft_preferences,
        exclude_terms=exclude_terms,
        comparison_mode=comparison_mode,
        needs_clarification=needs_clarification,
        clarification_question=_clarification_question(category_candidates, facets) if needs_clarification else None,
        confidence=round(confidence, 2),
    )


def _hard_budget(query: str) -> float | None:
    amount = r"(\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万点半]+)"
    patterns = [
        rf"{amount}\s*(?:元|块)?\s*(?:以[内下]|以内|以下|之内|内)",
        rf"(?:预算|价格|价位).{{0,8}}(?:放宽到|放宽至|放到|放至|调高到|调高至|提高到|提高至)\s*{amount}\s*(?:元|块)?",
        rf"(?:预算|价格|价位)\s*(?:降到|降至|降低到|压到|压低到|控制在|调到|改成|设成|缩到)\s*{amount}\s*(?:元|块)?",
        rf"(?:预算|价格|价位).{{0,8}}(?:可能只有|只有|只剩|大概|大约|最多|上限|控制在)\s*(?:在)?\s*{amount}\s*(?:元|块)?",
        rf"(?:放宽到|放宽至|放到|放至|调高到|调高至|提高到|提高至)\s*{amount}\s*(?:元|块)?",
        rf"(?:预算|价格|价位)\s*(?:大概在|大约在|大概|大约|在|不超过|别超过|低于|小于|不高于|<=)?\s*{amount}\s*(?:元|块)?",
        rf"(?:降到|降至|降低到|压到|压低到|控制在|调到|改成|设成|缩到)\s*{amount}\s*(?:元|块)?",
        rf"(?:不超过|别超过|低于|小于|不高于|<=)\s*{amount}\s*(?:元|块)?",
    ]
    matches: list[tuple[int, float]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, query):
            amount_value = _parse_budget_amount(match.group(1))
            if amount_value is not None:
                matches.append((match.start(), amount_value))
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def _parse_budget_amount(raw_value: str) -> float | None:
    normalized = raw_value.strip()
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return _chinese_number_to_float(normalized)


def _chinese_number_to_float(raw_value: str) -> float | None:
    text = raw_value.strip().replace("两", "二").replace("〇", "零")
    if not text:
        return None
    if text == "半":
        return 0.5

    if "点" in text:
        integer_part, decimal_part = text.split("点", 1)
        integer = _chinese_integer_to_int(integer_part) if integer_part else 0
        if integer is None:
            return None
        digits = []
        digit_values = _chinese_digit_values()
        for char in decimal_part:
            if char == "半":
                digits.append("5")
            elif char in digit_values:
                digits.append(str(digit_values[char]))
            else:
                return None
        return float(f"{integer}.{''.join(digits)}") if digits else float(integer)

    integer = _chinese_integer_to_int(text)
    return float(integer) if integer is not None else None


def _chinese_integer_to_int(text: str) -> int | None:
    if not text:
        return 0
    if "万" in text:
        high, low = text.split("万", 1)
        high_value = _chinese_integer_to_int(high)
        low_value = _chinese_integer_to_int(low)
        if high_value is None or low_value is None:
            return None
        return high_value * 10000 + low_value

    digit_values = _chinese_digit_values()
    unit_values = {"十": 10, "百": 100, "千": 1000}
    total = 0
    number = 0
    last_unit = 1
    zero_after_unit = False
    seen = False
    for char in text:
        if char in digit_values:
            seen = True
            digit = digit_values[char]
            if digit == 0:
                zero_after_unit = True
                number = 0
            else:
                number = digit
            continue
        if char not in unit_values:
            return None
        seen = True
        unit = unit_values[char]
        if number == 0:
            number = 1
        total += number * unit
        number = 0
        last_unit = unit
        zero_after_unit = False

    if not seen:
        return None
    if number:
        if total and last_unit >= 100 and number < 10 and not zero_after_unit:
            total += number * (last_unit // 10)
        else:
            total += number
    return total


def _chinese_digit_values() -> dict[str, int]:
    return {
        "零": 0,
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }


def _extract_referenced_product_ids(query: str) -> list[str]:
    ids = re.findall(r"\bp_[a-z]+_\d+\b", query)
    return list(dict.fromkeys(ids))


def _relaxes_budget(query: str) -> bool:
    if _hard_budget(query) is not None:
        return False
    return bool(
        re.search(
            r"(放宽|不限制|先不看|先不用管|可以超过|不限).{0,8}(预算|价格|价位)",
            query,
        )
        or re.search(r"(预算|价格|价位).{0,8}(放宽|不限制|先不看|先不用管|可以超过|不限)", query)
    )


def _relaxes_exclusions(query: str) -> bool:
    if _extract_exclude_terms(query):
        return False
    return bool(
        re.search(
            r"(放宽|先不看|先不用管|可以接受).{0,8}(排除|避开|成分)",
            query,
        )
        or re.search(r"(排除|避开|酒精|刺激|成分).{0,8}(放宽|先不看|先不用管|可以接受)", query)
    )


def _extract_facets(query: str) -> dict[str, list[str]]:
    facets: dict[str, list[str]] = {}
    query_lower = query.lower()
    for facet_name, values in FACET_LEXICON.items():
        matched: list[str] = []
        for canonical, synonyms in values.items():
            if any(synonym.lower() in query_lower for synonym in synonyms):
                matched.append(canonical)
        if matched:
            facets[facet_name] = matched
    return facets


def _apply_purpose_facets(query: str, facets: dict[str, list[str]]) -> None:
    """Map purpose-first food queries to safe candidate sub-categories."""
    if not any(term in query for term in ENERGY_PURPOSE_TERMS):
        return
    sub_categories = facets.setdefault("sub_category", [])
    if not set(sub_categories).intersection(FOOD_SUB_CATEGORIES):
        for sub_category in ENERGY_SUB_CATEGORIES:
            if sub_category not in sub_categories:
                sub_categories.append(sub_category)
    use_cases = facets.setdefault("use_case", [])
    if "提神" not in use_cases:
        use_cases.append("提神")


def _extract_exclude_terms(query: str) -> list[str]:
    terms: list[str] = []
    for term in EXCLUDE_TERMS:
        if term in query and (
            re.search(rf"(不要|不想|不含|避开|排除|别太|不能).*{re.escape(term)}", query)
            or re.search(rf"{re.escape(term)}[^。；，,.]{{0,12}}(不要|不想|不行|避开|排除|别太|不能|还是不要)", query)
        ):
            terms.append(term)
    return list(dict.fromkeys(terms))


def _extract_soft_preferences(query: str) -> list[str]:
    return [term for term in SOFT_PREFERENCE_TERMS if term in query]


def _is_comparison_query(query: str) -> bool:
    query = re.sub(r"比较(合适|适合|舒服|稳妥|好|划算|便宜|贵|大|小)", "", query)
    query = re.sub(r"比较(喜欢|偏|常|经常|多|少|高|低|轻|重|宽松|修身)", "", query)
    return any(term in query for term in COMPARISON_TERMS)


def _extract_category_candidates(
    query: str,
    facets: dict[str, list[str]],
    exclude_terms: list[str],
) -> list[str]:
    candidates: list[str] = []
    excluded_categories = set(category_exclusions(query))
    if "beauty" not in excluded_categories and (_looks_like_beauty_query(query, facets) or exclude_terms):
        candidates.append("beauty")
    if "apparel" not in excluded_categories and _looks_like_apparel_query(query):
        candidates.append("apparel")
    if "digital" not in excluded_categories and _looks_like_digital_query(query):
        candidates.append("digital")
    if "food" not in excluded_categories and _looks_like_food_query(query):
        candidates.append("food")
    return list(dict.fromkeys(candidates))


def _is_scene_bundle_query(query: str) -> bool:
    return _planned_recommendation_mode(query) == "scene_bundle"


def _planned_recommendation_mode(query: str) -> str | None:
    matches = re.findall(r"(?m)^-\s*推荐模式：([^\n]+)$", query)
    if not matches:
        return None
    label = matches[-1].strip()
    if "场景组合" in label:
        return "scene_bundle"
    return label or None


def _structured_category_candidates(query: str) -> list[str] | None:
    matches = re.findall(r"(?m)^-\s*类目：([^\n]+)$", query)
    if not matches:
        return None
    categories: list[str] = []
    for raw_value in re.split(r"[、,，\s]+", matches[-1]):
        value = raw_value.strip()
        if not value:
            continue
        if value in CATEGORY_TO_RAW:
            categories.append(value)
        elif value in RAW_TO_CATEGORY:
            categories.append(RAW_TO_CATEGORY[value])
    return list(dict.fromkeys(categories))


def category_exclusions(query: str) -> list[str]:
    excluded: list[str] = []
    for category, patterns in CATEGORY_NEGATION_PATTERNS.items():
        if any(re.search(pattern, query) for pattern in patterns):
            excluded.append(category)
    return excluded


def _looks_like_beauty_query(query: str, facets: dict[str, list[str]]) -> bool:
    if any(term in query for term in BEAUTY_TERMS):
        return True
    return any(key in facets for key in ["skin_type", "effect"])


def _looks_like_apparel_query(query: str) -> bool:
    return any(term in query for term in APPAREL_TERMS)


def _looks_like_digital_query(query: str) -> bool:
    return any(term in query for term in DIGITAL_TERMS)


def _looks_like_food_query(query: str) -> bool:
    return any(term in query for term in FOOD_TERMS)


def _needs_clarification(query: str, signal_count: int) -> bool:
    if signal_count > 0:
        return False
    return any(term in query for term in GENERIC_RECOMMEND_TERMS)


def _clarification_question(category_candidates: list[str], facets: dict[str, list[str]]) -> str:
    primary_category = category_candidates[0] if category_candidates else _category_from_facets(facets)
    if primary_category == "food":
        return "你更想看咖啡/茶饮/功能饮料，还是更在意预算、含糖情况和便携包装？"
    if primary_category == "digital":
        return "你更在意预算、使用场景、性能/续航，还是便携性？"
    if primary_category == "apparel":
        return "你更在意预算、尺码/材质、使用场景，还是天气条件？"
    if primary_category == "beauty":
        return "你更在意肤质、预算，还是防晒/修护/控油这类具体功效？"
    return "你更在意预算、送礼/自用场景、品类方向，还是需要避开的条件？"


def _category_from_facets(facets: dict[str, list[str]]) -> str | None:
    sub_categories = set(facets.get("sub_category", []))
    if sub_categories.intersection(FOOD_SUB_CATEGORIES):
        return "food"
    if sub_categories.intersection({"智能手机", "笔记本电脑", "平板电脑", "真无线耳机"}):
        return "digital"
    if sub_categories.intersection({"短袖T恤", "跑步鞋", "徒步鞋", "背包", "运动长裤", "卫衣", "篮球鞋", "瑜伽裤", "户外裤", "帽子", "速干T恤", "运动短裤"}):
        return "apparel"
    if sub_categories or any(key in facets for key in ["skin_type", "effect"]):
        return "beauty"
    return None


def retrieve(
    query: str,
    products: list[dict],
    limit: int = 3,
    index_dir: Path | None = None,
    memory_profile: UserMemoryProfile | None = None,
    recipient_profile: RecipientProfile | None = None,
) -> RetrievalResult:
    # RAG 主入口：确定性约束优先于语义召回。
    # 预算、类目、明确排除项和必要功效会先作为硬过滤生效，
    # 之后 keyword / vector / graph 分数才参与排序。
    intent = parse_query_intent(query)
    memory_applied: list[str] = []
    if memory_profile is not None:
        intent, memory_applied = _apply_memory_profile(
            intent,
            memory_profile,
            now=datetime.now(UTC),
            recipient_profile=recipient_profile,
        )

    _apply_catalog_product_references(intent, query, products)
    if intent.needs_clarification:
        # 信息不足时先追问，不为了凑商品卡片而强行推荐。
        trace = RetrievalTrace(
            query=query,
            parsed_intent=intent,
            guardrail_checks=GuardrailChecks(needs_clarification=True),
            constraint_trace=_constraint_trace_from_intent(intent, memory_applied=memory_applied),
            safety_trace=_safety_trace(query, intent),
        )
        return RetrievalResult(
            cards=[],
            context="信息不足，先追问关键条件，不进入普通推荐。",
            trace=trace,
            clarification_question=intent.clarification_question,
        )

    budget = intent.universal_constraints.budget_max
    terms = _query_terms(query)
    vector_scores, vector_hits, metadata_filter = _vector_scores(query, index_dir, intent)
    keyword_hits: list[RetrievalHit] = []
    graph_hits: list[RetrievalHit] = []
    final_hits: list[RetrievalHit] = []
    hard_filtered_out: list[FilteredProduct] = []
    scored: list[tuple[float, dict, list[str]]] = []
    skin_type_backfill_scored: list[tuple[float, dict, list[str]]] = []

    # 这里刻意先排除、再打分：违反硬约束的商品不能因为向量命中而返回。
    for item in products:
        raw = item["raw"]
        is_referenced_product = raw["product_id"] in intent.referenced_product_ids
        if intent.referenced_product_ids and not is_referenced_product:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"product_id {raw['product_id']} not in {intent.referenced_product_ids}")
            )
            continue
        if not is_referenced_product and intent.category_candidates and not _matches_category_candidate(raw.get("category", ""), intent.category_candidates):
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"category {raw.get('category', '')} not in {intent.category_candidates}")
            )
            continue
        required_sub_categories = intent.facets.get("sub_category", [])
        if not is_referenced_product and required_sub_categories and raw.get("sub_category", "") not in required_sub_categories:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"sub_category {raw.get('sub_category', '')} not in {required_sub_categories}")
            )
            continue
        if not is_referenced_product and _matches_brand_exclude(raw.get("brand", ""), intent.universal_constraints.brand_exclude):
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"brand {raw.get('brand', '')} in brand_exclude")
            )
            continue
        if not is_referenced_product and budget is not None and not _has_price_within_budget(raw, budget):
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"price {_min_purchase_price(raw):g} > budget {budget:g}")
            )
            continue
        excluded_term = _matched_exclude_term(intent.exclude_terms, item)
        if not is_referenced_product and excluded_term is not None:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"matches excluded term: {excluded_term}")
            )
            continue
        missing_effect = _missing_required_effect(intent, item)
        if not is_referenced_product and missing_effect is not None:
            hard_filtered_out.append(
                FilteredProduct(product_id=raw["product_id"], reason=f"missing required effect: {missing_effect}")
            )
            continue
        skin_type_near_miss: str | None = None
        missing_skin_type = _missing_required_skin_type(intent, item)
        if not is_referenced_product and missing_skin_type is not None:
            if _can_backfill_skin_type_near_miss(intent, query):
                skin_type_near_miss = missing_skin_type
            else:
                hard_filtered_out.append(
                    FilteredProduct(product_id=raw["product_id"], reason=f"missing required skin_type: {missing_skin_type}")
                )
                continue
        text = product_search_text(item).lower()
        score = 0.0
        reasons: list[str] = []
        if skin_type_near_miss is not None:
            score -= 2.0
            reasons.append(f"skin_type_near_miss:{skin_type_near_miss}")
        if is_referenced_product:
            score += 20.0
            reasons.append("referenced_product")
        keyword_score = sum(1 for term in terms if len(term) >= 2 and term.lower() in text)
        if keyword_score:
            score += keyword_score
            reasons.append(f"keyword_match:{keyword_score:g}")
            keyword_hits.append(RetrievalHit(product_id=raw["product_id"], score=float(keyword_score), reasons=["keyword_match"]))
        facet_score, facet_reasons = _facet_score(intent, item)
        score += facet_score
        reasons.extend(facet_reasons)
        graph_score, graph_reasons = _graph_score(intent, item)
        if graph_score:
            score += graph_score
            reasons.extend(graph_reasons)
            graph_hits.append(
                RetrievalHit(
                    product_id=raw["product_id"],
                    score=round(graph_score, 3),
                    reasons=graph_reasons,
                )
            )
        purpose_score, purpose_reasons = _purpose_priority_score(intent, item, query)
        if purpose_score:
            score += purpose_score
            reasons.extend(purpose_reasons)
        if raw["product_id"] in vector_scores:
            vector_score = vector_scores[raw["product_id"]]
            score += vector_score
            reasons.append(f"vector_hit:{vector_score:g}")
        if budget is not None:
            score += 1.0
            reasons.append("budget_match")
        if score > 0:
            entry = (score, item, reasons)
            if skin_type_near_miss is not None:
                skin_type_backfill_scored.append(entry)
            else:
                scored.append(entry)

    if not scored and skin_type_backfill_scored:
        scored = skin_type_backfill_scored
        skin_type_backfill_scored = []
    if not scored:
        # 如果没有正向匹配信号，保留通过硬过滤的商品，
        # 让下游 fallback 仍然能基于证据回答，而不是编造。
        scored = [
            (0.1, item, ["fallback_after_hard_filters"])
            for item in products
            if not _is_hard_filtered(item, hard_filtered_out)
        ]
    if not scored:
        trace = RetrievalTrace(
            query=query,
            parsed_intent=intent,
            metadata_filter=metadata_filter,
            hard_filtered_out=hard_filtered_out,
            filter_summary=_filter_summary(hard_filtered_out),
            retrieval_channels=RetrievalChannels(
                keyword=sorted(keyword_hits, key=lambda hit: hit.score, reverse=True)[:8],
                vector=vector_hits,
                graph=sorted(graph_hits, key=lambda hit: hit.score, reverse=True)[:8],
            ),
            guardrail_checks=GuardrailChecks(
                over_budget_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("price")),
                excluded_term_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("matches excluded")),
                needs_clarification=True,
            ),
            constraint_trace=_constraint_trace_from_intent(intent, memory_applied=memory_applied),
            safety_trace=_safety_trace(query, intent),
        )
        return RetrievalResult(
            cards=[],
            context="硬约束过滤后没有可推荐商品。",
            trace=trace,
            clarification_question=_no_result_clarification(intent),
        )

    scored.sort(key=lambda pair: (pair[0], -_min_purchase_price(pair[1]["raw"])), reverse=True)
    skin_type_backfill_scored.sort(key=lambda pair: (pair[0], -_min_purchase_price(pair[1]["raw"])), reverse=True)
    selected_scored = _select_ranked_scored(scored, limit=limit, intent=intent, query=query)
    selected_scored = _fill_underfilled_with_backfill(
        selected_scored,
        skin_type_backfill_scored,
        limit=limit,
    )
    selected_scored = _order_referenced_scored(selected_scored, intent)
    selected = [item for _, item, _ in selected_scored]
    final_hits = [
        RetrievalHit(product_id=item["raw"]["product_id"], score=round(score, 3), reasons=reasons)
        for score, item, reasons in selected_scored
    ]

    cards = [_to_card(item, query, budget=budget) for item in selected]
    context = "\n\n".join(_context_block(item, budget=budget) for item in selected)
    # RetrievalTrace 是可复验的证据链：记录过滤项、召回通道和商品卡片来源字段。
    trace = RetrievalTrace(
        query=query,
        parsed_intent=intent,
        metadata_filter=metadata_filter,
        hard_filtered_out=hard_filtered_out,
        filter_summary=_filter_summary(hard_filtered_out),
        retrieval_channels=RetrievalChannels(
            keyword=sorted(keyword_hits, key=lambda hit: hit.score, reverse=True)[:8],
            vector=vector_hits,
            graph=sorted(graph_hits, key=lambda hit: hit.score, reverse=True)[:8],
        ),
        final_ranking=final_hits,
        ranking_signals=_ranking_signals(final_hits),
        guardrail_checks=GuardrailChecks(
            over_budget_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("price")),
            excluded_term_candidates=sum(1 for item in hard_filtered_out if item.reason.startswith("matches excluded")),
            needs_clarification=False,
        ),
        constraint_trace=_constraint_trace_from_intent(intent, memory_applied=memory_applied),
        safety_trace=_safety_trace(query, intent),
        source_trace=_source_trace(selected),
    )
    return RetrievalResult(cards=cards, context=context, trace=trace)


def _apply_memory_profile(
    intent: QueryIntent,
    memory_profile: UserMemoryProfile,
    now: datetime,
    recipient_profile: RecipientProfile | None = None,
) -> tuple[QueryIntent, list[str]]:
    applied: list[str] = []
    recipient = recipient_profile or _recipient_for_profile(memory_profile)
    constraints = recipient.constraints
    if constraints.budget_max is not None:
        current_budget = intent.universal_constraints.budget_max
        if current_budget is None or constraints.budget_max < current_budget:
            intent.universal_constraints.budget_max = constraints.budget_max
            applied.append(f"budget_max:{constraints.budget_max:g}")
    avoid_terms = _unique_lower_stripped(constraints.avoid_terms + constraints.allergies)
    if avoid_terms:
        for term in avoid_terms:
            if term not in intent.exclude_terms:
                intent.exclude_terms.append(term)
        applied.append(f"avoid_terms:{','.join(dict.fromkeys(avoid_terms))}")

    if constraints.brand_exclude:
        cleaned_brand_exclude = _unique_lower_stripped(constraints.brand_exclude)
        if cleaned_brand_exclude:
            intent.universal_constraints.brand_exclude = _unique_lower_stripped(
                intent.universal_constraints.brand_exclude + cleaned_brand_exclude
            )
            applied.append(f"brand_exclude:{','.join(cleaned_brand_exclude)}")

    for category, weight in _top_typed_preferences(recipient.long_term_preferences.preferred_categories, limit=2, min_weight=0.55):
        mapped_category = _raw_category_from_label(category)
        if mapped_category and mapped_category not in intent.soft_preferences:
            intent.soft_preferences.append(mapped_category)
            applied.append(f"recipient_long_term_category:{mapped_category}:{weight:g}")

    for interest in _active_memory_snapshots(memory_profile.short_term_snapshots.recent_interests, now=now):
        if interest["key"] and interest["key"] not in intent.soft_preferences:
            intent.soft_preferences.append(interest["key"])
            applied.append(f"recent_interest:{interest['key']}:{interest['weight']:.2f}")

    for avoidance in _active_memory_snapshots(memory_profile.short_term_snapshots.recent_avoidance, now=now):
        if avoidance["key"] and avoidance["key"] not in intent.exclude_terms:
            intent.exclude_terms.append(avoidance["key"])
            applied.append(f"recent_avoidance:{avoidance['key']}:{avoidance['weight']:.2f}")

    for tag, weight in _top_typed_preferences(recipient.long_term_preferences.preferred_tags, limit=4, min_weight=0.4):
        if tag and tag not in intent.soft_preferences:
            intent.soft_preferences.append(tag)
            applied.append(f"recipient_long_term_tag:{tag}:{weight:g}")

    intent.soft_preferences = _unique_strings(intent.soft_preferences)
    intent.exclude_terms = _unique_lower_stripped(intent.exclude_terms)
    return intent, applied


def _recipient_for_profile(memory_profile: UserMemoryProfile) -> RecipientProfile:
    if memory_profile.recipients:
        return memory_profile.recipients[0]
    return RecipientProfile(
        recipient_id="self",
        display_name="自己",
        relationship="self",
        constraints=memory_profile.constraints,
        long_term_preferences=memory_profile.long_term_preferences,
    )


def _top_typed_preferences(
    source: dict[str, float],
    *,
    limit: int,
    min_weight: float,
) -> list[tuple[str, float]]:
    items = [
        (str(key).strip(), float(value))
        for key, value in source.items()
        if str(key).strip() and isinstance(value, (int, float)) and float(value) >= min_weight
    ]
    items.sort(key=lambda item: item[1], reverse=True)
    return items[:limit]


def _raw_category_from_label(label: str) -> str | None:
    normalized = str(label).strip()
    if not normalized:
        return None
    if normalized in CATEGORY_TO_RAW:
        return CATEGORY_TO_RAW[normalized]
    if normalized in RAW_TO_CATEGORY:
        return normalized
    lowered = normalized.lower()
    for category, raw in CATEGORY_TO_RAW.items():
        if lowered == category.lower():
            return raw
    return None


def _active_memory_snapshots(
    snapshots: list,
    now: datetime,
) -> list[dict[str, object]]:
    active: list[dict[str, object]] = []
    for snapshot in snapshots:
        created_at = str(getattr(snapshot, "created_at", ""))
        ttl_days = getattr(snapshot, "ttl_days", 3)
        if ttl_days <= 0:
            continue
        if not _is_snapshot_active(created_at, now, int(ttl_days)):
            continue
        key = str(getattr(snapshot, "key", "")).strip()
        if not key:
            continue
        weight = float(getattr(snapshot, "weight", 0.5))
        source = str(getattr(snapshot, "source", "recent_query"))
        active.append({"key": key, "weight": weight, "source": source})
    return sorted(active, key=lambda item: float(item["weight"]), reverse=True)


def _is_snapshot_active(created_at_raw: str, now: datetime, ttl_days: int) -> bool:
    try:
        created_at = datetime.fromisoformat(created_at_raw)
    except ValueError:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return now - created_at <= timedelta(days=ttl_days)


def _matches_brand_exclude(brand: str, exclusions: list[str]) -> bool:
    target = str(brand).strip().lower()
    for exclusion in exclusions:
        normalized = str(exclusion).strip().lower()
        if not normalized:
            continue
        if normalized in target:
            return True
    return False


def _unique_strings(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def _unique_lower_stripped(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        normalized = str(value).strip().lower()
        if normalized and normalized not in output:
            output.append(normalized)
    return output


def _constraint_trace_from_intent(
    intent: QueryIntent,
    memory_applied: list[str] | None = None,
) -> ConstraintTrace:
    current_turn = _constraints_from_intent(intent)
    return ConstraintTrace(
        current_turn=current_turn,
        inherited={},
        relaxed=[],
        effective=current_turn,
        actions=list(memory_applied or []),
    )


def _constraints_from_intent(intent: QueryIntent) -> dict[str, object]:
    constraints: dict[str, object] = {}
    if intent.category_candidates:
        constraints["category_candidates"] = intent.category_candidates
    if intent.referenced_product_ids:
        constraints["referenced_product_ids"] = intent.referenced_product_ids
    if intent.universal_constraints.budget_max is not None:
        constraints["budget_max"] = intent.universal_constraints.budget_max
    if intent.facets:
        constraints["facets"] = intent.facets
    if intent.exclude_terms:
        constraints["exclude_terms"] = intent.exclude_terms
    if intent.soft_preferences:
        constraints["soft_preferences"] = intent.soft_preferences
    if intent.comparison_mode:
        constraints["comparison_mode"] = True
    return constraints


def _safety_trace(query: str, intent: QueryIntent) -> SafetyTrace:
    risks: list[str] = []
    boundaries: list[str] = []
    if any(term in query for term in ["过敏", "不耐受", "烂脸"]):
        risks.append("allergy_or_intolerance")
        boundaries.append("不能保证不过敏；只能按商品资料提示风险，并建议先做局部测试。")
    if any(term in query for term in ["孕妇", "孕期", "怀孕", "哺乳"]):
        risks.append("pregnancy_or_lactation")
        boundaries.append("涉及孕期/哺乳期时不能替代医生或专业人士建议。")
    if any(term in query for term in ["敏感肌", "屏障", "泛红", "刺痛"]):
        risks.append("sensitive_skin_or_barrier")
        boundaries.append("敏感肌相关回答需保守，避免绝对安全和资料外功效承诺。")
    if intent.exclude_terms:
        risks.append("exclusion_constraints")
        boundaries.append("排除条件只能按商品资料和风险词过滤；没有明确证据时不能声称不含。")
    if any(term in query for term in ["保证", "绝对", "一定不会", "不会过敏", "肯定安全"]):
        risks.append("absolute_safety_claim")
        boundaries.append("必须避免绝对安全、治疗和确定性结果承诺。")

    risk_level: Literal["low", "medium", "high"] = "low"
    if any(risk in risks for risk in ["allergy_or_intolerance", "pregnancy_or_lactation", "absolute_safety_claim"]):
        risk_level = "high"
    elif risks:
        risk_level = "medium"
    return SafetyTrace(
        triggered_risks=list(dict.fromkeys(risks)),
        required_boundaries=list(dict.fromkeys(boundaries)),
        risk_level=risk_level,
    )


def _source_trace(items: list[dict]) -> SourceTrace:
    supported_claims: list[SourceClaim] = []
    review_only_claims: list[SourceClaim] = []
    for item in items:
        raw = item["raw"]
        product_id = str(raw["product_id"])
        supported_claims.extend(
            [
                SourceClaim(claim=f"品牌：{raw.get('brand', '')}", source="raw.brand", product_id=product_id),
                SourceClaim(claim=f"价格：{raw.get('base_price', '')}", source="raw.base_price", product_id=product_id),
                SourceClaim(
                    claim=f"类目：{raw.get('category', '')}/{raw.get('sub_category', '')}",
                    source="raw.category",
                    product_id=product_id,
                ),
            ]
        )
        attrs = item.get("attributes", {})
        for field_name, source_name in [
            ("tags", "attributes.tags"),
            ("selling_points", "attributes.selling_points"),
            ("cautions", "attributes.cautions"),
            ("suitable_for", "attributes.suitable_for"),
            ("avoid_for", "attributes.avoid_for"),
        ]:
            for value in _limited_strings(attrs.get(field_name, []), limit=3):
                supported_claims.append(SourceClaim(claim=value, source=source_name, product_id=product_id))

        knowledge = raw.get("rag_knowledge", {})
        for item_faq in knowledge.get("official_faq", [])[:2]:
            if not isinstance(item_faq, dict):
                continue
            answer = str(item_faq.get("answer", "")).strip()
            if answer:
                supported_claims.append(SourceClaim(claim=answer, source="rag_knowledge.official_faq", product_id=product_id))
        for review in knowledge.get("user_reviews", [])[:2]:
            if not isinstance(review, dict):
                continue
            content = str(review.get("content", "")).strip()
            if content:
                review_only_claims.append(SourceClaim(claim=content, source="rag_knowledge.user_reviews", product_id=product_id))

    return SourceTrace(
        supported_claims=supported_claims[:40],
        review_only_claims=review_only_claims[:20],
        unsupported_claims=[],
    )


def _limited_strings(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:limit] if str(item).strip()]


def _apply_catalog_product_references(intent: QueryIntent, query: str, products: list[dict]) -> None:
    if intent.referenced_product_ids:
        return
    matched_ids = _catalog_product_references(query, products)
    if not matched_ids:
        return
    intent.referenced_product_ids = matched_ids
    intent.hard_constraints.extend(f"referenced_product:{product_id}" for product_id in matched_ids)
    intent.needs_clarification = False
    intent.clarification_question = None
    intent.confidence = max(intent.confidence, 0.85)


def _catalog_product_references(query: str, products: list[dict]) -> list[str]:
    normalized_query = _normalize_alias_text(query)
    if not normalized_query:
        return []
    matches: list[str] = []
    for item in products:
        raw = item["raw"]
        aliases = _product_aliases(raw)
        if any(alias and alias in normalized_query for alias in aliases):
            matches.append(raw["product_id"])
    return list(dict.fromkeys(matches))


def _product_aliases(raw: dict) -> list[str]:
    brand = str(raw.get("brand", "")).strip()
    title = str(raw.get("title", "")).strip()
    aliases = {_normalize_alias_text(brand)}
    if brand.startswith("巴黎") and len(brand) > 2:
        aliases.add(_normalize_alias_text(brand.removeprefix("巴黎")))
    if brand == "安热沙":
        aliases.add(_normalize_alias_text("安耐晒"))
    if brand and title.startswith(brand):
        short_title = title[len(brand) : len(brand) + 8]
        aliases.add(_normalize_alias_text(short_title))
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", title):
        normalized_token = _normalize_alias_text(token)
        if len(normalized_token) >= 4:
            aliases.add(normalized_token)
    return [alias for alias in aliases if len(alias) >= 2]


def _normalize_alias_text(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _filter_summary(filtered: list[FilteredProduct]) -> dict[str, int]:
    counts = {
        "category": 0,
        "sub_category": 0,
        "budget": 0,
        "exclude_terms": 0,
        "required_effect": 0,
        "referenced_product": 0,
        "other": 0,
    }
    for entry in filtered:
        reason = entry.reason
        if reason.startswith("category"):
            counts["category"] += 1
        elif reason.startswith("sub_category"):
            counts["sub_category"] += 1
        elif reason.startswith("price"):
            counts["budget"] += 1
        elif reason.startswith("matches excluded"):
            counts["exclude_terms"] += 1
        elif reason.startswith("missing required effect"):
            counts["required_effect"] += 1
        elif reason.startswith("product_id"):
            counts["referenced_product"] += 1
        else:
            counts["other"] += 1
    return {key: value for key, value in counts.items() if value}


def _ranking_signals(final_hits: list[RetrievalHit]) -> dict[str, dict[str, list[str]]]:
    signals: dict[str, dict[str, list[str]]] = {}
    for hit in final_hits:
        buckets: dict[str, list[str]] = {
            "keyword": [],
            "vector": [],
            "graph": [],
            "facet": [],
            "budget": [],
            "soft_preference": [],
            "other": [],
        }
        for reason in hit.reasons:
            if reason.startswith("keyword_match"):
                buckets["keyword"].append(reason)
            elif reason.startswith("vector_hit"):
                buckets["vector"].append(reason)
            elif reason.startswith("graph_"):
                buckets["graph"].append(reason)
            elif reason == "budget_match":
                buckets["budget"].append(reason)
            elif reason.startswith("soft_preference"):
                buckets["soft_preference"].append(reason)
            elif "_match:" in reason:
                buckets["facet"].append(reason)
            else:
                buckets["other"].append(reason)
        signals[hit.product_id] = {key: value for key, value in buckets.items() if value}
    return signals


def _matched_exclude_term(exclude_terms: list[str], item: dict) -> str | None:
    text = product_search_text(item).lower()
    for term in exclude_terms:
        if _has_excluded_risk(text, term.lower()):
            return term
    return None


def _missing_required_effect(intent: QueryIntent, item: dict) -> str | None:
    required_effects = intent.facets.get("effect", [])
    if not required_effects:
        return None
    if item["raw"].get("category") != "美妆护肤" and "防晒" in required_effects:
        required_effects = [effect for effect in required_effects if effect != "防晒"]
        if not required_effects:
            return None
    specific_effects = [
        effect
        for effect in required_effects
        if effect in {"底妆", "定妆", "洁面", "卸妆", "眼周护理", "唇妆", "眉妆"}
    ]
    if specific_effects:
        if any(_matches_specific_effect(effect, item) for effect in specific_effects):
            return None
        return ",".join(specific_effects)
    text = product_search_text(item).lower()
    if any(effect.lower() in text for effect in required_effects):
        return None
    return ",".join(required_effects)


def _missing_required_skin_type(intent: QueryIntent, item: dict) -> str | None:
    required_skin_types = intent.facets.get("skin_type", [])
    if not required_skin_types or intent.comparison_mode or intent.referenced_product_ids:
        return None
    if item["raw"].get("category") != "美妆护肤":
        return None
    if any(_has_positive_skin_type_evidence(skin_type, item) for skin_type in required_skin_types):
        return None
    return ",".join(required_skin_types)


def _can_backfill_skin_type_near_miss(intent: QueryIntent, query: str) -> bool:
    required_skin_types = set(intent.facets.get("skin_type", []))
    if not required_skin_types:
        return False
    if "敏感肌" in required_skin_types:
        return False
    if intent.comparison_mode or intent.referenced_product_ids:
        return False
    if not any(skin_type in {"油皮", "混油皮", "干皮"} for skin_type in required_skin_types):
        return False
    if _is_scene_bundle_query(query):
        return False
    return True


def _has_positive_skin_type_evidence(skin_type: str, item: dict) -> bool:
    aliases = _skin_type_aliases(skin_type)
    structured_text = _positive_structured_text(item)
    if any(alias in structured_text for alias in aliases):
        return True

    official_text = _official_positive_text(item)
    positive_words = "适合|适用|友好|可用|推荐|选择|专为|福音"
    for alias in aliases:
        if re.search(rf"({positive_words})[^。；，,.]{{0,18}}{re.escape(alias)}", official_text):
            return True
        if re.search(rf"{re.escape(alias)}[^。；，,.]{{0,18}}({positive_words})", official_text):
            return True
    return False


def _skin_type_aliases(skin_type: str) -> list[str]:
    alias_map = {
        "敏感肌": ["敏感肌", "易敏肌"],
        "油皮": ["油皮"],
        "混油皮": ["混油皮", "混合皮", "混合偏油"],
        "干皮": ["干皮", "干性肌"],
    }
    return alias_map.get(skin_type, [skin_type])


def _positive_structured_text(item: dict) -> str:
    attrs = item.get("attributes", {})
    beauty = item.get("beauty_attributes", {})
    values: list[str] = []
    for field_name in ["tags", "target_users", "suitable_for"]:
        values.extend(_string_list(attrs.get(field_name, [])))
    values.extend(_string_list(beauty.get("skin_types", [])))
    return " ".join(values)


def _official_positive_text(item: dict) -> str:
    raw = item["raw"]
    knowledge = raw.get("rag_knowledge", {})
    parts = [str(knowledge.get("marketing_description", ""))]
    for faq in knowledge.get("official_faq", []):
        if isinstance(faq, dict):
            parts.append(str(faq.get("answer", "")))
    return " ".join(parts)


def _matches_specific_effect(effect: str, item: dict) -> bool:
    raw = item["raw"]
    sub_category = str(raw.get("sub_category", ""))
    attrs = item.get("attributes", {})
    tags = {str(tag) for tag in attrs.get("tags", [])}
    allowed_sub_categories = {
        "底妆": {"粉底液"},
        "定妆": {"蜜粉"},
        "洁面": {"洁面"},
        "卸妆": {"卸妆"},
        "眼周护理": {"眼霜"},
        "唇妆": {"唇釉"},
        "眉妆": {"眉笔"},
    }
    return sub_category in allowed_sub_categories.get(effect, set()) or effect in tags


def _has_excluded_risk(text: str, term: str) -> bool:
    if term not in text:
        return False
    if term == "酒精":
        return _has_risky_occurrence(
            text,
            term,
            safe_patterns=[
                r"(不含|无|没有|不添加)[^。；，,.]{0,8}酒精",
                r"酒精[^。；，,.]{0,8}(不含|无|没有|不添加)",
                r"(不含|无|没有|不添加)[^。；，,.]{0,16}酒精[^。；，,.]{0,16}刺激",
            ],
            risk_patterns=[
                r"(含有|包含|添加|如|对|酒精味)[^。；，,.]{0,12}酒精",
                r"酒精[^。；，,.]{0,12}(敏感|味|刺激|含量)",
            ],
        )
    if term == "香精":
        return _has_risky_occurrence(
            text,
            term,
            safe_patterns=[
                r"(不含|无|没有|不添加)[^。；，,.]{0,8}香精",
                r"香精[^。；，,.]{0,8}(不含|无|没有|不添加)",
                r"(不含|无|没有|不添加)[^。；，,.]{0,16}香精[^。；，,.]{0,16}酒精",
            ],
            risk_patterns=[
                r"(含有|包含|添加|如|对|香精味|香味)[^。；，,.]{0,12}香精",
                r"香精[^。；，,.]{0,12}(敏感|味|刺激|含量)",
            ],
        )
    if term == "刺激":
        return _has_risky_occurrence(
            text,
            term,
            safe_patterns=[
                r"(不含|无|没有|不添加)[^。；，,.]{0,12}刺激",
                r"刺激[^。；，,.]{0,8}(不含|无|没有|不添加)",
                r"(舒缓|缓解|改善|减少|降低)[^。；，,.]{0,12}刺激",
                r"刺激[^。；，,.]{0,12}(舒缓|缓解|改善|减少|降低)",
                r"刺激性产品",
            ],
            risk_patterns=[
                r"(可能|容易|会|强烈|明显|产生|造成|导致|带来)[^。；，,.]{0,12}刺激",
                r"刺激[^。；，,.]{0,12}(较强|明显|敏感|刺痛)",
                r"刺激感",
            ],
        )
    return term in text


def _has_risky_occurrence(
    text: str,
    term: str,
    safe_patterns: list[str],
    risk_patterns: list[str],
) -> bool:
    safe_spans = [match.span() for pattern in safe_patterns for match in re.finditer(pattern, text)]
    for pattern in risk_patterns:
        for risk_match in re.finditer(pattern, text):
            term_match = re.search(re.escape(term), risk_match.group(0))
            if term_match is None:
                return True
            term_start = risk_match.start() + term_match.start()
            term_end = risk_match.start() + term_match.end()
            if not any(safe_start <= term_start and term_end <= safe_end for safe_start, safe_end in safe_spans):
                return True
    for match in re.finditer(re.escape(term), text):
        start, end = match.span()
        if not any(safe_start <= start and end <= safe_end for safe_start, safe_end in safe_spans):
            return False
    return False


def _facet_score(intent: QueryIntent, item: dict) -> tuple[float, list[str]]:
    raw = item["raw"]
    text = product_search_text(item).lower()
    score = 0.0
    reasons: list[str] = []
    weights = {"sub_category": 5.0, "skin_type": 4.0, "effect": 3.0, "use_case": 2.0}
    for facet_name, values in intent.facets.items():
        weight = weights.get(facet_name, 1.0)
        for value in values:
            if facet_name == "sub_category":
                if str(raw.get("sub_category", "")) == value:
                    score += weight
                    reasons.append(f"{facet_name}_match:{value}")
                continue
            if value.lower() in text:
                score += weight
                reasons.append(f"{facet_name}_match:{value}")
    for preference in intent.soft_preferences:
        if preference.lower() in text:
            score += 1.0
            reasons.append(f"soft_preference:{preference}")
    return score, reasons


def _purpose_priority_score(intent: QueryIntent, item: dict, query: str) -> tuple[float, list[str]]:
    apparel_score = _apparel_purpose_priority_score(intent, item, query)
    if apparel_score[0]:
        return apparel_score

    has_energy_intent = "提神" in intent.facets.get("use_case", []) or any(
        term in query for term in ENERGY_PURPOSE_TERMS
    )
    if not has_energy_intent:
        return 0.0, []

    raw_sub_category = str(item["raw"].get("sub_category", ""))
    if raw_sub_category not in ENERGY_SUB_CATEGORIES:
        return 0.0, []

    if any(term in query for term in STRONG_ENERGY_CONTEXT_TERMS):
        context = "strong_energy"
        preferences = {"功能饮料": 2.0, "咖啡": 1.0, "茶饮": 0.5}
    elif any(term in query for term in EARLY_ENERGY_CONTEXT_TERMS):
        context = "early_energy"
        preferences = {"咖啡": 3.0, "茶饮": 0.8, "功能饮料": -0.8}
    else:
        context = "general_energy"
        preferences = {"咖啡": 1.5, "茶饮": 0.8, "功能饮料": 0.5}

    score = preferences.get(raw_sub_category, 0.0)
    if score == 0.0:
        return 0.0, []
    return score, [f"purpose_priority:{context}:{raw_sub_category}:{score:g}"]


def _apparel_purpose_priority_score(intent: QueryIntent, item: dict, query: str) -> tuple[float, list[str]]:
    raw = item["raw"]
    raw_sub_category = str(raw.get("sub_category", ""))
    raw_category = str(raw.get("category", ""))
    if raw_category != "服饰运动" and "apparel" not in intent.category_candidates:
        return 0.0, []

    text = product_search_text(item)
    score = 0.0
    reasons: list[str] = []

    if raw_sub_category == "跑步鞋" and any(term in query for term in CASUAL_RUNNING_CONTEXT_TERMS):
        if any(term in text for term in ["入门跑者", "日常慢跑", "3-10公里", "小区夜跑"]):
            score += 10.0
            reasons.append("purpose_priority:casual_running:daily_training")
        elif any(term in text for term in ["慢跑爱好者", "日常通勤", "通勤", "压街"]):
            score += 2.5
            reasons.append("purpose_priority:casual_running:general")
        if any(term in text for term in PERFORMANCE_RUNNING_TERMS):
            score -= 6.0
            reasons.append("purpose_penalty:casual_running:performance_shoe")

    if raw_sub_category == "徒步鞋" and any(term in query for term in LIGHT_HIKING_CONTEXT_TERMS):
        if any(term in text for term in ["近郊", "单日10-20公里", "轻装徒步", "郊野绿道", "城市雨天步行"]):
            score += 8.0
            reasons.append("purpose_priority:light_hiking:single_day")
        elif any(term in text for term in ["徒步", "登山", "户外"]):
            score += 2.0
            reasons.append("purpose_priority:light_hiking:general")
        if "硬核户外" in text:
            score -= 2.0
            reasons.append("purpose_penalty:light_hiking:hardcore")

    if not score:
        return 0.0, []
    return score, reasons


def _select_ranked_scored(
    scored: list[tuple[float, dict, list[str]]],
    *,
    limit: int,
    intent: QueryIntent,
    query: str,
) -> list[tuple[float, dict, list[str]]]:
    if _is_scene_bundle_query(query) and not intent.referenced_product_ids:
        selected = _select_scene_bundle_scored(
            scored,
            limit=limit,
            intent=intent,
            slots=_planned_search_slots(query),
        )
        if selected:
            return selected

    if not intent.comparison_mode or intent.referenced_product_ids:
        return scored[:limit]

    required_sub_categories = list(dict.fromkeys(intent.facets.get("sub_category", [])))
    if len(required_sub_categories) < 2:
        return scored[:limit]

    selected: list[tuple[float, dict, list[str]]] = []
    selected_ids: set[str] = set()
    for sub_category in required_sub_categories:
        match = next(
            (
                entry
                for entry in scored
                if entry[1]["raw"].get("sub_category") == sub_category
                and entry[1]["raw"].get("product_id") not in selected_ids
            ),
            None,
        )
        if match is None:
            continue
        selected.append(match)
        selected_ids.add(str(match[1]["raw"].get("product_id")))
        if len(selected) >= limit:
            return selected[:limit]

    for entry in scored:
        product_id = str(entry[1]["raw"].get("product_id"))
        if product_id in selected_ids:
            continue
        selected.append(entry)
        selected_ids.add(product_id)
        if len(selected) >= limit:
            break
    return selected[:limit]


def _fill_underfilled_with_backfill(
    selected: list[tuple[float, dict, list[str]]],
    backfill: list[tuple[float, dict, list[str]]],
    *,
    limit: int,
) -> list[tuple[float, dict, list[str]]]:
    if len(selected) >= limit or not backfill:
        return selected[:limit]
    filled = list(selected)
    selected_ids = {str(entry[1]["raw"].get("product_id")) for entry in filled}
    for entry in backfill:
        product_id = str(entry[1]["raw"].get("product_id"))
        if product_id in selected_ids:
            continue
        filled.append(entry)
        selected_ids.add(product_id)
        if len(filled) >= limit:
            break
    return filled[:limit]


def _select_scene_bundle_scored(
    scored: list[tuple[float, dict, list[str]]],
    *,
    limit: int,
    intent: QueryIntent,
    slots: list[SearchSlot] | None = None,
) -> list[tuple[float, dict, list[str]]]:
    selected: list[tuple[float, dict, list[str]]] = []
    selected_ids: set[str] = set()
    selected_sub_categories: set[str] = set()

    for slot in slots or []:
        match = _first_slot_match(scored, selected_ids, slot)
        if match is None:
            continue
        _append_selected_scored(match, selected, selected_ids, selected_sub_categories)
        if len(selected) >= limit:
            return selected[:limit]

    for category in intent.category_candidates:
        match = _first_unselected(
            scored,
            selected_ids,
            lambda entry, expected=category: _canonical_category(entry[1]) == expected,
        )
        if match is None:
            continue
        _append_selected_scored(match, selected, selected_ids, selected_sub_categories)
        if len(selected) >= limit:
            return selected[:limit]

    for entry in scored:
        product_id = str(entry[1]["raw"].get("product_id"))
        sub_category = str(entry[1]["raw"].get("sub_category", ""))
        if product_id in selected_ids or sub_category in selected_sub_categories:
            continue
        _append_selected_scored(entry, selected, selected_ids, selected_sub_categories)
        if len(selected) >= limit:
            return selected[:limit]

    for entry in scored:
        product_id = str(entry[1]["raw"].get("product_id"))
        if product_id in selected_ids:
            continue
        _append_selected_scored(entry, selected, selected_ids, selected_sub_categories)
        if len(selected) >= limit:
            break
    return selected[:limit]


def _planned_search_slots(query: str) -> list[SearchSlot]:
    slots: list[SearchSlot] = []
    for match in re.finditer(r"(?m)^-\s*搜索槽：([^\n]+)$", query):
        raw_parts = [part.strip() for part in match.group(1).split("|")]
        if not raw_parts:
            continue
        label = raw_parts[0]
        category: str | None = None
        sub_categories: list[str] = []
        effects: list[str] = []
        use_cases: list[str] = []
        for part in raw_parts[1:]:
            if "=" not in part:
                continue
            key, raw_value = [item.strip() for item in part.split("=", 1)]
            values = [value.strip() for value in re.split(r"[、,，]+", raw_value) if value.strip()]
            if key == "类目":
                category = _slot_category(values)
            elif key == "子类":
                sub_categories.extend(value for value in values if value in FACET_LEXICON["sub_category"])
            elif key == "功效":
                effects.extend(value for value in values if value in FACET_LEXICON["effect"])
            elif key == "场景":
                use_cases.extend(value for value in values if value in FACET_LEXICON["use_case"])
        if category or sub_categories or effects or use_cases:
            slots.append(
                SearchSlot(
                    label=label,
                    category=category,
                    sub_categories=tuple(dict.fromkeys(sub_categories)),
                    effects=tuple(dict.fromkeys(effects)),
                    use_cases=tuple(dict.fromkeys(use_cases)),
                )
            )
    return slots[:6]


def _slot_category(values: list[str]) -> str | None:
    for value in values:
        if value in CATEGORY_TO_RAW:
            return value
        if value in RAW_TO_CATEGORY:
            return RAW_TO_CATEGORY[value]
    return None


def _first_slot_match(
    scored: list[tuple[float, dict, list[str]]],
    selected_ids: set[str],
    slot: SearchSlot,
) -> tuple[float, dict, list[str]] | None:
    for sub_category in slot.sub_categories:
        match = _first_unselected(
            scored,
            selected_ids,
            lambda entry, expected=sub_category: _matches_slot(entry[1], slot, required_sub_category=expected),
        )
        if match is not None:
            return match
    return _first_unselected(
        scored,
        selected_ids,
        lambda entry: _matches_slot(entry[1], slot),
    )


def _matches_slot(item: dict, slot: SearchSlot, required_sub_category: str | None = None) -> bool:
    raw = item["raw"]
    if slot.category and _canonical_category(item) != slot.category:
        return False
    raw_sub_category = str(raw.get("sub_category", ""))
    if required_sub_category is not None:
        return raw_sub_category == required_sub_category
    if slot.sub_categories and raw_sub_category not in slot.sub_categories:
        return False
    text = product_search_text(item).lower()
    if slot.effects and not any(effect.lower() in text for effect in slot.effects):
        return False
    if slot.use_cases and not any(use_case.lower() in text for use_case in slot.use_cases):
        return False
    return True


def _first_unselected(
    scored: list[tuple[float, dict, list[str]]],
    selected_ids: set[str],
    predicate,
) -> tuple[float, dict, list[str]] | None:
    for entry in scored:
        product_id = str(entry[1]["raw"].get("product_id"))
        if product_id in selected_ids:
            continue
        if predicate(entry):
            return entry
    return None


def _append_selected_scored(
    entry: tuple[float, dict, list[str]],
    selected: list[tuple[float, dict, list[str]]],
    selected_ids: set[str],
    selected_sub_categories: set[str],
) -> None:
    selected.append(entry)
    selected_ids.add(str(entry[1]["raw"].get("product_id")))
    selected_sub_categories.add(str(entry[1]["raw"].get("sub_category", "")))


def _canonical_category(item: dict) -> str:
    return str(
        item.get("canonical_category")
        or CATEGORY_TO_CANONICAL.get(str(item["raw"].get("category", "")), "unknown")
    )


def _order_referenced_scored(
    selected_scored: list[tuple[float, dict, list[str]]],
    intent: QueryIntent,
) -> list[tuple[float, dict, list[str]]]:
    if not intent.referenced_product_ids:
        return selected_scored

    order = {
        product_id: index
        for index, product_id in enumerate(intent.referenced_product_ids)
    }
    indexed = list(enumerate(selected_scored))
    indexed.sort(
        key=lambda entry: (
            order.get(str(entry[1][1]["raw"].get("product_id", "")), len(order)),
            entry[0],
        )
    )
    return [pair for _, pair in indexed]


def _graph_score(intent: QueryIntent, item: dict) -> tuple[float, list[str]]:
    raw = item["raw"]
    text = product_search_text(item).lower()
    score = 0.0
    reasons: list[str] = []

    canonical_category = str(
        item.get("canonical_category")
        or CATEGORY_TO_CANONICAL.get(str(raw.get("category", "")), "unknown")
    )
    if intent.category_candidates and canonical_category in intent.category_candidates:
        score += 0.4
        reasons.append(f"graph_category:{canonical_category}")

    for sub_category in intent.facets.get("sub_category", []):
        if str(raw.get("sub_category", "")) == sub_category:
            score += 0.8
            reasons.append(f"graph_sub_category:{sub_category}")

    budget = intent.universal_constraints.budget_max
    if budget is not None and float(raw.get("base_price", 0)) <= budget:
        score += 0.3
        reasons.append("graph_price_within_budget")

    facet_weights = {
        "skin_type": 0.5,
        "effect": 0.5,
        "use_case": 0.4,
    }
    for facet_name, weight in facet_weights.items():
        for value in intent.facets.get(facet_name, []):
            if value.lower() in text:
                score += weight
                reasons.append(f"graph_{facet_name}:{value}")

    for preference in intent.soft_preferences:
        if preference.lower() in text:
            score += 0.2
            reasons.append(f"graph_soft_preference:{preference}")

    return score, reasons


def _is_hard_filtered(item: dict, filtered: list[FilteredProduct]) -> bool:
    product_id = item["raw"]["product_id"]
    return any(entry.product_id == product_id for entry in filtered)


def _matches_category_candidate(raw_category: str, candidates: list[str]) -> bool:
    allowed = {CATEGORY_TO_RAW[candidate] for candidate in candidates if candidate in CATEGORY_TO_RAW}
    return not allowed or raw_category in allowed


def _no_result_clarification(intent: QueryIntent) -> str:
    constraints: list[str] = []
    budget = intent.universal_constraints.budget_max
    if budget is not None:
        constraints.append(f"{budget:g}元以内")
    skin_types = intent.facets.get("skin_type", [])
    if skin_types:
        constraints.append(f"肤质：{'、'.join(skin_types)}")
    effects = intent.facets.get("effect", [])
    if effects:
        constraints.append(f"功效：{'、'.join(effects)}")
    sub_categories = intent.facets.get("sub_category", [])
    if sub_categories:
        constraints.append(f"品类：{'、'.join(sub_categories)}")
    use_cases = intent.facets.get("use_case", [])
    if use_cases:
        constraints.append(f"场景：{'、'.join(use_cases)}")
    if intent.exclude_terms:
        constraints.append(f"避开：{'、'.join(intent.exclude_terms)}")

    if constraints:
        joined = "；".join(constraints)
        options = _relaxation_options(intent)
        return (
            f"当前商品池里没有同时满足「{joined}」的商品。"
            f"你想优先放宽哪一项：{options}？"
        )
    return _clarification_question(intent.category_candidates, intent.facets)


def _relaxation_options(intent: QueryIntent) -> str:
    primary_category = intent.category_candidates[0] if intent.category_candidates else _category_from_facets(intent.facets)
    if primary_category == "food":
        return "预算、品类方向，还是含糖/便携/口味要求"
    if primary_category == "digital":
        return "预算、性能/续航要求，还是使用场景"
    if primary_category == "apparel":
        return "预算、尺码/材质，还是使用场景"
    if primary_category == "beauty":
        return "预算、排除条件，还是先只看其中一个功效/场景"
    return "预算、品类方向，还是需要避开的条件"


def _vector_scores(
    query: str,
    index_dir: Path | None,
    intent: QueryIntent,
) -> tuple[dict[str, float], list[RetrievalHit], dict]:
    where = _metadata_where(intent)
    if index_dir is None or not index_dir.exists():
        return {}, [], where or {}
    try:
        import chromadb
        from chromadb.config import Settings

        model = sentence_model()
        embedding = model.encode([query], normalize_embeddings=True)[0].tolist()
        with contextlib.redirect_stderr(io.StringIO()):
            client = chromadb.PersistentClient(
                path=str(index_dir),
                settings=Settings(anonymized_telemetry=False),
            )
            collection = _get_products_collection(client)
            collection_size = collection.count()
            if collection_size == 0:
                return {}, [], where or {}
            query_kwargs = {
                "query_embeddings": [embedding],
                "n_results": min(8, collection_size),
            }
            if where is not None:
                query_kwargs["where"] = where
            result = collection.query(**query_kwargs)
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0] if result.get("distances") else []
        scores: dict[str, float] = {}
        hits: list[RetrievalHit] = []
        filter_reason = f"metadata_filter:{where}" if where is not None else "metadata_filter:none"
        for rank, product_id in enumerate(ids):
            distance = float(distances[rank]) if rank < len(distances) else float(rank)
            score = max(0.0, 8.0 - rank) + max(0.0, 1.0 - distance)
            scores[product_id] = score
            hits.append(
                RetrievalHit(
                    product_id=product_id,
                    score=round(score, 3),
                    reasons=[f"vector_rank:{rank}", filter_reason],
                )
            )
        return scores, hits, where or {}
    except Exception:
        return {}, [], where or {}


def _get_products_collection(client):
    try:
        return client.get_collection("products")
    except Exception:
        return client.get_collection("beauty_products")


def _metadata_where(intent: QueryIntent) -> dict | None:
    clauses: list[dict] = []
    category_candidates = intent.category_candidates
    if category_candidates:
        clauses.append(_field_filter("canonical_category", category_candidates))

    sub_categories = intent.facets.get("sub_category", [])
    if sub_categories:
        clauses.append(_field_filter("sub_category", sub_categories))

    budget = intent.universal_constraints.budget_max
    if budget is not None:
        clauses.append({"base_price": {"$lte": budget}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _field_filter(field: str, values: list[str]) -> dict:
    unique_values = list(dict.fromkeys(values))
    if len(unique_values) == 1:
        return {field: unique_values[0]}
    return {field: {"$in": unique_values}}


def _to_card(item: dict, query: str, budget: float | None = None) -> ProductCard:
    raw = item["raw"]
    attrs = item.get("attributes", {})
    display = item.get("display", {})
    knowledge = raw.get("rag_knowledge", {})
    tags = list(dict.fromkeys(attrs.get("tags", [])[:5]))
    reason = (
        item.get("card_reason")
        or display.get("card_reason")
        or "匹配本次需求，推荐理由来自商品资料和结构化标签。"
    )
    if "防晒" in query and raw["sub_category"] == "防晒":
        reason = "防晒相关需求匹配；请结合肤质、户外时长和补涂频率选择。"
    variants = _variant_cards(raw=raw, parent_reason=reason, budget=budget)
    display_price = variants[0].price if variants else float(raw["base_price"])
    return ProductCard(
        product_id=raw["product_id"],
        title=raw["title"],
        brand=raw["brand"],
        category=raw["category"],
        sub_category=raw["sub_category"],
        price=display_price,
        image_path=raw["image_path"],
        tags=tags,
        reason=reason,
        target_users=_string_list(attrs.get("target_users", [])),
        use_cases=_string_list(attrs.get("use_cases", [])),
        selling_points=_string_list(attrs.get("selling_points", [])),
        cautions=_string_list(attrs.get("cautions", [])),
        suitable_for=_string_list(attrs.get("suitable_for", [])),
        avoid_for=_string_list(attrs.get("avoid_for", [])),
        description=_knowledge_text(knowledge),
        variants=variants,
    )


def _variant_cards(raw: dict, parent_reason: str, budget: float | None = None) -> list[ProductVariantCard]:
    variants: list[ProductVariantCard] = []
    for sku in raw.get("skus", []):
        if not isinstance(sku, dict):
            continue
        price = float(sku.get("price", raw.get("base_price", 0)))
        if budget is not None and price > budget:
            continue
        properties = _sku_properties(sku)
        label = _sku_label(properties)
        if not label:
            label = str(sku.get("sku_id", "")).strip() or "默认规格"
        variants.append(
            ProductVariantCard(
                variant_id=str(sku.get("sku_id", "")),
                parent_product_id=str(raw["product_id"]),
                label=label,
                properties=properties,
                price=price,
                image_path=str(sku.get("image_path") or raw.get("image_path", "")),
                reason=_variant_reason(label=label, price=price, parent_reason=parent_reason),
            )
        )
    return variants


def _sku_properties(sku: dict) -> dict[str, str]:
    properties = sku.get("properties", {})
    if not isinstance(properties, dict):
        return {}
    return {str(key): str(value) for key, value in properties.items() if str(value).strip()}


def _sku_label(properties: dict[str, str]) -> str:
    return " / ".join(value for value in properties.values() if value.strip())


def _variant_reason(label: str, price: float, parent_reason: str) -> str:
    return f"{label}，数据源价格 ¥{price:g}；{parent_reason}"


def _min_purchase_price(raw: dict) -> float:
    prices = [
        float(sku.get("price", raw.get("base_price", 0)))
        for sku in raw.get("skus", [])
        if isinstance(sku, dict)
    ]
    if prices:
        return min(prices)
    return float(raw.get("base_price", 0))


def _has_price_within_budget(raw: dict, budget: float) -> bool:
    skus = [sku for sku in raw.get("skus", []) if isinstance(sku, dict)]
    if skus:
        return any(float(sku.get("price", raw.get("base_price", 0))) <= budget for sku in skus)
    return float(raw.get("base_price", 0)) <= budget


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _knowledge_text(knowledge: dict) -> str:
    parts: list[str] = []
    marketing_description = knowledge.get("marketing_description", "")
    if marketing_description:
        parts.append(str(marketing_description))
    for item in knowledge.get("official_faq", []):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if question or answer:
            parts.append(f"官方FAQ：{question} {answer}".strip())
    for item in knowledge.get("user_reviews", []):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if content:
            parts.append(f"用户评价：{content}")
    return "\n".join(parts)


def _context_block(item: dict, budget: float | None = None) -> str:
    raw = item["raw"]
    knowledge = raw.get("rag_knowledge", {})
    attrs = item.get("attributes", {})
    beauty = item.get("beauty_attributes", {})
    category_attrs = item.get("category_attributes", {})
    variants = item.get("variants", {})
    source = item.get("source", {})
    return f"""商品ID: {raw['product_id']}
标题: {raw['title']}
品牌: {raw['brand']}
类目: {raw['category']} / {raw['sub_category']}
价格: {raw['base_price']}
结构化标签: {attrs}
美妆属性: {beauty}
品类属性: {category_attrs}
变体维度: {variants}
可用SKU: {_sku_context(raw, budget)}
证据来源: {source}
商品资料: {_knowledge_text(knowledge)}
"""


def _sku_context(raw: dict, budget: float | None = None) -> list[dict[str, object]]:
    context: list[dict[str, object]] = []
    for sku in raw.get("skus", []):
        if not isinstance(sku, dict):
            continue
        price = float(sku.get("price", raw.get("base_price", 0)))
        if budget is not None and price > budget:
            continue
        properties = _sku_properties(sku)
        context.append(
            {
                "variant_id": sku.get("sku_id", ""),
                "label": _sku_label(properties),
                "properties": properties,
                "price": price,
            }
        )
    return context
