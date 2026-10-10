# MeClaw

> 本地桌面 AI 助手 · **第一代**
> Python + pywebview + Web 前端

同一个仓库里还有第二代 —— [`../mnemos/`](../mnemos/)（Web 版，代号 MNEMOS）。

---

## 快速开始

1. 复制 `config.example.json` 为 `config.json`，填入 API 信息
2. 创建至少一个角色目录，例如 `souls/default/soul.md`（写人设），并在 `config.json` 里把 Bot 的 `soul_folder` 指向它
3. 装依赖：`pip install -r requirements.txt`
4. 启动：`python main.py` 或双击 `启动MeClaw.bat`

首次配置在 `config.json` 里：`api_profiles` 是个数组，可存多组供应商（Base URL + Key + 模型），每个 Bot 通过 `profile_id` 挑一组。

---

## 能做什么

| 能力 | 说明 |
|---|---|
| 多角色（souls） | `souls/{bot-id}/`，每个角色一份 `soul.md` 人设 + 独立记忆库 |
| 多供应商 | `api_profiles` 存多组，可给不同 Bot 分配不同大脑 |
| 记忆系统 | sqlite 索引 + `scratchpad.md` + 按日期归档条目，带 token 预算与压缩阈值 |
| 群聊 | `groups/`，群级记忆与成员提及 |
| 联网搜索 | 内置 `search_web` 函数调用（Bing 本地 / DuckDuckGo / SerpAPI） |
| 技能 | `skills/{id}/` 下放 `skill.json` + `instructions.md` |
| 专家模式 | `expert_mode` / `expert_council` / `shared_blackboard` |
| 代码模式 | `code_mode` |

---

## 目录结构

```
.
├── main.py                    # 入口
├── backend/                   # 后端，18 个模块
│   ├── api.py                 #   MeClawAPI 基类（配置 / Bot / Profile 管理）
│   ├── main.py                #   启动与应用装配
│   ├── expert_mode.py         #   专家模式
│   ├── expert_council.py      #   专家议会
│   ├── code_mode.py           #   代码模式
│   ├── web_search.py          #   联网搜索
│   ├── skills.py              #   技能扫描与注入
│   ├── memory/                #   记忆系统
│   └── ...
├── souls/                     # 角色：人设 + 记忆（运行时生成，不入库）
├── skills/                    # code-review / web-search
├── web/  webversion/          # 两套前端
├── openspec/                  # 规格驱动开发：变更提案与主规格
├── docs/                      # 见下方文档入口
├── config.example.json        # 配置模板
└── requirements.txt
```

---

## 文档入口

| 文档 | 用途 |
|------|------|
| [docs/系统结构.md](docs/系统结构.md) | 目录树、路径约定、模块职责 |
| [docs/API参考.md](docs/API参考.md) | 后端 API、前端函数、config 全字段 |
| [docs/记忆系统技术文档.md](docs/记忆系统技术文档.md) | 记忆系统实现细节 |
| [docs/记忆系统使用帮助.md](docs/记忆系统使用帮助.md) | 记忆系统日常使用 |
| [docs/对话文件目录设计.md](docs/对话文件目录设计.md) | 按对话隔离的文件接收目录 |
| [docs/联网与MCP预留.md](docs/联网与MCP预留.md) | 联网搜索与 MCP 扩展（Phase B 未实现） |
| [docs/迭代更新文档.md](docs/迭代更新文档.md) | 开发流程与规矩 |

---

## 与第二代的区别

| | 第一代（本目录） | 第二代（`../mnemos/`） |
|---|---|---|
| 形态 | 桌面应用（pywebview 原生窗口） | 浏览器 Web 应用（:8766） |
| 后端 | `backend/` 拆成 18 个模块 | `backend/main.py` + `domain/` 分层 |
| 数据目录 | `history/`、`souls/` 在根目录 | 统一收在 `data/` 下 |
| 群聊 | 有 | 无 |
| 专家 / 议会 / 代码模式 | 有 | 无 |
| 分层记忆 + 向量检索 | 无 | 有（含 PersonaMem 基准） |

**两代数据互不通用**，各自独立运行、各自配置。可以同时装、同时跑。

---

## 注意

- `config.json` 里是真实 API Key，**已在 `.gitignore` 中**，请勿提交
- `history/`、`groups/`、`souls/*/memory/` 是运行时会话与记忆数据，同样不入库
- Bot 的 `soul_folder` 请使用相对路径，如 `souls/default`
- 删除某个角色的记忆库，等于让它失忆 —— 备份请连 `souls/` 一起
