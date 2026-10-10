## Context

- **1.0 现状**：Python + pywebview + 原生 Web；`pywebview.api` 约 90+ 处调用；数据在 `config.json`、`history/`、`souls/`、`groups/`；功能涵盖单聊、群聊、记忆、编程模式、联网等。
- **2.0 动机**：先做出**可交付的最小闭环**，架构上前后端分离，便于本机 Web / 未来桌面壳复用；记忆与群聊等**延后**，仅预留接口与目录。
- **约束**：本地优先、数据在用户机器；不依赖云账号；MVP 可先在浏览器访问 `localhost`；与 1.0 **并行目录** `meclaw2/`，不破坏现有启动方式。

## Goals / Non-Goals

**Goals:**

- 独立工程 `meclaw2/`，FastAPI + WebSocket + Web UI
- P0 闭环：本地持久化、多供应商配置、多 Bot + soul、按 Bot 会话、流式对话
- UI：清晰两层导航（Bot → 会话 → 聊天），设置入口集中
- `MemoryService` 抽象 + NoOp；`souls/{id}/memory/` 目录占位
- 文档化 2.0 路线图（MVP 后 Phase 2/3/4）

**Non-Goals（MVP）:**

- 记忆检索/写入/压缩提取、记忆库面板
- 群聊、编程模式、联网、技能、专家模式
- 附件、上下文压缩、API 日志
- 1.0 → 2.0 自动迁移
- 移动端响应式（MVP 桌面宽度即可）

---

## 2.0 路线图（功能优先）

```text
Phase 0 — 本变更 MVP（闭环）
  平台启动、配置、供应商、Bot、soul、会话、流式聊天、Memory NoOp

Phase 1 — 体验补齐
  上下文条数/粗算 token、重新生成、暗色/亮色、简单搜索会话
  可选：pywebview 壳加载 localhost

Phase 2 — 记忆 v2
  实现 MemoryService（L1 atom + FTS）；压缩双管线；记忆 UI
  复用 1.0 思路或新分层引擎（独立变更）

Phase 3 — 群聊
  群实体、@、接话链（可沿用 1.0 已验证规则）

Phase 4 — 高级能力
  编程模式、联网、技能、Web 局域网部署、数据迁移工具
```

**MVP 完成定义**：用户不配代码即可「配 API → 建 2 个 Bot → 各聊多会话 → 重启仍在」。

---

## 架构决策

### D1. 前后端分离（相对 1.0 的 BREAKING）

| 层 | 技术 | 说明 |
|----|------|------|
| UI | HTML/CSS/JS（无构建链 MVP） | `fetch` + `WebSocket` |
| API | FastAPI | REST 配置/CRUD；WS 流式 chat |
| Domain | Python 包 `meclaw2/backend/domain/` | Chat/Bot/Session/Soul/Memory |
| 适配 | `adapters/providers.py` | 从 1.0 思路移植 OpenAI/Anthropic/DeepSeek |
| 存储 | 文件 JSON + Markdown | 与 1.0 类似，schema 可简化 |

**备选**：继续 pywebview.api → 否决，无法 Web 复用。

### D2. 数据根目录

- **默认**：`meclaw2/data/`（与代码分离，便于备份）
- 环境变量 `MECLAW2_DATA_DIR` 可覆盖
- 所有 JSON 写入必须走原子写：`*.tmp` 写完后 `os.replace()` 替换目标文件
- 关键文件（至少 `config.json`）写入前可保留上一版 `.bak`，读失败时给出清晰错误
- 结构：

```text
data/
  config.json
  history/
    sessions.json
    {session-id}.json
  souls/
    {bot-id}/
      soul.md
      constraints.md          # 可选
      memory/                 # MVP 空目录占位
        .gitkeep
```

**备选**：共用 1.0 根目录 → MVP 不采用，避免误写 1.0 数据。

### D2.1 首次启动 Bootstrap

首次启动必须能从空目录进入可配置状态：

