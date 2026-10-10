import json
import os
import re
import uuid
from datetime import datetime

from .constants import CHUNK_MAX, CHUNK_MIN, CHUNK_TARGET, ITEM_TYPES, slugify


def memory_root(soul_folder):
    return os.path.join(soul_folder, "memory")


def items_dir(soul_folder, item_type):
    return os.path.join(memory_root(soul_folder), "items", item_type)


def docs_dir(soul_folder):
    return os.path.join(memory_root(soul_folder), "docs")


def entries_dir(soul_folder):
    return os.path.join(memory_root(soul_folder), "entries")


def index_path(soul_folder):
    return os.path.join(memory_root(soul_folder), "index.sqlite")


def ensure_layout(soul_folder):
    """Create memory/ subtree if missing."""
    root = memory_root(soul_folder)
    os.makedirs(root, exist_ok=True)
    for t in ITEM_TYPES:
        os.makedirs(items_dir(soul_folder, t), exist_ok=True)
    os.makedirs(docs_dir(soul_folder), exist_ok=True)
    os.makedirs(entries_dir(soul_folder), exist_ok=True)
    return root


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _new_id():
    return datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]


def write_item(soul_folder, item):
    """Write one memory item JSON under items/{type}/."""
    ensure_layout(soul_folder)
    item_type = item.get("type", "fact")
    if item_type not in ITEM_TYPES:
        item_type = "fact"
    item_id = item.get("id") or _new_id()
    now = _now_iso()
    record = {
        "id": item_id,
        "type": item_type,
        "content": (item.get("content") or "").strip(),
        "summary": (item.get("summary") or "").strip(),
        "keywords": item.get("keywords") or [],
        "importance": int(item.get("importance", 3)),
        "confidence": float(item.get("confidence", 0.8)),
        "source_session_id": item.get("source_session_id") or "",
        "created_at": item.get("created_at") or now,
        "updated_at": now,
        "expires_at": item.get("expires_at"),
    }
    if not record["content"]:
        return None
    if not record["summary"]:
        record["summary"] = record["content"][:80]

    path = os.path.join(items_dir(soul_folder, item_type), f"{item_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    return record, path


def read_item_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def delete_item(soul_folder, item_id, item_type):
    if item_type not in ITEM_TYPES:
        return False
    path = os.path.join(items_dir(soul_folder, item_type), f"{item_id}.json")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def list_item_files(soul_folder):
    files = []
    for t in ITEM_TYPES:
        folder = items_dir(soul_folder, t)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if name.endswith(".json"):
                files.append(os.path.join(folder, name))
    return files


def list_items(soul_folder, limit=50):
    items = []
    for path in list_item_files(soul_folder):
        data = read_item_file(path)
        if data:
            items.append(data)
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return items[:limit]


def list_documents(soul_folder, limit=30):
    """列出长文收藏 docs/ 元数据。"""
    root = docs_dir(soul_folder)
    if not os.path.isdir(root):
        return []
    docs = []
    for slug in sorted(os.listdir(root), reverse=True):
        base = os.path.join(root, slug)
        if not os.path.isdir(base):
            continue
        meta_path = os.path.join(base, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            chunk_count = sum(
                1 for n in os.listdir(base)
                if n.startswith("chunk-") and n.endswith(".md")
            )
            docs.append({
                "slug": slug,
                "title": meta.get("title", slug),
                "summary": meta.get("summary", ""),
                "tags": meta.get("tags", []),
                "created_at": meta.get("created_at", ""),
                "chunk_count": chunk_count,
            })
        except (OSError, json.JSONDecodeError):
            continue
        if len(docs) >= limit:
            break
    return docs


def delete_document(soul_folder, slug):
    import shutil
    base = os.path.join(docs_dir(soul_folder), slug)
    if os.path.isdir(base):
        shutil.rmtree(base)
        return True
    return False


def _split_chunks(text):
    text = (text or "").strip()
    if not text:
        return []
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    buf = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) > CHUNK_MAX:
            if buf:
                chunks.append(buf.strip())
                buf = ""
            for i in range(0, len(para), CHUNK_TARGET):
                chunks.append(para[i:i + CHUNK_TARGET])
            continue
        candidate = (buf + "\n\n" + para).strip() if buf else para
        if len(candidate) > CHUNK_MAX:
            if buf:
                chunks.append(buf.strip())
            buf = para
        else:
            buf = candidate
        if len(buf) >= CHUNK_MIN:
            chunks.append(buf.strip())
            buf = ""
    if buf:
        chunks.append(buf.strip())
    if not chunks and text:
        for i in range(0, len(text), CHUNK_TARGET):
            chunks.append(text[i:i + CHUNK_TARGET])
    return chunks


def collect_document(soul_folder, title, content, tags=None, source="用户收藏", summary=""):
    ensure_layout(soul_folder)
    doc_slug = slugify(title)
    base = os.path.join(docs_dir(soul_folder), doc_slug)
    if os.path.exists(base):
        doc_slug = f"{doc_slug}-{_new_id()[:8]}"
        base = os.path.join(docs_dir(soul_folder), doc_slug)
    os.makedirs(base, exist_ok=True)

    meta = {
        "title": title or doc_slug,
        "source": source,
        "tags": tags or [],
        "summary": summary or (content[:120] + "…") if len(content) > 120 else content,
        "slug": doc_slug,
        "created_at": _now_iso(),
    }
    with open(os.path.join(base, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    chunks = _split_chunks(content)
    chunk_paths = []
    for i, chunk in enumerate(chunks, start=1):
        fname = f"chunk-{i:03d}.md"
        path = os.path.join(base, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(chunk)
        chunk_paths.append((fname, chunk))
    return {"meta": meta, "slug": doc_slug, "chunks": chunk_paths}


def collect_quote(soul_folder, text, source_session_id=""):
    text = (text or "").strip()
    if not text:
        return None
    item = {
        "type": "quote",
        "content": text,
        "summary": text[:60],
        "keywords": [],
        "importance": 3,
        "confidence": 1.0,
        "source_session_id": source_session_id,
    }
    return write_item(soul_folder, item)


def _parse_yaml_frontmatter(text):
    """Parse YAML frontmatter from a Markdown entry file."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end < 0:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 3:].strip()
    meta = {}
    current_key = None
    current_list = None
    for line in fm_text.split("\n"):
        line = line.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_key:
            if current_list is None:
                current_list = []
            current_list.append(line[4:].strip())
            meta[current_key] = current_list
            continue
        if ":" in line:
            if current_list is not None:
                current_list = None
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                items = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
                meta[key] = items
            elif val.lower() in ("true", "false"):
                meta[key] = val.lower() == "true"
            elif val.isdigit():
                meta[key] = int(val)
            else:
                try:
                    meta[key] = float(val)
                except ValueError:
                    meta[key] = val
            current_key = key
    return meta, body


def _serialize_yaml_frontmatter(meta):
    """Serialize metadata dict to YAML frontmatter string."""
    lines = ["---"]
    for key in ("type", "importance", "keywords", "related", "created_at"):
        val = meta.get(key)
        if val is None:
            continue
        if isinstance(val, list):
            if val:
                lines.append(f"{key}: [{', '.join(str(v) for v in val)}]")
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines)


def _parse_markdown_sections(body):
    """Parse Markdown body into sections: title, summary, points, keywords."""
    title = ""
    summary = ""
    points = []
    keywords = ""
    current_section = None
    buf = []
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            continue
        if stripped == "## 摘要":
            if current_section == "points":
                points = [l.strip().lstrip("- ").strip() for l in buf if l.strip().startswith("-")]
            elif current_section == "summary":
                summary = "\n".join(buf).strip()
            current_section = "summary"
            buf = []
            continue
        if stripped == "## 要点":
            if current_section == "summary":
                summary = "\n".join(buf).strip()
            current_section = "points"
            buf = []
            continue
        if stripped == "## 关键词":
            if current_section == "points":
                points = [l.strip().lstrip("- ").strip() for l in buf if l.strip().startswith("-")]
            elif current_section == "summary":
                summary = "\n".join(buf).strip()
            current_section = "keywords"
            buf = []
            continue
        buf.append(line)
    # flush remaining
    if current_section == "keywords":
        keywords = "\n".join(buf).strip()
    elif current_section == "points":
        points = [l.strip().lstrip("- ").strip() for l in buf if l.strip().startswith("-")]
    elif current_section == "summary":
        summary = "\n".join(buf).strip()
    return title, summary, points, keywords


def write_entry(soul_folder, entry_data):
    """Write a structured Markdown entry to memory/entries/{date}-{slug}.md.

    entry_data keys: title, type, importance, keywords, related, summary, points
    """
    ensure_layout(soul_folder)
    today = datetime.now().strftime("%Y-%m-%d")
    title = (entry_data.get("title") or "untitled").strip()
    slug = slugify(title)
    filename = f"{today}-{slug}.md"
    base = entries_dir(soul_folder)
    path = os.path.join(base, filename)
    # avoid collision
    if os.path.exists(path):
        filename = f"{today}-{slug}-{uuid.uuid4().hex[:4]}.md"
        path = os.path.join(base, filename)

    meta = {
        "type": entry_data.get("type", "fact"),
        "importance": int(entry_data.get("importance", 3)),
        "keywords": entry_data.get("keywords") or [],
        "related": entry_data.get("related") or [],
        "created_at": today,
    }

    summary = (entry_data.get("summary") or "").strip()
    points = entry_data.get("points") or []
    keywords_str = ", ".join(meta["keywords"])

    body_parts = [f"# {title}", ""]
    body_parts.append("## 摘要")
    body_parts.append(summary)
    body_parts.append("")
    body_parts.append("## 要点")
    for p in points:
        body_parts.append(f"- {p}")
    body_parts.append("")
    body_parts.append("## 关键词")
    body_parts.append(keywords_str)

    content = _serialize_yaml_frontmatter(meta) + "\n\n" + "\n".join(body_parts) + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    slug_name = filename.replace(".md", "")
    return {
        "id": slug_name,
        "file_path": path,
        "filename": filename,
        "meta": meta,
        "title": title,
        "summary": summary,
        "points": points,
        "keywords": keywords_str,
    }


def read_entry(file_path):
    """Read an entry file and return structured data."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    meta, body = _parse_yaml_frontmatter(text)
    title, summary, points, keywords_str = _parse_markdown_sections(body)
    slug_name = os.path.basename(file_path).replace(".md", "")
    return {
        "id": slug_name,
        "file_path": file_path,
        "filename": os.path.basename(file_path),
        "meta": meta,
        "title": title or slug_name,
        "summary": summary,
        "points": points,
        "keywords": keywords_str,
        "type": meta.get("type", "fact"),
        "importance": meta.get("importance", 3),
        "created_at": meta.get("created_at", ""),
        "related": meta.get("related", []),
    }


def list_entries(soul_folder, limit=50):
    """List all entry files, sorted by date descending."""
    base = entries_dir(soul_folder)
    if not os.path.isdir(base):
        return []
    files = []
    for name in os.listdir(base):
        if name.endswith(".md"):
            files.append(os.path.join(base, name))
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    entries = []
    for path in files[:limit]:
        data = read_entry(path)
        if data:
            entries.append(data)
    return entries


def delete_entry(soul_folder, slug):
    """Delete an entry file by slug (filename without .md)."""
    base = entries_dir(soul_folder)
    path = os.path.join(base, f"{slug}.md")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def memory_md_path(soul_folder):
    return os.path.join(soul_folder, "memory.md")


def read_memory_md(soul_folder):
    path = memory_md_path(soul_folder)
    if not os.path.isfile(path):
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            continue
    return ""


def append_memory_md_line(soul_folder, line, cap=None):
    from .constants import MEMORY_MD_CAP

    cap = cap or MEMORY_MD_CAP
    path = memory_md_path(soul_folder)
    existing = read_memory_md(soul_folder)
    line = line.strip()
    if not line:
        return {"ok": False, "msg": "空行"}
    if line in existing:
        return {"ok": True, "msg": "已存在", "skipped": True}
    new_content = (existing.rstrip() + "\n" + line + "\n") if existing.strip() else (line + "\n")
    if len(new_content.encode("utf-8")) > cap:
        return {"ok": False, "msg": f"memory.md 已超过 {cap} 字节上限，跳过自动追加"}
    os.makedirs(soul_folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return {"ok": True, "msg": "已更新 memory.md"}


def append_entry_index_line(soul_folder, line, cap=None):
    """Append an entry index line to memory.md (index format)."""
    from .constants import MEMORY_MD_CAP

    cap = cap or MEMORY_MD_CAP
    path = memory_md_path(soul_folder)
    existing = read_memory_md(soul_folder)
    line = line.strip()
    if not line:
        return {"ok": False, "msg": "空行"}
    if line in existing:
        return {"ok": True, "msg": "已存在", "skipped": True}

    # If memory.md is in old format (no "# 长期记忆索引" header), add header
    if existing.strip() and "# 长期记忆索引" not in existing:
        # Preserve old content as legacy section
        header = "# 长期记忆索引\n\n"
        new_content = header + line + "\n"
    else:
        new_content = (existing.rstrip() + "\n" + line + "\n") if existing.strip() else ("# 长期记忆索引\n\n" + line + "\n")

    if len(new_content.encode("utf-8")) > cap:
        return {"ok": False, "msg": f"memory.md 已超过 {cap} 字节上限，跳过自动追加"}
    os.makedirs(soul_folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return {"ok": True, "msg": "已更新 memory.md"}
