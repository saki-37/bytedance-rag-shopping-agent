# 用户记忆与本地偏好层方案

日期：2026-06-09

用途：把“多轮上下文”继续往下推进到“跨会话用户偏好 / 约束 / 交互习惯”的本地化记忆层，并给后续实现代理一份可直接拆任务的方案。

## 背景

当前项目已经有一条比较完整的上下文链路：

- `history` 和 `conversation_state` 负责本轮对话内的预算、类目、排除条件、商品指代和比较对象继承。
- Always-light Planner 负责把口语、多轮、隐含偏好翻译成可校验的 retrieval plan。
- Runtime trace 和 feedback 负责把现场失败转成可复盘的证据快照。

这条链路解决的是“这次对话里用户刚刚说了什么”。用户记忆层再往下一步，解决的是：

```text
同一个用户跨会话反复出现的约束、偏好、近期目标和交互习惯
```

典型例子：

- 用户长期不能吃某类成分，或明确说过要避开某类商品。
- 用户最近在运动、通勤、旅行、控糖、换季护肤等场景里消费意愿更高。
- 用户偏好简短回答、详细解释，或希望推荐理由更可追溯。

这不是替代 Planner，也不是替代 retrieval。它是检索前的本地用户状态层，给 Planner 和 retrieval 提供更稳定的个人化输入。

## 当前决策

短期建议采用：

```text
本仓库结构化 LocalMemoryProvider
  -> 硬约束由本地 schema 和规则执行
  -> 软偏好 / 近期兴趣作为 Planner 和 rerank 的辅助上下文
  -> Mem0 只作为可选 provider，不接管硬约束
```

不建议几个小时内直接做：

- 直接上 Mem0 OSS 自托管全家桶。
- 让 Mem0 的语义召回直接决定过滤结果。
- 把用户所有聊天自动写进长期记忆。
- 推断医疗、身份、残障等敏感信息并自动用于推荐。

原因：

- 本项目已有 FastAPI、Ark/OpenAI-compatible provider、Chroma 商品索引和本地 trace；快速 demo 阶段不宜把基础设施一次换太多。
- 过敏、禁忌、预算上限、无障碍限制这类约束必须结构化执行，不能只依赖语义搜索。
- Mem0 很适合作为“软记忆抽取和召回层”，但硬过滤应该留在本仓库的 deterministic path。

## Mem0 调研结论

Mem0 当前适合做可选增强，不适合在本项目几小时 demo 里成为唯一实现。

可借鉴点：

| 方向 | Mem0 能力 | 本项目用法 |
| --- | --- | --- |
| Python / Node SDK | 可作为库嵌入应用 | 后续可做 `Mem0MemoryProvider` |
| 自托管 server | 可运行 server + dashboard + per-user API key | 适合后续生产化，不适合快速 demo |
| 用户级 add/search | 支持按 `user_id` 写入和召回记忆 | 用于软偏好、近期兴趣、交互习惯 |
| 可配置组件 | 可配置 LLM、embedder、vector store、reranker | 若接入，应复用现有 provider 思路，避免重复基础设施 |

官方参考：

- Mem0 OSS overview: https://docs.mem0.ai/open-source/overview
- Mem0 OSS configuration: https://docs.mem0.ai/open-source/configuration

## 记忆分层

### 1. 硬约束层

必须满足，优先级高于当前 query、长期偏好和短期兴趣。

示例字段：

```json
{
  "allergies": ["坚果", "乳制品"],
  "avoid_terms": ["咖啡因", "酒精味太重"],
  "brand_exclude": ["某品牌"],
  "budget_max": 300,
  "accessibility_needs": ["low_vision_mode"]
}
```

执行规则：

- 只从用户明确声明、用户编辑或可信业务导入中产生。
- 不从单次浏览、单次点击或模型猜测中自动升级。
- retrieval 执行层必须把它转成 `exclude_terms`、`budget_max`、`brand_exclude` 或未来更明确的 metadata filter。
- 如果商品数据没有对应字段，只能提示“资料不足，建议核对”，不能假装已完成过滤。

