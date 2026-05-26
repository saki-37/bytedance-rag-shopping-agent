# 安全与本地配置

日期：2026-05-26  
用途：记录 API Key、`.env`、提交前检查和脱敏要求，避免因为共享密钥泄露导致比赛和工程风险。

## 核心原则

1. 真实 API Key 只放本地 `.env`。
2. `.env` 已在 `.gitignore` 中，不提交。
3. `.env.example` 只保留空值或占位说明。
4. 包含共享 API Key 的官方说明会原文不能原样提交到公开仓库。
5. Demo、截图、文档中展示配置时必须脱敏。

## 本地文件分工

| 文件 | 是否提交 | 用途 |
| --- | --- | --- |
| `.env` | 不提交 | 本地真实 API Key、模型名、base URL |
| `.env.example` | 提交 | 给别人说明需要哪些环境变量，不含真实值 |
| `docs/*.md` | 提交 | 设计、评测、Demo 说明；不能含真实 Key |
| 官方说明会原文 | 不建议提交 | 若包含共享 Key，只作为本地参考 |

## 提交前自动扫描

项目提供了一个轻量本地扫描脚本：

```bash
python3 scripts/scan_secrets.py --staged
```

它会扫描“即将被 commit 的内容”，如果发现类似 `ark-...`、`sk-...` 或已经填值的 `API_KEY=...`，会阻止提交并打印脱敏后的风险位置。

也可以手动扫描当前仓库中所有 tracked 和未忽略文件：

```bash
python3 scripts/scan_secrets.py --all
```

## Git Hook

本仓库提供 `.githooks/pre-commit`。启用后，每次 `git commit` 前都会自动运行：

```bash
python3 scripts/scan_secrets.py --staged
```

本地启用方式：

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit scripts/scan_secrets.py
```

这只影响当前本地仓库，不会把你的真实密钥写入 Git。

## 如果扫描失败

1. 不要继续提交。
2. 把真实值移到 `.env`。
3. 文档里改成 `<redacted>`、`YOUR_API_KEY` 或空值。
4. 重新运行：

```bash
python3 scripts/scan_secrets.py --staged
```

## 仍然需要人工注意的情况

自动扫描不是绝对保险，以下情况仍然需要人工检查：

1. 截图、录屏、PDF 中出现真实 Key。
2. 官方说明会原文包含 Key。
3. 聊天记录或复制粘贴材料中包含 Key。
4. 非常规格式的密钥没有被规则匹配。

最终提交前，建议同时确认：

```bash
git status --short
git diff --cached --name-only
python3 scripts/scan_secrets.py --staged
```
