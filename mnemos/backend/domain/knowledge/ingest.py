"""Knowledge import orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .extractor import extract_knowledge
from .fetch import fetch_url
from .indexer import index_note
from .paths import KnowledgePaths, ensure_knowledge_layout
from .store import add_source, get_note, new_id, write_note, write_raw


def _raw_markdown(title: str, body: str, *, url: str = "", source_type: str = "text") -> str:
    header = [
        f"# {title or '未命名来源'}",
        "",
        f"- type: {source_type}",
    ]
    if url:
        header.append(f"- url: {url}")
    header.extend(["", "---", ""])
    return "\n".join(header) + body.strip() + "\n"


class KnowledgeIngestService:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self.paths = ensure_knowledge_layout(data_root)

    def import_payload(
        self,
        *,
        import_type: str,
        content: str,
        profile: dict,
        title_hint: str = "",
    ) -> dict[str, Any]:
        import_type = (import_type or "text").strip().lower()
        content = (content or "").strip()
        if not content:
            raise ValueError("导入内容不能为空")

        if import_type == "url":
            fetched = fetch_url(content)
            if fetched.get("ok"):
                raw_body = fetched["text"]
                title = fetched.get("title") or content
                source = add_source(
                    self.paths,
                    source_type="url",
                    title=title,
                    raw_path="",
                    url=content,
                    status="ok",
                )
            else:
                raw_body = f"URL: {content}\n\n抓取失败: {fetched.get('error', '未知错误')}"
                title = content
                source = add_source(
                    self.paths,
                    source_type="url",
                    title=title,
                    raw_path="",
                    url=content,
                    status="error",
                    error=fetched.get("error") or "抓取失败",
                )
            raw_rel = f"knowledge/raw/{source['id']}.md"
            write_raw(
                self.paths,
                source["id"],
                _raw_markdown(title, raw_body, url=content, source_type="url"),
            )
            source["raw_path"] = raw_rel
            from .store import load_sources, save_sources

            sources = load_sources(self.paths)
            for i, s in enumerate(sources):
                if s.get("id") == source["id"]:
                    sources[i] = source
                    break
            save_sources(self.paths, sources)
            extract_input = raw_body if fetched.get("ok") else raw_body
        elif import_type == "markdown":
            title = title_hint or "Markdown 资料"
            source = add_source(
                self.paths,
                source_type="markdown",
                title=title,
                raw_path="",
                status="ok",
            )
            write_raw(self.paths, source["id"], content if content.startswith("#") else _raw_markdown(title, content))
            source["raw_path"] = f"knowledge/raw/{source['id']}.md"
            from .store import load_sources, save_sources

            sources = load_sources(self.paths)
            for i, s in enumerate(sources):
                if s.get("id") == source["id"]:
                    sources[i] = source
                    break
            save_sources(self.paths, sources)
            extract_input = content
            title_hint = title_hint or title
        else:
            title = title_hint or "文本资料"
            source = add_source(
                self.paths,
                source_type="text",
                title=title,
                raw_path="",
                status="ok",
            )
            write_raw(self.paths, source["id"], _raw_markdown(title, content, source_type="text"))
            source["raw_path"] = f"knowledge/raw/{source['id']}.md"
            from .store import load_sources, save_sources

            sources = load_sources(self.paths)
            for i, s in enumerate(sources):
                if s.get("id") == source["id"]:
                    sources[i] = source
                    break
            save_sources(self.paths, sources)
            extract_input = content
            title_hint = title

        extracted = extract_knowledge(profile, extract_input, title_hint=title_hint or source.get("title", ""))
        note_id = new_id("note")
        write_note(
            self.paths,
            note_id=note_id,
            title=str(extracted.get("title") or source.get("title") or "未命名"),
            category=str(extracted.get("category") or "未分类"),
            tags=[str(x) for x in (extracted.get("tags") or [])][:8],
            source_id=source["id"],
            source_url=source.get("url") or "",
            summary=str(extracted.get("summary") or ""),
            key_points=[str(x) for x in (extracted.get("key_points") or [])][:10],
            related_terms=[str(x) for x in (extracted.get("related_terms") or [])][:12],
        )
        note = get_note(self.paths, note_id)
        if note:
            index_note(self.paths, note)
        return {"source": source, "note": note, "extracted": extracted}
