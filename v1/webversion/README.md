# MeClaw Web 版 — 从零开始指南

> 写给「比较笨」的自己看：照着做就行，不用一次全做完。  
> **不用买服务器**。Web 版可以先在你自己电脑上跑，和桌面版用同一台机器。

---

## 先搞懂三件事

### 1. 桌面版现在怎么工作的？

```
浏览器页面（web/ 文件夹里的 HTML/JS）
        ↕  pywebview.api.xxx()  （进程内桥接，外网访问不到）
Python 后端（backend/ 文件夹）
        ↕
本地文件：config.json、souls/、history/、memory/
```

桌面版**没有**对外 HTTP 端口，所以别人连不上你的电脑。

### 2. Web 版要改什么？

只改「中间那层连接方式」：

```
浏览器页面（可以复用 web/ 大部分代码）
        ↕  fetch / WebSocket  （HTTP 请求）
Python 后端 + 一层 HTTP 服务（写在 webversion/server/）
        ↕
本地文件（和桌面版共用，不用搬家）
```

**核心业务逻辑不用重写**：`backend/api.py`、`backend/memory/`、`backend/soul.py` 等继续用。

### 3. 哪些东西放 `webversion/` 文件夹？

| 放这里（新建） | 不搬（继续用原来的） |
|----------------|----------------------|
| HTTP 服务启动入口 | `backend/api.py` 全部业务 |
| API 路由（把 pywebview 方法映射成 URL） | `backend/main.py` 里的业务方法 |
| WebSocket 流式推送 | `backend/providers.py` |
| 前端「桥接层」`api-bridge.js` | `backend/memory/`、`backend/soul.py` 等 |
| 一键启动脚本 | `souls/`、`history/`、`config.json` |
| 本说明文档 | 桌面版 `web/`（先复制再改，原文件不动） |

**原则：`webversion/` 只放「Web 专用的新胶水代码」，不复制整个后端。**

---

## 最终目录长什么样（目标）

做完后项目里会多这一块（现在只有文档，代码以后按步骤往里加）：

```
meclaw/
├── backend/              ← 不动，共用
├── web/                  ← 桌面版前端，不动
├── config.json           ← 共用
├── souls/ history/ ...   ← 共用
│
└── webversion/
    ├── README.md         ← 你正在看的这个
    ├── 代码归属表.md     ← 每个 API 对应写哪
    ├── 启动Web版.bat     ← 第 6 步完成后才有
    ├── server/
    │   ├── __init__.py
    │   ├── app.py        ← FastAPI 入口，监听 localhost:8765
    │   ├── deps.py       ← 创建 MeClawAPI 实例、注入配置路径
    │   ├── routes/
    │   │   ├── config.py     ← GET/POST /api/config
    │   │   ├── bots.py       ← /api/bots/...
    │   │   ├── chat.py       ← POST /api/chat + WebSocket 流
    │   │   ├── sessions.py
    │   │   ├── memory.py
    │   │   └── files.py      ← 编程模式相关（Web 版可后期再做）
    │   └── stream.py     ← 把 evaluate_js(onToken) 改成 WebSocket 推送
    │
    └── web/              ← 从 ../web/ 复制过来再改
        ├── index.html    ← 多引一个 api-bridge.js
        ├── style.css     ← 后期加移动端样式
        └── js/
            └── api-bridge.js  ← 核心：假装自己是 pywebview.api
```

---

## 分阶段做（别一次啃完）

| 阶段 | 你能得到什么 | 大概难度 |
|------|-------------|----------|
| **第 0 步** | 看懂结构（你正在做） | ★ |
| **第 1 步** | 本机能打开网页、能读到配置 | ★★ |
| **第 2 步** | 能聊天、能看到流式打字 | ★★★ |
| **第 3 步** | 能切换 Bot、看历史会话 | ★★★ |
| **第 4 步** | 供应商设置、记忆库 | ★★★★ |
| **第 5 步** | 手机浏览器能用（响应式） | ★★★ |
| **第 6 步** | 双击 bat 一键启动 | ★ |

**第 1～3 步做完就已经是「能用的 Web 版」了。**

---

## 第 0 步：准备环境（一次性）

### 0.1 确认 Python 能用

打开 PowerShell，进入项目目录：

```powershell
cd <应用根目录>
python --version
```

应显示 Python 3.11 或更高。

### 0.2 安装 Web 版额外依赖

桌面版只需要 `pywebview` 和 `requests`。Web 版多加一个 HTTP 框架：

```powershell
pip install fastapi uvicorn websockets
```

### 0.3 不用装别的

- **不用买服务器**
- **不用装 Node.js**（前端没有 webpack，和桌面版一样是纯 JS）
- **不用改 config.json 位置**，Web 版继续读项目根目录那份

---

## 第 1 步：搭一个「能跑起来」的空壳

**目标**：浏览器打开 `http://127.0.0.1:8765` 能看到页面，点按钮能读到 `config.json` 里的 Bot 列表。

### 1.1 创建 `webversion/server/app.py`

