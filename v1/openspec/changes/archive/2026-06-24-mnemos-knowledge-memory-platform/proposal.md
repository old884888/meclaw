## Why

MeClaw 2.0 已经完成了前后端分离、本地数据目录、多供应商、多 Bot、soul、会话与流式聊天的基础设计，但当前定位仍偏向“MeClaw 1.0 的干净重构”。用户现在希望把 2.0 主线升级为一个更明确的产品：**MNEMOS**，一个本地优先、浏览器可打开、界面清爽、以知识整理与分层记忆为核心的 AI 工具。

目标不是把外部项目原样塞进来，而是吸收两类能力：

- **TencentDB Agent Memory 的分层记忆思想**：L0 原始材料 / 对话证据、L1 原子事实、L2 场景或主题块、L3 用户画像或知识画像，并保留可追溯链路。
- **llm-wiki-agent 的知识库工作流思想**：收集资料、整理为可读 Markdown、分类、标签、交叉引用、综合页与知识图谱。

本变更重新定义 2.0 的路线图：先保持可运行的小闭环，再分步增加知识导入、分层记忆与 Wiki 模式，避免一次性重做过大。

## What Changes

### MNEMOS 产品定位

- 将 `meclaw2/` 的未来产品名调整为 **MNEMOS**。
- 2.0 仍作为独立子工程推进，不破坏 1.0 当前可用路径。
- 默认形态是本地 Web 应用：FastAPI + WebSocket 后端，浏览器访问 `http://127.0.0.1:8766`。
- 后续可再增加 pywebview 桌面壳，但浏览器打开能力必须保持一等公民。

### UI 方向

- 从传统聊天工具视觉调整为更清爽的 iOS 感界面。
- 设计语言强调留白、半透明/柔和层次、圆角卡片、清晰侧栏、轻量动画。
- 桌面优先，同时为未来移动端 / 平板 Web 留布局余地。
- 主导航从单纯 Bot/会话扩展为可容纳：
  - Chat：聊天与会话
  - Knowledge：资料导入与知识卡片
  - Memory：分层记忆面板
  - Settings：供应商、Bot、数据目录

### 分层记忆路线

- 在现有 `MemoryService` 预留接口上推进真正实现。
- 记忆模型按阶段落地：
  - L0：原始资料、网页正文、导入文件、对话原文与引用证据。
  - L1：原子事实 / 偏好 / 术语 / 结论。
  - L2：主题块 / 场景块 / 项目块。
  - L3：用户画像 / 知识画像 / 长期策略。
- 每一层都必须能回溯到底层来源，不做不可解释的黑盒摘要。
- MVP 先使用 SQLite FTS 关键词检索；向量检索、RRF 混合排序与短期 offload 后续分阶段实现。

### llm-wiki-agent 思维的未来模式

- 设计一个未来的 **Wiki Mode**，用于资料整理而不是普通聊天。
- Wiki Mode 负责：
  - 导入 URL / Markdown / 文本。
  - 保留 `raw/` 原文。
  - 生成可读 Markdown 知识卡片。
  - 自动分类、标签、摘要、实体/概念。
  - 使用 `[[PageName]]` 风格交叉引用。
  - 后续生成图谱与 synthesis 综合页。
- 本变更先设计路线和数据边界，具体图谱可视化不放入第一阶段实现。

### 独立化约束

- `meclaw2/` 后续应能被整理为独立 MNEMOS 项目。
- 当前子目录运行方式可以保留，但设计上要避免强依赖 1.0 根目录。
- 启动脚本、数据目录、包名、README 后续需要支持“单独拿出文件夹也能运行”。

## Non-Goals

- 不在本变更中删除 MeClaw 1.0。
- 不把 TencentDB Agent Memory Node/TypeScript 插件原样引入运行时。
- 不把 llm-wiki-agent 仓库作为子模块直接嵌入。
- 不在第一阶段实现群聊、编程模式、文件树、主动联网搜索、技能系统。
- 不在第一阶段实现完整向量数据库、RRF 混合检索、短期上下文 offload。
- 不默认开放公网或局域网访问；仍默认监听 `127.0.0.1`。

## Capabilities

### New Capabilities

- `mnemos-platform`: MNEMOS 产品命名、独立化边界、本地 Web 运行方式。
- `mnemos-ui-shell`: iOS 感清爽界面、主导航、卡片式知识工作区。
- `mnemos-knowledge-ingest`: 资料导入、URL 抓正文、原文归档、知识卡片生成路线。
- `mnemos-layered-memory`: L0/L1/L2/L3 分层记忆模型、可追溯引用链、MemoryService 实现路线。
- `mnemos-wiki-mode`: llm-wiki-agent 风格的 Wiki Mode 设计，包括 Markdown、交叉引用、图谱与 synthesis 的阶段规划。

### Modified Capabilities

- `meclaw2-platform`: 从“MeClaw 2.0 MVP”调整为 MNEMOS 主线的工程基础。
- `meclaw2-memory-port`: 从 NoOp 预留扩展为分层记忆接口与实现路线。
- `meclaw2-ui-shell`: 从传统聊天壳调整为清爽知识 AI 工作台。

## Impact

- **主要影响目录**：`meclaw2/`、`openspec/changes/mnemos-knowledge-memory-platform/`。
- **后续可能新增数据目录**：
  - `data/knowledge/raw/`
  - `data/knowledge/notes/`
  - `data/knowledge/sources/`
  - `data/memory/l0/`
  - `data/memory/l1/`
  - `data/memory/l2/`
  - `data/memory/l3/`
- **后续可能新增依赖**：
  - URL 正文提取：`trafilatura` 或等价库。
  - Markdown frontmatter：可先用轻量解析，必要时再引入依赖。
  - 向量检索：后续阶段再评估，不进入第一阶段。
- **不影响**：现有 1.0 `backend/`、`web/`、`main.py`、`history/`、`souls/` 的运行路径。

## Product Priority

| Priority | Capability | Acceptance |
|----------|------------|------------|
| P0 | MNEMOS 命名与独立 Web 运行 | 浏览器可打开，产品名、标题、默认文案统一 |
| P0 | 清爽 UI 壳 | 主导航和聊天页具备 iOS 感视觉基线 |
| P0 | 2.0 现有聊天闭环不回退 | API 配置、Bot、Soul、会话、流式聊天继续可用 |
| P1 | L0/L1 知识导入 | URL/文本/Markdown 可入库并生成可检索卡片 |
| P1 | MemoryService 实现基础检索 | 聊天前可注入相关 L1/L2 知识块 |
| P2 | Wiki Mode | 可浏览卡片、交叉引用、分类/标签 |
| P3 | TencentDB 式增强 | L2/L3 聚合、混合检索、可视化追溯链 |
