import re

_DOC_INTENT_KEYWORDS = (
    "风格", "写法", "语气", "参考", "那篇", "那篇文章", "喜欢", "收藏",
    "像上次", "像我", "文风", "仿照", "模仿", "之前那", "写过",
)


def wants_doc_retrieval(query):
    """Phase 1: keyword rules for long-document chunk retrieval."""
    text = (query or "").strip().lower()
    if not text:
        return False
    for kw in _DOC_INTENT_KEYWORDS:
        if kw in text:
            return True
    if re.search(r"按.{0,8}(风格|写法|语气)", text):
        return True
    return False
