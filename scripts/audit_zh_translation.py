#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "book"
ZH = ROOT / "zh"
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
PLACEHOLDER_RE = re.compile(r"__AFML_KEEP_\d+__")
EXCLUDED_PAGES = {"book-index.html"}
BAD_TEXT_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"Table of contents",
        r"Start Reading",
        r"Search contents",
        r"Previous:",
        r"Next:",
        r"Front Matter",
        r"前置内容",
        r"查看前置内容",
        r"Snippet \d+",
        r"Figure \d+",
        r"Table \d+",
        r"标准普通",
        r"内容 \|金融机器学习的进展",
        r"\(一\)-\(二\)",
        r"光盘",
        r"为索引的交易价格",
        r"U\.S。",
        r"e\.g，",
        r"i\.e，",
        r"等人。",
        r"ML的",
        r"ML算法",
        r"金融ML",
        r"音量时钟",
        r"音量条",
        r"交易柱",
        r"成交量柱",
        r"请参阅",
    )
]


def text_of_math(soup: BeautifulSoup) -> list[str]:
    return [node.get_text("", strip=False) for node in soup.select(".math.inline,.math.display")]


def text_of_code(soup: BeautifulSoup) -> list[str]:
    return [node.get_text("", strip=False) for node in soup.select("figure.code-listing code")]


def article_chinese_ratio(soup: BeautifulSoup) -> float:
    clone = BeautifulSoup(str(soup), "html.parser")
    for node in clone.select("script,style,code,pre,.math.inline,.math.display,.references-list"):
        node.decompose()
    text = clone.get_text(" ", strip=True)
    letters = [ch for ch in text if ch.isalpha() or "\u4e00" <= ch <= "\u9fff"]
    if not letters:
        return 1.0
    return sum(1 for ch in letters if CHINESE_RE.match(ch)) / len(letters)


def main() -> int:
    failures: list[str] = []
    if not ZH.exists():
        failures.append("zh/: translated site directory is missing")
    for excluded_page in EXCLUDED_PAGES:
        if (ZH / excluded_page).exists():
            failures.append(f"zh/{excluded_page} should not exist in the static Chinese site")
    pages = [page for page in sorted(BOOK.glob("*.html")) if page.name not in EXCLUDED_PAGES]
    print("page\tzh_ratio\tmath\tcode\tfigures\timages")
    for page in pages:
        zh_page = ZH / page.name
        if not zh_page.exists():
            failures.append(f"{zh_page.relative_to(ROOT)} missing")
            continue
        src = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        zh = BeautifulSoup(zh_page.read_text(encoding="utf-8"), "html.parser")
        if zh.html is None or zh.html.get("lang") != "zh-CN":
            failures.append(f"{zh_page.name}: html lang is not zh-CN")
        if page.name == "front-matter.html":
            h1 = zh.select_one("article h1")
            article_text = zh.select_one("article").get_text(" ", strip=True) if zh.select_one("article") else ""
            if zh.select_one("body.cover-page") is None:
                failures.append("front-matter.html: cover page body class is missing")
            if h1 is None or h1.get_text(strip=True) != "封面":
                failures.append("front-matter.html: page title should be 封面")
            for dirty_text in ("推荐语", "关于作者", "pdf-page", "CONTENTS"):
                if dirty_text in article_text:
                    failures.append(f"front-matter.html: dirty front-matter text remains: {dirty_text}")
        src_math = text_of_math(src)
        zh_math = text_of_math(zh)
        if src_math != zh_math:
            failures.append(f"{zh_page.name}: MathJax nodes differ from source")
        src_code = text_of_code(src)
        zh_code = text_of_code(zh)
        if src_code != zh_code:
            failures.append(f"{zh_page.name}: code listing text differs from source")
        for selector in ("figure", "figure.code-listing", "figure.book-figure", "figure.table-figure", "table"):
            if len(src.select(selector)) != len(zh.select(selector)):
                failures.append(f"{zh_page.name}: selector count differs for {selector}")
        html = zh_page.read_text(encoding="utf-8")
        for excluded_page in EXCLUDED_PAGES:
            if f'href="{excluded_page}"' in html:
                failures.append(f"{zh_page.name}: links to excluded page {excluded_page}")
        if PLACEHOLDER_RE.search(html):
            failures.append(f"{zh_page.name}: placeholder leaked")
        for pattern in BAD_TEXT_PATTERNS:
            if pattern.search(html):
                failures.append(f"{zh_page.name}: bad text pattern remains: {pattern.pattern}")
                break
        for img in zh.select("img[src]"):
            src_attr = img.get("src", "")
            if src_attr.startswith("media/") and not (ZH / src_attr).exists():
                failures.append(f"{zh_page.name}: missing image {src_attr}")
        ratio = article_chinese_ratio(zh)
        if ratio < 0.35:
            failures.append(f"{zh_page.name}: Chinese ratio too low ({ratio:.3f})")
        print(
            "\t".join(
                [
                    page.name,
                    f"{ratio:.3f}",
                    str(len(zh_math)),
                    str(len(zh_code)),
                    str(len(zh.select("figure"))),
                    str(len(zh.select("img"))),
                ]
            )
        )
    if failures:
        print("\nFailures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
