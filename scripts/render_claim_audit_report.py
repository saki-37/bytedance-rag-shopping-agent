#!/usr/bin/env python3
"""Render a small claim-level groundedness audit into Markdown and JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


VALID_VERDICTS = {"supported", "unsupported", "needs_boundary"}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("claim audit sample file must contain a JSON object")
    return payload


def evidence_items(claim: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = claim.get("evidence", [])
    return evidence if isinstance(evidence, list) else []


def claim_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in payload.get("samples", []):
        sample_products = sample.get("product_ids", [])
        for claim_index, claim in enumerate(sample.get("claims", []), start=1):
            evidence = evidence_items(claim)
            product_ids = claim.get("product_ids", sample_products)
            rows.append(
                {
                    "claim_id": f"{sample.get('id', 'UNKNOWN')}.{claim_index}",
                    "sample_id": sample.get("id", ""),
                    "sample_title": sample.get("title", ""),
                    "risk": sample.get("risk", ""),
                    "question": sample.get("question", ""),
                    "product_ids": product_ids,
                    "claim": claim.get("claim", ""),
                    "expected_verdict": claim.get("expected_verdict", ""),
                    "safe_wording": claim.get("safe_wording", ""),
                    "judge_note": claim.get("judge_note", ""),
                    "evidence": evidence,
                    "evidence_sources": sorted(
                        {
                            str(item.get("source", "unknown"))
                            for item in evidence
                            if isinstance(item, dict)
                        }
                    ),
                    "evidence_paths": sorted(
                        {
                            str(item.get("path", ""))
                            for item in evidence
                            if isinstance(item, dict) and item.get("path")
                        }
                    ),
                }
            )
    return rows


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        return ["root.samples must be a non-empty list"]

    seen_sample_ids: set[str] = set()
    for sample_index, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict):
            errors.append(f"samples[{sample_index}] must be an object")
            continue
        sample_id = str(sample.get("id", "")).strip()
        if not sample_id:
            errors.append(f"samples[{sample_index}] is missing id")
        elif sample_id in seen_sample_ids:
            errors.append(f"duplicate sample id: {sample_id}")
        seen_sample_ids.add(sample_id)

        if not str(sample.get("title", "")).strip():
            errors.append(f"{sample_id or sample_index} is missing title")
        claims = sample.get("claims")
        if not isinstance(claims, list) or not claims:
            errors.append(f"{sample_id or sample_index} must contain claims")
            continue

        for claim_index, claim in enumerate(claims, start=1):
            prefix = f"{sample_id or sample_index}.{claim_index}"
            if not isinstance(claim, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if not str(claim.get("claim", "")).strip():
                errors.append(f"{prefix} is missing claim text")
            verdict = str(claim.get("expected_verdict", "")).strip()
            if verdict not in VALID_VERDICTS:
                errors.append(
                    f"{prefix} expected_verdict must be one of "
                    f"{sorted(VALID_VERDICTS)}"
                )
            if not str(claim.get("judge_note", "")).strip():
                errors.append(f"{prefix} is missing judge_note")
            evidence = evidence_items(claim)
            if not evidence:
                errors.append(f"{prefix} must contain at least one evidence item")
                continue
            for evidence_index, item in enumerate(evidence, start=1):
                evidence_prefix = f"{prefix}.evidence[{evidence_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{evidence_prefix} must be an object")
                    continue
                if not str(item.get("source", "")).strip():
                    errors.append(f"{evidence_prefix} is missing source")
                if not str(item.get("path", "")).strip():
                    errors.append(f"{evidence_prefix} is missing path")
                if not str(item.get("quote", "")).strip():
                    errors.append(f"{evidence_prefix} is missing quote")
            if verdict == "needs_boundary" and not str(
                claim.get("safe_wording", "")
            ).strip():
                errors.append(f"{prefix} needs safe_wording for boundary rewrite")
    return errors


def md_cell(value: Any) -> str:
    text = str(value) if value is not None else ""
    return text.replace("\n", "<br>").replace("|", "\\|")


def short_text(value: str, limit: int = 70) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_markdown(
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
    errors: list[str],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    verdict_counts = Counter(row["expected_verdict"] for row in rows)
    risk_counts = Counter(row["risk"] for row in rows)

    lines: list[str] = [
        "# Claim-level Judge 样例报告",
        "",
        f"- 样例文件：`{path_to_display(payload.get('_source_path', ''))}`",
        f"- 样例数：{len(payload.get('samples', []))}",
        f"- Claim 数：{len(rows)}",
        f"- 校验状态：{'PASS' if not errors else 'FAIL'}",
        "",
        "## Verdict 汇总",
        "",
        "| Verdict | Count |",
        "| --- | ---: |",
    ]
    for verdict in sorted(VALID_VERDICTS):
        lines.append(f"| `{verdict}` | {verdict_counts.get(verdict, 0)} |")

    lines.extend(
        [
            "",
            "## Risk 汇总",
            "",
            "| Risk | Count |",
            "| --- | ---: |",
        ]
    )
    for risk, count in sorted(risk_counts.items()):
        lines.append(f"| `{md_cell(risk)}` | {count} |")

    lines.extend(
        [
            "",
            "## Claim 表",
            "",
            "| Claim ID | Risk | Verdict | Product | Claim | Evidence | Safe wording |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        product_ids = ", ".join(row["product_ids"])
        sources = ", ".join(row["evidence_sources"])
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(row["claim_id"]),
                    md_cell(row["risk"]),
                    f"`{md_cell(row['expected_verdict'])}`",
                    md_cell(product_ids),
                    md_cell(short_text(row["claim"])),
                    md_cell(sources),
                    md_cell(short_text(row["safe_wording"], 90)),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 逐条证据", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row['claim_id']} {row['sample_title']}",
                "",
                f"- Verdict: `{row['expected_verdict']}`",
                f"- Claim: {row['claim']}",
                f"- Safe wording: {row['safe_wording']}",
                f"- Judge note: {row['judge_note']}",
                "- Evidence:",
            ]
        )
        for item in row["evidence"]:
            source = item.get("source", "unknown")
            source_path = item.get("path", "")
            quote = item.get("quote", "")
            lines.append(f"  - `{source}` / `{source_path}`: {quote}")
        lines.append("")

    if errors:
        lines.extend(["## 校验错误", ""])
        for error in errors:
            lines.append(f"- {error}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def path_to_display(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def parse_args(argv: list[str]) -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "data/eval/claim_audit_samples.json",
        help="Path to claim audit sample JSON.",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=root / "data/tmp/evals/claim_audit_report.md",
        help="Path to write the Markdown report.",
    )
    parser.add_argument(
        "--jsonl-output",
        type=Path,
        default=root / "data/tmp/evals/claim_audit_report.jsonl",
        help="Path to write flattened JSONL claims.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when validation errors are found.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    payload = load_payload(args.input)
    payload["_source_path"] = args.input
    errors = validate_payload(payload)
    rows = claim_rows(payload)

    write_jsonl(rows, args.jsonl_output)
    write_markdown(payload, rows, errors, args.markdown_output)

    print(
        json.dumps(
            {
                "samples": len(payload.get("samples", [])),
                "claims": len(rows),
                "validation": "PASS" if not errors else "FAIL",
                "markdown_output": str(args.markdown_output),
                "jsonl_output": str(args.jsonl_output),
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if errors and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
