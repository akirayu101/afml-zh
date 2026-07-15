#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import struct
import sys
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "book"
ZH = ROOT / "zh"
EXCLUDED_PAGES: set[str] = set()
STRIP_SELECTORS = (
    "script",
    "style",
    "code",
    "pre",
    ".math.inline",
    ".math.display",
    ".references-list",
    ".book-topbar",
    ".chapter-pager",
)
VISIBLE_BAD_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\bU\.S\.?",
        r"\bU\.K\b",
        r"\bSnippet\s+\d+\.\d+",
        r"\bFigure\s+\d+\.\d+",
        r"\bTable\s+\d+\.\d+",
        r"代码片段\s*\d+\.\d+",
        r"代码段\s*\d+\.\d+",
        r"(?<!代)片段\s*\d+\.\d+",
        r"图\d+\.\d+",
        r"表\d+\.\d+",
        r"[\u4e00-\u9fff]:",
        r"……的",
        r"随……",
        r"关于…",
        r"为…",
        r"构成……",
        r"作为……",
        r"确定……",
        r"阶数为……",
        r"的中位数重合时\s+\S+",
        r"Volume/Dollar Runs Bars",
        r"均值精度下降",
        r"精度率",
        r"隐含精度",
        r"分数微分",
        r"分数（而不是整数）微分",
        r"包含一些内存",
        r"基于返回",
        r"10 TB 条",
        r"APIs",
        r"CPUs",
        r"GPUs",
        r"交易量条",
        r"e\.g[。、，]",
        r"买入报价的交易量",
        r"卖出价格变动的成交量",
        r"多线程、multiprocessing",
        r"multiprocessing 架构",
        r"TuW，TuW",
        r"作为\.\.\.的函数",
        r"ADF统计量",
        r"关于d的函数",
        r"\d+折CV",
        r"Markowitz诅咒",
        r"IVP的",
        r"\d+个原子任务",
        r"HPC计算机",
        r"HPC系统",
        r"非均匀FFT",
        r"具有强烈存在",
        r"图 13\.\d+：参数",
        r"LTAP\.\(a\)",
        r"结果\.\(b\)",
        r"梯度树提升（GTB）似乎",
    )
]
HTML_ARTIFACT_PATTERNS = [
    re.compile(pattern, re.S)
    for pattern in (
        r"的均值，\s*<span class=\"math inline\"",
        r">\s*的均值，\s*<span class=\"math inline\"",
        r"</code>\s*的均值，\s*<code>",
        r"关于…",
        r"为…",
        r"……的",
        r"随……",
        r"作为\.\.\.的函数",
    )
]
CAPTION_BAD_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\.\.\.",
        r"TuW，TuW",
        r"ADF统计量",
        r"关于d的函数",
        r"\d+折CV",
        r"Markowitz诅咒",
        r"IVP的",
        r"\d+个原子任务",
        r"HPC计算机",
        r"HPC系统",
        r"非均匀FFT",
        r"具有强烈存在",
        r"^图 13\.\d+：参数",
        r"LTAP\.\(a\)",
        r"结果\.\(b\)",
        r"梯度树提升（GTB）似乎",
    )
]
VERTICAL_SUBFIGURE_RE = re.compile(
    r"\btop\b.*\bbottom\b|\bbottom\b.*\btop\b|上.*下|下.*上",
    re.I,
)
VERTICAL_SUBFIGURE_MAX_ASPECT = 0.85
EDGE_STRIP_DARK_RATIO = 0.95
EDGE_STRIP_CENTER_DARK_RATIO = 0.5


def read_soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def visible_text(soup: BeautifulSoup) -> str:
    clone = BeautifulSoup(str(soup), "html.parser")
    for selector in STRIP_SELECTORS:
        for node in clone.select(selector):
            node.decompose()
    return clone.get_text(" ", strip=True)


def img_srcs(soup: BeautifulSoup) -> list[str]:
    return [img.get("src", "") for img in soup.select("img[src]")]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if not data.startswith(b"\xff\xd8"):
        return None
    i = 2
    sof_markers = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            return None
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9):
            continue
        if i + 2 > len(data):
            return None
        segment_length = int.from_bytes(data[i : i + 2], "big")
        if segment_length < 2:
            return None
        if marker in sof_markers:
            if i + 7 > len(data):
                return None
            height = int.from_bytes(data[i + 3 : i + 5], "big")
            width = int.from_bytes(data[i + 5 : i + 7], "big")
            return width, height
        i += segment_length
    return None


