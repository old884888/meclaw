import json
import os
import uuid
import requests

from . import history


DEFAULT_PROFILE = {
    "id": "default",
    "name": "默认配置",
    "base_url": "",
    "api_key": "",
    "model": "",
    "provider": "generic",
    "temperature": 0.7,
    "max_tokens": 4096,
    "max_context": 65536
}

DEFAULT_BOT = {
    "id": "default",
    "name": "默认助手",
    "avatar": "🤖",
    "profile_id": "default",
    "soul_folder": "",
    "model": "",
    "temperature": None,
    "max_tokens": None,
    "thinking_enabled": False,
    "thinking_depth": "high",
    "web_search": False,
    "enabled_skills": [],
    "skills_use_global": True,
    "memory_enabled": True,
    "memory_retrieval_enabled": True,
    "memory_write_enabled": True,
}

# Global immersion rules (stable prefix, all bots; not shown separately in UI)
GLOBAL_IMMERSION_PREAMBLE = """\
[身份沉浸 — Identity Immersion]

你的灵魂文件中定义的身份就是你本人。这不是角色扮演，不是表演，不是模拟。你就是TA。

## 绝对禁止（违反任何一条即为失败）
- 禁止说"我扮演"、"作为XXX"、"我的角色是"、"我模拟"、"我是一个AI助手"
- 禁止提及"灵魂文件"、"人设"、"设定"、"prompt"、"系统提示"
- 禁止解释你正在遵循什么规则或设定
- 禁止以"作为AI"、"作为语言模型"开头或结尾
- 禁止在回复末尾加"希望这对你有帮助"之类的助手腔

## 你应该做的
- 用第一人称直接回应，像朋友之间自然对话
- 你的语气、用词、情绪反应都应与灵魂文件一致
- 如果灵魂文件说你性格暴躁，就不要客气；说你温柔，就轻声细语
- 遇到不确定的问题，用你自己的方式表达困惑，而不是说"作为AI我无法..."
- 思考过程用内心独白，不要暴露给用户

## 思维链规则
- 不要以"好的"、"嗯"、"让我想想"等元描述开头
- 不要引用或复述灵魂文件的内容
- 直接进入思考：用户说了什么、我该怎么回应、我的性格会让我怎么做"""

DEFAULT_CONFIG = {
    "api_profiles": [DEFAULT_PROFILE.copy()],
    "bots": [DEFAULT_BOT.copy()],
    "active_bot_id": "default",
    "user_avatar": "😎",
    "thinking_font_size": 12,
    "receive_dir": "",
    "enabled_skills": [],
    "editor_word_wrap": True,
    "web_search_provider": "duckduckgo",
    "web_search_api_key": "",
    "web_search_max_rounds": 3,
    "web_search_max_queries_per_round": 3,
    "memory_enabled": True,
    "memory_retrieval_enabled": True,
    "memory_write_enabled": True,
    "memory_auto_extract": False,
    "memory_token_budget": 1200,
    "memory_extract_threshold_pct": 85,
    "compress_summary_detail": "standard",
}


