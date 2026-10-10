import os


PRIORITY_NAMES = ["soul.md", "constraints.md", "memory.md"]
LABELS = {
    "soul.md": "身份与人格",
    "constraints.md": "约束规则",
    "memory.md": "长期记忆"
}


def load_soul_folder(folder_path):
    if not folder_path or not os.path.isdir(folder_path):
        return ""
    parts = []
    for name in PRIORITY_NAMES:
        path = os.path.join(folder_path, name)
        if os.path.isfile(path):
            content = _read_md_file(path)
            if content:
                parts.append(f"## {LABELS[name]}\n{content}")
    knowledge_dir = os.path.join(folder_path, "knowledge")
    if os.path.isdir(knowledge_dir):
        for fname in sorted(os.listdir(knowledge_dir)):
            if fname.endswith(".md"):
                path = os.path.join(knowledge_dir, fname)
                content = _read_md_file(path)
                if content:
                    parts.append(f"## 知识：{fname[:-3]}\n{content}")
    for fname in sorted(os.listdir(folder_path)):
        if fname.endswith(".md") and fname not in PRIORITY_NAMES:
            path = os.path.join(folder_path, fname)
            if os.path.isfile(path):
                content = _read_md_file(path)
                if content:
                    parts.append(f"## 参考：{fname[:-3]}\n{content}")
    return "\n\n---\n\n".join(parts)


def _read_md_file(path):
    for encoding in ['utf-8', 'gbk']:
        try:
            with open(path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None
