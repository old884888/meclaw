import hashlib
import os
import re

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
             'dist', 'build', '.meclaw_backup', '.idea', '.vscode',
             '.next', '.nuxt', 'target', 'bin', 'obj'}
BINARY_EXTS = {'.exe', '.dll', '.png', '.jpg', '.jpeg', '.gif', '.mp4',
               '.zip', '.tar', '.gz', '.woff', '.woff2', '.ttf', '.ico',
               '.pdf', '.mp3', '.wav', '.avi', '.mov', '.so', '.dylib'}
MAX_FILES = 50
MAX_OVERVIEW_TOKENS = 1000  # 约 2000 字符（中文）或 4000 字符（英文）


def quick_summary(filepath, ext, head_content):
    """基于文件名 + 扩展名 + 结构特征生成一句话摘要"""
    basename = os.path.basename(filepath)

    if ext == '.py':
        classes = re.findall(r'^class\s+(\w+)', head_content, re.M)
        funcs = re.findall(r'^(?:def|async def)\s+(\w+)', head_content, re.M)
        if 'if __name__' in head_content:
            return f"入口文件，函数 {', '.join(funcs[:3])}" if funcs else "入口文件"
        if classes:
            return f"类 {', '.join(classes[:3])}"
        if funcs:
            return f"函数 {', '.join(funcs[:3])}"
        return "Python 模块"

    if ext in ('.js', '.ts', '.jsx', '.tsx'):
        exports = re.findall(r'export\s+(?:default\s+)?(?:class|function|const)\s+(\w+)', head_content)
        if exports:
            return f"导出 {', '.join(exports[:3])}"
        return f"{'TypeScript' if ext in ('.ts', '.tsx') else 'JavaScript'} 模块"

    if ext == '.json':
        if basename == 'package.json':
            return "Node.js 项目配置"
        if basename in ('tsconfig.json', 'jsconfig.json'):
            return "编译器配置"
        return "JSON 数据文件"

    if ext == '.md':
        return "文档"

    if ext in ('.html', '.htm'):
        return "HTML 页面"

    if ext == '.css':
        return "样式文件"

    if ext in ('.yaml', '.yml'):
        return "YAML 配置"

    if ext in ('.sh', '.bash', '.ps1', '.bat'):
        return "脚本文件"

    if ext == '.sql':
        return "SQL 脚本"

    if ext == '.go':
        funcs = re.findall(r'^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)', head_content, re.M)
        return f"函数 {', '.join(funcs[:3])}" if funcs else "Go 模块"

    if ext == '.rs':
        return "Rust 模块"

    if ext in ('.toml', '.ini', '.cfg', '.conf'):
        return "配置文件"

    return f"{ext.lstrip('.')} 文件" if ext else "文本文件"


def compute_project_dir_hash(folder_path):
    """目录结构指纹（路径 + mtime），用于 semi_stable 层复用项目概览。"""
    if not folder_path or not os.path.isdir(folder_path):
        return ""
    entries = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext in BINARY_EXTS:
                continue
            filepath = os.path.join(root, fname)
            try:
                st = os.stat(filepath)
                rel = os.path.relpath(filepath, folder_path)
                entries.append(f"{rel}:{int(st.st_mtime)}:{st.st_size}")
            except OSError:
                continue
    if not entries:
        return hashlib.sha256(folder_path.encode()).hexdigest()[:16]
    blob = "\n".join(sorted(entries))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def get_cached_project_overview(folder_path, cache):
    """
    返回 (overview_text, dir_hash)。cache 为可变 dict，键 path -> {hash, text}。
    hash 未变则复用 cache 中的 overview。
    """
    if not folder_path:
        return "", ""
    dir_hash = compute_project_dir_hash(folder_path)
    entry = cache.get(folder_path) if cache is not None else None
    if entry and entry.get("hash") == dir_hash and entry.get("text"):
        return entry["text"], dir_hash
    text = generate_project_overview(folder_path)
    if cache is not None:
        cache[folder_path] = {"hash": dir_hash, "text": text}
    return text, dir_hash


