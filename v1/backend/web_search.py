"""联网检索：供 Function Calling 的 search_web 工具调用。"""
import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

MAX_ITEMS_PER_SEARCH = 8

_CN_WEEK = '一二三四五六日'
_TZ_CN = timezone(timedelta(hours=8))


def get_current_time_context():
    """供 system 注入：模型不得臆造「今天」日期。"""
    now = datetime.now(_TZ_CN)
    wd = _CN_WEEK[now.weekday()]
    return (
        f"## Current time (local, Asia/Shanghai)\n"
        f"- Now: {now.strftime('%Y-%m-%d %H:%M:%S')} weekday {wd}\n"
        f"- ISO date: {now.strftime('%Y-%m-%d')}\n"
        f"For questions about today, latest, or current facts, use the dates above; "
        f"when calling search_web include this date in the query, not stale training dates."
    )


PROVIDER_LABELS = {
    'duckduckgo': 'DuckDuckGo',
    'bing_local': 'Bing 本地',
    'bing': 'Bing 本地',
    'serpapi': 'SerpAPI',
}


def provider_label(provider):
    p = (provider or 'duckduckgo').lower()
    return PROVIDER_LABELS.get(p, p)


@dataclass
class SearchResult:
    query: str
    provider: str
    items: list = field(default_factory=list)
    text_for_model: str = ''
    error: str | None = None

    def result_count(self):
        return len(self.items)

    def to_step_dict(self, step_id, phase='done'):
        return {
            'stepId': step_id,
            'phase': phase,
            'query': self.query,
            'provider': self.provider,
            'status': 'failed' if self.error else ('done' if self.items else 'empty'),
            'resultCount': self.result_count(),
            'items': self.items,
            'error': self.error or '',
            'params': {'query': self.query},
            'textPreview': (self.text_for_model or '')[:2000],
        }


def _make_item(index, title, url='', snippet=''):
    return {
        'index': index,
        'title': (title or '').strip(),
        'url': (url or '').strip(),
        'snippet': (snippet or '').strip(),
    }


def _items_to_lines(items):
    lines = []
    for it in items:
        title = it.get('title') or ''
        snippet = it.get('snippet') or ''
        url = it.get('url') or ''
        if url:
            lines.append(f"- {title}: {snippet} ({url})".strip())
        elif title or snippet:
            lines.append(f"- {title}: {snippet}".strip())
    return lines


def _build_text_for_model(query, used_provider, body_lines, error=None):
    now = datetime.now(_TZ_CN)
    time_hdr = now.strftime('%Y-%m-%d %H:%M') + ' 北京时间'
    header = (
        f"【检索时间】{time_hdr}\n"
        f"【引擎】{provider_label(used_provider)}\n"
        f"【查询】{query}\n\n"
    )
    if error:
        return header + error
    if body_lines:
        return header + '\n'.join(body_lines)
    return header + f'STATUS: empty\n未找到「{query}」的相关结果。'


def summarize_search_result(text_or_result):
    """供前端状态展示：估算命中条数。"""
    if isinstance(text_or_result, SearchResult):
        n = text_or_result.result_count()
        if n:
            return f'{n} 条结果'
        if text_or_result.error:
            return '无有效结果'
        return '无有效结果'
    text = text_or_result
    if not text:
        return '无结果'
    t = str(text)
    if any(x in t for x in ('未找到', '检索失败', 'failed', '错误：', 'STATUS: empty')):
        return '无有效结果'
    hits = len(re.findall(r'^- ', t, re.M))
    if hits:
        return f'{hits} 条结果'
    if len(t) > 80:
        return '有摘要'
    return '无有效结果'


def build_citations(steps):
    """按 URL 去重聚合引用列表。"""
    seen = set()
    citations = []
    for step in steps or []:
        for it in step.get('items') or []:
            url = (it.get('url') or '').strip()
            if not url or url in seen:
                continue
            seen.add(url)
            citations.append({
                'index': len(citations) + 1,
                'title': it.get('title') or url,
                'url': url,
                'snippet': it.get('snippet') or '',
            })
    return citations


def search_web_structured(query, provider='duckduckgo', api_key=''):
    """结构化检索，供 UI 与 tool 双通道使用。"""
    query = (query or '').strip()
    provider = (provider or 'duckduckgo').lower()
    if not query:
        text = 'STATUS: error\n错误：搜索关键词为空'
        return SearchResult(
            query='',
            provider=provider_label(provider),
            items=[],
            text_for_model=text,
            error='搜索关键词为空',
        )

    used_provider = provider
    items = []
    body_lines = None
    error = None

    if _is_weather_query(query):
        body_lines, items = _search_weather_wttr_structured(query)
        used_provider = 'wttr.in'
    if body_lines is None:
        if provider in ('bing_local', 'bing'):
            body_lines, items = _search_bing_local_structured(query)
            if not items:
                fb_lines, fb_items = _search_duckduckgo_structured(query)
                if fb_items:
                    body_lines, items = fb_lines, fb_items
                    used_provider = 'duckduckgo (fallback)'
                elif not body_lines:
                    body_lines, items = fb_lines, fb_items
        elif provider == 'serpapi' and api_key:
            body_lines, items = _search_serpapi_structured(query, api_key)
        else:
            body_lines, items = _search_duckduckgo_structured(query)

    text = _build_text_for_model(query, used_provider, body_lines or [], error)
    return SearchResult(
        query=query,
        provider=provider_label(used_provider),
        items=items[:MAX_ITEMS_PER_SEARCH],
        text_for_model=text,
        error=error,
    )