```text
若 data/config.json 不存在
  → 创建默认 config（schema_version=1，memory 关闭）
若 config.bots 为空
  → 创建 default Bot 与 souls/default/soul.md
若 config.api_profiles 为空
  → 前端显示「请先配置供应商」引导，不允许发送
若 souls/{bot}/soul.md 不存在
  → 自动创建默认 soul 文本
```

前端启动推荐调用 `GET /api/bootstrap`，一次性返回 `config`、`bots`、`providers`、`has_required_setup`、`active_bot_id`，减少多接口初始化和空配置分支。

### D3. 聊天主链路（无记忆块）

```text
用户发送
  → SessionStore 追加 user 消息
  → ChatService.build_messages()
       system: soul_loader(bot)
       system: memory_service.before_chat()  → "" (NoOp)
       history: session messages
  → ProviderAdapter.stream()
  → WebSocket 推送 token / done / error
  → SessionStore 追加 assistant 消息
  → memory_service.after_turn()  → no-op 后台
```

LLM 调用在**线程池**执行，避免阻塞 FastAPI event loop。

### D3.1 WebSocket 协议与生成生命周期

每次生成必须带 `generation_id`，避免停止/重连/快速切会话时事件串线。

**客户端 → 服务端**

```json
{ "event": "send", "generation_id": "...", "session_id": "...", "content": "..." }
{ "event": "stop", "generation_id": "..." }
```

**服务端 → 客户端**

```json
{ "event": "token", "generation_id": "...", "text": "..." }
{ "event": "done", "generation_id": "...", "message": { "...": "..." } }
{ "event": "stopped", "generation_id": "...", "message": { "...": "..." } }
{ "event": "error", "generation_id": "...", "message": "..." }
```

消息持久化规则：

- 正常完成：保存 assistant 消息，`status="done"`
- 用户停止：保存 partial assistant 消息，`status="stopped"`
- API 出错：保存错误状态或不保存均可，但必须在实现中固定一种行为；MVP 建议保存 `status="error"` 方便排查

MVP 每个进程只需支持**单个活跃生成**；若已有生成未结束，新的 `send` SHALL 返回错误或要求用户先停止。

### D4. Memory 扩展点

- 接口：`MemoryService`（Protocol）
- MVP 实现：`NoOpMemoryService`
- 注入：`ChatService` 构造时注入，配置 `memory_enabled: false` 时仍调用 NoOp（保持调用链稳定）
- 目录：`souls/{bot}/memory/` 创建但为空；设置页显示「记忆（即将推出）」灰色项

### D5. 部署方式 MVP

1. `uvicorn meclaw2.backend.main:app --host 127.0.0.1 --port 8766`
2. 浏览器打开 `http://127.0.0.1:8766`
3. Phase 1 可选：`启动MeClaw2.bat` + pywebview 打开同 URL

**性能**：全本地，无 GPU 要求；瓶颈在 LLM API 网络。

### D6. 安全边界（MVP 必须）

- 默认只监听 `127.0.0.1`，不默认绑定 `0.0.0.0`
- 默认不配置 CORS `*`
- `config.json` 可继续明文存 API Key，但 UI 只显示脱敏 Key（如 `sk-****abcd`）
- 日志、错误消息、测试连接结果不得输出完整 API Key
- 局域网 / 24 小时电脑访问属于 Phase 4，必须先引入访问 token 或等价保护

### D7. Provider MVP 边界

MVP 只做**普通文本对话与文本流式输出**：

- 支持 `generic` / `anthropic` / `deepseek` 的 endpoint、headers、payload 差异
- 不实现 tools / tool_choice / 联网工具
- 不实现 reasoning/thinking 独立 UI；若供应商返回 reasoning 字段，MVP 可忽略或作为调试日志，不进入用户气泡
- 测试连接必须使用 profile 自身 `model`，不受 Bot 覆盖影响

---

## UI / 布局设计（详细）

### 整体框架（桌面优先，最小宽度 900px）

