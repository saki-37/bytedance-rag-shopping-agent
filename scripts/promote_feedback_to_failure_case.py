#!/usr/bin/env python3
"""Promote inaccurate feedback records into triage-ready failure-case drafts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEEDBACK_DIR = ROOT / "data" / "tmp" / "feedback"
DEFAULT_TRACE_DIR = ROOT / "data" / "tmp" / "traces"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "tmp" / "failure_cases"

FAILURE_LABELS = {
    "product_mismatch": "商品错位/推荐对象不对",
    "reference_resolution": "多轮指代或序号解析问题",
    "price_or_budget": "价格/预算问题",
    "unsupported_claim": "资料外承诺或幻觉",
    "retrieval_filtering": "检索/过滤/排序问题",
    "ui_display": "Android 展示或交互问题",
    "trace_missing": "缺少可追溯证据",
    "needs_human_context": "需要人工补充反馈原因",
}


@dataclass
class FeedbackRecord:
    path: Path
    line_number: int
    payload: dict[str, Any]


def main() -> None:
    args = parse_args()
    records = load_feedback_records(args.feedback_dir, args.feedback, args.since, args.limit)
    traces = load_traces(args.trace_dir) if args.attach_trace else {}
    drafts = [build_failure_case(record, traces) for record in records]

    output_stem = args.output_prefix or f"feedback_failure_cases_{datetime.now():%Y-%m-%d_%H%M%S}"
    jsonl_path = args.output_dir / f"{output_stem}.jsonl"
    md_path = args.output_dir / f"{output_stem}.md"

    if not args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(jsonl_path, drafts)
        write_markdown(md_path, drafts)

    print(f"Loaded feedback records: {len(records)}")
    print(f"Generated failure drafts: {len(drafts)}")
    if args.dry_run:
        print("Dry run: no files written")
    else:
        print(f"JSONL: {jsonl_path}")
        print(f"Markdown: {md_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert inaccurate feedback JSONL records into failure-case drafts."
    )
    parser.add_argument(
        "--feedback-dir",
        type=Path,
        default=DEFAULT_FEEDBACK_DIR,
        help="Directory containing feedback_YYYY-MM-DD.jsonl files.",
    )
    parser.add_argument(
        "--trace-dir",
        type=Path,
        default=DEFAULT_TRACE_DIR,
        help="Directory containing trace_YYYY-MM-DD.jsonl files for trace_id enrichment.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated failure-case drafts.",
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Output filename prefix. Defaults to feedback_failure_cases_<timestamp>.",
    )
    parser.add_argument(
        "--feedback",
        choices=("inaccurate", "helpful", "all"),
        default="inaccurate",
        help="Feedback type to promote. Defaults to inaccurate.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only include records created on or after this date or datetime.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of records to include.")
    parser.add_argument(
        "--no-trace",
        dest="attach_trace",
        action="store_false",
        help="Do not look up runtime traces by trace_id.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing files.")
    parser.set_defaults(attach_trace=True)
    return parser.parse_args()


def load_feedback_records(
    feedback_dir: Path, feedback_type: str, since: str | None, limit: int | None
) -> list[FeedbackRecord]:
    if not feedback_dir.exists():
        return []
    since_dt = parse_datetime(since) if since else None
    records: list[FeedbackRecord] = []
    for path in sorted(feedback_dir.glob("feedback_*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if feedback_type != "all" and payload.get("feedback") != feedback_type:
                    continue
                created_at = parse_datetime(str(payload.get("created_at") or ""))
                if since_dt and (not created_at or created_at < since_dt):
                    continue
                records.append(FeedbackRecord(path=path, line_number=line_number, payload=payload))
                if limit and len(records) >= limit:
                    return records
    return records


def load_traces(trace_dir: Path) -> dict[str, dict[str, Any]]:
    traces: dict[str, dict[str, Any]] = {}
    if not trace_dir.exists():
        return traces
    for path in sorted(trace_dir.glob("trace_*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                trace_id = payload.get("trace_id")
                if trace_id:
                    traces[str(trace_id)] = payload
    return traces


def build_failure_case(record: FeedbackRecord, runtime_traces: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = record.payload
    snapshot = payload.get("snapshot") or {}
    trace_id = payload.get("trace_id") or snapshot.get("trace_id")
    snapshot_trace = snapshot.get("trace")
    runtime_trace = runtime_traces.get(str(trace_id)) if trace_id else None
    trace = snapshot_trace or (runtime_trace or {}).get("retrieval_trace")
    products = list(snapshot.get("products") or [])
    answer = str(snapshot.get("answer") or "")
    message = str(snapshot.get("message") or "")
    note = str(payload.get("note") or "")
    retrieval_message = str(snapshot.get("retrieval_message") or "")

    failure_types = infer_failure_types(
        message=message,
        answer=answer,
        note=note,
        retrieval_message=retrieval_message,
        products=products,
        trace=trace,
        trace_id=trace_id,
    )
    suite = suggest_suite(message, failure_types)
    return {
        "schema_version": "1.0",
        "case_id": make_case_id(payload, record),
        "status": "needs_triage",
        "source": {
            "feedback_file": display_path(record.path),
            "line_number": record.line_number,
            "record_id": payload.get("record_id"),
            "created_at": payload.get("created_at"),
            "conversation_id": payload.get("conversation_id"),
            "turn_id": payload.get("turn_id"),
            "trace_id": trace_id,
        },
        "user_message": message,
        "retrieval_message": retrieval_message or None,
        "assistant_answer": answer or None,
        "feedback_note": note or None,
        "suggested_failure_types": failure_types,
        "suggested_failure_labels": [FAILURE_LABELS[item] for item in failure_types],
        "products": summarize_products(products),
        "trace_summary": summarize_trace(trace, runtime_trace),
        "benchmark_candidate": {
            "suggested_suite": suite,
            "reason": explain_suite_choice(suite),
            "promote": "manual_review_required",
        },
        "triage_questions": build_triage_questions(failure_types),
        "manual_fields": {
            "expected_behavior": "",
            "actual_issue": "",
            "root_cause": "",
            "owner": "",
            "decision": "needs_more_info",
            "benchmark_case_id": "",
        },
    }


def infer_failure_types(
    *,
    message: str,
    answer: str,
    note: str,
    retrieval_message: str,
    products: list[dict[str, Any]],
    trace: dict[str, Any] | None,
    trace_id: str | None,
) -> list[str]:
    del products
    haystack = normalize_text(" ".join([message, answer, note, retrieval_message]))
    types: list[str] = []
    if contains_any(haystack, ["产品1", "产品2", "产品3", "第1", "第2", "第3", "第一", "第二", "第三", "前两个", "这几个", "刚才"]):
        types.append("reference_resolution")
    if contains_any(haystack, ["商品错", "推荐错", "错位", "不是这个", "不对应", "混入", "不相关", "方便面", "咖啡"]):
        types.append("product_mismatch")
    if contains_any(haystack, ["价格", "预算", "超预算", "元以内", "¥", "￥", "便宜", "贵"]):
        types.append("price_or_budget")
    if contains_any(
        haystack,
        ["绝对", "一定", "保证", "不会过敏", "不会闷痘", "不会堵塞", "治疗", "治愈", "库存", "现货", "优惠", "折扣", "下单", "购买链接"],
    ):
        types.append("unsupported_claim")
    if contains_any(haystack, ["召回", "检索", "排序", "类目", "品类", "筛选", "过滤", "漏掉", "误召回"]):
        types.append("retrieval_filtering")
    if contains_any(haystack, ["ui", "卡片", "表格", "markdown", "显示", "排版", "截图", "详情", "按钮", "加载", "转圈", "加粗"]):
        types.append("ui_display")
    if not trace_id and not trace:
        types.append("trace_missing")
    if not types:
        types.append("needs_human_context")
    return dedupe(types)


def suggest_suite(message: str, failure_types: list[str]) -> str:
    normalized = normalize_text(message)
    if "ui_display" in failure_types:
        return "manual_android_acceptance"
    if "unsupported_claim" in failure_types or contains_any(normalized, ["过敏", "孕期", "成分", "功效", "安全", "保证"]):
        return "groundedness_cases"
    if "reference_resolution" in failure_types:
        if contains_any(normalized, ["对比", "比较", "哪个", "怎么选"]):
            return "comparison_queries"
        return "conversation_cases"
    if contains_any(normalized, ["对比", "比较", "哪个", "怎么选"]):
        return "comparison_queries"
    return "conversation_cases"


def explain_suite_choice(suite: str) -> str:
    if suite == "manual_android_acceptance":
        return "反馈指向展示/交互问题，先进入人工 Android 验收记录。"
    if suite == "groundedness_cases":
        return "反馈涉及资料外承诺、安全边界或事实主张，适合沉淀为 groundedness case。"
    if suite == "comparison_queries":
        return "反馈涉及对比、序号或商品选择，适合沉淀为 comparison/conversation 回归。"
    return "反馈更像多轮意图或普通推荐问题，适合先进入 conversation case 草稿。"


def summarize_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for product in products[:5]:
        variants = []
        for variant in product.get("variants") or []:
            variants.append(
                {
                    "variant_id": variant.get("variant_id"),
                    "label": variant.get("label"),
                    "price": variant.get("price"),
                }
            )
        summary.append(
            {
                "product_id": product.get("product_id"),
                "title": product.get("title"),
                "brand": product.get("brand"),
                "category": product.get("category"),
                "sub_category": product.get("sub_category"),
                "price": product.get("price"),
                "variants": variants,
            }
        )
    return summary


def summarize_trace(trace: dict[str, Any] | None, runtime_trace: dict[str, Any] | None) -> dict[str, Any]:
    if not trace and not runtime_trace:
        return {"available": False}
    trace = trace or {}
    parsed_intent = trace.get("parsed_intent") or {}
    final_ranking = trace.get("final_ranking") or []
    planner_trace = trace.get("planner_trace") or {}
    return {
        "available": True,
        "runtime_endpoint": (runtime_trace or {}).get("endpoint"),
        "runtime_status": (runtime_trace or {}).get("status"),
        "parsed_intent": {
            "category_candidates": parsed_intent.get("category_candidates"),
            "referenced_product_ids": parsed_intent.get("referenced_product_ids"),
            "budget_max": ((parsed_intent.get("universal_constraints") or {}).get("budget_max")),
            "facets": parsed_intent.get("facets"),
            "exclude_terms": parsed_intent.get("exclude_terms"),
            "comparison_mode": parsed_intent.get("comparison_mode"),
            "needs_clarification": parsed_intent.get("needs_clarification"),
        },
        "filter_summary": trace.get("filter_summary"),
        "final_ranking_product_ids": [item.get("product_id") for item in final_ranking[:8]],
        "guardrail_checks": trace.get("guardrail_checks"),
        "planner_trace": {
            "called": planner_trace.get("called"),
            "applied": planner_trace.get("applied"),
            "fallback_reason": planner_trace.get("fallback_reason"),
            "latency_ms": planner_trace.get("latency_ms"),
        },
    }


def build_triage_questions(failure_types: list[str]) -> list[str]:
    questions = [
        "用户认为哪里不准确？请用一句话写实际问题。",
        "正确结果应该是什么？如果是商品问题，请写出期望 product_id / SKU。",
    ]
    if "reference_resolution" in failure_types:
        questions.append("本轮是否依赖上一轮商品顺序？请核对上一轮可见卡片顺序。")
    if "price_or_budget" in failure_types:
        questions.append("价格或预算是否来自 raw / SKU 数据？请核对 parent price 和 variant price。")
    if "unsupported_claim" in failure_types:
        questions.append("被质疑的事实主张能否在 raw / enriched / FAQ / 评论中找到直接证据？")
    if "ui_display" in failure_types:
        questions.append("这是数据问题还是展示问题？请补充截图或录屏路径。")
    return questions


def write_jsonl(path: Path, drafts: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for draft in drafts:
            f.write(json.dumps(draft, ensure_ascii=False) + "\n")


def write_markdown(path: Path, drafts: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("# Feedback Failure Case Drafts\n\n")
        f.write(f"Generated at: {datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write(
            "These drafts are generated from local feedback JSONL records. "
            "They are triage inputs, not confirmed benchmark cases.\n\n"
        )
        if not drafts:
            f.write("No matching feedback records found.\n")
            return
        for index, draft in enumerate(drafts, start=1):
            source = draft["source"]
            f.write(f"## {index}. {draft['case_id']}\n\n")
            f.write(f"- Status: `{draft['status']}`\n")
            f.write(f"- Feedback record: `{source.get('record_id')}`\n")
            f.write(f"- Trace ID: `{source.get('trace_id')}`\n")
            f.write(f"- Suggested suite: `{draft['benchmark_candidate']['suggested_suite']}`\n")
            f.write("- Suggested failure types: " + ", ".join(f"`{item}`" for item in draft["suggested_failure_types"]) + "\n\n")
            f.write("**User message**\n\n")
            f.write(blockquote_or_empty(draft.get("user_message")))
            f.write("\n**Assistant answer**\n\n")
            f.write(blockquote_or_empty(truncate(draft.get("assistant_answer"), 700)))
            f.write("\n**Feedback note**\n\n")
            f.write(blockquote_or_empty(draft.get("feedback_note")))
            f.write("\n**Products**\n\n")
            for product in draft["products"]:
                price = product.get("price")
                price_text = f"¥{price}" if price is not None else "price unknown"
                f.write(
                    f"- `{product.get('product_id')}` {product.get('brand') or ''} "
                    f"{product.get('title') or ''} `{price_text}`\n"
                )
                for variant in product.get("variants") or []:
                    variant_price = variant.get("price")
                    variant_price_text = f"¥{variant_price}" if variant_price is not None else "price unknown"
                    f.write(f"  - `{variant.get('variant_id')}` {variant.get('label')} `{variant_price_text}`\n")
            if not draft["products"]:
                f.write("- None\n")
            f.write("\n**Trace summary**\n\n")
            f.write("```json\n")
            f.write(json.dumps(draft["trace_summary"], ensure_ascii=False, indent=2))
            f.write("\n```\n\n")
            f.write("**Triage questions**\n\n")
            for question in draft["triage_questions"]:
                f.write(f"- [ ] {question}\n")
            f.write("\n**Manual fields**\n\n")
            for key in draft["manual_fields"]:
                f.write(f"- {key}: \n")
            f.write("\n")


def blockquote_or_empty(value: str | None) -> str:
    if not value:
        return "> _empty_\n\n"
    return "\n".join(f"> {line}" for line in str(value).splitlines()) + "\n\n"


def truncate(value: str | None, max_chars: int) -> str | None:
    if not value or len(value) <= max_chars:
        return value
    return value[: max_chars - 3] + "..."


def make_case_id(payload: dict[str, Any], record: FeedbackRecord) -> str:
    created = parse_datetime(str(payload.get("created_at") or "")) or datetime.now()
    record_id = str(payload.get("record_id") or f"{record.line_number}")
    short_id = re.sub(r"[^a-zA-Z0-9]", "", record_id)[:8] or str(record.line_number)
    return f"FB-{created:%Y%m%d}-{short_id}"


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return with_timezone(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        try:
            return with_timezone(datetime.fromisoformat(f"{value}T00:00:00"))
        except ValueError:
            return None


def with_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def contains_any(value: str, needles: list[str]) -> bool:
    return any(normalize_text(needle) in value for needle in needles)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


if __name__ == "__main__":
    main()
