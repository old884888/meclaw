import json
import os
import re
import sys
import webview
import difflib

# 跳过的隐藏文件夹
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.idea', '.vscode',
             '.meclaw_backup', 'dist', 'build', '.next', '.nuxt'}

# 跳过的二进制文件扩展名
BINARY_EXTS = {'.exe', '.dll', '.so', '.dylib', '.png', '.jpg', '.jpeg', '.gif', '.bmp',
               '.ico', '.svg', '.mp4', '.mp3', '.wav', '.avi', '.mov', '.zip', '.7z',
               '.rar', '.tar', '.gz', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt',
               '.pptx', '.woff', '.woff2', '.ttf', '.eot', '.pyc', '.pyo', '.class',
               '.o', '.obj', '.bin', '.dat', '.db', '.sqlite', '.sqlite3'}

# 文件大小限制
MAX_SIZE_BYTES = 200 * 1024  # 200KB
MAX_LINES = 3000

# 附件限制
MAX_ATTACH_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ATTACHMENTS = 5

# 图片扩展名
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

# 文本文件扩展名
TEXT_EXTS = {'.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.yaml', '.yml',
             '.csv', '.xml', '.toml', '.ini', '.cfg', '.sh', '.bat', '.ps1', '.sql',
             '.java', '.c', '.cpp', '.h', '.go', '.rs', '.ts', '.tsx', '.jsx', '.vue'}