def generate_project_overview(folder_path):
    """生成项目索引概览，控制在 1000 token 以内"""
    lines = []
    total_files = 0

    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]

        rel_root = os.path.relpath(root, folder_path)
        if rel_root == '.':
            rel_root = ''

        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext in BINARY_EXTS:
                continue

            total_files += 1
            filepath = os.path.join(root, fname)
            rel_path = os.path.join(rel_root, fname) if rel_root else fname

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    head = f.read(4000)  # 读前 4000 字符用于结构分析
                    total_lines = head.count('\n') + 1
                    summary = quick_summary(filepath, ext, head)
                    lines.append(f"{rel_path} ({total_lines}行) - {summary}")
            except (UnicodeDecodeError, PermissionError):
                lines.append(f"{rel_path} - (二进制/无法读取)")

    # 限制条目数
    if len(lines) > MAX_FILES:
        lines = lines[:MAX_FILES]
        lines.append(f"... 共 {total_files} 个文件，仅显示前 {MAX_FILES} 个")

    # 截断到 token 预算
    overview = "Project structure:\n" + "\n".join(lines)
    if len(overview) > 4000:  # ~1000 token
        overview = overview[:4000] + "\n... (概览已截断)"

    return overview


def safe_read_file(filepath):
    """安全读取文件，自动检测编码，返回 (content, encoding)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 'UTF-8'
    except UnicodeDecodeError:
        try:
            import chardet
            with open(filepath, 'rb') as f:
                raw = f.read()
            detected = chardet.detect(raw)
            enc = detected['encoding'] or 'latin-1'
            return raw.decode(enc, errors='replace'), enc
        except ImportError:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
            return content, 'latin-1'


class ReadFilesManager:
    """管理编程模式下读取的文件上下文（内存中，不持久化）"""

    def __init__(self, max_tokens=8000):
        self.files = {}           # {path: content}
        self.read_order = []      # 按读取顺序
        self.max_tokens = max_tokens
        self.snapshots = {}       # {msg_id: snapshot}，内存快照
        self.max_snapshots = 20   # 快照上限

    def add_file(self, path, content):
        """添加或更新文件，语义去重：同路径只保留最新版本"""
        if path not in self.files:
            self.read_order.append(path)
        self.files[path] = content
        self._trim()

    def get_context_text(self):
        """返回 dynamic 层文件上下文文本（非 system 消息）。"""
        if not self.files:
            return ""

        file_blocks = []
        for path in self.read_order:
            content = self.files[path]
            file_blocks.append(f"--- {path} ---\n```\n{content}\n```")

        return (
            "Files currently loaded for reference:\n\n" + "\n\n".join(file_blocks)
        )

    def get_context_messages(self):
        """兼容旧调用：返回 dynamic 文本块（调用方应放入 dynamic 层）。"""
        text = self.get_context_text()
        return [text] if text else []

    def get_snapshot(self):
        """返回当前状态快照"""
        return {
            "files": dict(self.files),
            "read_order": list(self.read_order)
        }

    def save_snapshot(self, msg_id):
        """保存快照（带上限控制）"""
        self.snapshots[msg_id] = self.get_snapshot()
        while len(self.snapshots) > self.max_snapshots:
            oldest_key = next(iter(self.snapshots))
            del self.snapshots[oldest_key]

    def restore_snapshot(self, msg_id):
        """恢复到指定快照"""
        if msg_id in self.snapshots:
            snap = self.snapshots[msg_id]
            self.files = dict(snap["files"])
            self.read_order = list(snap["read_order"])
            keys = list(self.snapshots.keys())
            idx = keys.index(msg_id)
            for k in keys[idx + 1:]:
                del self.snapshots[k]

    def total_chars(self):
        """当前文件上下文总字符数"""
        return sum(len(c) for c in self.files.values())

    def get_info(self):
        """返回文件列表和使用量，供前端状态面板显示"""
        return {
            "files": [
                {"path": p, "chars": len(self.files[p])}
                for p in self.read_order
            ],
            "total_chars": self.total_chars(),
            "total_tokens_est": self.total_chars() // 2,
            "max_tokens": self.max_tokens
        }

    def _trim(self):
        """超预算时移除最早的文件"""
        while self.total_chars() // 2 > self.max_tokens and len(self.read_order) > 1:
            oldest = self.read_order.pop(0)
            del self.files[oldest]

    def clear(self):
        self.files.clear()
        self.read_order.clear()
        self.snapshots.clear()
