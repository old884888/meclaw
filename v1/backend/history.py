import json
import os
import sys
from datetime import datetime


def _get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_history_dir():
    path = os.path.join(_get_app_dir(), 'history')
    os.makedirs(path, exist_ok=True)
    return path


def get_summaries_dir():
    path = os.path.join(get_history_dir(), 'summaries')
    os.makedirs(path, exist_ok=True)
    return path


def _sessions_index_path():
    return os.path.join(get_history_dir(), 'sessions.json')


def _session_file_path(session_id):
    return os.path.join(get_history_dir(), f'{session_id}.json')


def _load_index():
    path = _sessions_index_path()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"sessions": []}


def _save_index(index):
    with open(_sessions_index_path(), 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def load_sessions():
    index = _load_index()
    return index.get("sessions", [])


def create_session(
    profile_id="",
    soul_folder="",
    bot_id="",
    mode="chat",
    working_dir="",
    group_id="",
    member_bot_ids=None,
    title="新对话",
):
    if member_bot_ids is None:
        member_bot_ids = []
    if group_id and bot_id:
        raise ValueError("group_id 与 bot_id 不能同时设置")
    if group_id:
        bot_id = ""
        profile_id = ""
        soul_folder = ""

    session_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + os.urandom(4).hex()
    now = datetime.now().isoformat(timespec='seconds')
    session = {
        "id": session_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "profile_id": profile_id,
        "soul_folder": soul_folder,
        "bot_id": bot_id,
        "group_id": group_id or "",
        "member_bot_ids": list(member_bot_ids),
        "mode": mode,
        "working_dir": working_dir,
    }
    data = {
        "id": session_id,
        "title": title,
        "created_at": now,
        "profile_id": profile_id,
        "soul_folder": soul_folder,
        "bot_id": bot_id,
        "group_id": group_id or "",
        "member_bot_ids": list(member_bot_ids),
        "mode": mode,
        "working_dir": working_dir,
        "messages": [],
        "summary": None,
    }
    with open(_session_file_path(session_id), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    index = _load_index()
    index["sessions"].insert(0, session)
    _save_index(index)
    return session


def save_session(session_data):
    session_id = session_data["id"]
    with open(_session_file_path(session_id), 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    index = _load_index()
    for s in index["sessions"]:
        if s["id"] == session_id:
            s["title"] = session_data.get("title", s["title"])
            s["updated_at"] = datetime.now().isoformat(timespec='seconds')
            s["message_count"] = len([m for m in session_data.get("messages", []) if m["role"] != "system"])
            break
    _save_index(index)


def delete_session(session_id):
    path = _session_file_path(session_id)
    if os.path.exists(path):
        os.remove(path)

    summary_path = os.path.join(get_summaries_dir(), f'{session_id}_summary.md')
    if os.path.exists(summary_path):
        os.remove(summary_path)

    index = _load_index()
    index["sessions"] = [s for s in index["sessions"] if s["id"] != session_id]
    _save_index(index)


def delete_sessions(session_ids):
    """批量删除会话"""
    for sid in session_ids:
        path = _session_file_path(sid)
        if os.path.exists(path):
            os.remove(path)
        summary_path = os.path.join(get_summaries_dir(), f'{sid}_summary.md')
        if os.path.exists(summary_path):
            os.remove(summary_path)

    id_set = set(session_ids)
    index = _load_index()
    index["sessions"] = [s for s in index["sessions"] if s["id"] not in id_set]
    _save_index(index)


def rename_session(session_id, new_title):
    index = _load_index()
    for s in index["sessions"]:
        if s["id"] == session_id:
            s["title"] = new_title
            break
    _save_index(index)

    path = _session_file_path(session_id)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data["title"] = new_title
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def update_session_fields(session_id, **fields):
    """更新会话的指定字段（同时更新索引和会话文件）"""
    index = _load_index()
    for s in index["sessions"]:
        if s["id"] == session_id:
            for k, v in fields.items():
                s[k] = v
            break
    _save_index(index)

    path = _session_file_path(session_id)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k, v in fields.items():
            data[k] = v
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def load_session_messages(session_id):
    path = _session_file_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def append_messages(session_id, messages):
    path = _session_file_path(session_id)
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["messages"].extend(messages)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    index = _load_index()
    for s in index["sessions"]:
        if s["id"] == session_id:
            s["updated_at"] = datetime.now().isoformat(timespec='seconds')
            s["message_count"] = len([m for m in data["messages"] if m["role"] != "system"])
            if s["title"] == "新对话":
                user_msg = next((m for m in messages if m["role"] == "user"), None)
                if user_msg:
                    s["title"] = user_msg["content"][:20]
                    data["title"] = s["title"]
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
            break
    _save_index(index)


def save_summary(session_id, summary):
    path = _session_file_path(session_id)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data["summary"] = summary
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    summary_path = os.path.join(get_summaries_dir(), f'{session_id}_summary.md')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary)


def search_sessions(keyword, max_results=50):
    """搜索所有会话的标题和消息内容"""
    if not keyword:
        return []
    keyword_lower = keyword.lower()
    index = _load_index()
    results = []

    for session in index.get("sessions", []):
        sid = session["id"]
        title = session.get("title", "")
        data = load_session_messages(sid)
        if not data:
            continue

        matches = []

        # 搜索标题
        if keyword_lower in title.lower():
            matches.append({"type": "title", "text": title, "role": ""})

        # 搜索消息内容
        for msg in data.get("messages", []):
            if msg.get("role") == "system":
                continue
            content = msg.get("content", "")
            if keyword_lower in content.lower():
                # 截取关键词前后各 30 字符
                idx = content.lower().find(keyword_lower)
                start = max(0, idx - 30)
                end = min(len(content), idx + len(keyword) + 30)
                snippet = content[start:end]
                if start > 0:
                    snippet = '...' + snippet
                if end < len(content):
                    snippet = snippet + '...'
                matches.append({
                    "type": "message",
                    "text": snippet,
                    "role": msg.get("role", "")
                })

        if matches:
            results.append({
                "session_id": sid,
                "title": title or "新对话",
                "updated_at": session.get("updated_at", ""),
                "bot_id": session.get("bot_id", "") or data.get("bot_id", ""),
                "group_id": session.get("group_id", "") or data.get("group_id", ""),
                "matches": matches[:5]  # 每个会话最多 5 条匹配
            })

        if len(results) >= max_results:
            break

    # 按更新时间倒序
    results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return results


def export_session_markdown(session_id, export_path=None):
    data = load_session_messages(session_id)
    if not data:
        return ""

    lines = [f"# {data.get('title', '对话记录')}\n"]
    lines.append(f"时间：{data.get('created_at', '')}\n\n---\n")

    round_num = 0
    for msg in data.get("messages", []):
        if msg["role"] == "system":
            continue
        if msg["role"] == "user":
            round_num += 1
            lines.append(f"\n## 第 {round_num} 轮\n")
            lines.append(f"### 用户\n{msg['content']}\n")
        else:
            lines.append("\n### AI\n")
            if msg.get("reasoning_content"):
                lines.append(f"> 💭 深度思考\n>")
                for think_line in msg["reasoning_content"].split("\n"):
                    lines.append(f"> {think_line}")
                lines.append("")
            lines.append(f"{msg['content']}\n")

    content = "\n".join(lines)

    if export_path:
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(content)

    return content