这个文件干三件事：
1. 启动 FastAPI
2. 把 `../webversion/web/` 里的静态页面挂出去
3. 提供 `GET /api/config` 接口（内部调用现有的 `MeClawAPI.get_config()`）

伪代码逻辑（真正实现时让 AI 帮你写）：

```python
# 思路，不是完整代码
import sys, os
sys.path.insert(0, 项目根目录)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.api import MeClawAPI  # 或 MeClawAPIWithFiles

app = FastAPI()
api = MeClawAPI(config_path=项目根/config.json)

@app.get("/api/config")
def get_config():
    return api.get_config()  # 返回 JSON 字符串，前端 JSON.parse

# 静态文件：webversion/web/
app.mount("/", StaticFiles(directory="webversion/web", html=True))
```

### 1.2 复制前端

```powershell
# 在项目根目录执行
xcopy /E /I web webversion\web
```

**不要直接改 `web/` 原文件夹**，复制到 `webversion/web/` 里改，桌面版不受影响。

### 1.3 创建 `webversion/web/js/api-bridge.js`

这是 Web 版**最关键的一个新文件**。它让原来的 `pywebview.api.get_config()` 不用改调用方式：

```javascript
// api-bridge.js — 思路示例
const API_BASE = '';  // 同源，不用写域名

window.pywebview = {
  api: new Proxy({}, {
    get(_, method) {
      return async (...args) => {
        const res = await fetch(`/api/rpc/${method}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ args }),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.msg);
        return data.result;  // 保持和原来一样返回字符串
      };
    },
  }),
};

// 桌面版用 pywebviewready 事件；Web 版直接触发
window.dispatchEvent(new Event('pywebviewready'));
```

然后在 `webversion/web/index.html` 的 `<script>` 列表**最前面**加上：

```html
<script src="js/api-bridge.js"></script>
```

### 1.4 启动试试

```powershell
cd <应用根目录>
uvicorn webversion.server.app:app --host 127.0.0.1 --port 8765
```

浏览器打开：http://127.0.0.1:8765

**成功标志**：页面能出来，控制台没有「配置加载失败」。

### 1.5 本步只监听本机

`--host 127.0.0.1` 表示只有你自己电脑能访问，和桌面版一样安全。**先不要改成 `0.0.0.0`。**

---

## 第 2 步：能聊天（最核心）

**目标**：输入一句话，AI 流式回复。

### 2.1 为什么流式要单独处理？

桌面版后端用 `self.window.evaluate_js("onToken(...)")` 往页面推字。  
Web 版没有 pywebview 窗口，要改成 **WebSocket** 或 **SSE（Server-Sent Events）**。

推荐：**WebSocket**，一个连接推 `onToken`、`onReasoningToken`、`onStreamDone`、`onError`。

### 2.2 后端要改什么？

| 桌面版写法 | Web 版写法 |
|-----------|-----------|
| `self.window.evaluate_js(f"onToken({x})")` | `websocket.send_json({"event":"onToken","data":x})` |
| `send_message(msgs_json)` 同步阻塞 | 路由里 `await` 或放线程池，避免卡死整个服务 |

**做法**：在 `webversion/server/stream.py` 写一个 `WebStreamBridge` 类，方法和 `evaluate_js` 同名（`push_token`、`push_done`、`push_error`），内部发 WebSocket。  
`MeClawAPI` 子类化，把 `self.window.evaluate_js` 替换成这个 bridge。

**代码仍写在 `webversion/server/`，不要改 `backend/api.py` 一大坨**——用继承覆盖：

```python
# 思路
class WebMeClawAPI(MeClawAPIWithFiles):
    def __init__(self, config_path, stream_bridge):
        super().__init__(config_path)
        self._bridge = stream_bridge

    # 覆盖 _log 或封装 evaluate_js 的调用点
