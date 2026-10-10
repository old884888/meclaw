# MNEMOS

> **MeClaw 2.0** — 本地优先的轻量 AI 对话壳
> 浏览器打开：`http://127.0.0.1:8766`

同一个仓库里还有第一代 —— [`../v1/`](../v1/)（桌面版）。

---

## 这是什么

一个跑在本机的小型 AI 对话前端。你自己填 API Key，不依赖任何托管服务。

核心是 **Bot 大厅** —— 每个 Bot 有自己的 Soul（人设）、绑定自己的供应商配置。

| 能力 | 说明 |
|---|---|
| Bot 大厅 | 大模块网格展示所有 Bot，新建 / 编辑 / 删除 / 拖动排序 |
| Soul 人设 | 每个 Bot 一份人格定义，含 `_platform/` 全局约束（自动注入所有 Bot） |
| 供应商管理 | 设置里管理 API Profile（Base URL + Key + 模型），可点「测试」验证 |
| 流式对话 | 逐字输出，带 Reasoning 流式展示 |
| 分层记忆 | L1/L2/L3 + 本地语义检索（fastembed 向量）+ 话题聚类 + 记忆固化 |
| 按角色配模型 | 「记忆提取」「上下文摘要」可各选模型，回退：角色 → background_model → 主模型 |
| 知识库 | `data/knowledge/`，可检索 |
| 本地备份 | 会话历史导出 ZIP |

---

## 快速开始

**第一次用，双击：**

```
启动MNEMOS.bat
```

出来是中文菜单。第一次请先选 **[6] 首次安装 / 环境检测**，再选 **[1] 启动服务**。

浏览器自动打开后：**设置 → 供应商 → 填 API Key → 绑定给 Bot**。

### 手动启动

```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8766
```

首次运行前请先创建配置：

```bash
mkdir data
cp config.example.json data/config.json
# 然后编辑 data/config.json，把 <在此填写密钥> 换成你自己的 Key
```

> `data/` 是运行时目录（对话、记忆、知识库），已在 `.gitignore` 中排除，所以仓库里只有 `config.example.json` 模板，不在 `data/` 内。

### 启动器入口

| 文件 | 作用 |
|---|---|
| `启动MNEMOS.bat` | 中文菜单（启动 / 停止 / 重启 / 状态 / 安装） |
| `重启MNEMOS.bat` | 直接重启 |
| `停止MNEMOS.bat` | 停掉占用 8766 的进程 |

---

## 目录结构

```
.
├── backend/
│   ├── main.py              # 后端主体（约 52 KB 单文件）
│   └── domain/              # 领域层
│       ├── brains/          #   多脑编排、模型角色
│       └── memory/          #   分层记忆、向量索引、话题聚类、固化
├── web/                     # 前端
├── data/                    # 运行时数据（不入库，见 .gitignore）
│   ├── config.example.json  #   配置模板（入库）
│   ├── config.json          #   你的 API Key（不入库）
│   ├── history/             #   会话记录
│   ├── souls/               #   各 Bot 人设与记忆
│   ├── knowledge/           #   知识库
│   └── wiki/                #   关系图与索引
├── scripts/
│   ├── mnemos.cmd           # 启动器主体（菜单 / 进程管理 / 环境检测）
│   ├── setup_check.py       # 环境检测与首次安装向导
│   ├── offline_pack.ps1     # 离线打包
│   └── offline_install.sh   # 离线安装（Linux / macOS）
├── docs/                    # 设计文档
├── tests/                   # 测试套件（140 项）
├── requirements.txt
└── requirements-embedding.txt
```

项目内所有路径都是相对的，换机器时整个目录拷走即可。

---

## 与第一代的区别

| | 第一代（`../v1/`） | 第二代（本目录） |
|---|---|---|
| 形态 | 桌面应用（pywebview 原生窗口） | 浏览器 Web 应用（:8766） |
| 后端 | `backend/` 拆成 18 个模块 | `backend/main.py` + `domain/` 分层 |
| 数据目录 | `history/`、`souls/` 在根目录 | 统一收在 `data/` |
| 群聊 | 有 | 无 |
| 专家 / 议会 / 代码模式 | 有 | 无 |
| 分层记忆 + 向量检索 | 无 | 有 |

**两代数据互不通用**，各自独立运行、各自配置。可以同时装、同时跑。

---

## 测试

```bash
python -m pytest tests -q --ignore=tests/benchmark
```

当前状态：

```
139 passed, 1 failed
```

那 1 个失败是开发中遗留的：

```
tests/test_multi_brain_smoke.py::test_l1_uses_profile_model_when_available
```

测试调用 `brain.after_turn(..., profile={...})`，但 `MemoryBrain.after_turn` 的签名还没有 `profile` 参数 —— 也就是说「L1 提取时按当前 profile 选模型」这个能力，测试先写下了，实现还没跟上。属于已知的未完成项。

`tests/benchmark/` 是 PersonaMem 记忆基准，默认跳过（数据集体积较大）。

---

## 可选：本地 Embedding

混合检索的真语义分支默认关闭。需要时：

```bash
pip install -r requirements-embedding.txt
```

然后在 `data/config.json` 里设 `embedding_provider: "local"` 与 `embedding_model`（详见 [`docs/超级大脑增强路线.md`](docs/超级大脑增强路线.md)）。可选 `rerank_enabled: true` + `rerank_provider: "local"` 做精排。

首次开启需要下载约 470 MB 的向量模型（fastembed），缓存在项目内的 `.fastembed_cache\`，不写系统盘。模型就绪前，记忆检索会降级为关键词匹配，功能可用。

---

## 隐私

- 默认只监听 `127.0.0.1`，不对外暴露
- API Key 与会话数据全部保存在本地明文文件，请自行备份
- `data/config.json` 里是真实 Key —— 本仓库已在 `.gitignore` 中排除整个 `data/`，只保留 `data/config.example.json` 模板