```text
┌──────────────────────────────────────────────────────────────────┐
│ 顶栏 header-h                                                    │
│ [≡]  MeClaw 2.0          当前：🤖 狗哥 · 会话标题    [⚙ 设置]   │
├──────────────┬───────────────────────────────────────────────────┤
│ 侧栏 260px   │ 主区 main                                         │
│              │ ┌─────────────────────────────────────────────┐   │
│ [对话]       │ │ 消息区 chat-messages（可滚动）                 │   │
│              │ │  user / assistant 气泡                       │   │
│ Bot 列表 或  │ │  流式光标 / 错误条                           │   │
│ 会话列表     │ └─────────────────────────────────────────────┘   │
│              │ ┌─────────────────────────────────────────────┐   │
│              │ │ 输入区 composer                              │   │
│              │ │ [多行输入]              [停止] [发送 ▶]        │   │
│              │ │ 用量提示：约 N 条消息                          │   │
│              │ └─────────────────────────────────────────────┘   │
└──────────────┴───────────────────────────────────────────────────┘
```

### 侧栏导航状态机

```text
view: 'bots' | 'sessions'

bots:
  - 列表所有 Bot（头像、名称、最近活跃时间）
  - 底部「+ 新建 Bot」
  - 点击 Bot → view=sessions, selectedBotId=id

sessions:
  - 顶：← 返回 Bot 列表
  - 列表该 Bot 下会话（标题、时间、条数）
  - 「+ 新建对话」
  - 点击会话 → 加载消息，header 显示 Bot+标题

无群聊 Tab（MVP）；无文件树。
```

### 顶栏语义

| 状态 | 左侧 | 中间 | 右侧 |
|------|------|------|------|
| 未进会话 | Logo | — | ⚙ 设置 |
| 会话中 | Logo | Bot 头像+名 · 会话标题（只读） | ⚙ 设置 |
| 生成中 | 同上 | 同上 | 停止（可选与输入区重复） |

**Bot 锁定**：会话内不可切换 Bot（与 1.0 bot-centric 一致）。

### 设置（⚙）— 全屏或右侧抽屉 Modal

**MVP 仅两个 Tab：**

```text
[供应商]  [机器人]

供应商 Tab:
  - Profile 卡片列表（名称、模型、启用）
  - 新建 / 编辑：名称、Base URL、API Key、模型、provider 类型
  - 「测试连接」按钮 + 结果条

机器人 Tab:
  - Bot 列表
  - 编辑：名称、头像 emoji、绑定供应商、模型覆盖（可空）
  - 灵魂：soul.md 文本框（或跳转简单编辑器页）
  - 高级项折叠：temperature、max_tokens（可空=继承 profile）

灰色不可用（占位）:
  - 记忆
  - 群聊
  - 外观（Phase 1）
```

### 对话区交互

- 用户消息：右对齐或左侧带「你」标签
- Bot 消息：左对齐，显示 Bot 头像+名
- 流式：assistant 气泡尾部闪烁光标；`onDone` 移除光标
- 错误：红色 inline 条，可重试（Phase 1）
- 空状态：「和 {Bot名} 打个招呼吧」

### 视觉（MVP）

- 默认**暗色**（延续 1.0 变量名风格：`--bg`, `--text`, `--accent`）
- 侧栏与主区对比分隔；圆角气泡
- 不追求 1.0 全功能 UI parity

---

## 后端模块边界

```text
meclaw2/backend/
  main.py                 # FastAPI app、静态文件、WS 路由
  api/
    routes_config.py      # GET/PUT config
    routes_providers.py   # CRUD、test
    routes_bots.py        # CRUD、soul 读写
    routes_sessions.py    # list/new/switch/delete
    routes_chat.py        # WS /ws/chat
  domain/
    chat_service.py
    bot_service.py
    session_service.py
    soul_loader.py
    memory/
      protocol.py
      noop.py
  adapters/
    providers.py
  storage/
    config_store.py
    history_store.py
    soul_store.py
```

