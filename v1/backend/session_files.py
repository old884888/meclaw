"""按对话隔离的 AI 发送文件目录布局。"""
import os
import shutil

FILES_SUBDIR = "files"


def get_receive_root(config, app_dir):
    """全局根目录：用户配置的 receive_dir，未配置则用 app/downloads。"""
    rd = (config.get("receive_dir") or "").strip()
    if not rd:
        rd = os.path.join(app_dir, "downloads")
    os.makedirs(rd, exist_ok=True)
    return os.path.normpath(rd)


def get_session_dir(receive_root, session_id):
    return os.path.normpath(os.path.join(receive_root, session_id))


def get_session_files_dir(receive_root, session_id):
    """{根目录}/{对话ID}/files/"""
    path = os.path.join(get_session_dir(receive_root, session_id), FILES_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def remove_session_storage(receive_root, session_id):
    """删除整条对话对应的磁盘目录（含 files 子目录）。"""
    path = get_session_dir(receive_root, session_id)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def layout_pattern(receive_root):
    return os.path.join(receive_root, "{对话ID}", FILES_SUBDIR)