### 2. 长期偏好层

稳定但可变，用于排序和解释，不直接硬过滤。

示例字段：

```json
{
  "preferred_categories": {
    "食品饮料": 0.7,
    "服饰运动": 0.5
  },
  "preferred_tags": {
    "低糖": 0.8,
    "通勤": 0.6,
    "轻量": 0.5
  },
  "price_sensitivity": 0.7
}
```

执行规则：

- 连续多次行为或显式反馈才更新。
- 只参与 rerank / Planner context / answer style。
- 与当前用户明确需求冲突时，让当前需求优先。

### 3. 短期快照层

反映最近几天或本轮周期的兴趣，带 TTL 和衰减。

示例字段：

```json
{
  "recent_interests": [
    {
      "key": "运动",
      "weight": 0.8,
      "source": "recent_query",
      "created_at": "2026-06-09T12:00:00+08:00",
      "ttl_days": 7
    }
  ],
  "recent_avoidance": [
    {
      "key": "太甜",
      "weight": 0.7,
      "source": "feedback",
      "created_at": "2026-06-09T12:00:00+08:00",
      "ttl_days": 14
    }
  ]
}
```

执行规则：

- 默认 3 / 7 / 30 天 TTL。
- 用于 query expansion 和 rerank 加权。
- 过期后不再进入 Planner context。

### 4. 交互偏好层

影响回答形式，不改变推荐候选边界。

示例字段：

```json
{
  "answer_length": "brief",
  "explanation_depth": "medium",
  "tone": "warm_pragmatic",
  "show_trace_reason": true
}
```

执行规则：

- 注入 `stream_answer` 的 prompt 或回答模板。
- 不参与硬过滤。
- 不能让回答绕过 groundedness 和 guardrail。

## 最小 Schema

建议新增本地 JSON schema，存放在 `data/tmp/user_memory/{user_id}.json`。`data/tmp/` 已是本地临时目录，不进入 Git。

```json
{
  "schema_version": "0.1",
  "user_id": "local-demo-user",
  "updated_at": "2026-06-09T12:00:00+08:00",
  "constraints": {
    "allergies": [],
    "avoid_terms": [],
    "brand_exclude": [],
    "budget_max": null,
    "accessibility_needs": []
  },
  "long_term_preferences": {
    "preferred_categories": {},
    "preferred_tags": {},
    "price_sensitivity": null
  },
  "short_term_snapshots": {
    "recent_interests": [],
    "recent_avoidance": []
  },
  "interaction_preferences": {
    "answer_length": "normal",
    "explanation_depth": "medium",
    "tone": "natural",
    "show_trace_reason": true
  },
  "governance": {
    "auto_learn_enabled": false,
    "user_editable": true,
    "retention_days": 30
  },
  "source_events": []
}
```

MVP 默认建议：

- `auto_learn_enabled=false`。
- 只支持显式 demo seed 或用户主动反馈写入。
- 后续再决定是否从普通对话里自动抽取。

## 接入位置

当前主链路：

```text
POST /api/chat/stream
  -> build_planned_retrieval_message(settings, request)
  -> retrieve(retrieval_message, enriched_products)
  -> stream_answer(...)
  -> write_runtime_trace
```

用户记忆层插入后：

```text
POST /api/chat/stream
  -> resolve_user_id(request)
  -> load_user_memory(user_id)
  -> build_memory_augmented_request(request, memory)
  -> build_planned_retrieval_message(settings, augmented_request)
  -> retrieve(retrieval_message, enriched_products, memory_constraints)
  -> stream_answer(..., memory_interaction_preferences)
  -> write_runtime_trace(memory_trace)
```

关键原则：

- 给 Planner 的 memory context 要短，只放当前有用的约束和偏好。
- 硬约束必须进入 retrieval 执行层或 validated retrieval state。
- 回答风格偏好只进入生成层。
- trace 要记录本轮用了哪些 memory 字段，方便答辩解释和失败复盘。

