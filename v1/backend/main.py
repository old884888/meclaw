import json
import os
import sys
import webview

from .api import MeClawAPI, DEFAULT_BOT
from .file_ops import (select_folder, get_file_tree, read_file, get_working_dir,
    parse_file_operations, execute_file_operation, save_working_file, generate_diff,
    get_backup_list, restore_backup, get_file_info, read_image_as_base64, MAX_ATTACH_SIZE,
    MAX_ATTACHMENTS, parse_file_sends, copy_to_receive_dir, is_image_file)
from . import history
from . import groups as groups_mod
from .skills import scan_skills, create_default_skill
from .code_mode import ReadFilesManager, safe_read_file
from .session_files import (
    get_receive_root,
    get_session_files_dir,
    remove_session_storage,
    layout_pattern,
)


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONFIG_PATH = os.path.join(get_app_dir(), 'config.json')
WEB_DIR = os.path.join(get_app_dir(), 'web')
SOULS_DIR = os.path.join(get_app_dir(), 'souls')


class MeClawAPIWithFiles(MeClawAPI):
    """扩展 MeClawAPI，添加文件系统操作方法"""

    def __init__(self):
        super().__init__(CONFIG_PATH)
        self.working_dir = None
        self.read_files = ReadFilesManager()
        self._auto_compress_armed = True
        # 首次运行时创建内置技能
        create_default_skill(get_app_dir())

    def _get_auto_compress_config(self):
        """私聊用全局/Bot 设置；群聊可用群 meta 独立开关。"""
        session = self._get_current_session_data()
        if session and session.get("group_id"):
            meta = groups_mod.load_group_meta(get_app_dir(), session["group_id"]) or {}
            if meta.get("auto_compress_enabled"):
                from .group_mentions import DEFAULT_GROUP_COMPRESS_THRESHOLD
                return {
                    "enabled": True,
                    "threshold": int(meta.get("auto_compress_threshold") or DEFAULT_GROUP_COMPRESS_THRESHOLD),
                }
            return {"enabled": False, "threshold": 85}
        return self.get_auto_compress_settings()

    def _try_auto_compress(self):
        """上下文达到阈值时自动压缩（每轮降至阈值以下前只触发一次）。"""
        # 群聊接话链进行中不压缩，避免每个 Bot 之间卡一次完整摘要 API
        if getattr(self, "_group_chain_reply", False):
            return None
        cfg = self._get_auto_compress_config()
        if not cfg.get("enabled"):
            return None

        usage = json.loads(self.calc_context_usage())
        pct = float(usage.get("percentage", 0))
        threshold = cfg.get("threshold", 85)

        if pct < threshold - 5:
            self._auto_compress_armed = True
            return None
        if pct < threshold:
            return None
        if not self._auto_compress_armed:
            return None

        non_system = [m for m in self.current_messages if m.get("role") != "system"]
        keep_count = self._compress_keep_count()
        if len(non_system) <= keep_count:
            return None

        result = json.loads(self.compress_context())
        if result.get("ok"):
            self._auto_compress_armed = False
            payload = json.dumps({
                "msg": f"⚙️ 上下文已达 {int(pct)}%，已自动压缩：{result.get('msg', '')}",
                "messages": result.get("messages"),
            }, ensure_ascii=False)
            if self.window:
                try:
                    self.window.evaluate_js(f"onAutoCompress({payload})")
                except Exception:
                    pass
        return result

    def send_message(self, messages_json):
        try:
            messages = json.loads(messages_json)
        except json.JSONDecodeError:
            super().send_message(messages_json)
            return
        # 与前端 conversationHistory 对齐，供自动压缩/用量统计使用
        system_msgs = [m for m in self.current_messages if m.get("role") == "system"]
        self.current_messages = system_msgs + list(messages)
        self._try_auto_compress()
        session = self._get_current_session_data()
        if session and session.get("group_id"):
            users = [m for m in messages if m.get("role") == "user"]
            if users:
                last_user = users[-1]
                if isinstance(last_user, dict):
                    last_user.pop("_council_mode", None)
                    last_user.pop("_council_participant_ids", None)
                mention_ids = self._parse_mention_bot_ids(last_user)
                if not mention_ids:
                    self._save_group_user_only(last_user)
                    try:
                        self.window.evaluate_js("onGroupUserOnly()")
                    except Exception:
                        pass
                    return
                self._save_group_user_only(last_user)
                self._reply_bot_id = mention_ids[0]
        try:
            super().send_message(messages_json)
        finally:
            self._reply_bot_id = None

    def _run_group_council(self, topic, participant_ids=None):
        """群聊专家会议入口。"""
        session = self._get_current_session_data()
        if not session or not session.get("group_id"):
            try:
                self.window.evaluate_js(
                    f"onCouncilDone({json.dumps({'ok': False, 'msg': '非群聊会话'}, ensure_ascii=False)})"
                )
            except Exception:
                pass
            return
        from .expert_council import run_council_pipeline
        self.stop_flag = False
        run_council_pipeline(
            self,
            topic,
            session["group_id"],
            session,
            participant_ids=participant_ids,
        )

    def council_arbitration(self, action, option_index=0):
        """专家会议仲裁：select / deepen / end。"""
        from .expert_council import continue_council_after_arbitration
        try:
            result = continue_council_after_arbitration(self, action, int(option_index))
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def send_group_bot_reply(self, messages_json, bot_id):
        """群聊中依次回复后续被 @ 的成员（不再重复保存用户消息）。"""
        return self._send_group_bot_reply_internal(messages_json, bot_id, empty_retry=False)

    def retry_group_bot_reply(self, messages_json, bot_id):
        """群聊空回复后快速模式重试一次。"""
        return self._send_group_bot_reply_internal(messages_json, bot_id, empty_retry=True)

    def _send_group_bot_reply_internal(self, messages_json, bot_id, empty_retry=False):
        bot_id = (bot_id or "").strip()
        if not bot_id:
            return json.dumps({"ok": False, "msg": "未指定机器人"})
        session = self._get_current_session_data()
        if not session or not session.get("group_id"):
            return json.dumps({"ok": False, "msg": "非群聊会话"})
        try:
            self._reply_bot_id = bot_id
            self._group_chain_reply = not empty_retry
            self._group_empty_retry = empty_retry
            self._try_auto_compress()
            MeClawAPI.send_message(self, messages_json)
            return json.dumps({"ok": True})
        finally:
            self._reply_bot_id = None
            self._group_chain_reply = False
            self._group_empty_retry = False

    def save_assistant_message(self, assistant_msg_json):
        """仅追加助手消息（群聊多 Bot 连续回复时用）。"""
        if isinstance(assistant_msg_json, str):
            assistant_msg = json.loads(assistant_msg_json)
        else:
            assistant_msg = assistant_msg_json
        if not self.current_session_id:
            return json.dumps({"ok": False, "msg": "无当前会话"})
        self.current_messages.append(assistant_msg)
        history.append_messages(self.current_session_id, [assistant_msg])
        session_data = self._get_current_session_data()
        if session_data and session_data.get("group_id"):
            groups_mod.touch_group(get_app_dir(), session_data["group_id"])
        return json.dumps({"ok": True})

    @staticmethod
    def _parse_mention_bot_ids(user_msg):
        ids = list(user_msg.get("mention_bot_ids") or [])
        ids = [i.strip() for i in ids if i and str(i).strip()]
        if not ids and user_msg.get("mention_bot_id"):
            single = str(user_msg.get("mention_bot_id", "")).strip()
            if single:
                ids = [single]
        # 去重保序
        seen = set()
        out = []
        for i in ids:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def select_folder(self):
        """弹出系统文件夹选择对话框，返回选中的路径（从当前工作目录打开）"""
        initial = self.working_dir or ""
        result = select_folder(self.window, initial)
        data = __import__('json').loads(result)
        if data.get('ok'):
            self.working_dir = data['path']
        return result

    def _refresh_file_tree_js(self):
        """刷新左侧文件树（不传路径，避免 Windows 反斜杠破坏 JS 字符串）"""
        if self.window:
            self.window.evaluate_js('refreshFileTree()')

    def get_file_tree(self, folder_path=None):
        """递归扫描目录，返回 JSON 格式的文件树结构"""
        path = folder_path or self.working_dir
        if not path:
            return __import__('json').dumps({"ok": False, "msg": "请先打开文件夹"})
        wd = self.working_dir
        if wd:
            if not os.path.isabs(path):
                path = os.path.normpath(os.path.join(wd, path))
            elif not os.path.exists(path):
                path = wd
        if os.path.isfile(path):
            path = os.path.dirname(path) or wd
        if not path or not os.path.isdir(path):
            if wd and os.path.isdir(wd):
                path = wd
            else:
                return __import__('json').dumps({"ok": False, "msg": "无效的工作目录"})
        return get_file_tree(path)

    def read_file(self, file_path):
        """读取文件内容，大文件截断"""
        if not os.path.isabs(file_path) and self.working_dir:
            file_path = os.path.join(self.working_dir, file_path)
        return read_file(file_path)

    def save_working_file(self, rel_path, content):
        """保存编程模式工作区内的文件"""
        if not self.working_dir:
            return json.dumps({"ok": False, "msg": "请先打开文件夹"})
        result_str = save_working_file(self.working_dir, rel_path, content)
        result = json.loads(result_str)
        if result.get("ok"):
            self._refresh_file_tree_js()
            self.window.evaluate_js(
                f'onWorkingFileSaved({json.dumps(result.get("path", rel_path))})'
            )
        return result_str

    def get_working_dir(self):
        """返回当前工作目录路径"""
        return self.working_dir or ""

    def parse_file_operations(self, ai_response):
        """解析 AI 回复中的文件操作标记"""
        return parse_file_operations(ai_response)

    def execute_file_operation(self, op_json):
        """执行单个文件操作"""
        if not self.working_dir:
            return json.dumps({"ok": False, "msg": "请先打开文件夹"})
        result_str = execute_file_operation(op_json, self.working_dir)
        result = json.loads(result_str)
        if result.get("ok"):
            self._refresh_file_tree_js()
        return result_str

    def get_diff(self, file_path, new_content):
        """获取文件的新旧 diff"""
        if not os.path.isabs(file_path) and self.working_dir:
            file_path = os.path.join(self.working_dir, file_path)
        try:
            old_content = ""
            if os.path.exists(file_path):
                for encoding in ['utf-8', 'gbk']:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            old_content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
            diff = generate_diff(old_content, new_content)
            return json.dumps({"ok": True, "diff": diff})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def get_backup_list(self):
        """获取备份列表"""
        if not self.working_dir:
            return json.dumps({"ok": False, "msg": "请先打开文件夹"})
        return get_backup_list(self.working_dir)

    def restore_backup(self, backup_path, original_path):
        """从备份恢复文件"""
        if not self.working_dir:
            return json.dumps({"ok": False, "msg": "请先打开文件夹"})
        result_str = restore_backup(backup_path, original_path, self.working_dir)
        result = json.loads(result_str)
        if result.get("ok"):
            self._refresh_file_tree_js()
        return result_str

    # ---- 附件 ----

    def select_attachments(self):
        """弹出系统文件选择对话框，支持多选，限 5 个"""
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        if not result:
            return json.dumps({"ok": False, "files": []})
        files = []
        for path in result[:MAX_ATTACHMENTS]:
            try:
                if os.path.getsize(path) > MAX_ATTACH_SIZE:
                    continue
                info = get_file_info(path)
                if info["is_image"]:
                    info["base64"] = read_image_as_base64(path)
                elif info["is_text"]:
                    read_result = json.loads(read_file(path))
                    if read_result.get("ok"):
                        info["text_content"] = read_result["content"]
                        info["truncated"] = read_result.get("truncated", False)
                files.append(info)
            except Exception:
                continue
        return json.dumps({"ok": True, "files": files})

    # ---- 接收目录 ----

    def _get_receive_root(self):
        return get_receive_root(self.config, get_app_dir())

    def _get_session_files_dir(self, session_id=None):
        sid = session_id or self.current_session_id
        if not sid:
            return None
        return get_session_files_dir(self._get_receive_root(), sid)

    def get_receive_dir(self):
        """返回对话文件根目录（各对话在其下按 ID 分子目录）"""
        return self._get_receive_root()

    def get_receive_layout(self):
        """返回目录结构说明，供设置页展示"""
        root = self._get_receive_root()
        return json.dumps({
            "ok": True,
            "root": root,
            "pattern": layout_pattern(root),
        })

    def select_receive_dir(self):
        """弹出文件夹选择对话框设置接收目录（从当前根目录打开）"""
        result = select_folder(self.window, self._get_receive_root())
        data = json.loads(result)
        if data.get("ok"):
            self.config["receive_dir"] = data["path"]
            self._write_config(self.config)
        return result

    def open_receive_dir(self):
        """用系统文件管理器打开对话文件根目录"""
        os.startfile(self._get_receive_root())
        return json.dumps({"ok": True})

    def open_session_files_dir(self, session_id=None):
        """打开指定对话（默认当前对话）的 files 子目录"""
        sid = session_id or self.current_session_id
        if not sid:
            return json.dumps({"ok": False, "msg": "请先选择或新建一条对话"})
        path = self._get_session_files_dir(sid)
        os.startfile(path)
        return json.dumps({"ok": True, "path": path})

    def process_file_sends(self, content):
        """解析 AI 回复中的 file:send 标记，复制到当前对话的 files 目录"""
        if not self.working_dir:
            return json.dumps({"ok": True, "files": []})
        paths = parse_file_sends(content)
        if not paths:
            return json.dumps({"ok": True, "files": []})
        receive_dir = self._get_session_files_dir()
        if not receive_dir:
            return json.dumps({"ok": False, "msg": "无当前对话，无法保存文件", "files": []})
        result_files = []
        for rel_path in paths:
            try:
                abs_src = os.path.normpath(os.path.join(self.working_dir, rel_path))
                if not abs_src.startswith(os.path.normpath(self.working_dir)):
                    continue
                if not os.path.exists(abs_src):
                    continue
                # 复制到接收目录
                dest, err = copy_to_receive_dir(rel_path, receive_dir, self.working_dir)
                if err:
                    continue
                info = get_file_info(dest)
                info["saved_path"] = dest
                if info["is_image"]:
                    info["base64"] = read_image_as_base64(dest)
                result_files.append(info)
            except Exception:
                continue
        return json.dumps({"ok": True, "files": result_files})

    # ---- 技能系统 ----

    def get_skills(self):
        """返回所有可用技能列表"""
        skills = scan_skills(get_app_dir())
        return json.dumps({"ok": True, "skills": skills})

    def open_skills_dir(self):
        """用系统文件管理器打开技能目录"""
        skills_dir = os.path.join(get_app_dir(), 'skills')
        os.makedirs(skills_dir, exist_ok=True)
        os.startfile(skills_dir)
        return json.dumps({"ok": True})

    # ---- Bot 管理 ----

    def save_bot(self, bot_json):
        """保存/更新机器人配置，新建时自动创建灵魂文件夹"""
        try:
            bot = json.loads(bot_json) if isinstance(bot_json, str) else bot_json
            bots = self.config.get("bots", [])
            is_new = not bot.get("id")

            if is_new:
                # 新建 bot
                bot["id"] = str(__import__('uuid').uuid4())[:8]
                soul_abs = os.path.join(SOULS_DIR, bot["id"])
                if not os.path.exists(soul_abs):
                    os.makedirs(soul_abs, exist_ok=True)
                    soul_md = os.path.join(soul_abs, "soul.md")
                    with open(soul_md, 'w', encoding='utf-8') as f:
                        name = bot.get("name", "助手")
                        f.write(f"# {name}\n\n## 身份\n（在这里描述你是谁）\n\n## 性格\n（在这里描述你的性格特点）\n\n## 说话风格\n（在这里描述你的说话方式）\n")
                bot["soul_folder"] = f"souls/{bot['id']}"
                bots.append(bot)
            else:
                # 更新已有 bot
                for i, b in enumerate(bots):
                    if b["id"] == bot["id"]:
                        bots[i] = bot
                        break

            for b in bots:
                if b.get("soul_folder"):
                    b["soul_folder"] = self.to_config_relative_path(b["soul_folder"])

            self.config["bots"] = bots
            self._write_config(self.config)
            return json.dumps({"ok": True, "bot": bot})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def delete_bot(self, bot_id):
        """删除机器人（至少保留一个）"""
        bots = self.config.get("bots", [])
        if len(bots) <= 1:
            return json.dumps({"ok": False, "msg": "至少保留一个机器人"})

        bots = [b for b in bots if b["id"] != bot_id]
        self.config["bots"] = bots

        # 如果删除的是当前激活的 bot，切换到第一个
        if self.config.get("active_bot_id") == bot_id:
            self.config["active_bot_id"] = bots[0]["id"]

        self._write_config(self.config)
        return json.dumps({"ok": True})

    def select_soul_folder(self, current_path=""):
        """弹出系统文件夹选择对话框，从当前灵魂路径（或其父级 souls）打开"""
        initial = ""
        if current_path and str(current_path).strip():
            resolved = self.resolve_app_path(str(current_path).strip())
            initial = resolved or str(current_path).strip()
        if not initial:
            souls_root = os.path.join(get_app_dir(), "souls")
            if os.path.isdir(souls_root):
                initial = souls_root
        result = select_folder(self.window, initial)
        return result

    def preview_soul_folder(self, folder_path):
        """预览灵魂文件夹内容，返回文件列表 JSON"""
        try:
            folder_path = self.resolve_app_path(folder_path)
            if not folder_path or not os.path.isdir(folder_path):
                return json.dumps({"ok": False, "msg": "文件夹不存在"})
            items = []
            for name in sorted(os.listdir(folder_path)):
                path = os.path.join(folder_path, name)
                if os.path.isfile(path) and name.endswith(".md"):
                    items.append({"name": name, "type": "file", "loaded": True})
                elif os.path.isdir(path):
                    count = 0
                    if os.path.isdir(path):
                        for f in os.listdir(path):
                            if f.endswith(".md"):
                                count += 1
                    items.append({"name": name + "/", "type": "dir", "count": count})
            return json.dumps({"ok": True, "items": items})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def get_soul_folder(self):
        """返回当前 bot 的灵魂文件夹路径"""
        bot = self.get_active_bot()
        return bot.get("soul_folder", "")

    def write_memory_file(self, content):
        """写入记忆文件到当前 bot 的灵魂文件夹"""
        bot = self.get_active_bot()
        soul_folder = self.resolve_app_path(bot.get("soul_folder", ""))
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "当前机器人未设置灵魂文件夹"})
        if not os.path.isdir(soul_folder):
            os.makedirs(soul_folder, exist_ok=True)
        path = os.path.join(soul_folder, 'memory.md')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return json.dumps({"ok": True, "msg": "记忆文件已更新"})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    # ---- 对话历史 ----

    def get_sessions(self, bot_id=None, group_id=None):
        """返回会话列表；bot_id='' 遗留私聊；group_id 指定群的会话"""
        sessions = history.load_sessions()
        if group_id is not None:
            if group_id == "":
                sessions = [s for s in sessions if s.get("group_id")]
            else:
                sessions = [s for s in sessions if s.get("group_id") == group_id]
        elif bot_id is not None:
            if bot_id == "":
                sessions = [
                    s for s in sessions
                    if not s.get("bot_id") and not s.get("group_id")
                ]
            else:
                sessions = [
                    s for s in sessions
                    if s.get("bot_id") == bot_id and not s.get("group_id")
                ]
        return json.dumps({"ok": True, "sessions": sessions})

    def _get_current_session_data(self):
        if not self.current_session_id:
            return None
        return history.load_session_messages(self.current_session_id)

    def _save_group_user_only(self, user_msg):
        if not self.current_session_id:
            return
        if isinstance(user_msg, str):
            user_msg = json.loads(user_msg)
        if self.current_messages:
            last = self.current_messages[-1]
            if last.get("role") == "user" and last.get("content") == user_msg.get("content"):
                return
        self.current_messages.append(user_msg)
        history.append_messages(self.current_session_id, [user_msg])
        session = self._get_current_session_data()
        if session and session.get("group_id"):
            groups_mod.touch_group(get_app_dir(), session["group_id"])

    def _cleanup_empty_session(self):
        """清理空会话（只有 system 消息，没有实际对话）"""
        if not self.current_session_id:
            return
        non_system = [m for m in self.current_messages if m.get("role") != "system"]
        if len(non_system) == 0:
            history.delete_session(self.current_session_id)
            self.current_session_id = None
            self.current_messages = []
            self.current_summary = None

    def new_session(self, bot_id=None):
        """创建新会话；可显式指定 bot_id，否则使用当前 active bot"""
        self._cleanup_empty_session()
        bots = self.config.get("bots", [])
        if bot_id:
            bot = next((b for b in bots if b["id"] == bot_id), None)
            if not bot:
                return json.dumps({"ok": False, "msg": "机器人不存在"})
            bot = dict(bot)
        else:
            bot = self.get_active_bot()
        if bot.get("id") and bot["id"] != self.config.get("active_bot_id", ""):
            self.config["active_bot_id"] = bot["id"]
            self._write_config(self.config)
        session = history.create_session(
            profile_id=bot.get("profile_id", ""),
            soul_folder=bot.get("soul_folder", ""),
            bot_id=bot.get("id", "")
        )
        self.current_session_id = session["id"]
        self.current_messages = []
        self.current_summary = None
        # 新会话重置模式和工作目录
        self.current_mode = "chat"
        self.working_dir = None
        self.read_files.clear()
        # 专家模式：清空草稿纸
        if bot.get("expert_mode_enabled"):
            from .expert_mode import clear_scratchpad
            resolved = self.resolve_app_path(bot.get("soul_folder", ""))
            if resolved:
                clear_scratchpad(resolved)
        return json.dumps({"ok": True, "session": session})

    def switch_session(self, session_id):
        """切换到指定会话（自动切换 bot）"""
        self._cleanup_empty_session()
        data = history.load_session_messages(session_id)
        if not data:
            return json.dumps({"ok": False, "msg": "会话不存在"})

        # 如果会话关联了 bot，自动切换
        session_bot_id = data.get("bot_id", "")
        group_id = data.get("group_id", "")
        member_bot_ids = data.get("member_bot_ids", [])
        group_name = ""
        if group_id:
            meta = groups_mod.load_group_meta(get_app_dir(), group_id)
            if meta:
                group_name = meta.get("name", "")
        elif session_bot_id and session_bot_id != self.config.get("active_bot_id", ""):
            bots = self.config.get("bots", [])
            if any(b["id"] == session_bot_id for b in bots):
                self.config["active_bot_id"] = session_bot_id
                self._write_config(self.config)

        self.current_session_id = session_id
        self.current_messages = data.get("messages", [])
        self.current_summary = data.get("summary")
        # 恢复会话的模式和工作目录
        self.current_mode = data.get("mode", "chat")
        session_working_dir = data.get("working_dir", "")
        self.working_dir = session_working_dir if session_working_dir else None
        messages = [m for m in self.current_messages if m["role"] != "system"]
        return json.dumps({
            "ok": True, "messages": messages, "title": data.get("title", ""),
            "mode": data.get("mode", "chat"),
            "working_dir": session_working_dir,
            "bot_id": session_bot_id,
            "group_id": group_id,
            "member_bot_ids": member_bot_ids,
            "group_name": group_name,
            "is_group": bool(group_id),
        })

    def switch_mode(self, mode):
        """切换模式（chat/code），更新当前会话"""
        if mode not in ("chat", "code"):
            return json.dumps({"ok": False, "msg": "无效模式"})
        self.current_mode = mode
        if self.current_session_id:
            history.update_session_fields(self.current_session_id, mode=mode)
        return json.dumps({"ok": True, "mode": mode})

    def set_working_dir(self, path):
        """设置编程模式的工作目录，更新当前会话"""
        if not path or not os.path.isdir(path):
            return json.dumps({"ok": False, "msg": "无效路径"})
        self.working_dir = path
        if self.current_session_id:
            history.update_session_fields(self.current_session_id, working_dir=path)
        return json.dumps({"ok": True, "path": path})

    def handle_file_read(self, file_path, lines_range=None):
        """处理 file:read 标记，读取文件并注入 read_files"""
        if not self.working_dir:
            return json.dumps({"ok": False, "msg": "请先打开文件夹"})
        if not os.path.isabs(file_path):
            abs_path = os.path.normpath(os.path.join(self.working_dir, file_path))
        else:
            abs_path = os.path.normpath(file_path)
        # 路径安全检查
        if not abs_path.startswith(os.path.normpath(self.working_dir)):
            return json.dumps({"ok": False, "msg": "路径越界"})
        if not os.path.exists(abs_path):
            return json.dumps({"ok": False, "msg": f"文件不存在: {file_path}"})
        try:
            content, encoding = safe_read_file(abs_path)
            # 行范围截取
            if lines_range:
                lines = content.split('\n')
                parts = lines_range.split('-')
                if len(parts) == 2:
                    start = max(1, int(parts[0])) - 1
                    end = min(len(lines), int(parts[1]))
                    content = '\n'.join(lines[start:end])
            rel_path = os.path.relpath(abs_path, self.working_dir)
            self.read_files.add_file(rel_path, content)
            # 返回文件信息供前端渲染记录块
            total_lines = content.count('\n') + 1
            return json.dumps({
                "ok": True,
                "path": rel_path,
                "lines": total_lines,
                "encoding": encoding,
                "chars": len(content)
            })
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def get_read_files_info(self):
        """返回 read_files 状态 JSON"""
        info = self.read_files.get_info()
        return json.dumps({"ok": True, **info})

    def delete_session(self, session_id):
        """删除会话（含该对话下的 files 目录）"""
        history.delete_session(session_id)
        remove_session_storage(self._get_receive_root(), session_id)
        if self.current_session_id == session_id:
            self.current_session_id = None
            self.current_messages = []
            self.current_summary = None
        return json.dumps({"ok": True})

    def delete_sessions(self, session_ids_json):
        """批量删除会话"""
        try:
            session_ids = json.loads(session_ids_json) if isinstance(session_ids_json, str) else session_ids_json
            root = self._get_receive_root()
            history.delete_sessions(session_ids)
            for sid in session_ids:
                remove_session_storage(root, sid)
            if self.current_session_id in session_ids:
                self.current_session_id = None
                self.current_messages = []
                self.current_summary = None
            return json.dumps({"ok": True, "count": len(session_ids)})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def rename_session(self, session_id, new_title):
        """重命名会话"""
        history.rename_session(session_id, new_title)
        return json.dumps({"ok": True})

    def save_current_messages(self, user_msg, assistant_msg):
        """保存当前对话消息到历史"""
        if isinstance(user_msg, str):
            user_msg = json.loads(user_msg)
        if isinstance(assistant_msg, str):
            assistant_msg = json.loads(assistant_msg)
        session_data = self._get_current_session_data()
        if session_data and session_data.get("group_id"):
            speaker = (assistant_msg.get("speaker_bot_id") if isinstance(assistant_msg, dict) else None)
            if not speaker:
                speaker = getattr(self, "_reply_bot_id", None) or ""
            if not speaker:
                ids = self._parse_mention_bot_ids(user_msg)
                speaker = ids[0] if ids else ""
            if speaker and isinstance(assistant_msg, dict):
                assistant_msg["speaker_bot_id"] = speaker
        if not self.current_session_id:
            bot = self.get_active_bot()
            session = history.create_session(
                profile_id=bot.get("profile_id", ""),
                soul_folder=bot.get("soul_folder", ""),
                bot_id=bot.get("id", ""),
            )
            self.current_session_id = session["id"]
        self.current_messages.append(user_msg)
        self.current_messages.append(assistant_msg)
        history.append_messages(self.current_session_id, [user_msg, assistant_msg])
        if session_data and session_data.get("group_id"):
            groups_mod.touch_group(get_app_dir(), session_data["group_id"])
        return json.dumps({"ok": True})

    def export_session(self, session_id):
        """导出会话为 Markdown"""
        content = history.export_session_markdown(session_id)
        return json.dumps({"ok": True, "content": content})

    def search_sessions(self, keyword):
        """搜索所有会话内容"""
        try:
            results = history.search_sessions(keyword)
            return json.dumps({"ok": True, "results": results})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def _notify_compress_progress(self, phase, detail=""):
        """向前端推送压缩阶段（摘要 / 保存 / 记忆整理）。"""
        try:
            payload = json.dumps({"phase": phase, "detail": detail or ""}, ensure_ascii=False)
            self.window.evaluate_js(f"onCompressProgress({payload})")
        except Exception:
            pass

    def _compress_keep_count(self):
        """群聊保留更多近期消息，避免多 Bot 接话上下文断裂。"""
        from .group_mentions import DEFAULT_GROUP_COMPRESS_KEEP
        session = self._get_current_session_data()
        if session and session.get("group_id"):
            return DEFAULT_GROUP_COMPRESS_KEEP
        return 2

    def _format_compress_line(self, msg, session_data=None):
        """压缩摘要用角色标签；群聊区分各 Bot 发言。"""
        if msg.get("role") == "user":
            return "用户", msg.get("content", "") or ""
        if session_data and session_data.get("group_id"):
            sp_id = msg.get("speaker_bot_id", "")
            if sp_id:
                bots = self.config.get("bots", [])
                sp = next((b for b in bots if b["id"] == sp_id), None)
                name = sp.get("name", sp_id) if sp else sp_id
                return name, msg.get("content", "") or ""
        return "AI", msg.get("content", "") or ""

    def compress_context(self, direction="", detail_level=None):
        """压缩上下文：把旧对话发给 AI 生成摘要，保留最近若干条"""
        from .memory.compress_prompts import build_compress_prompt, DETAIL_LEVEL_LABELS
        from .memory.config import get_compress_summary_detail
        from .group_mentions import DEFAULT_GROUP_COMPRESS_KEEP

        non_system = [m for m in self.current_messages if m.get("role") != "system"]
        session_data = self._get_current_session_data()
        keep_count = self._compress_keep_count()
        is_group = bool(session_data and session_data.get("group_id"))

        if len(non_system) <= keep_count:
            return json.dumps({"ok": False, "msg": "对话轮数不足，无需压缩"})

        keep_messages = non_system[-keep_count:]
        old_messages = non_system[:-keep_count]

        conversation_text = ""
        for msg in old_messages:
            role, text = self._format_compress_line(msg, session_data)
            conversation_text += f"{role}：{text}\n\n"

        if detail_level == "":
            detail_level = None
        resolved_level = get_compress_summary_detail(
            self.config, self.get_active_bot(), detail_level
        )
        compress_prompt = build_compress_prompt(
            conversation_text,
            direction_text=direction,
            detail_level=resolved_level,
        )

        mem_cfg = self.get_memory_settings()
        will_extract = bool(mem_cfg.get("enabled") and mem_cfg.get("write"))
        current_phase = "summary"

        try:
            self._notify_compress_progress(
                "start",
                json.dumps({"memory": will_extract}, ensure_ascii=False),
            )
            self._notify_compress_progress("summary")
            summary = self._call_api_sync(
                [{"role": "user", "content": compress_prompt}], use_organizer=True
            )
            old_summary = self.current_summary or ""
            if old_summary:
                self.current_summary = old_summary + "\n\n" + summary
            else:
                self.current_summary = summary
            self.current_messages = [m for m in self.current_messages if m.get("role") == "system"]
            self.current_messages.extend(keep_messages)

            current_phase = "save"
            self._notify_compress_progress("save")
            if self.current_session_id:
                history.save_summary(self.current_session_id, self.current_summary)
                history.save_session({
                    "id": self.current_session_id,
                    "title": "",
                    "messages": self.current_messages,
                    "summary": self.current_summary
                })

            mem_msg = ""
            if will_extract:
                current_phase = "memory"
                self._notify_compress_progress("memory")
                try:
                    from .memory.extractor import run_memory_extraction
                    mem_result = run_memory_extraction(
                        self,
                        conversation_text,
                        self.current_session_id or "",
                        detail_level=resolved_level,
                    )
                    if mem_result.get("ok"):
                        w = mem_result.get("written", 0)
                        m = mem_result.get("merged_md", 0)
                        if w or m:
                            mem_msg = f"，整理记忆 {w} 条"
                            if m:
                                mem_msg += f"（memory.md +{m}）"
                except Exception as mem_err:
                    mem_msg = f"，记忆整理失败: {mem_err}"

            self._notify_compress_progress("done")
            level_label = DETAIL_LEVEL_LABELS.get(resolved_level, resolved_level)
            api_messages = [m for m in keep_messages]
            return json.dumps({
                "ok": True,
                "msg": f"已压缩 {len(old_messages)} 条消息为摘要（{level_label}）{mem_msg}",
                "count": len(old_messages),
                "detail_level": resolved_level,
                "messages": api_messages,
            })
        except Exception as e:
            self._notify_compress_progress("error", current_phase)
            return json.dumps({"ok": False, "msg": str(e)})

    # ---- 记忆系统 ----

    def _active_soul_folder(self):
        folder = self._resolve_memory_store_folder()
        if not folder:
            return None
        return folder

    # ---- 群聊 ----

    def get_group_sessions(self, group_id):
        sessions = history.load_sessions()
        sessions = [s for s in sessions if s.get("group_id") == group_id]
        return json.dumps({"ok": True, "sessions": sessions})

    def get_groups(self):
        try:
            items = groups_mod.load_groups(get_app_dir())
            return json.dumps({"ok": True, "groups": items})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def create_group(self, name, member_bot_ids_json, avatar="👥"):
        try:
            member_ids = json.loads(member_bot_ids_json) if isinstance(member_bot_ids_json, str) else member_bot_ids_json
            group = groups_mod.create_group(get_app_dir(), name, avatar=avatar, member_bot_ids=member_ids)
            return json.dumps({"ok": True, "group": group})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def get_group_meta(self, group_id):
        try:
            meta = groups_mod.load_group_meta(get_app_dir(), group_id)
            if not meta:
                return json.dumps({"ok": False, "msg": "群不存在"})
            return json.dumps({"ok": True, "group": meta})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def update_group(
        self,
        group_id,
        name=None,
        member_bot_ids_json=None,
        avatar=None,
        settings_json=None,
    ):
        try:
            member_ids = None
            if member_bot_ids_json is not None:
                member_ids = json.loads(member_bot_ids_json) if isinstance(member_bot_ids_json, str) else member_bot_ids_json
            max_rounds = None
            member_settings = None
            chain_fast_mode = None
            chain_history_limit = None
            auto_compress_enabled = None
            auto_compress_threshold = None
            if settings_json is not None:
                settings = json.loads(settings_json) if isinstance(settings_json, str) else settings_json
                if "max_chain_rounds" in settings:
                    max_rounds = settings["max_chain_rounds"]
                if "member_settings" in settings:
                    member_settings = settings["member_settings"]
                if "chain_fast_mode" in settings:
                    chain_fast_mode = settings["chain_fast_mode"]
                if "chain_history_limit" in settings:
                    chain_history_limit = settings["chain_history_limit"]
                if "auto_compress_enabled" in settings:
                    auto_compress_enabled = settings["auto_compress_enabled"]
                if "auto_compress_threshold" in settings:
                    auto_compress_threshold = settings["auto_compress_threshold"]
            meta = groups_mod.update_group(
                get_app_dir(),
                group_id,
                name=name,
                avatar=avatar,
                member_bot_ids=member_ids,
                max_chain_rounds=max_rounds,
                member_settings=member_settings,
                chain_fast_mode=chain_fast_mode,
                chain_history_limit=chain_history_limit,
                auto_compress_enabled=auto_compress_enabled,
                auto_compress_threshold=auto_compress_threshold,
            )
            if not meta:
                return json.dumps({"ok": False, "msg": "群不存在"})
            return json.dumps({"ok": True, "group": meta})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def postprocess_group_assistant(
        self,
        speaker_bot_id,
        content,
        chain_state_json="{}",
        pending_mention_chain=False,
    ):
        """群聊 Bot 回复后：解析/补 @、扣减接话链余额、计算接话队列。"""
        if isinstance(pending_mention_chain, str):
            pending_mention_chain = pending_mention_chain.lower() in ("1", "true", "yes")
        from .group_mentions import normalize_oral_mentions, process_bot_reply_chain

        try:
            session = self._get_current_session_data()
            if not session or not session.get("group_id"):
                return json.dumps({"ok": False, "msg": "非群聊会话"})
            group_id = session["group_id"]
            meta = groups_mod.load_group_meta(get_app_dir(), group_id) or {}
            member_ids = session.get("member_bot_ids") or meta.get("member_bot_ids") or []
            bots = self.config.get("bots", [])
            member_bots = [b for b in bots if b["id"] in member_ids]
            if not any(b["id"] == speaker_bot_id for b in member_bots):
                return json.dumps({"ok": False, "msg": "发言者不在群成员中"})

            chain_state = (
                json.loads(chain_state_json)
                if isinstance(chain_state_json, str)
                else (chain_state_json or {})
            )
            text = normalize_oral_mentions(content or "", member_bots, exclude_bot_id=speaker_bot_id)
            oral_normalized = text != (content or "")

            result = process_bot_reply_chain(
                meta,
                speaker_bot_id,
                text,
                chain_state,
                member_bots,
                is_user_round=bool(pending_mention_chain),
            )
            if oral_normalized and not result.get("supplemented"):
                result["supplemented"] = True
            spoken = list(chain_state.get("spoken_bot_ids") or [])
            if speaker_bot_id and speaker_bot_id not in spoken:
                spoken.append(speaker_bot_id)
            result["spoken_bot_ids"] = spoken
            return json.dumps({"ok": True, **result})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def delete_group(self, group_id):
        try:
            sessions = history.load_sessions()
            group_sessions = [s["id"] for s in sessions if s.get("group_id") == group_id]
            if group_sessions:
                history.delete_sessions(group_sessions)
            groups_mod.delete_group(get_app_dir(), group_id)
            if self.current_session_id in group_sessions:
                self.current_session_id = None
                self.current_messages = []
                self.current_summary = None
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def new_group_session(self, group_id):
        self._cleanup_empty_session()
        meta = groups_mod.load_group_meta(get_app_dir(), group_id)
        if not meta:
            return json.dumps({"ok": False, "msg": "群不存在"})
        session = history.create_session(
            group_id=group_id,
            member_bot_ids=meta.get("member_bot_ids", []),
            title="新群对话",
        )
        self.current_session_id = session["id"]
        self.current_messages = []
        self.current_summary = None
        self.current_mode = "chat"
        self.working_dir = None
        self.read_files.clear()
        groups_mod.touch_group(get_app_dir(), group_id)
        return json.dumps({"ok": True, "session": session})

    def open_group_folder(self, group_id):
        folder = groups_mod.get_group_memory_folder(get_app_dir(), group_id)
        os.makedirs(folder, exist_ok=True)
        os.startfile(folder)
        return json.dumps({"ok": True})

    def collect_quote(self, text):
        """收藏好句到 memory/items/quote/"""
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "当前机器人未设置灵魂文件夹"})
        from .memory import store, indexer
        from .memory.store import ensure_layout
        ensure_layout(soul_folder)
        result = store.collect_quote(soul_folder, text, self.current_session_id or "")
        if not result:
            return json.dumps({"ok": False, "msg": "内容为空"})
        _, path = result
        indexer.index_after_write(soul_folder, path)
        return json.dumps({"ok": True, "msg": "已收藏到记忆库", "id": result[0]["id"]})

    def collect_document(self, title, content, tags_json="[]"):
        """收藏长文到 memory/docs/"""
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "当前机器人未设置灵魂文件夹"})
        try:
            tags = json.loads(tags_json) if isinstance(tags_json, str) else (tags_json or [])
        except json.JSONDecodeError:
            tags = []
        from .memory import store, indexer
        from .memory.store import ensure_layout
        ensure_layout(soul_folder)
        doc = store.collect_document(soul_folder, title, content, tags=tags)
        indexer.index_after_document(soul_folder, doc["slug"])
        return json.dumps({
            "ok": True,
            "msg": f"已收藏文章「{doc['meta']['title']}」",
            "slug": doc["slug"],
            "chunks": len(doc["chunks"]),
        })

    def list_memory_items(self, limit=50):
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "未设置灵魂文件夹"})
        from .memory.store import list_items
        items = list_items(soul_folder, limit=int(limit) if limit else 50)
        return json.dumps({"ok": True, "items": items})

    def delete_memory_item(self, item_id, item_type):
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "未设置灵魂文件夹"})
        from .memory import store, indexer
        ok = store.delete_item(soul_folder, item_id, item_type)
        if ok:
            indexer.remove_item_from_index(soul_folder, item_id)
        return json.dumps({"ok": ok, "msg": "已删除" if ok else "条目不存在"})

    def list_memory_docs(self, limit=30):
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "未设置灵魂文件夹"})
        from .memory.store import list_documents
        docs = list_documents(soul_folder, limit=int(limit) if limit else 30)
        return json.dumps({"ok": True, "docs": docs})

    def delete_memory_document(self, slug):
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "未设置灵魂文件夹"})
        from .memory import store, indexer
        ok = store.delete_document(soul_folder, slug)
        if ok:
            indexer.reindex_all(soul_folder)
        return json.dumps({"ok": ok, "msg": "已删除收藏" if ok else "文档不存在"})

    def list_memory_entries(self, limit=50):
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "未设置灵魂文件夹"})
        from .memory.store import list_entries
        entries = list_entries(soul_folder, limit=int(limit) if limit else 50)
        return json.dumps({"ok": True, "entries": entries})

    def delete_memory_entry(self, slug):
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "未设置灵魂文件夹"})
        from .memory import store, indexer
        ok = store.delete_entry(soul_folder, slug)
        if ok:
            indexer.remove_entry_from_index(soul_folder, slug)
        return json.dumps({"ok": ok, "msg": "已删除" if ok else "条目不存在"})

    def open_memory_folder(self):
        """在资源管理器中打开当前 Bot 的 memory/ 目录。"""
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "未设置灵魂文件夹"})
        from .memory.store import ensure_layout
        path = ensure_layout(soul_folder)
        try:
            os.startfile(path)
            return json.dumps({"ok": True, "path": path})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    def clear_bot_memory(self):
        """清空当前 Bot 的全部记忆（memory/ 目录下所有内容）。"""
        soul_folder = self._active_soul_folder()
        if not soul_folder:
            return json.dumps({"ok": False, "msg": "未设置灵魂文件夹"})
        from .memory.store import memory_root
        mem_root = memory_root(soul_folder)
        if not os.path.isdir(mem_root):
            return json.dumps({"ok": True, "msg": "记忆目录不存在，无需清空"})
        import shutil
        try:
            shutil.rmtree(mem_root)
            return json.dumps({"ok": True, "msg": "已清空全部记忆"})
        except Exception as e:
            return json.dumps({"ok": False, "msg": f"清空失败: {e}"})

    # ---- 回退 ----

    def rollback_to_message(self, msg_index):
        """回退到指定消息索引（保留该索引之前的消息，移除该索引及之后的）"""
        try:
            non_system = [i for i, m in enumerate(self.current_messages) if m.get("role") != "system"]
            if msg_index < 0 or msg_index >= len(non_system):
                return json.dumps({"ok": False, "msg": "无效的消息索引"})

            # 被移除的消息
            removed = non_system[msg_index:]
            keep = non_system[:msg_index]

            # 保存被移除的消息到 _rollback/ 目录
            if self.working_dir:
                rollback_dir = os.path.join(self.working_dir, '_rollback')
                os.makedirs(rollback_dir, exist_ok=True)
                from datetime import datetime
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                rollback_file = os.path.join(rollback_dir, f'{ts}.json')
                removed_msgs = [self.current_messages[i] for i in removed]
                with open(rollback_file, 'w', encoding='utf-8') as f:
                    json.dump(removed_msgs, f, indent=2, ensure_ascii=False)

            # 更新当前消息
            keep_msgs = [self.current_messages[i] for i in keep]
            # 保留 system 消息
            system_msgs = [m for m in self.current_messages if m.get("role") == "system"]
            self.current_messages = system_msgs + keep_msgs

            # 恢复 read_files 快照（如果有的话）
            if hasattr(self, 'read_files') and self.read_files.snapshots:
                # 找到 keep 中最后一条消息的快照
                pass  # 快照恢复需要 msg_id，简化处理

            # 保存到历史
            if self.current_session_id:
                history.save_session({
                    "id": self.current_session_id,
                    "title": "",
                    "messages": self.current_messages,
                    "summary": self.current_summary
                })

            return json.dumps({"ok": True, "removed": len(removed)})
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)})

    # ---- 新任务 ----

    def new_task(self):
        """新建任务：继承 Bot 和工作目录，清空对话和 read_files"""
        self._cleanup_empty_session()
        bot = self.get_active_bot()
        session = history.create_session(
            profile_id=bot.get("profile_id", ""),
            soul_folder=bot.get("soul_folder", ""),
            bot_id=bot.get("id", ""),
            mode="code",
            working_dir=self.working_dir or ""
        )
        self.current_session_id = session["id"]
        self.current_messages = []
        self.current_summary = None
        # 保持 current_mode 和 working_dir 不变
        if hasattr(self, 'read_files'):
            self.read_files.clear()
        return json.dumps({"ok": True, "session": session})

    # ---- 上下文 ----

    def get_context_usage(self):
        """返回上下文使用情况（供前端调用）"""
        return self.calc_context_usage()


def _debug_mode_enabled():
    """是否启用 Web 开发者工具（F12 / 右键检查）。"""
    if '--debug' in sys.argv or '-d' in sys.argv:
        return True
    flag = os.environ.get('MECLAW_DEBUG', '').strip().lower()
    return flag in ('1', 'true', 'yes', 'on')


def start(debug=None):
    api = MeClawAPIWithFiles()
    window = webview.create_window(
        'MeClaw',
        url=os.path.join(WEB_DIR, 'index.html'),
        js_api=api,
        width=900,
        height=700,
        min_size=(600, 400)
    )
    api.window = window

    if debug is None:
        debug = _debug_mode_enabled()
    if debug:
        # 不自动弹出 DevTools，由用户按 F12 或右键「检查」打开
        webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
        if not getattr(sys, 'frozen', False):
            print('[MeClaw 调试] 已启用开发者工具：按 F12，或右键页面 →「检查」→ 选择元素')
    webview.start(debug=debug)


if __name__ == '__main__':
    start()
