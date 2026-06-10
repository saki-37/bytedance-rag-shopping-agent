#!/usr/bin/env python3
"""Scan staged or repository files for likely leaked secrets.

This is intentionally lightweight and local. It focuses on high-risk patterns
for this project, especially Ark/Doubao keys, while avoiding printing the
secret value back to the terminal.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]


RULES = [
    Rule("Ark API key", re.compile(r"ark-[A-Za-z0-9_-]{20,}")),
    # 飞书/Markdown 导出会把连字符转义成 "\-"，导致明文 Key 绕过上面的规则
    #（曾真实发生：课题说明文档里的 ark\-xxxx\-... 未被扫出）。
    Rule(
        "Ark/OpenAI API key (escaped dashes)",
        re.compile(r"(?:ark|sk)(?:\\-[A-Za-z0-9_]{2,}){3,}"),
    ),
    Rule("OpenAI-style API key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    Rule("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    Rule(
        "Generic populated secret assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|secret|token|authorization|bearer)\b"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9._/\-+]{16,}"
        ),
    ),
]


SAFE_REFERENCES = (
    "settings.",
    "os.environ",
    "os.getenv",
    "getenv(",
    "YOUR_",
    "<redacted",
    "REDACTED",
)


BINARY_SUFFIXES = {
    ".a",
    ".apk",
    ".class",
    ".dex",
    ".gif",
    ".jar",
    ".jpeg",
    ".jpg",
    ".keystore",
    ".mov",
    ".mp4",
    ".pdf",
    ".png",
    ".so",
    ".webp",
    ".zip",
}


def run_git(args: list[str]) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def staged_paths() -> list[str]:
    output = run_git(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"])
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def repository_paths() -> list[str]:
    output = run_git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def staged_content(path: str) -> bytes | None:
    try:
        return run_git(["show", f":{path}"])
    except subprocess.CalledProcessError:
        return None


def working_tree_content(path: str) -> bytes | None:
    full_path = ROOT / path
    if not full_path.is_file():
        return None
    return full_path.read_bytes()


def should_skip(path: str, content: bytes | None) -> bool:
    if content is None:
        return True
    if Path(path).suffix.lower() in BINARY_SUFFIXES:
        return True
    if b"\0" in content[:4096]:
        return True
    return False


def scan_content(path: str, content: bytes) -> list[str]:
    text = content.decode("utf-8", errors="ignore")
    findings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            matches = list(rule.pattern.finditer(line))
            visible_matches = [
                match for match in matches if not is_safe_reference(match.group(0))
            ]
            if visible_matches:
                redacted = line
                for match in visible_matches:
                    redacted = redacted.replace(match.group(0), "<redacted secret>")
                findings.append(f"{path}:{line_number}: {rule.name}: {redacted.strip()}")
    return findings


def is_safe_reference(match_text: str) -> bool:
    return any(reference in match_text for reference in SAFE_REFERENCES)


# 这些二进制文档无法做文本扫描，但可能内嵌密钥（曾真实发生：课题 PDF 内嵌
# 共用 APIKey 被提交）。一旦被 Git 跟踪就直接报错，要求人工确认或移出 Git。
RISKY_TRACKED_BINARY_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".zip"}


def tracked_paths() -> set[str]:
    output = run_git(["ls-files", "-z", "--cached"])
    return {item.decode("utf-8") for item in output.split(b"\0") if item}


def risky_tracked_binaries() -> list[str]:
    findings: list[str] = []
    for path in sorted(tracked_paths()):
        if Path(path).suffix.lower() in RISKY_TRACKED_BINARY_SUFFIXES:
            findings.append(
                f"{path}: Tracked binary document: cannot be text-scanned and may embed "
                "secrets; keep it out of Git (gitignore) or manually verify and allowlist."
            )
    return findings


def scan(paths: list[str], *, staged: bool) -> list[str]:
    findings: list[str] = []
    for path in paths:
        content = staged_content(path) if staged else working_tree_content(path)
        if should_skip(path, content):
            continue
        findings.extend(scan_content(path, content or b""))
    findings.extend(risky_tracked_binaries())
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan for likely secret leaks.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="scan staged commit content")
    mode.add_argument("--all", action="store_true", help="scan tracked and untracked non-ignored files")
    args = parser.parse_args()

    paths = staged_paths() if args.staged else repository_paths()
    findings = scan(paths, staged=args.staged)
    if findings:
        print("Secret scan failed. Review these likely secret leaks:", file=sys.stderr)
        for finding in findings:
            print(f"  - {finding}", file=sys.stderr)
        print(
            "\nMove real secrets to local .env, keep .env ignored, and commit only placeholders.",
            file=sys.stderr,
        )
        return 1

    print(f"Secret scan passed ({len(paths)} files checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