## Provider 设计

建议定义一个很薄的 provider interface：

```python
class MemoryProvider(Protocol):
    def get_profile(self, user_id: str) -> UserMemoryProfile:
        ...

    def update_profile(self, user_id: str, event: MemoryUpdateEvent) -> UserMemoryProfile:
        ...

    def search_soft_memory(self, user_id: str, query: str, limit: int = 5) -> list[MemorySearchHit]:
        ...
```

Provider 选择：

| Provider | 适用阶段 | 行为 |
| --- | --- | --- |
| `local` | P0 快速 demo | 读写 `data/tmp/user_memory/*.json` |
| `mem0` | P1 可选增强 | 调 Mem0 add/search，只承载软记忆 |
| `disabled` | fallback | 不加载用户记忆，保持当前行为 |

配置项建议：

```env
MEMORY_PROVIDER=local
MEMORY_DIR=data/tmp/user_memory
MEMORY_AUTO_LEARN=false
MEM0_API_KEY=
MEM0_BASE_URL=
```

## API 契约建议

短期可以不新增独立接口，只在已有请求里增加可选 `user_id`：

```json
{
  "user_id": "local-demo-user",
  "conversation_id": "demo-session",
  "message": "早八想提神，有啥推荐的吗？",
  "history": []
}
```

如果不想动 Android，可先用：

```text
user_id = request.conversation_id or "local-demo-user"
```

后续可补独立接口：

| 接口 | 用途 |
| --- | --- |
| `GET /api/user-memory/{user_id}` | 查看当前本地记忆 |
| `PUT /api/user-memory/{user_id}` | 手动替换或编辑 profile |
| `POST /api/user-memory/{user_id}/events` | 写入显式反馈或 demo seed |
| `DELETE /api/user-memory/{user_id}` | 清空用户记忆 |

## 给实现代理的任务包

### 目标

在不重构 Planner / retrieval / Android 协议的前提下，给后端增加一个本地用户记忆薄层。P0 只需要 local provider，不强制接 Mem0。

### 建议修改文件

| 文件 | 修改内容 |
| --- | --- |
| `server/app/models.py` | 新增 `user_id` 可选字段；新增 `UserMemoryProfile`、`MemoryTrace` 等 Pydantic model |
| `server/app/config.py` | 新增 `memory_provider`、`memory_dir`、`memory_auto_learn`、`mem0_*` 配置 |
| `server/app/user_memory.py` | 新增 local provider、profile load/save、memory context builder |
| `server/app/main.py` | 在 `chat_stream` 和 `debug_retrieve` 中加载 memory，生成 augmented request，写入 trace |
| `server/app/retrieval.py` | P0 可先不改；若要强硬过滤更稳，再增加 `memory_constraints` 参数 |
| `server/app/llm.py` | 可选：接收 interaction preferences，影响回答长短和解释深度 |
| `docs/04_api_contract.md` | 实现后补 `user_id`、memory trace 和 user-memory API 契约 |

### 非目标

- 不接真实用户系统。
- 不写入 Git-tracked 个人 profile。
- 不做自动敏感信息推断。
- 不把 Mem0 设为必需依赖。
- 不修改商品 enriched schema。
- 不改变现有 SSE 事件顺序。

### P0 实现步骤

当前进度（2026-06-09）：已完成 `1-7`。

1. ✅ 新增 `UserMemoryProfile` schema 和 `LocalMemoryProvider`。
2. ✅ `chat_stream` 和 `debug_retrieve` 通过 `user_id / conversation_id / local-demo-user` 解析用户。
3. ✅ 加载本地 profile，不存在则返回空 profile。
4. ✅ 把 `constraints` 和有效 `short_term_snapshots` 压缩成 memory context。
5. ✅ 用 memory context 构造 augmented request，只供 Planner / retrieval 使用。
6. ✅ 在 runtime trace 增加 `memory_trace`，记录 provider、user_id、applied constraints、applied preferences、applied short-term signals。
7. ✅ 如 `MEMORY_PROVIDER=disabled`，保持当前行为完全不变（当前实现将 `mem0` 也按禁用处理，先完成 P0 本地路径）。