```

如果继承不好改，第二步的捷径是：先在 `webversion/server/routes/chat.py` 里**只实现简化版** `send_message`（非流式），能通再上流式。

### 2.3 前端要改什么？

在 `api-bridge.js` 里，页面加载时建立 WebSocket：

```javascript
const ws = new WebSocket(`ws://${location.host}/ws/stream`);
ws.onmessage = (e) => {
  const { event, data } = JSON.parse(e.data);
  if (event === 'onToken' && typeof onToken === 'function') onToken(data);
  if (event === 'onStreamDone' && typeof onStreamDone === 'function') onStreamDone(data);
  // ... 其他事件同理
};
```

`web/js/chat.js` 里的 `onToken`、`onStreamDone` **不用改**，它们已经在那等着了。

### 2.4 本步成功标志

- 能发「你好」
- 能看到 AI 一个字一个字出来
- 能点停止

---

## 第 3 步：Bot 和会话

**目标**：侧边栏能切换 Bot、新建会话、打开历史。

### 3.1 要暴露的接口（对应原来 pywebview 方法）

按优先级实现这些 RPC 即可（完整列表见 `代码归属表.md`）：

| 前端调用 | 后端已有方法 | 路由建议 |
|---------|-------------|----------|
| `get_bots()` | `MeClawAPI.get_bots` | `GET /api/bots` |
| `switch_bot(id)` | `MeClawAPI.switch_bot` | `POST /api/bots/switch` |
| `get_sessions()` | `main.get_sessions` | `GET /api/sessions` |
| `new_session()` | `main.new_session` | `POST /api/sessions` |
| `switch_session(id)` | `main.switch_session` | `POST /api/sessions/switch` |
| `save_config(...)` | `MeClawAPI.save_config` | `POST /api/config` |

### 3.2 实现技巧：通用 RPC 路由（省事）

不想每个方法写一条路由？可以做一个总入口：

```
POST /api/rpc/{method_name}
Body: { "args": [...] }
```

服务端查表：`method_name` → 调用 `api.xxx(*args)`。  
**注意**：`send_message` 走 WebSocket 那条路，别走普通 RPC。

---

## 第 4 步：设置、供应商、记忆

### 4.1 供应商（providers.js）

| 调用 | 说明 |
|------|------|
| `test_connection()` | 已修过，用 profile 自己的 model |
| `switch_profile(id)` | 切换当前 bot 的 profile |
| `fetch_profile_balance(id)` | 查余额 |

### 4.2 记忆（memory.js）

| 调用 | 说明 |
|------|------|
| `list_memory_entries` | 列表 |
| `delete_memory_entry` | 删除 |
| `open_memory_folder` | **Web 版可改成返回路径字符串**，不能 `os.startfile` |

### 4.3 桌面专属功能 — Web 版先跳过

这些依赖 Windows 文件对话框，Web 第一版**不做**：

- `select_folder` / `select_attachments` / `select_soul_folder`
- `open_receive_dir` / `open_skills_dir` / `open_memory_folder`（打开资源管理器）
- `get_file_tree` / 编程模式全套（`code-editor.js`、`ops.js`）

在 `api-bridge.js` 里对这些方法返回友好提示即可：

```javascript
if (method === 'select_folder') {
  return JSON.stringify({ ok: false, msg: 'Web 版暂不支持选择文件夹，请用桌面版' });
}
```

---

## 第 5 步：手机浏览器能用（可选）

1. 在 `webversion/web/style.css` 加 `@media (max-width: 768px)` 规则
2. 侧边栏改成抽屉（汉堡菜单）
3. 后端改 `--host 0.0.0.0`，手机和电脑连**同一 WiFi**，手机访问 `http://电脑IP:8765`
4. 建议加一个简单访问密码（环境变量 `MECLAW_WEB_TOKEN`），防止室友误连

**仍然不用买服务器**，只是局域网访问。

---

## 第 6 步：一键启动

创建 `webversion/启动Web版.bat`：

```bat
@echo off
cd /d %~dp0..
python -m uvicorn webversion.server.app:app --host 127.0.0.1 --port 8765
pause
```

双击 → 浏览器打开 http://127.0.0.1:8765 。

---

## 常见问题

### Q：Web 版和桌面版数据通吗？

**通。** 共用 `config.json`、`souls/`、`history/`。  
同时开两个没问题，但别两边同时改配置，容易覆盖。

### Q：API Key 会暴露给浏览器用户吗？

- **自托管本机**：只有你自己用，和桌面版风险一样
- **`get_config` 接口**：返回里含 api_key，**不要挂公网**
- 以后上公网再加登录，并把 config 接口里的 key 打码

### Q：要不要重写 Python？

**不要。** 用「薄 HTTP 壳 + 继承」包一层就行。  
估计新代码 800～1500 行（主要在 `webversion/server/`），而不是重写几万行。

### Q：我做不下去了怎么办？

每次只做一个接口。顺序建议：

```
get_config → get_bots → send_message(流式) → switch_bot → get_sessions → 其他
```

把 `代码归属表.md` 打勾，做一条勾一条。

### Q：让 AI 帮我写代码时怎么说？

复制下面这段话发给 Cursor（Agent 模式）：

> 请按 `webversion/README.md` 第 N 步，在 `webversion/server/` 实现代码。  
> 要求：复用 `backend/` 现有逻辑，不修改桌面版 `web/` 原文件，只改 `webversion/web/`。

---

## 和 Android 版比，为什么先做 Web？

| | Web 版 | Android APK |
|--|--------|---------------|
| 复用前端 | 几乎全复用 | 要重做 UI |
| 复用后端 | 几乎全复用 | 要重写 |
| 要不要买服务器 | 不要 | 不要 |
| 手机能用 | 浏览器就行 | 要装 APK |
| 开发量 | 2～4 周 MVP | 2～3 月 |

**建议路线：Web 版先做 → 手机用浏览器访问 → 真有需要再做 APK。**

---

## 下一步

1. 打开 `webversion/代码归属表.md`，了解每个接口归哪
2. 切换到 **Agent 模式**，说：「请实现 README 第 1 步」
3. 第 1 步跑通后，再做第 2 步

一步一步来，做完一步就能用一点，不用等全部完工。
