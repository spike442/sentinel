import io
from html.parser import HTMLParser

from pypdf import PdfReader
from stonks.core.http import HttpSource
from stonks.dividends.config.settings import PagesConfig

SKIPPED_TAGS = frozenset({"script", "style", "noscript", "template", "svg"})
BLOCK_TAGS = frozenset(
    {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "table"}
)


class PageTooLarge(ValueError):
    pass


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED_TAGS:
            self.skipping += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS and self.skipping:
            self.skipping -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)

    def text(self) -> str:
        joined = "".join(self.parts)
        lines = [" ".join(line.split()) for line in joined.splitlines()]
        return "\n".join(line for line in lines if line)


def html_text(html: str) -> str:
    extractor = TextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.text()


def pdf_text(content: bytes) -> str:
    stream = io.BytesIO(content)
    reader = PdfReader(stream)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def is_pdf(content_type: str, content: bytes) -> bool:
    return "pdf" in content_type or content.startswith(b"%PDF")


class PageReader:
    def __init__(self, source: HttpSource, pages: PagesConfig):
        self.source = source
        self.pages = pages

    def read(self, url: str) -> str:
        response = self.source.get(url)
        content = response.content
        if len(content) > self.pages.max_bytes:
            raise PageTooLarge(f"page is {len(content)} bytes, above {self.pages.max_bytes}")
        content_type = response.headers.get("content-type", "").casefold()
        if is_pdf(content_type, content):
            return pdf_text(content)
        if "html" in content_type:
            return html_text(response.text)
        return response.text