### P1 实现步骤

1. 增加 `Mem0MemoryProvider`，仅实现软记忆 `search_soft_memory`。
2. `constraints` 仍来自 local profile，不从 Mem0 search hit 直接升级。
3. 只有 `MEMORY_PROVIDER=mem0` 且 key/base_url 配齐时才启用。
4. `requirements.txt` 只在真正启用 Mem0 SDK 时增加 `mem0ai`；否则可先用 REST client 或留空。

### 最小验收

| 验收点 | 期望 |
| --- | --- |
| `MEMORY_PROVIDER=disabled` | `/api/debug/retrieve` 输出与当前无记忆路径一致 |
| 空 profile | 不改变推荐结果 |
| 本地 profile 有 `avoid_terms` | retrieval message / trace 中能看到该约束被应用 |
| 本地 profile 有 `recent_interests` | Planner context 中能看到短期兴趣，但不强制硬过滤 |
| trace | `data/tmp/traces/trace_YYYY-MM-DD.jsonl` 含 `memory_trace`，不含 API key |
| feedback | 现有 `/api/feedback` 不受影响 |

建议 smoke 命令：

```bash
server/.venv/bin/python scripts/check_feedback_loop.py
server/.venv/bin/python scripts/run_subcategory_queries.py --cases data/eval/all_category_queries.json --require-vector
```

如果没有显式要求，不需要在 P0 同时跑 Android 编译。

## 答辩叙事

这条路线可以这样解释：

```text
我们不是只做单轮商品召回，而是把购物 agent 拆成三层状态：

1. 会话上下文：本轮和最近几轮说过什么，由 history、conversation_state 和 Planner 处理。
2. 商品事实上下文：商品资料、价格、功效和证据来源，由 enriched data、retrieval trace 和 guardrail 处理。
3. 用户本地偏好上下文：用户长期约束、近期目标和交互习惯，由本地 user memory profile 管理。

其中硬约束本地结构化执行，软偏好可以用 Mem0 这类记忆层增强，但不会让语义记忆越过商品事实和安全边界。
```

这能和现有文档自然接上：

- [Agentic RAG / LLM Planner 调研补充](19_agentic_rag_planner_research.md)：用户记忆给 Planner 提供跨会话输入。
- [Runtime Trace Log 与可追溯反馈闭环](25_runtime_trace_log_plan.md)：memory trace 进入同一套本地证据链。
- [场景化组合推荐 Planner 实现记录](30_scene_bundle_planner_implementation.md)：近期目标可帮助 scene bundle 选择更合适的槽位。
- [首屏极速响应与临时聊天气泡方案](33_first_screen_fast_response_plan.md)：memory 不应影响临时气泡的安全边界。

## 风险与边界

| 风险 | 边界 |
| --- | --- |
| 记错用户偏好 | 提供可查看 / 可删除 / 可禁用入口 |
| 硬约束被语义召回稀释 | 硬约束只走本地结构化字段和 deterministic filter |
| 隐私过度收集 | P0 默认不自动学习，只写 demo seed 或显式反馈 |
| 敏感属性推断 | 不从行为推断医疗、身份、残障等敏感属性 |
| 推荐解释过度个性化 | 回答只说明与当前需求相关的记忆，不暴露无关 profile |
| Mem0 vendor lock-in | provider interface 保持 local / mem0 / disabled 可切换 |

## 后续可选增强

1. Android 端增加“我的偏好 / 清空记忆”调试页。
2. `/api/feedback` 中把明确的“不喜欢太甜 / 不要咖啡因”转成待确认 memory event。
3. `promote_feedback_to_failure_case.py` 支持识别 memory-related failure。
4. 给 `RetrievalTrace` 增加 `memory_trace` 字段，和 planner trace 同级展示。
5. 如果 demo 需要更像真实 AI 记忆，再接 `Mem0MemoryProvider` 做软记忆 search。