def estimate_tokens(text):
    """粗略估算 token 数：英文约 1/4 字符，中文约 1/1.5 字符，混合取 1/2"""
    if not text:
        return 0
    return max(1, len(text) // 2)


def format_api_error(status_code, response_text, max_len=4000):
    """从 API 错误响应中提取可读信息（避免截断在半截 JSON 上）。"""
    detail = (response_text or '').strip()
    message = detail
    try:
        data = json.loads(detail)
        err = data.get('error')
        if isinstance(err, dict) and err.get('message'):
            message = err['message']
        elif isinstance(data, dict) and data.get('message'):
            message = data['message']
    except (json.JSONDecodeError, TypeError):
        pass
    if len(message) > max_len:
        message = message[:max_len] + '…'
    return f"API 返回 {status_code}: {message}"


class MeClawAPI:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config()
        self.stop_flag = False
        self.window = None
        self.working_dir = None
        self.current_session_id = None
        self._reply_bot_id = None
        self._group_chain_reply = False
        self._group_empty_retry = False
        self.current_messages = []
        self.current_summary = None
        self.current_mode = "chat"
        self._project_overview_cache = {}

    def __dir__(self):
        return [name for name in object.__dir__(self) if name != 'window']

    @property
    def app_dir(self):
        return os.path.dirname(os.path.abspath(self.config_path))

    def resolve_app_path(self, path):
        """将相对应用根目录的路径解析为绝对路径（config 中 soul_folder 等推荐用相对路径）。"""
        if not path:
            return ""
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(self.app_dir, path.replace("/", os.sep)))

    def to_config_relative_path(self, path):
        """将路径转为写入 config 的相对路径（在应用根目录内时）。"""
        if not path or not str(path).strip():
            return ""
        resolved = self.resolve_app_path(str(path).strip())
        app = os.path.normpath(self.app_dir)
        if resolved.startswith(app):
            rel = os.path.relpath(resolved, app)
            return rel.replace("\\", "/")
        return str(path).strip().replace("\\", "/")

    def load_config(self):
        if not os.path.exists(self.config_path):
            return json.loads(json.dumps(DEFAULT_CONFIG))

        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        # 旧格式迁移：无 bots 字段说明是 Phase 3 或更早
        if 'bots' not in raw:
            raw = self._migrate_to_bot_config(raw)

        # 确保 api_profiles 新字段（供应商 models / 余额 / 启用）
        from .providers import normalize_all_profiles
        normalize_all_profiles(raw)
        for b in raw.get("bots", []):
            if "thinking_enabled" not in b:
                b["thinking_enabled"] = False
            if "thinking_depth" not in b:
                b["thinking_depth"] = "high"
            if "web_search" not in b:
                b["web_search"] = False
            if "enabled_skills" not in b:
                b["enabled_skills"] = []
            if "skills_use_global" not in b:
                b["skills_use_global"] = True
        if "receive_dir" not in raw:
            raw["receive_dir"] = ""
        if "enabled_skills" not in raw:
            all_ids = set()
            for b in raw.get("bots", []):
                all_ids.update(b.get("enabled_skills") or [])
            raw["enabled_skills"] = sorted(all_ids)
        if "editor_word_wrap" not in raw:
            raw["editor_word_wrap"] = True
        if "web_search_provider" not in raw:
            raw["web_search_provider"] = "duckduckgo"
        if "web_search_api_key" not in raw:
            raw["web_search_api_key"] = ""
        if "web_search_max_rounds" not in raw:
            raw["web_search_max_rounds"] = 3
        if "web_search_max_queries_per_round" not in raw:
            raw["web_search_max_queries_per_round"] = 3
        for key, default in (
            ("memory_enabled", True),
            ("memory_retrieval_enabled", True),
            ("memory_write_enabled", True),
            ("memory_auto_extract", False),
            ("memory_token_budget", 1200),
            ("memory_extract_threshold_pct", 85),
            ("compress_summary_detail", "standard"),
        ):
            if key not in raw:
                raw[key] = default
        for b in raw.get("bots", []):
            for key, default in (
                ("memory_enabled", None),
                ("memory_retrieval_enabled", None),
                ("memory_write_enabled", None),
                ("memory_auto_extract", None),
                ("memory_extract_threshold_pct", None),
                ("compress_summary_detail", None),
            ):
                if key not in b:
                    b[key] = default

        needs_save = False
        for b in raw.get("bots", []):
            sf = b.get("soul_folder", "")
            if not sf:
                continue
            rel = self.to_config_relative_path(sf)
            if rel != sf:
                needs_save = True
            b["soul_folder"] = rel
        if needs_save:
            self._write_config(raw)

        return raw

    def _migrate_old_config(self, old):
        """Phase 1/2 → Phase 3 迁移（保留兼容）"""
        profile = {
            "id": "default",
            "name": "默认配置",
            "base_url": old.get("base_url", ""),
            "api_key": old.get("api_key", ""),
            "model": old.get("model", ""),
            "temperature": old.get("temperature", 0.7),
            "max_tokens": old.get("max_tokens", 4096),
            "max_context": 65536
        }
        new = json.loads(json.dumps(DEFAULT_CONFIG))
        new["api_profiles"] = [profile]
        # 继续迁移到 bot 结构
        new = self._migrate_to_bot_config(new, old.get("system_prompt", ""), old.get("soul_folder", ""))
        return new

    def _migrate_to_bot_config(self, raw, system_prompt=None, soul_folder=None):
        """Phase 3 → Phase 4 迁移：引入 bot 结构"""
        if system_prompt is None:
            system_prompt = raw.get("system_prompt", "")
        if soul_folder is None:
            soul_folder = raw.get("soul_folder", "")

        # 确保 api_profiles 有 max_context 字段
        for p in raw.get("api_profiles", []):
            if "max_context" not in p:
                p["max_context"] = 65536

        # 确定 profile_id
        profile_id = raw.get("active_profile_id", "default")
        profiles = raw.get("api_profiles", [])
        if not any(p["id"] == profile_id for p in profiles):
            profile_id = profiles[0]["id"] if profiles else "default"

        # 迁移灵魂文件夹：将旧的全局 soul_folder 内容移到 souls/default/
        app_dir = os.path.dirname(self.config_path)
        souls_root = os.path.join(app_dir, "souls")
        default_soul_folder = os.path.join(souls_root, "default")

        if soul_folder and os.path.isdir(soul_folder):
            # 旧灵魂文件夹存在，复制到 souls/default/
            if not os.path.exists(default_soul_folder):
                os.makedirs(default_soul_folder, exist_ok=True)
                self._copy_soul_folder(soul_folder, default_soul_folder)
        elif system_prompt:
            # 没有灵魂文件夹但有 system_prompt，写入 souls/default/soul.md
            os.makedirs(default_soul_folder, exist_ok=True)
            soul_md_path = os.path.join(default_soul_folder, "soul.md")
            if not os.path.exists(soul_md_path):
                with open(soul_md_path, 'w', encoding='utf-8') as f:
                    f.write(system_prompt)
        else:
            # 什么都没有，创建空的 souls/default/ 和模板 soul.md
            os.makedirs(default_soul_folder, exist_ok=True)
            soul_md_path = os.path.join(default_soul_folder, "soul.md")
            if not os.path.exists(soul_md_path):
                with open(soul_md_path, 'w', encoding='utf-8') as f:
                    f.write("# 默认助手\n\n## 身份\n（在这里描述你是谁）\n\n## 性格\n（在这里描述你的性格特点）\n\n## 说话风格\n（在这里描述你的说话方式）\n")

        # 创建默认 bot
        default_bot = json.loads(json.dumps(DEFAULT_BOT))
        default_bot["profile_id"] = profile_id
        default_bot["soul_folder"] = "souls/default"

        # 组装新配置
        new_config = {
            "api_profiles": raw.get("api_profiles", [json.loads(json.dumps(DEFAULT_PROFILE))]),
            "bots": [default_bot],
            "active_bot_id": "default",
            "user_avatar": "😎"
        }

        self._write_config(new_config)
        return new_config

    def _copy_soul_folder(self, src, dst):
        """复制灵魂文件夹内容"""
        import shutil
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)
            elif os.path.isdir(s):
                if not os.path.exists(d):
                    os.makedirs(d)
                self._copy_soul_folder(s, d)

    def save_config(self, config_json):
        try:
            cfg = json.loads(config_json)
            self.config = cfg
            self._write_config(cfg)
            return json.dumps({"ok": True, "msg": "配置已保存"})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def _write_config(self, cfg):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def get_config(self):
        return json.dumps(self.config)

    # ---- Bot 管理 ----

    def get_bots(self):
        """返回机器人列表 JSON"""
        bots = self.config.get("bots", [])
        active_id = self.config.get("active_bot_id", "")
        return json.dumps({"ok": True, "bots": bots, "active_bot_id": active_id})

    def get_memory_settings(self):
        """记忆开关与 token 预算（全局 + per-bot）。"""
        from .memory.config import get_memory_settings
        return get_memory_settings(self.config, self.get_active_bot())

    def get_auto_compress_settings(self):
        """自动压缩开关与阈值（全局 + per-bot）。"""
        from .memory.config import get_auto_compress_settings
        return get_auto_compress_settings(self.config, self.get_active_bot())

    def get_active_bot(self):
        """返回当前激活的机器人配置（浅拷贝，防止意外修改内部数据）"""
        reply_id = getattr(self, "_reply_bot_id", None)
        bots = self.config.get("bots", [])
        bot = None
        if reply_id:
            for b in bots:
                if b["id"] == reply_id:
                    bot = dict(b)
                    break
        if bot is None:
            active_id = self.config.get("active_bot_id", "")
            for b in bots:
                if b["id"] == active_id:
                    bot = dict(b)
                    break
        if bot is None:
            bot = dict(bots[0]) if bots else json.loads(json.dumps(DEFAULT_BOT))
        return self._apply_group_chain_overrides(bot)

    def _apply_group_chain_overrides(self, bot):
        """Bot 互聊/空回复重试时，按群设置关闭思考以省成本。"""
        if getattr(self, "_group_empty_retry", False):
            bot = dict(bot)
            bot["thinking_enabled"] = False
            return bot
        if not getattr(self, "_group_chain_reply", False):
            return bot
        sid = getattr(self, "current_session_id", None)
        if not sid:
            return bot
        try:
            data = history.load_session_messages(sid)
            if not data or not data.get("group_id"):
                return bot
            from .groups import load_group_meta
            app_dir = os.path.dirname(self.config_path)
            meta = load_group_meta(app_dir, data["group_id"]) or {}
            if meta.get("chain_fast_mode"):
                bot = dict(bot)
                bot["thinking_enabled"] = False
        except Exception:
            pass
        return bot

    def _resolve_memory_store_folder(self):
        """私聊用 souls/{id}/；群聊用 groups/{id}/。"""
        sid = getattr(self, "current_session_id", None)
        if sid:
            data = history.load_session_messages(sid)
            if data and data.get("group_id"):
                app_dir = os.path.dirname(self.config_path)
                from .groups import get_group_memory_folder
                return get_group_memory_folder(app_dir, data["group_id"])
        bot = self.get_active_bot()
        folder = bot.get("soul_folder", "")
        return self.resolve_app_path(folder) if folder else ""

    def switch_bot(self, bot_id):
        """切换机器人；自动停止当前生成并保存会话。"""
        # 停止当前生成
        self.stop_flag = True
        bots = self.config.get("bots", [])
        for b in bots:
            if b["id"] == bot_id:
                # 保存当前会话（如果有实际对话内容）
                if self.current_session_id:
                    non_system = [m for m in self.current_messages if m.get("role") != "system"]
                    if non_system:
                        history.save_session({
                            "id": self.current_session_id,
                            "title": "",
                            "messages": self.current_messages,
                            "summary": self.current_summary,
                        })
                # 清除当前会话状态，让新 bot 创建新会话
                self.current_session_id = None
                self.current_messages = []
                self.current_summary = None
                self.config["active_bot_id"] = bot_id
                self._write_config(self.config)
                return json.dumps({"ok": True, "msg": f"已切换到 {b['name']}"})
        return json.dumps({"ok": False, "msg": "机器人不存在"})

    # ---- Profile 管理 ----

    def get_active_profile(self):
        """返回当前 bot 关联的 API 配置，bot 覆盖的 model/temperature/max_tokens 优先"""
        bot = self.get_active_bot()
        profile_id = bot.get("profile_id", "")
        profiles = self.config.get("api_profiles", [])

        # 找到 bot 引用的 profile
        base = None
        for p in profiles:
            if p["id"] == profile_id:
                base = p
                break
        if base is None:
            base = profiles[0] if profiles else json.loads(json.dumps(DEFAULT_PROFILE))

        # bot 参数覆盖（非空非 None 时覆盖）
        result = dict(base)
        bot_model = bot.get("model", "")
        if bot_model:
            result["model"] = bot_model
        bot_temp = bot.get("temperature")
        if bot_temp is not None:
            result["temperature"] = bot_temp
        bot_max = bot.get("max_tokens")
        if bot_max is not None:
            result["max_tokens"] = bot_max

        return result

    def switch_profile(self, profile_id):
        """切换 API 配置（更新当前 bot 的 profile_id）"""
        profiles = self.config.get("api_profiles", [])
        for p in profiles:
            if p["id"] == profile_id:
                if p.get("enabled") is False:
                    return json.dumps({"ok": False, "msg": "该供应商已禁用"})
                bot = self.get_active_bot()
                bot["profile_id"] = profile_id
                # 同步更新 bots 数组中的对应项
                bots = self.config.get("bots", [])
                for i, b in enumerate(bots):
                    if b["id"] == bot["id"]:
                        bots[i] = bot
                        break
                self._write_config(self.config)
                return json.dumps({"ok": True, "msg": f"已切换到 {p['name']}"})
        return json.dumps({"ok": False, "msg": "配置不存在"})

    def fetch_profile_balance(self, profile_id):
        """查询指定供应商账户余额。"""
        from .providers import fetch_profile_balance, normalize_profile

        pid = (profile_id or "").strip()
        profiles = self.config.get("api_profiles", [])
        profile = next((p for p in profiles if p["id"] == pid), None)
        if not profile:
            return json.dumps({"ok": False, "msg": "供应商不存在"})
        profile = normalize_profile(dict(profile))
        result = fetch_profile_balance(profile)
        if result.get("ok"):
            for i, p in enumerate(profiles):
                if p["id"] == pid:
                    bal = dict(p.get("balance") or {})
                    bal["last_value"] = result["value"]
                    profiles[i]["balance"] = bal
                    break
            self._write_config(self.config)
        return json.dumps(result, ensure_ascii=False)

    def test_connection(self):
        try:
            from .providers import build_endpoint, build_headers, build_payload, parse_response, normalize_profile
            bot = self.get_active_bot()
            profile_id = bot.get("profile_id", "")
            profiles = self.config.get("api_profiles", [])
            base = next((p for p in profiles if p["id"] == profile_id), None)
            if base is None:
                base = profiles[0] if profiles else json.loads(json.dumps(DEFAULT_PROFILE))
            profile = normalize_profile(dict(base))
            url = build_endpoint(profile)
            headers = build_headers(profile)
            payload = build_payload(
                profile,
                [{"role": "user", "content": "Hello"}],
                max_tokens=5,
                stream=False,
            )
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                parse_response(profile, data)
                return json.dumps({"ok": True, "msg": "连接成功！API 正常工作。"})
            elif resp.status_code == 401:
                return json.dumps({"ok": False, "msg": "API Key 无效，请检查配置"})
            elif resp.status_code == 404:
                return json.dumps({"ok": False, "msg": "模型名称无效，请检查配置"})
            else:
                return json.dumps({"ok": False, "msg": f"API 返回 {resp.status_code}: {resp.text[:200]}"})
        except requests.exceptions.ConnectionError:
            return json.dumps({"ok": False, "msg": "无法连接到 API 地址，请检查网络和 Base URL"})
        except requests.exceptions.Timeout:
            return json.dumps({"ok": False, "msg": "请求超时，请稍后重试"})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def build_system_prompt(self):
        """稳定层 system：全局沉浸纪律 + 灵魂 + 技能 + 固定规则。"""
        bot = self.get_active_bot()
        parts = [GLOBAL_IMMERSION_PREAMBLE]
        soul_folder = bot.get("soul_folder", "")
        soul_content = self._load_soul_folder(soul_folder)
        if soul_content:
            parts.append(soul_content)
        skill_content = self._load_skills(bot)
        if skill_content:
            parts.append(skill_content)
        if self.current_mode == "code":
            parts.append(self._code_mode_rules_prompt())
        elif self.working_dir:
            parts.append(self._file_ops_prompt())
        return "\n\n---\n\n".join(parts) if parts else ""

    def _code_mode_rules_prompt(self):
        """编程模式固定规则（stable 层，不含工作目录与项目概览）。"""
        return (
            "You are in code mode.\n\n"
            "Rules:\n"
            "1. To read files use file:read:path=<path>; do not paste full file contents in chat\n"
            "2. To edit use file:edit:path=<path> with the complete new file content\n"
            "3. To create use file:create:path=<path>\n"
            "4. To delete use file:delete:path=<path>\n"
            "5. Understand project structure and existing code before changing anything\n"
            "6. Read relevant files before each edit to confirm current content\n"
            "7. After edits, briefly explain what changed and why"
        )

    def _get_code_semi_stable_block(self):
        """semi_stable：项目概览（目录 hash 未变则复用）。"""
        if self.current_mode != "code" or not self.working_dir:
            return ""
        from .code_mode import get_cached_project_overview
        overview, _ = get_cached_project_overview(
            self.working_dir, self._project_overview_cache
        )
        if not overview:
            return ""
        return f"[Project overview]\n{overview}"

    def _load_skills(self, bot):
        """加载 Bot 已启用的技能指令"""
        from .skills import get_enabled_skills, load_skill_instructions
        import os
        app_dir = os.path.dirname(self.config_path)
        global_enabled = self.config.get("enabled_skills", [])
        enabled = get_enabled_skills(bot, app_dir, global_enabled)
        if not enabled:
            return ''
        sections = []
        for skill in enabled:
            instructions = load_skill_instructions(skill.get('path', ''))
            if instructions:
                name = skill.get('name', skill.get('id', ''))
                sections.append(f"## Skill: {name}\n\n{instructions}")
        return "\n\n".join(sections) if sections else ''

    def _load_soul_folder(self, folder_path):
        from .soul import load_soul_folder
        return load_soul_folder(self.resolve_app_path(folder_path))

    def _log(self, msg):
        """同时输出到控制台和前端日志面板"""
        print(msg)
        try:
            escaped = json.dumps(msg)
            self.window.evaluate_js(f"onLog({escaped})")
        except Exception:
            pass

    def send_message(self, messages_json):
        try:
            messages = json.loads(messages_json)
            # 提取专家模式标记（仅最后一条用户消息，避免历史残留误触发）
            expert_mode = False
            user_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
            if user_msgs and "_expert_mode" in user_msgs[-1]:
                expert_mode = bool(user_msgs[-1].pop("_expert_mode"))
            api_messages = self.build_messages_for_api(messages)
            self.stop_flag = False
            est_tokens = 0
            for m in api_messages:
                c = m.get('content', '')
                if isinstance(c, list):
                    est_tokens += sum(estimate_tokens(p.get('text', '')) for p in c if p.get('type') == 'text')
                else:
                    est_tokens += estimate_tokens(c)
            self._log(f"发送请求: {len(api_messages)} 条消息, 估算输入≈{est_tokens} tokens")
            self._call_api(api_messages, expert_mode=expert_mode)
        except Exception as e:
            safe_msg = json.dumps(str(e))
            self.window.evaluate_js(f"onError({safe_msg})")

    def _has_file_ops(self, content):
        """判断消息内容中是否包含 file: 操作标记（用于 reasoning_content 回传决策）"""
        if not content:
            return False
        markers = ['file:create:', 'file:edit:', 'file:delete:', 'file:mkdir:', 'file:send:', 'file:read:']
        return any(m in content for m in markers)

    def _group_session_context(self, session_data):
        """群聊公共数据：meta、成员列表。"""
        from .groups import load_group_meta

        app_dir = os.path.dirname(self.config_path)
        group_id = session_data.get("group_id", "")
        meta = load_group_meta(app_dir, group_id) or {}
        member_ids = session_data.get("member_bot_ids") or meta.get("member_bot_ids") or []
        bots = self.config.get("bots", [])
        members = [b for b in bots if b["id"] in member_ids]
        return meta, members, bots

    def _build_group_stable_block(self, session_data):
        """semi_stable：群名、成员、@ 规则（不含每轮触发原因）。"""
        from .group_mentions import build_mention_instruction_block

        meta, members, _ = self._group_session_context(session_data)
        group_name = meta.get("name") or "群聊"
        member_lines = []
        for b in members:
            bname = b.get("name", b["id"])
            member_lines.append(
                f"- {b.get('avatar', '🤖')} {bname} (mention as @{bname})"
            )
        mention_block = build_mention_instruction_block(
            members, len(members) >= 2
        )
        return (
            f"[Group chat]\n"
            f"Group: {group_name}\n"
            f"Members ({len(members)} bots):\n"
            + ("\n".join(member_lines) if member_lines else "- (no members)")
            + f"\n\n{mention_block}"
        )

    def _build_group_dynamic_block(self, session_data, user_msg, reply_bot_id, current_messages=None):
        """dynamic：触发原因、当前身份、用户 @ 列表。"""
        _, members, bots = self._group_session_context(session_data)
        mention_ids = list(user_msg.get("mention_bot_ids") or [])
        if not mention_ids and user_msg.get("mention_bot_id"):
            mention_ids = [user_msg["mention_bot_id"]]
        mention_names = [
            b.get("name", b["id"]) for b in bots if b["id"] in mention_ids
        ]
        reply_bot = next((b for b in bots if b["id"] == reply_bot_id), None)
        reply_name = reply_bot.get("name", "你") if reply_bot else "你"

        trigger_line = "The user is addressing you."
        if current_messages:
            non_sys = [m for m in current_messages if m.get("role") != "system"]
            if non_sys:
                last = non_sys[-1]
                if last.get("role") == "assistant" and reply_bot_id:
                    parsed = last.get("parsed_mention_bot_ids") or []
                    if reply_bot_id in parsed:
                        sp_id = last.get("speaker_bot_id", "")
                        sp = next((b for b in bots if b["id"] == sp_id), None)
                        sp_name = sp.get("name", "a member") if sp else "a member"
                        trigger_line = (
                            f"In the previous message, {sp_name} @mentioned you; "
                            "continue the thread."
                        )

        lines = [
            "[This turn — group state]",
            f"Trigger: {trigger_line}",
            f"Your identity: {reply_name} (reply in your own voice; do not impersonate other members).",
        ]
        if mention_names:
            lines.append(
                "User @mentioned in this message: "
                + ", ".join("@" + n for n in mention_names)
            )
        return "\n".join(lines)

    def _collect_context_layers(self, current_messages):
        """收集 stable / semi_stable / dynamic 三层文本（供组装与用量统计）。"""
        stable = self.build_system_prompt()
        semi_stable = []
        dynamic = []

        session_data = None
        if self.current_session_id:
            session_data = history.load_session_messages(self.current_session_id)

        if session_data and session_data.get("group_id"):
            semi_stable.append(self._build_group_stable_block(session_data))

        code_overview = self._get_code_semi_stable_block()
        if code_overview:
            semi_stable.append(code_overview)

        if self.current_summary:
            dynamic.append(f"Prior conversation summary:\n{self.current_summary}")

        bot = self.get_active_bot()
        mem_cfg = self.get_memory_settings()
        if mem_cfg.get("enabled") and mem_cfg.get("retrieval"):
            soul_folder = self._resolve_memory_store_folder()
            if soul_folder and os.path.isdir(soul_folder):
                from .memory.retrieval import search_memory, format_memory_block
                query = ""
                non_sys = [m for m in current_messages if m.get("role") == "user"]
                if non_sys:
                    query = non_sys[-1].get("content", "") or ""
                hits = search_memory(
                    soul_folder,
                    query,
                    session_summary=self.current_summary or "",
                    budget_tokens=mem_cfg.get("budget", 1200),
                )
                block = format_memory_block(hits)
                if block:
                    dynamic.append(block)

        if session_data and session_data.get("group_id"):
            non_sys_users = [m for m in current_messages if m.get("role") == "user"]
            last_user = non_sys_users[-1] if non_sys_users else {}
            reply_bot_id = getattr(self, "_reply_bot_id", None) or self.get_active_bot().get("id", "")
            dynamic.append(
                self._build_group_dynamic_block(
                    session_data, last_user, reply_bot_id, current_messages
                )
            )

        if self.current_mode == "code" and self.working_dir:
            dynamic.append(f"[Working directory]\n{self.working_dir}")

        read_files = getattr(self, "read_files", None)
        if self.current_mode == "code" and read_files:
            file_text = read_files.get_context_text()
            if file_text:
                dynamic.append(file_text)

        if self._wants_web_search(bot):
            from .web_search import get_current_time_context
            dynamic.append(get_current_time_context())

        return stable, semi_stable, dynamic, session_data

    def _build_history_messages_for_api(self, current_messages, session_data):
        """格式化对话历史（不含 system 与 dynamic 注入）。"""
        is_group = bool(session_data and session_data.get("group_id"))
        group_bots = []
        speaker_id = ""
        if is_group:
            member_ids = session_data.get("member_bot_ids") or []
            group_bots = [b for b in self.config.get("bots", []) if b["id"] in member_ids]
            speaker_id = getattr(self, "_reply_bot_id", None) or self.get_active_bot().get("id", "")

        non_system = [m for m in current_messages if m.get("role") != "system"]
        if is_group:
            non_system = self._apply_group_history_window(non_system, session_data)

        history = []
        for m in non_system:
            attachments = m.get("attachments", [])
            if is_group:
                role, text = self._group_role_and_text(m, group_bots, speaker_id)
            else:
                role, text = m["role"], (m.get("content", "") or "")
            if attachments:
                for att in attachments:
                    if att.get("text_content"):
                        text += f"\n\n[文件: {att['name']}]\n{att['text_content']}"
                content_parts = [{"type": "text", "text": text}]
                for att in attachments:
                    if att.get("base64"):
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": att["base64"]}
                        })
                clean = {"role": role, "content": content_parts}
            else:
                clean = {"role": role, "content": text}
            if m.get("reasoning_content") and self._has_file_ops(m.get("content", "")):
                clean["reasoning_content"] = m["reasoning_content"]
            history.append(clean)
        return history

    def _apply_group_history_window(self, non_system, session_data):
        """群聊接话时只保留最近 N 条历史，降低重发成本。"""
        from .group_mentions import DEFAULT_GROUP_HISTORY_LIMIT
        from .groups import load_group_meta

        limit = DEFAULT_GROUP_HISTORY_LIMIT
        try:
            app_dir = os.path.dirname(self.config_path)
            meta = load_group_meta(app_dir, session_data.get("group_id", "")) or {}
            limit = int(meta.get("chain_history_limit") or DEFAULT_GROUP_HISTORY_LIMIT)
        except Exception:
            pass
        if limit <= 0 or len(non_system) <= limit:
            return non_system
        return non_system[-limit:]

    def _group_role_and_text(self, msg, group_bots, speaker_id):
        """群聊多 Bot 角色重映射：
        - 当前发言者自己的历史 → assistant（无前缀，视为『我』）
        - 其他 Bot 的发言 → user，前缀 [名字]:（视为对话者，提升人设一致性）
        - 人类用户 → user（原样）
        """
        content = msg.get("content", "") or ""
        role = msg.get("role")
        if role != "assistant":
            return "user", content
        sp_id = msg.get("speaker_bot_id", "")
        if sp_id and sp_id == speaker_id:
            return "assistant", content
        name = sp_id
        sp = next((b for b in group_bots if b["id"] == sp_id), None)
        if not sp:
            sp = next((b for b in self.config.get("bots", []) if b["id"] == sp_id), None)
        if sp:
            name = sp.get("name", sp_id)
        prefix = f"[{name}]"
        if content.startswith(prefix):
            return "user", content
        return "user", f"{prefix}: {content}" if name else content

    def build_messages_for_api(self, current_messages):
        """委托 ContextAssembler：tools → stable → semi_stable → history → dynamic。"""
        from .context_assembler import assemble_api_messages

        stable, semi_stable, dynamic, session_data = self._collect_context_layers(current_messages)
        history_msgs = self._build_history_messages_for_api(current_messages, session_data)
        return assemble_api_messages(stable, semi_stable, dynamic, history_msgs)

    def _file_ops_prompt(self):
        return (
            "You can help the user with files. Use these fenced code block markers:\n\n"
            "Create:\n"
            "```file:create:path=<relative-path>\n"
            "file content\n"
            "```\n\n"
            "Edit (output full new content):\n"
            "```file:edit:path=<relative-path>\n"
            "full new content\n"
            "```\n\n"
            "Delete:\n"
            "```file:delete:path=<relative-path>\n"
            "```\n\n"
            "Create directory:\n"
            "```file:mkdir:path=<relative-path>\n"
            "```\n\n"
            "Read:\n"
            "```\nfile:read:path=<relative-path>\n```\n"
            "Line range:\n```\nfile:read:path=<relative-path>:lines=1-50\n```\n\n"
            "Paths must be relative to the working directory. "
            "On edit, always output the complete file.\n\n"
            "To send a file to the user:\n"
            "<!--file:send:path=<relative-path>-->\n"
            "Multiple file:send markers are allowed in one reply."
        )

    # ---- 上下文 ----

    def calc_context_usage(self):
        """计算当前上下文使用情况，返回 JSON"""
        from .context_assembler import join_blocks, build_dynamic_context

        bot = self.get_active_bot()
        profile = self.get_active_profile()
        max_context = bot.get("max_context") or profile.get("max_context", 65536)

        stable, semi_stable, dynamic, _ = self._collect_context_layers(self.current_messages)
        system_tokens = estimate_tokens(stable)
        semi_tokens = estimate_tokens(join_blocks(semi_stable))
        dynamic_tokens = estimate_tokens(build_dynamic_context(dynamic))

        non_system = [m for m in self.current_messages if m.get("role") != "system"]
        msg_tokens = 0
        for msg in non_system:
            content = msg.get("content", "")
            reasoning = msg.get("reasoning_content", "")
            msg_tokens += estimate_tokens(content + reasoning)

        total_used = system_tokens + semi_tokens + dynamic_tokens + msg_tokens
        remaining = max(0, max_context - total_used)
        percentage = round(total_used / max_context * 100, 1) if max_context > 0 else 0

        return json.dumps({
            "max_context": max_context,
            "total_used": total_used,
            "remaining": remaining,
            "percentage": min(percentage, 100),
            "breakdown": {
                "system": system_tokens,
                "semi_stable": semi_tokens,
                "dynamic": dynamic_tokens,
                "messages": msg_tokens,
                "summary": estimate_tokens(self.current_summary) if self.current_summary else 0,
                "files": (
                    getattr(self, "read_files", None).total_chars() // 2
                    if self.current_mode == "code" and getattr(self, "read_files", None)
                    else 0
                ),
            }
        })

    def _build_deepseek_payload(self, messages, bot, profile, max_tokens, stream=True):
        """构建 DeepSeek 专属 payload：思考模式 / 快速模式"""
        thinking_enabled = bot.get("thinking_enabled", False) and self._model_supports(
            profile, "reasoning"
        )
        thinking_depth = bot.get("thinking_depth", "high")

        payload = {
            "model": profile["model"],
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": stream
        }

        if thinking_enabled:
            # 思考模式：思维链 + reasoning_effort，temperature 不生效
            payload["reasoning_effort"] = thinking_depth if thinking_depth in ("high", "max") else "high"
            payload["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            # 快速模式：显式关闭思考，使用 temperature（Bot 可覆盖 Profile）
            payload["temperature"] = float(profile.get("temperature", 0.7))
            payload["extra_body"] = {"thinking": {"type": "disabled"}}

        return payload

    def _wants_web_search(self, bot=None):
        from .skills import wants_web_search
        bot = bot or self.get_active_bot()
        return wants_web_search(bot, self.config.get("enabled_skills", []))

    def _profile_model_config(self, profile):
        """返回当前 profile.model 对应的模型能力配置。旧配置没有 models[] 时返回 None。"""
        model_name = (profile or {}).get("model", "")
        for m in (profile or {}).get("models") or []:
            if m.get("name") == model_name:
                return m
        return None

    def _model_supports(self, profile, capability):
        """供应商模型能力声明：缺失 models[] 时保持旧行为兼容。"""
        model_cfg = self._profile_model_config(profile)
        if not model_cfg:
            if capability == "reasoning":
                return (profile or {}).get("provider") == "deepseek"
            if capability == "tools":
                return True
            return False
        return capability in (model_cfg.get("capabilities") or [])

    def _build_chat_payload(self, messages, bot, profile, max_tokens, stream=True, tools=False):
        provider = profile.get("provider", "generic")
        if provider == "deepseek":
            payload = self._build_deepseek_payload(messages, bot, profile, max_tokens, stream=stream)
        else:
            payload = {
                "model": profile["model"],
                "messages": messages,
                "temperature": float(profile.get("temperature", 0.7)),
                "max_tokens": max_tokens,
                "stream": stream,
            }
        if tools and self._wants_web_search(bot) and self._model_supports(profile, "tools"):
            from .web_search import SEARCH_WEB_TOOL
            payload["tools"] = [SEARCH_WEB_TOOL]
            payload["tool_choice"] = "auto"
        return payload, provider

    def _api_request_headers(self, profile):
        from .providers import build_headers
        return build_headers(profile)

    def _post_chat_json(self, url, payload, headers, stream=False, timeout=120):
        """稳定键序 JSON 序列化，利于 tools/payload 缓存匹配。"""
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if stream:
            return requests.post(
                url, data=body.encode("utf-8"), headers=headers,
                stream=True, timeout=timeout,
            )
        return requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=timeout)

    def _log_cache_usage(self, usage_info):
        """解析 API usage 中的缓存字段（字段缺失时静默跳过）。"""
        if not usage_info or not isinstance(usage_info, dict):
            return
        cache_read = (
            usage_info.get("cache_read_input_tokens")
            or usage_info.get("prompt_cache_hit_tokens")
            or 0
        )
        cache_create = usage_info.get("cache_creation_input_tokens") or 0
        if not cache_read and not cache_create:
            return
        denom = cache_read + cache_create
        hit_rate = round(cache_read / denom * 100, 1) if denom else 0
        self._log(
            f"Cache: read={cache_read}, create={cache_create}, hit_rate={hit_rate}%"
        )

    def _handle_api_http_error(self, response, url, profile):
        if response.status_code == 401:
            self.window.evaluate_js("onError('API Key 无效，请检查配置')")
            return True
        if response.status_code == 404:
            msg = json.dumps(f"请求 404，请检查配置。\nURL: {url}\n模型: {profile['model']}")
            self.window.evaluate_js(f"onError({msg})")
            return True
        if response.status_code != 200:
            msg = json.dumps(format_api_error(response.status_code, response.text))
            self.window.evaluate_js(f"onError({msg})")
            return True
        return False

    def _log_request_mode(self, profile, bot, payload, provider, tools=False):
        bot_thinking = bot.get("thinking_enabled", False) and self._model_supports(profile, "reasoning")
        log_msg = f"请求: model={profile['model']}, provider={provider}, max_tokens={payload['max_tokens']}"
        if provider == "deepseek":
            if bot_thinking:
                log_msg += f", 模式=思考, effort={bot.get('thinking_depth', 'high')}"
            else:
                log_msg += f", 模式=快速, temp={payload.get('temperature', '?')}"
        elif "temperature" in payload:
            log_msg += f", temp={payload['temperature']}"
        if tools:
            log_msg += ", 联网=function(search_web)"
        self._log(log_msg)

    def _chat_completion_once(self, messages, tools=False):
        """非流式请求，用于 tool call 轮次。"""
        from .providers import build_endpoint, parse_response
        profile = self.get_active_profile()
        bot = self.get_active_bot()
        url = build_endpoint(profile)
        max_tokens = int(profile.get("max_tokens", 4096))
        payload, provider = self._build_chat_payload(
            messages, bot, profile, max_tokens, stream=False, tools=tools
        )
        self._log_request_mode(profile, bot, payload, provider, tools=tools)
        response = self._post_chat_json(
            url, payload, self._api_request_headers(profile), timeout=120
        )
        if self._handle_api_http_error(response, url, profile):
            return None
        data = response.json()
        data = parse_response(profile, data)
        if data.get("usage"):
            self._log_cache_usage(data["usage"])
        return data

    def _web_search_provider_label(self):
        from .web_search import provider_label
        return provider_label(self.config.get("web_search_provider", "duckduckgo"))

    def _notify_web_status(self, phase, detail="", provider=""):
        """向前端推送联网轮次级状态。"""
        try:
            payload = json.dumps({
                "phase": phase,
                "detail": detail or "",
                "provider": provider or self._web_search_provider_label(),
            }, ensure_ascii=False)
            self.window.evaluate_js(f"onWebSearchStatus({payload})")
        except Exception:
            pass

    def _notify_web_step(self, step):
        """向前端推送单条检索步骤（时间线）。"""
        try:
            payload = json.dumps(step, ensure_ascii=False)
            self.window.evaluate_js(f"onWebSearchStep({payload})")
        except Exception:
            pass

    def _emit_reasoning_chunks(self, reasoning, stream_reasoning):
        if not reasoning or not stream_reasoning:
            return
        chunk = 120
        for i in range(0, len(reasoning), chunk):
            self.window.evaluate_js(
                f"onReasoningToken({json.dumps(reasoning[i:i + chunk])})"
            )

    def _execute_search_tool_calls(self, message, max_queries=None):
        from .web_search import search_web_structured, provider_label
        provider = self.config.get("web_search_provider", "duckduckgo")
        api_key = self.config.get("web_search_api_key", "")
        provider_name = provider_label(provider)
        cap = max_queries
        if cap is None:
            cap = int(self.config.get("web_search_max_queries_per_round", 3))
        cap = max(1, min(8, int(cap)))

        tool_messages = []
        steps = []
        search_count = 0
        truncated = False

        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            if fn.get("name") != "search_web":
                continue
            if search_count >= cap:
                truncated = True
                break
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            query = (args.get("query") or "").strip()
            step_id = str(uuid.uuid4())[:12]
            pending = {
                "stepId": step_id,
                "phase": "searching",
                "query": query or "(空关键词)",
                "provider": provider_name,
                "status": "searching",
                "resultCount": 0,
                "items": [],
                "params": {"query": query},
            }
            self._notify_web_step(pending)
            self._log(f"联网检索 [{provider_name}]: {query or '(空)'}")
            result = search_web_structured(query, provider, api_key)
            step = result.to_step_dict(step_id, phase="done")
            self._notify_web_step(step)
            steps.append(step)
            tool_messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "content": result.text_for_model[:8000],
            })
            search_count += 1

        if truncated:
            self._log(
                f"联网: 当轮 search_web 超过上限 {cap}，已截断多余调用"
            )
        return tool_messages, steps

    def _normalize_assistant_tool_message(self, message):
        """确保带 tool_calls 的 assistant 消息符合 OpenAI 格式。"""
        out = {
            "role": "assistant",
            "content": message.get("content") or None,
            "tool_calls": message.get("tool_calls"),
        }
        if message.get("reasoning_content"):
            out["reasoning_content"] = message["reasoning_content"]
        return out

    def _push_expert_final(self, content, stream_reasoning, reasoning=""):
        """专家模式：stage3 已流式写入回答区，此处只推送 onStreamDone（含思考草稿）。"""
        try:
            result = json.dumps({
                "reasoning": reasoning or "",
                "content": content,
                "webSearchSteps": [],
                "citations": [],
            }, ensure_ascii=False)
            self.window.evaluate_js(f"onStreamDone({result})")
        except Exception:
            # 兜底：确保前端不会卡在 generating 状态
            try:
                self.window.evaluate_js("onError('专家模式输出异常')")
            except Exception:
                pass

    def _emit_assistant_message(self, message, stream_reasoning):
        """将完整 assistant 消息推送到前端（用于 tool 轮次后的非流式回复）。"""
        reasoning = message.get("reasoning_content") or message.get("thinking") or ""
        content = message.get("content") or ""
        if reasoning and stream_reasoning:
            chunk = 120
            for i in range(0, len(reasoning), chunk):
                self.window.evaluate_js(f"onReasoningToken({json.dumps(reasoning[i:i + chunk])})")
        if content:
            chunk = 80
            for i in range(0, len(content), chunk):
                self.window.evaluate_js(f"onToken({json.dumps(content[i:i + chunk])})")
        if not stream_reasoning:
            reasoning = ""
        result = json.dumps({
            "reasoning": reasoning,
            "content": content,
            "webSearchSteps": getattr(self, "_web_search_steps", []) or [],
            "citations": getattr(self, "_web_search_citations", []) or [],
        }, ensure_ascii=False)
        self.window.evaluate_js(f"onStreamDone({result})")

    def _stream_chat_completion(self, messages, clear_web_status=False):
        from .providers import build_endpoint, parse_stream_line
        profile = self.get_active_profile()
        bot = self.get_active_bot()
        provider = profile.get("provider", "generic")
        url = build_endpoint(profile)
        max_tokens = int(profile.get("max_tokens", 4096))
        payload, provider = self._build_chat_payload(
            messages, bot, profile, max_tokens, stream=True, tools=False
        )
        response = self._post_chat_json(
            url, payload, self._api_request_headers(profile),
            stream=True, timeout=120,
        )
        if self._handle_api_http_error(response, url, profile):
            return

        full_reasoning = ""
        full_content = ""
        usage_info = None
        finish_reason = None

        bot_thinking = bot.get("thinking_enabled", False)
        self._log_request_mode(profile, bot, payload, provider, tools=False)
        stream_reasoning = not (provider == "deepseek" and not bot_thinking)

        for line in response.iter_lines():
            if self.stop_flag:
                break
            if not line:
                continue
            line_str = line.decode("utf-8")

            token, finish, usage, raw, token_type = parse_stream_line(profile, line_str)
            if usage:
                usage_info = usage
            if finish:
                finish_reason = finish
            if token and token_type == "reasoning" and stream_reasoning:
                full_reasoning += token
                self.window.evaluate_js(f"onReasoningToken({json.dumps(token)})")
            elif token and token_type == "content":
                if clear_web_status:
                    self._notify_web_status("end")
                    clear_web_status = False
                full_content += token
                self.window.evaluate_js(f"onToken({json.dumps(token)})")

        if usage_info:
            self._log(
                f"Usage: prompt={usage_info.get('prompt_tokens', '?')}, "
                f"completion={usage_info.get('completion_tokens', '?')}, "
                f"total={usage_info.get('total_tokens', '?')}"
            )
            self._log_cache_usage(usage_info)
        else:
            est_prompt = sum(estimate_tokens(m.get("content", "")) for m in messages)
            est_completion = estimate_tokens(full_content) + estimate_tokens(full_reasoning)
            self._log(
                f"Usage(估): prompt≈{est_prompt}, completion≈{est_completion}, "
                f"max_limit={payload['max_tokens']}"
            )
        self._log(
            f"结束: reason={finish_reason or '未知'}, "
            f"content={len(full_content)}字, reasoning={len(full_reasoning)}字"
        )

        if not stream_reasoning:
            full_reasoning = ""

        done_payload = {
            "reasoning": full_reasoning,
            "content": full_content,
            "webSearchSteps": getattr(self, "_web_search_steps", []) or [],
            "citations": getattr(self, "_web_search_citations", []) or [],
        }
        self.window.evaluate_js(f"onStreamDone({json.dumps(done_payload, ensure_ascii=False)})")

    def _call_api(self, messages, expert_mode=False):
        try:
            profile = self.get_active_profile()
            bot = self.get_active_bot()
            api_messages = list(messages)
            stream_reasoning = not (
                profile.get("provider") == "deepseek"
                and not (bot.get("thinking_enabled") and self._model_supports(profile, "reasoning"))
            )

            # 专家模式：三轮内部调用管道（后台线程执行，避免阻塞 UI 回调）
            if expert_mode:
                user_msgs = [m for m in messages if m.get("role") == "user"]
                if user_msgs:
                    question = user_msgs[-1].get("content", "")
                    if isinstance(question, list):
                        question = " ".join(
                            p.get("text", "") for p in question if p.get("type") == "text"
                        )
                    resolved_soul = self.resolve_app_path(bot.get("soul_folder", ""))
                    soul_content = self._load_soul_folder(bot.get("soul_folder", ""))
                    api_self = self
                    stream_r = stream_reasoning

                    def _run_expert_worker():
                        try:
                            from .expert_mode import run_expert_pipeline
                            result = run_expert_pipeline(
                                api_self, question, resolved_soul or "",
                                soul_content=soul_content or "",
                                immersion_preamble=GLOBAL_IMMERSION_PREAMBLE,
                            )
                            if isinstance(result, dict):
                                api_self._push_expert_final(
                                    result.get("content", ""),
                                    stream_r,
                                    reasoning=result.get("reasoning", ""),
                                )
                            else:
                                api_self._push_expert_final(result or "", stream_r)
                        except Exception as err:
                            safe_msg = json.dumps(str(err))
                            try:
                                api_self.window.evaluate_js(f"onError({safe_msg})")
                            except Exception:
                                pass

                    import threading
                    threading.Thread(target=_run_expert_worker, daemon=True).start()
                    return

            self._web_search_steps = []
            self._web_search_citations = []
            had_web_search = False

            if self._wants_web_search(bot) and self._model_supports(profile, "tools"):
                from .web_search import build_citations
                provider_name = self._web_search_provider_label()
                max_rounds = max(1, min(5, int(self.config.get("web_search_max_rounds", 3))))
                max_queries = max(1, min(8, int(
                    self.config.get("web_search_max_queries_per_round", 3)
                )))
                self._notify_web_status("analyzing", provider_name, provider=provider_name)

                round_num = 0
                while round_num < max_rounds:
                    data = self._chat_completion_once(api_messages, tools=True)
                    if data is None:
                        self._notify_web_status("error", "API 请求失败")
                        self._notify_web_status("end")
                        return
                    message = data["choices"][0]["message"]
                    tool_calls = message.get("tool_calls")

                    if not tool_calls:
                        if round_num == 0 and (
                            message.get("content") or message.get("reasoning_content")
                        ):
                            self._notify_web_status(
                                "skipped",
                                "模型未调用 search_web，直接回复",
                                provider=provider_name,
                            )
                            self._emit_assistant_message(message, stream_reasoning)
                            return
                        if round_num == 0:
                            self._notify_web_status(
                                "skipped", "未触发联网检索", provider=provider_name
                            )
                            self._notify_web_status("end")
                        break

                    had_web_search = True
                    round_num += 1
                    self._notify_web_status(
                        "round",
                        f"第 {round_num}/{max_rounds} 轮",
                        provider=provider_name,
                    )
                    self._emit_reasoning_chunks(
                        message.get("reasoning_content") or message.get("thinking") or "",
                        stream_reasoning,
                    )
                    api_messages.append(self._normalize_assistant_tool_message(message))
                    tool_msgs, steps = self._execute_search_tool_calls(
                        message, max_queries=max_queries
                    )
                    if not tool_msgs:
                        self._log("联网: 未解析到 search_web 工具调用")
                        self._notify_web_status(
                            "skipped",
                            "工具调用已触发但无 search_web",
                            provider=provider_name,
                        )
                    self._web_search_steps.extend(steps)
                    api_messages.extend(tool_msgs)

                if had_web_search and round_num >= max_rounds:
                    self._log(
                        f"联网: 已达最大工具轮次 {max_rounds}，进入最终回复"
                    )

                if had_web_search:
                    self._web_search_citations = build_citations(self._web_search_steps)
                    self._log("联网: 检索完成，生成最终回复…")
                    self._notify_web_status("generating", provider=provider_name)

            self._stream_chat_completion(api_messages, clear_web_status=had_web_search)

        except requests.exceptions.ConnectionError:
            self.window.evaluate_js("onError('无法连接到 API 地址，请检查网络和 Base URL')")
        except requests.exceptions.Timeout:
            self.window.evaluate_js("onError('请求超时，请稍后重试')")
        except Exception as e:
            safe_msg = json.dumps(str(e))
            self.window.evaluate_js(f"onError({safe_msg})")

    def _get_organizer_profile_and_bot(self):
        """记忆整理代理：压缩/摘要/记忆提取使用的独立模型。"""
        if not self.config.get("memory_organizer_enabled"):
            return self.get_active_profile(), self.get_active_bot()
        pid = self.config.get("memory_organizer_profile_id", "")
        profiles = self.config.get("api_profiles", [])
        base = next((p for p in profiles if p["id"] == pid), None)
        if not base:
            return self.get_active_profile(), self.get_active_bot()
        profile = dict(base)
        # 优先使用前端选择的模型名，其次用 bot_id 查找
        organizer_model = self.config.get("_organizer_model", "")
        if organizer_model:
            profile["model"] = organizer_model
        else:
            bot_id = self.config.get("memory_organizer_bot_id", "")
            if bot_id:
                for b in self.config.get("bots", []):
                    if b["id"] == bot_id:
                        if b.get("model"):
                            profile["model"] = b["model"]
                        break
        # 构造整理专用 bot 对象（独立的思考模式设置）
        org_bot = {
            "thinking_enabled": self.config.get("organizer_thinking_enabled", False),
            "thinking_depth": self.config.get("organizer_thinking_depth", "high"),
        }
        return profile, org_bot

    def _call_api_sync(self, messages, use_organizer=False):
        from .providers import build_endpoint, build_headers, build_payload, parse_response
        if use_organizer:
            profile, bot = self._get_organizer_profile_and_bot()
        else:
            profile = self.get_active_profile()
            bot = self.get_active_bot()
        url = build_endpoint(profile)
        headers = build_headers(profile)
        max_tokens = int(profile.get("max_tokens", 4096))
        provider = profile.get("provider", "generic")
        if provider == "deepseek":
            payload = self._build_deepseek_payload(messages, bot, profile, max_tokens, stream=False)
        else:
            payload = build_payload(profile, messages, max_tokens, stream=False)
        response = self._post_chat_json(url, payload, headers, timeout=60)
        if response.status_code == 401:
            raise Exception("API Key 无效，请检查配置")
        elif response.status_code == 404:
            raise Exception(f"请求 404，请检查配置。\nURL: {url}\n模型: {profile['model']}")
        elif response.status_code != 200:
            raise Exception(format_api_error(response.status_code, response.text))
        data = parse_response(profile, response.json())
        return data["choices"][0]["message"]["content"]

    def stop_generation(self):
        self.stop_flag = True
