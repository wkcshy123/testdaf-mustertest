"""参考素材收集与网页正文抽取。"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

MAX_URLS = 6
MAX_TEXT_CHARS = 6000
MAX_PAGE_CHARS = 4000
REQUEST_TIMEOUT_SECONDS = 12


@dataclass(frozen=True)
class ReferenceMaterialBundle:
    """传给出题生成器的合并素材及可追溯来源。"""

    combined_text: str
    sources: dict


class _HTMLTextExtractor(HTMLParser):
    """轻量 HTML 正文抽取器，避免为网页素材引入重型依赖。"""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._title_parts: list[str] = []
        self._body_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "article", "section"}:
            self._body_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in {"p", "li", "h1", "h2", "h3", "article", "section"}:
            self._body_parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
            return
        if self._skip_depth == 0:
            self._body_parts.append(text)

    @property
    def title(self) -> str:
        return _normalize_space(" ".join(self._title_parts))

    @property
    def body(self) -> str:
        return _normalize_space(" ".join(self._body_parts))


class ReferenceMaterialService:
    """将老师输入的文字和多个网页链接合并为 LLM 可用参考素材。"""

    def build(self, text_material: str, url_material: str) -> ReferenceMaterialBundle:
        text = text_material.strip()
        urls = self._extract_urls(url_material)
        pages = [self._fetch_page(url) for url in urls]

        parts = []
        if text:
            parts.extend(["【老师文字参考素材】", _truncate(text, MAX_TEXT_CHARS), ""])
        for index, page in enumerate(pages, start=1):
            if page["status"] != "ok":
                continue
            parts.extend(
                [
                    f"【网页参考素材 {index}】",
                    f"URL: {page['url']}",
                    f"标题: {page.get('title') or '无标题'}",
                    "正文摘录:",
                    page["text"],
                    "",
                ]
            )

        combined = "\n".join(parts).strip()
        if not combined:
            combined = "无额外参考素材。"

        return ReferenceMaterialBundle(
            combined_text=combined,
            sources={
                "text_material_chars": len(text),
                "url_count": len(urls),
                "urls": urls,
                "pages": pages,
            },
        )

    def _extract_urls(self, url_material: str) -> list[str]:
        candidates = re.split(r"[\s,，]+", url_material.strip())
        urls = []
        for item in candidates:
            if not item:
                continue
            parsed = urlparse(item)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            normalized = item.rstrip(").,，。")
            if normalized not in urls:
                urls.append(normalized)
            if len(urls) >= MAX_URLS:
                break
        return urls

    def _fetch_page(self, url: str) -> dict:
        try:
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT_SECONDS,
                headers={"User-Agent": "TestDaF-Platform/0.1"},
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower() and not response.text.lstrip().startswith("<"):
                return {"url": url, "status": "skipped", "error": f"非 HTML 内容：{content_type}"}

            extractor = _HTMLTextExtractor()
            extractor.feed(response.text)
            text = _truncate(extractor.body, MAX_PAGE_CHARS)
            if not text:
                return {"url": url, "status": "failed", "error": "未抽取到正文文本"}
            return {
                "url": url,
                "status": "ok",
                "title": extractor.title,
                "text": text,
                "text_chars": len(text),
            }
        except Exception as exc:
            return {"url": url, "status": "failed", "error": str(exc)}


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[内容已截断]"