def search_web(query, provider='duckduckgo', api_key=''):
    """执行网页检索，返回给模型的文本摘要。"""
    return search_web_structured(query, provider, api_key).text_for_model


def _looks_empty(text):
    if not text:
        return True
    markers = ('未找到', '检索失败', 'failed', 'STATUS: empty')
    return any(m in text for m in markers)


def _bing_request_headers():
    return {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }


def _strip_tags(text):
    text = re.sub(r'<[^>]+>', '', text or '')
    return re.sub(r'\s+', ' ', text).strip()


def _search_bing_local_structured(query):
    try:
        items = _parse_bing_html(query)
        if items:
            lines = _items_to_lines(items)
            return ["Web results (Bing local):"] + lines, items
        items = _parse_bing_rss(query)
        if items:
            lines = _items_to_lines(items)
            return ["Web results (Bing RSS):"] + lines, items
    except Exception as e:
        return [f'Bing local search failed: {e}'], []
    return None, []


def _parse_bing_html(query):
    params = urllib.parse.urlencode({
        'q': query,
        'setlang': 'zh-Hans',
        'cc': 'CN',
        'ensearch': '0',
        'count': '10',
        'form': 'QBRE',
    })
    url = f'https://www.bing.com/search?{params}'
    req = urllib.request.Request(url, headers=_bing_request_headers())
    with urllib.request.urlopen(req, timeout=15) as resp:
        page = resp.read().decode('utf-8', errors='replace')

    items = []
    for m in re.finditer(
        r'<li[^>]+class="b_algo"[^>]*>(.*?)</li>',
        page, re.S | re.I
    ):
        block = m.group(1)
        link_m = re.search(
            r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            block, re.S | re.I
        )
        if not link_m:
            continue
        link = link_m.group(1).strip()
        if link.startswith('javascript:'):
            continue
        title = _strip_tags(link_m.group(2))
        snippet_m = re.search(
            r'<div[^>]+class="b_caption"[^>]*>\s*<p[^>]*>(.*?)</p>',
            block, re.S | re.I
        )
        if not snippet_m:
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.S | re.I)
        snippet = _strip_tags(snippet_m.group(1)) if snippet_m else ''
        if title:
            items.append(_make_item(len(items) + 1, title, link, snippet))
        if len(items) >= MAX_ITEMS_PER_SEARCH:
            break
    return items


def _parse_bing_rss(query):
    params = urllib.parse.urlencode({
        'q': query,
        'format': 'rss',
        'setlang': 'zh-Hans',
        'cc': 'CN',
    })
    url = f'https://www.bing.com/search?{params}'
    req = urllib.request.Request(url, headers=_bing_request_headers())
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml = resp.read().decode('utf-8', errors='replace')

    items = []
    for m in re.finditer(r'<item>(.*?)</item>', xml, re.S | re.I):
        block = m.group(1)
        title_m = re.search(r'<title>(.*?)</title>', block, re.S | re.I)
        link_m = re.search(r'<link>(.*?)</link>', block, re.S | re.I)
        desc_m = re.search(r'<description>(.*?)</description>', block, re.S | re.I)
        if not title_m or not link_m:
            continue
        title = html.unescape(_strip_tags(title_m.group(1)))
        link = html.unescape(link_m.group(1).strip())
        snippet = html.unescape(_strip_tags(desc_m.group(1))) if desc_m else ''
        if title:
            items.append(_make_item(len(items) + 1, title, link, snippet))
        if len(items) >= MAX_ITEMS_PER_SEARCH:
            break
    return items


def _is_weather_query(query):
    return bool(re.search(r'天气|气温|温度|降雨|forecast|weather', query, re.I))


def _extract_weather_location(query):
    q = re.sub(r'\d{4}[-年/]\d{1,2}[-月/]\d{1,2}[日号]?', ' ', query)
    q = re.sub(r'\d{1,2}月\d{1,2}日', ' ', q)
    for w in ('今天', '明天', '后天', '现在', '当前', '的', '天气', '气温', '温度',
              '如何', '怎么样', '怎样', '查询', '帮我', '请', '多少度'):
        q = q.replace(w, ' ')
    loc = ' '.join(q.split()).strip()
    return loc or query.strip()