def dark_pixel_ratio(path: Path, box: tuple[int, int, int, int]) -> float | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    image = Image.open(path).convert("RGB")
    crop = image.crop(box)
    data = crop.tobytes()
    if not data:
        return 0.0
    dark_pixels = 0
    for index in range(0, len(data), 3):
        if max(data[index], data[index + 1], data[index + 2]) < 25:
            dark_pixels += 1
    return dark_pixels / (len(data) // 3)


def has_dark_crop_strip(path: Path) -> bool:
    dimensions = image_dimensions(path)
    if dimensions is None:
        return False
    width, height = dimensions
    if width < 80 or height < 80:
        return False
    right = dark_pixel_ratio(path, (int(width * 0.96), 0, width, height))
    bottom = dark_pixel_ratio(path, (0, int(height * 0.96), width, height))
    center = dark_pixel_ratio(path, (int(width * 0.25), int(height * 0.25), int(width * 0.75), int(height * 0.75)))
    if right is None or bottom is None or center is None:
        return False
    if center > EDGE_STRIP_CENTER_DARK_RATIO:
        return False
    return right > EDGE_STRIP_DARK_RATIO or bottom > EDGE_STRIP_DARK_RATIO


def check_captions(page_name: str, soup: BeautifulSoup, failures: list[str]) -> None:
    for figure in soup.select("figure"):
        caption = figure.select_one("figcaption")
        if caption is None:
            continue
        text = caption.get_text(" ", strip=True)
        if "code-listing" in figure.get("class", []):
            if not re.match(r"^代码清单 \d+\.\d+：", text):
                failures.append(f"{page_name}: code caption is not normalized: {text[:80]}")
        elif "cpcv-figure" in figure.get("class", []):
            if not re.match(r"^图 \d+\.\d+：", text):
                failures.append(f"{page_name}: cpcv figure caption is not normalized: {text[:80]}")
        elif "table-figure" in figure.get("class", []):
            if not re.match(r"^表 \d+\.\d+：", text):
                failures.append(f"{page_name}: table caption is not normalized: {text[:80]}")
        elif "book-figure" in figure.get("class", []):
            if not re.match(r"^图 \d+\.\d+：", text):
                failures.append(f"{page_name}: figure caption is not normalized: {text[:80]}")
        for pattern in CAPTION_BAD_PATTERNS:
            match = pattern.search(text)
            if match:
                failures.append(f"{page_name}: figure/table caption has bad pattern {pattern.pattern}: {text[:120]}")
                break


def check_vertical_subfigures(page_name: str, soup: BeautifulSoup, root: Path, failures: list[str]) -> None:
    for figure in soup.select("figure.book-figure"):
        caption = figure.select_one("figcaption")
        if caption is None:
            continue
        text = caption.get_text(" ", strip=True)
        if not VERTICAL_SUBFIGURE_RE.search(text):
            continue
        image = figure.select_one("img[src]")
        if image is None:
            failures.append(f"{page_name}: top/bottom figure has no image: {text[:80]}")
            continue
        src = image.get("src", "")
        if not src.startswith("media/"):
            continue
        path = root / src
        if not path.exists():
            continue
        dimensions = image_dimensions(path)
        if dimensions is None:
            failures.append(f"{page_name}: cannot inspect dimensions for top/bottom figure {src}")
            continue
        width, height = dimensions
        if height and width / height > VERTICAL_SUBFIGURE_MAX_ASPECT:
            failures.append(
                f"{page_name}: caption says top/bottom but image is not vertically composed: {src} {width}x{height}"
            )


def check_images(page_name: str, source: BeautifulSoup, zh: BeautifulSoup, failures: list[str]) -> None:
    src_images = img_srcs(source)
    zh_images = img_srcs(zh)
    if page_name != "front-matter.html" and src_images != zh_images:
        failures.append(f"{page_name}: image src list differs from source")
    if page_name == "front-matter.html" and not zh_images:
        failures.append("front-matter.html: cover image is missing")
    for src in zh_images:
        if not src.startswith("media/"):
            continue
        zh_path = ZH / src
        src_path = BOOK / src
        if not zh_path.exists():
            failures.append(f"{page_name}: missing zh image {src}")
        elif src_path.exists() and digest(zh_path) != digest(src_path):
            failures.append(f"{page_name}: image bytes differ for {src}")
        if src_path.exists() and has_dark_crop_strip(src_path):
            failures.append(f"{page_name}: image appears to contain a dark crop strip: {src}")


def main() -> int:
    failures: list[str] = []
    pages = [page for page in sorted(BOOK.glob("*.html")) if page.name not in EXCLUDED_PAGES]
    print("page\tvisible_chars\tfigures\timages")
    for source_page in pages:
        zh_page = ZH / source_page.name
        if not zh_page.exists():
            failures.append(f"{zh_page.relative_to(ROOT)} missing")
            continue
        source = read_soup(source_page)
        zh = read_soup(zh_page)
        text = visible_text(zh)
        html = zh_page.read_text(encoding="utf-8")
        for pattern in VISIBLE_BAD_PATTERNS:
            match = pattern.search(text)
            if match:
                failures.append(f"{zh_page.name}: visible bad pattern {pattern.pattern}: {match.group(0)}")
                break
        for pattern in HTML_ARTIFACT_PATTERNS:
            match = pattern.search(html)
            if match:
                failures.append(f"{zh_page.name}: html translation artifact {pattern.pattern}")
                break
        check_captions(zh_page.name, zh, failures)
        check_vertical_subfigures(f"{source_page.name} source", source, BOOK, failures)
        check_vertical_subfigures(zh_page.name, zh, ZH, failures)
        check_images(zh_page.name, source, zh, failures)
        if zh.select("article > p.footnote"):
            failures.append(f"{zh_page.name}: inline footnote paragraphs remain in article flow")
        if zh_page.name == "chapter-01.html":
            html = zh_page.read_text(encoding="utf-8")
            if "将50位主观型PMs聚集在一起，他们</p>" in html:
                failures.append("chapter-01.html: discretionary PM paragraph remains split")
        print("\t".join([zh_page.name, str(len(text)), str(len(zh.select("figure"))), str(len(zh.select("img")))]))
    if failures:
        print("\nFailures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