def is_image_file(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXTS


def is_text_file(path):
    return os.path.splitext(path)[1].lower() in TEXT_EXTS


def get_file_info(path):
    name = os.path.basename(path)
    size = os.path.getsize(path)
    ext = os.path.splitext(name)[1].lower()
    return {
        "name": name,
        "path": path,
        "size": size,
        "ext": ext,
        "is_image": is_image_file(path),
        "is_text": is_text_file(path)
    }


def read_image_as_base64(path):
    import base64
    ext = os.path.splitext(path)[1].lower()
    mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp'}
    mime = mime_map.get(ext, 'application/octet-stream')
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')
    return f"data:{mime};base64,{data}"


def parse_file_sends(response):
    """解析 AI 回复中的所有 <!--file:send:path=...--> 标记"""
    pattern = r'<!--file:send:path=(.+?)-->'
    matches = re.findall(pattern, response)
    return [m.strip() for m in matches]


def copy_to_receive_dir(file_path, receive_dir, working_dir):
    """复制文件到接收目录，返回目标路径。路径安全检查：文件必须在工作目录内"""
    import shutil
    abs_src = os.path.normpath(os.path.join(working_dir, file_path))
    if not abs_src.startswith(os.path.normpath(working_dir)):
        return None, "路径越界"
    if not os.path.exists(abs_src):
        return None, f"文件不存在: {file_path}"
    os.makedirs(receive_dir, exist_ok=True)
    dest = os.path.join(receive_dir, os.path.basename(file_path))
    # 同名文件自动重命名
    if os.path.exists(dest):
        base, ext = os.path.splitext(os.path.basename(file_path))
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = os.path.join(receive_dir, f"{base}_{ts}{ext}")
    shutil.copy2(abs_src, dest)
    return dest, None


def normalize_dialog_directory(path):
    """将路径规范为文件夹选择对话框可用的初始目录（存在则直达，否则回退到最近存在的父目录）。"""
    if not path:
        return ""
    path = os.path.normpath(str(path).strip())
    if os.path.isdir(path):
        return path
    if os.path.isfile(path):
        return os.path.dirname(path)
    probe = path
    for _ in range(32):
        if os.path.isdir(probe):
            return probe
        parent = os.path.dirname(probe)
        if not parent or parent == probe:
            break
        probe = parent
    return ""


def select_folder(window, directory=""):
    """弹出系统文件夹选择对话框，directory 为初始打开路径"""
    initial = normalize_dialog_directory(directory)
    if initial:
        result = window.create_file_dialog(webview.FOLDER_DIALOG, directory=initial)
    else:
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
    if result and len(result) > 0:
        path = result[0]
        return json.dumps({"ok": True, "path": path})
    return json.dumps({"ok": False, "path": ""})


def get_file_tree(folder_path):
    """递归扫描目录，返回 JSON 格式的文件树结构"""
    try:
        tree = _scan_directory(folder_path)
        return json.dumps({"ok": True, "tree": tree})
    except Exception as e:
        return json.dumps({"ok": False, "msg": str(e)})


def read_file(file_path):
    """读取文件内容，大文件截断"""
    try:
        if not os.path.exists(file_path):
            return json.dumps({"ok": False, "msg": "文件不存在"})

        file_size = os.path.getsize(file_path)
        if file_size > MAX_SIZE_BYTES:
            return json.dumps({
                "ok": True,
                "content": "",
                "truncated": True,
                "total_lines": 0,
                "msg": f"文件过大（{file_size / 1024:.1f}KB），超过 200KB 限制，不支持预览"
            })

        # 检测二进制文件
        ext = os.path.splitext(file_path)[1].lower()
        if ext in BINARY_EXTS:
            return json.dumps({"ok": False, "msg": "不支持预览此文件类型"})

        # 尝试读取文件
        content, encoding = _read_file_content(file_path)
        if content is None:
            return json.dumps({"ok": False, "msg": "文件编码无法识别（已尝试 utf-8 和 gbk）"})

        lines = content.split('\n')
        total_lines = len(lines)

        if total_lines > MAX_LINES:
            truncated_content = '\n'.join(lines[:MAX_LINES])
            return json.dumps({
                "ok": True,
                "content": truncated_content,
                "truncated": True,
                "total_lines": total_lines,
                "encoding": encoding,
                "msg": f"文件共 {total_lines} 行，超过 3000 行限制，仅显示前 3000 行"
            })

        return json.dumps({
            "ok": True,
            "content": content,
            "truncated": False,
            "total_lines": total_lines,
            "encoding": encoding,
            "msg": ""
        })
    except Exception as e:
        return json.dumps({"ok": False, "msg": str(e)})


def get_working_dir():
    """返回当前工作目录路径"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _scan_directory(path, base_path=None):
    """递归扫描目录，返回文件树结构"""
    if base_path is None:
        base_path = path

    name = os.path.basename(path)
    rel_path = os.path.relpath(path, base_path).replace('\\', '/')

    if os.path.isdir(path):
        children = []
        try:
            entries = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
        except PermissionError:
            return {"name": name, "path": rel_path, "type": "folder", "children": []}

        for entry in entries:
            if entry in SKIP_DIRS:
                continue
            if entry.startswith('.') and entry not in ('.env', '.gitignore', '.eslintrc', '.prettierrc'):
                continue

            child_path = os.path.join(path, entry)
            child_node = _scan_directory(child_path, base_path)
            if child_node:
                children.append(child_node)

        return {"name": name, "path": rel_path, "type": "folder", "children": children}
    else:
        ext = os.path.splitext(name)[1].lower()
        if ext in BINARY_EXTS:
            return None

        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0

        return {"name": name, "path": rel_path, "type": "file", "size": size}


def _read_file_content(file_path):
    """尝试用 utf-8 和 gbk 读取文件内容，返回 (content, encoding)"""
    for encoding in ['utf-8', 'gbk']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read(), encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None, None


def parse_file_operations(ai_response):
    """解析 AI 回复中的 file:create/edit/delete/mkdir 标记"""
    pattern = r'```file:(create|edit|delete|mkdir):path=(.+?)\n(.*?)```'
    matches = re.findall(pattern, ai_response, re.DOTALL)

    operations = []
    for op_type, path, content in matches:
        path = path.strip()
        content = content.strip()
        operations.append({
            "type": op_type,
            "path": path,
            "content": content
        })

    return json.dumps({"ok": True, "operations": operations})


def resolve_working_abs_path(working_dir, rel_path):
    """将相对路径解析为 workdir 内绝对路径，越界返回 None。"""
    if not working_dir or not rel_path:
        return None
    rel = str(rel_path).replace('\\', '/').strip().lstrip('/')
    if not rel or '..' in rel.split('/'):
        return None
    wd = os.path.normpath(working_dir)
    abs_path = os.path.normpath(os.path.join(wd, rel.replace('/', os.sep)))
    if abs_path != wd and not abs_path.startswith(wd + os.sep):
        return None
    return abs_path


def save_working_file(working_dir, rel_path, content):
    """保存工作区内的文件（用户编辑器）。"""
    abs_path = resolve_working_abs_path(working_dir, rel_path)
    if not abs_path:
        return json.dumps({"ok": False, "msg": "路径越界或无效"})
    try:
        parent = os.path.dirname(abs_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.exists(abs_path):
            _backup_file(abs_path, working_dir)
        with open(abs_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content if content is not None else '')
        rel = os.path.relpath(abs_path, os.path.normpath(working_dir)).replace('\\', '/')
        return json.dumps({"ok": True, "path": rel})
    except Exception as e:
        return json.dumps({"ok": False, "msg": str(e)})


def execute_file_operation(op_json, working_dir):
    """执行单个文件操作（修改和删除前自动备份）"""
    try:
        op = json.loads(op_json) if isinstance(op_json, str) else op_json
        op_type = op.get("type")
        rel_path = op.get("path", "").strip()
        content = op.get("content", "")

        if not rel_path:
            return json.dumps({"ok": False, "msg": "路径为空"})

        # 安全检查：路径必须在工作目录内
        abs_path = os.path.normpath(os.path.join(working_dir, rel_path))
        if not abs_path.startswith(os.path.normpath(working_dir)):
            return json.dumps({"ok": False, "msg": "路径越界，拒绝操作"})

        if op_type == "create":
            return _op_create(abs_path, content)
        elif op_type == "edit":
            _backup_file(abs_path, working_dir)
            return _op_edit(abs_path, content)
        elif op_type == "delete":
            _backup_file(abs_path, working_dir)
            return _op_delete(abs_path)
        elif op_type == "mkdir":
            return _op_mkdir(abs_path)
        else:
            return json.dumps({"ok": False, "msg": f"未知操作类型: {op_type}"})
    except Exception as e:
        return json.dumps({"ok": False, "msg": str(e)})


def _ensure_backup_dir(working_dir):
    """确保备份目录存在"""
    backup_dir = os.path.join(working_dir, '.meclaw_backup')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def _backup_file(file_path, working_dir):
    """备份文件到 .meclaw_backup/，返回备份路径"""
    if not os.path.exists(file_path):
        return None
    backup_dir = _ensure_backup_dir(working_dir)
    rel_path = os.path.relpath(file_path, working_dir)
    backup_subdir = os.path.join(backup_dir, os.path.dirname(rel_path))
    os.makedirs(backup_subdir, exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = os.path.basename(file_path)
    backup_path = os.path.join(backup_subdir, f"{base_name}.{timestamp}.bak")

    import shutil
    shutil.copy2(file_path, backup_path)
    return backup_path


def _op_create(abs_path, content):
    """创建文件"""
    if os.path.exists(abs_path):
        return json.dumps({"ok": False, "msg": f"文件已存在: {abs_path}"})
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return json.dumps({"ok": True, "msg": f"已创建: {os.path.basename(abs_path)}"})


def _op_edit(abs_path, content):
    """修改文件（全文替换）"""
    if not os.path.exists(abs_path):
        return json.dumps({"ok": False, "msg": f"文件不存在: {abs_path}"})
    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return json.dumps({"ok": True, "msg": f"已修改: {os.path.basename(abs_path)}"})


def _op_delete(abs_path):
    """删除文件"""
    if not os.path.exists(abs_path):
        return json.dumps({"ok": False, "msg": f"文件不存在: {abs_path}"})
    os.remove(abs_path)
    return json.dumps({"ok": True, "msg": f"已删除: {os.path.basename(abs_path)}"})


def _op_mkdir(abs_path):
    """创建文件夹"""
    os.makedirs(abs_path, exist_ok=True)
    return json.dumps({"ok": True, "msg": f"已创建文件夹: {os.path.basename(abs_path)}"})


def generate_diff(old_content, new_content):
    """生成新旧内容的 diff"""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = list(difflib.ndiff(old_lines, new_lines))
    return ''.join(diff)


def get_backup_list(working_dir):
    """扫描 .meclaw_backup/ 目录，返回备份记录列表"""
    backup_dir = os.path.join(working_dir, '.meclaw_backup')
    if not os.path.exists(backup_dir):
        return json.dumps({"ok": True, "backups": []})

    backups = []
    for root, dirs, files in os.walk(backup_dir):
        for fname in files:
            if not fname.endswith('.bak'):
                continue
            full_path = os.path.join(root, fname)
            # 解析文件名：原文件名.时间戳.bak
            parts = fname.rsplit('.', 2)  # [原名, 时间戳, bak]
            if len(parts) < 3:
                continue
            original_name = parts[0]
            timestamp_str = parts[1]

            # 还原原始相对路径
            rel_dir = os.path.relpath(root, backup_dir)
            if rel_dir == '.':
                original_rel = original_name
            else:
                original_rel = os.path.join(rel_dir, original_name).replace('\\', '/')

            # 格式化时间戳
            try:
                from datetime import datetime
                ts = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                display_time = ts.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                display_time = timestamp_str

            file_size = os.path.getsize(full_path)

            backups.append({
                "backup_path": full_path.replace('\\', '/'),
                "original_path": original_rel,
                "time": display_time,
                "size": file_size
            })

    # 按时间倒序
    backups.sort(key=lambda x: x['time'], reverse=True)
    return json.dumps({"ok": True, "backups": backups})


def restore_backup(backup_path, original_path, working_dir):
    """从备份恢复文件"""
    try:
        abs_backup = os.path.normpath(backup_path)
        abs_original = os.path.normpath(os.path.join(working_dir, original_path))

        if not abs_backup.startswith(os.path.normpath(working_dir)):
            return json.dumps({"ok": False, "msg": "备份路径越界"})
        if not abs_original.startswith(os.path.normpath(working_dir)):
            return json.dumps({"ok": False, "msg": "恢复路径越界"})

        if not os.path.exists(abs_backup):
            return json.dumps({"ok": False, "msg": "备份文件不存在"})

        import shutil
        os.makedirs(os.path.dirname(abs_original), exist_ok=True)
        shutil.copy2(abs_backup, abs_original)
        return json.dumps({"ok": True, "msg": f"已恢复: {original_path}"})
    except Exception as e:
        return json.dumps({"ok": False, "msg": str(e)})