**API 概览（REST）**

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/config` | 读配置 |
| PUT | `/api/config` | 写配置 |
| GET | `/api/bootstrap` | 初始状态 |
| GET | `/api/providers` | 供应商列表 |
| POST | `/api/providers` | 新建供应商 |
| GET | `/api/providers/{id}` | 供应商详情 |
| PUT | `/api/providers/{id}` | 更新供应商 |
| DELETE | `/api/providers/{id}` | 删除供应商 |
| POST | `/api/providers/{id}/test` | 测试连接 |
| GET | `/api/bots` | Bot 列表 |
| POST | `/api/bots` | 新建 Bot |
| GET | `/api/bots/{id}` | Bot 详情 |
| PUT | `/api/bots/{id}` | 更新 Bot |
| DELETE | `/api/bots/{id}` | 删除 Bot |
| GET/PUT | `/api/bots/{id}/soul` | soul.md |
| GET | `/api/sessions?bot_id=` | 会话列表 |
| POST | `/api/sessions` | 新建会话 |
| POST | `/api/sessions/{id}/switch` | 切换 |
| DELETE | `/api/sessions/{id}` | 删除 |
| WS | `/ws/chat` | 流式聊天事件 |

**WebSocket 事件（服务端 → 客户端）**

- `token`：正文片段，带 `generation_id`
- `done`：结束，带 `generation_id` 与最终 assistant message
- `stopped`：用户停止，带 `generation_id` 与 partial assistant message
- `error`：错误文案，带 `generation_id`

**WebSocket（客户端 → 服务端）**

- `send`：`{ generation_id, session_id, content }`
- `stop`：`{ generation_id }`

---

## 数据模型（MVP 简化）

### config.json

```json
{
  "schema_version": 1,
  "api_profiles": [{ "id", "name", "base_url", "api_key", "model", "provider", "enabled" }],
  "bots": [{ "id", "name", "avatar", "profile_id", "model", "temperature", "max_tokens" }],
  "active_bot_id": "",
  "memory_enabled": false,
  "memory_retrieval_enabled": false,
  "memory_write_enabled": false,
  "memory_token_budget": 1200
}
```

（无 `soul_folder` 字段：约定 `souls/{bot.id}/` 固定映射。）

### session（sessions.json 条目）

`id`, `bot_id`, `title`, `created_at`, `updated_at`, `message_count`

标题规则：首条用户消息前 20～30 字，去除换行；空内容回退为「新对话」。

### session 消息文件

```json
[
  {
    "id": "",
    "role": "user|assistant",
    "content": "",
    "status": "done|stopped|error",
    "created_at": "",
    "speaker_bot_id": ""
  }
]
```

MVP 仅单 Bot 对话，`speaker_bot_id` 为未来群聊预留；用户消息可省略 `status` 或固定为 `done`。

---

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 双工程维护成本 | MVP 功能少；1.0 冻结大改 |
| 用户不知访问 URL | bat 一键打开浏览器；Phase 1 pywebview |
| API Key 明文存 config | 与 1.0 一致；仅 localhost |
| JSON 文件损坏 | 原子写 + 可选 `.bak` |
| 无压缩导致超长上下文 | MVP 提示新建会话；Phase 2 压缩 |
| 前端无框架难扩展 | Phase 1 后可引入 Vue 仅 UI 层 |

---

## Migration Plan

1. 实现 `meclaw2/`，默认 `data/` 空配置 + 模板 soul
2. 用户手动复制 1.0 `config.json` / `souls/`（Phase 4 写脚本）
3. 验证闭环后可选切换默认启动 bat
4. 回滚：继续用 1.0 `启动MeClaw.bat`，互不影响

---

## Open Questions

| # | 问题 | MVP 默认 |
|---|------|----------|
| Q1 | 2.0 端口 | `8766`（与 webversion 文档 8765 错开） |
| Q2 | soul 编辑在设置内嵌 vs 独立页 | 设置 Modal 内大文本框 |
| Q3 | 是否 MVP 即打包 exe | 否，先 bat + 浏览器 |
| Q4 | 1.0 `knowledge/` MVP 是否加载 | 否，Phase 2 与记忆一并考虑 |