def _search_weather_wttr_structured(query):
    """wttr.in 免费天气（无需 Key）。"""
    loc = _extract_weather_location(query)
    try:
        fmt = '%l: %c, 气温 %t, 湿度 %h, 风速 %w'
        url = (
            'https://wttr.in/'
            + urllib.parse.quote(loc)
            + '?format='
            + urllib.parse.quote(fmt)
            + '&lang=zh'
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'MeClaw/1.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            text = resp.read().decode('utf-8', errors='replace').strip()
        if text and 'Unknown location' not in text:
            items = [_make_item(1, f'{loc} 天气', 'https://wttr.in/' + urllib.parse.quote(loc), text)]
            return [f"天气（wttr.in）:", text], items
    except Exception:
        pass
    return None, []


def _search_duckduckgo_structured(query):
    """Instant Answer + HTML 摘要回退。"""
    instant_lines, instant_items = _search_duckduckgo_instant_structured(query)
    if instant_items or (instant_lines and '未找到' not in '\n'.join(instant_lines)):
        if instant_items:
            return instant_lines, instant_items
    html_lines, html_items = _search_duckduckgo_html_structured(query)
    if html_items:
        return html_lines, html_items
    if instant_lines:
        return instant_lines, instant_items
    return [f'未找到「{query}」的相关结果。'], []


def _search_duckduckgo_html_structured(query):
    """DuckDuckGo Lite HTML 抓取标题摘要（无 Key）。"""
    try:
        data = urllib.parse.urlencode({'q': query}).encode('utf-8')
        req = urllib.request.Request(
            'https://lite.duckduckgo.com/lite/',
            data=data,
            headers={
                'User-Agent': 'MeClaw/1.0',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        items = []
        for m in re.finditer(
            r'<a[^>]+class="result-link"[^>]*>([^<]+)</a>.*?'
            r'<td[^>]+class="result-snippet"[^>]*>([^<]*)',
            html, re.S | re.I
        ):
            title = re.sub(r'\s+', ' ', m.group(1)).strip()
            snippet = re.sub(r'\s+', ' ', m.group(2)).strip()
            if title:
                items.append(_make_item(len(items) + 1, title, '', snippet))
            if len(items) >= MAX_ITEMS_PER_SEARCH:
                break
        if items:
            lines = ["网页摘要（DuckDuckGo）:"] + _items_to_lines(items)
            return lines, items
    except Exception:
        pass
    return None, []


def _search_duckduckgo_instant_structured(query):
    """DuckDuckGo Instant Answer API（stdlib，无需 API Key）。"""
    try:
        params = urllib.parse.urlencode({
            'q': query,
            'format': 'json',
            'no_redirect': '1',
            'no_html': '1',
            'skip_disambig': '1',
        })
        url = f'https://api.duckduckgo.com/?{params}'
        req = urllib.request.Request(url, headers={'User-Agent': 'MeClaw/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        lines = []
        items = []
        if data.get('AbstractText'):
            url = data.get('AbstractURL') or ''
            lines.append(data['AbstractText'])
            if url:
                lines.append(f"来源: {url}")
            items.append(_make_item(1, data.get('Heading') or query, url, data['AbstractText']))
        if data.get('Answer'):
            lines.append(f"直接答案: {data['Answer']}")
            items.append(_make_item(len(items) + 1, '直接答案', '', str(data['Answer'])))

        related = data.get('RelatedTopics') or []
        for item in related[:5]:
            if isinstance(item, dict) and item.get('Text'):
                lines.append(f"- {item['Text']}")
                items.append(_make_item(len(items) + 1, item['Text'], '', item['Text']))

        if lines:
            return lines, items

        return (
            [f'未找到「{query}」的即时摘要。请结合已有知识回答，'
             '并建议用户自行在浏览器核实最新信息。'],
            [],
        )
    except Exception as e:
        return [f'联网检索失败: {e}。请根据已有知识回答并说明可能过时。'], []


def _search_serpapi_structured(query, api_key):
    """SerpAPI（需用户在设置中填写 web_search_api_key）。"""
    try:
        params = urllib.parse.urlencode({
            'q': query,
            'api_key': api_key,
            'engine': 'google',
        })
        url = f'https://serpapi.com/search.json?{params}'
        req = urllib.request.Request(url, headers={'User-Agent': 'MeClaw/1.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        lines = []
        items = []
        if data.get('answer_box'):
            ab = data['answer_box']
            if ab.get('answer'):
                lines.append(str(ab['answer']))
                items.append(_make_item(1, 'Answer box', '', str(ab['answer'])))
            elif ab.get('snippet'):
                lines.append(str(ab['snippet']))
                items.append(_make_item(1, 'Answer box', '', str(ab['snippet'])))
        for item in (data.get('organic_results') or [])[:MAX_ITEMS_PER_SEARCH]:
            title = item.get('title', '')
            snippet = item.get('snippet', '')
            link = item.get('link', '')
            items.append(_make_item(len(items) + 1, title, link, snippet))
            lines.append(f"- {title}: {snippet} ({link})")

        if lines:
            return lines, items
        return _search_duckduckgo_instant_structured(query)
    except Exception as e:
        fb_lines, fb_items = _search_duckduckgo_instant_structured(query)
        return [f'SerpAPI 检索失败: {e}。'] + fb_lines, fb_items


SEARCH_WEB_TOOL = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": (
            "Search the internet for up-to-date information. "
            "Use the current date from the system message in your query. "
            "Use for weather, news, prices, versions, and time-sensitive facts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query including location and today's date from system context",
                }
            },
            "required": ["query"],
        },
    },
}
