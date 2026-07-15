#!/usr/bin/env python3
from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "book"
CSS = ROOT / "assets" / "afml-book.css"
JS = ROOT / "assets" / "afml-book.js"

PROSE_PREFIXES = (
    "Suppose that I =",
    "This concludes",
    "It is worth",
    "A vectorized solution",
    "Solving for",
)
BAD_REFERENCE_RE = re.compile(
    r"pp\.\s*\d+\s*[–-]\s*$|PART |CHAPTER |"
    r"(Data Analysis|Modelling|Backtesting|Useful Financial Features|High-Performance Computing Recipes) Chapter \d+"
)
BAD_CODE_GLYPH_RE = re.compile(r"[–—−’‘“”]")
BAD_TEX_RE = re.compile(
    r"\\p_i|\\Deltapt|\\Deltamt|\\varepsilont|sqr_t|log\^2|"
    r"\\sqrt\{\}|\\hat\{\}|\\tilde\{\}|\\sum[A-Za-z0-9]|\\prod[A-Za-z0-9]|\\Lambda[a-zA-Z]"
)
RAW_TEX_DELIMITERS = (r"\(", r"\)", r"\[", r"\]")


def max_blank_run(text: str) -> int:
    max_run = 0
    run = 0
    for line in text.splitlines():
        if line.strip():
            run = 0
        else:
            run += 1
            max_run = max(max_run, run)
    return max_run


def next_element_sibling(node):
    sibling = node.find_next_sibling()
    while sibling is not None and getattr(sibling, "name", None) is None:
        sibling = sibling.find_next_sibling()
    return sibling


def table_row_width(row) -> int:
    total = 0
    for cell in row.select("th,td"):
        try:
            total += int(cell.get("colspan", "1"))
        except ValueError:
            total += 1
    return total


def main() -> int:
    failures: list[str] = []
    rows: list[tuple[str, int, int, int, int, int, int, int, int, int, int]] = []
    ids_by_file: dict[Path, set[str]] = {}

    if not CSS.exists():
        failures.append("assets/afml-book.css: generated stylesheet is missing")
    else:
        css = CSS.read_text(encoding="utf-8")
        if ':root[data-theme="light"]' not in css:
            failures.append("assets/afml-book.css: light theme variable block is missing")
        if ".theme-toggle" not in css:
            failures.append("assets/afml-book.css: theme toggle style is missing")
        for expected in (
            ".codex-selection-button",
            ".codex-selection-dialog",
            ".codex-selection-question",
            ".codex-selection-command",
            ".selection-note-highlight",
        ):
            if expected not in css:
                failures.append(f"assets/afml-book.css: selection note style missing `{expected}`")
        caption_block = re.search(r"\.book-figure figcaption,\s*figure\.table-figure figcaption\s*\{(?P<body>[^}]*)\}", css)
        if caption_block is None:
            failures.append("assets/afml-book.css: figure/table caption style block is missing")
        else:
            caption_css = caption_block.group("body")
            for expected in (
                "font-size: .82rem;",
                "line-height: 1.4;",
                "color: var(--muted);",
                "text-align: left;",
                "padding-top: .55rem;",
                "border-top: 1px solid var(--line);",
                "max-width: 52rem;",
                "overflow-wrap: anywhere;",
            ):
                if expected not in caption_css:
                    failures.append(f"assets/afml-book.css: figure/table caption style missing `{expected}`")
        caption_math_block = re.search(
            r"\.book-figure figcaption mjx-container,\s*figure\.table-figure figcaption mjx-container\s*\{(?P<body>[^}]*)\}",
            css,
        )
        if caption_math_block is None or "font-size: 100% !important;" not in caption_math_block.group("body"):
            failures.append("assets/afml-book.css: caption MathJax size inheritance is missing")
        code_caption_block = re.search(r"figure\.code-listing figcaption\s*\{(?P<body>[^}]*)\}", css)
        if code_caption_block is None:
            failures.append("assets/afml-book.css: code-listing caption style block is missing")
        elif "font-weight: 600;" not in code_caption_block.group("body"):
            failures.append("assets/afml-book.css: code-listing captions should remain stronger than figure captions")
        code_frame_block = re.search(r"div\.sourceCode\s*\{(?P<body>[^}]*)\}", css)
        if code_frame_block is None:
            failures.append("assets/afml-book.css: sourceCode frame style block is missing")
        else:
            code_frame_css = code_frame_block.group("body")
            for expected in ("overflow-x: auto;", "max-width: 100%;", "box-sizing: border-box;"):
                if expected not in code_frame_css:
                    failures.append(f"assets/afml-book.css: sourceCode frame style missing `{expected}`")
        code_listing_block = re.search(r"figure\.code-listing\s*\{(?P<body>[^}]*)\}", css)
        if code_listing_block is None:
            failures.append("assets/afml-book.css: code-listing layout block is missing")
        else:
            code_listing_css = code_listing_block.group("body")
            for expected in ("width: 100%;", "max-width: 100%;", "overflow-x: hidden;"):
                if expected not in code_listing_css:
                    failures.append(f"assets/afml-book.css: code-listing layout style missing `{expected}`")
        references_block = re.search(r"\.references-list\s*\{(?P<body>[^}]*)\}", css)
        if references_block is None:
            failures.append("assets/afml-book.css: references-list style block is missing")
        elif "list-style: none;" not in references_block.group("body"):
            failures.append("assets/afml-book.css: references-list should suppress browser bullets")
        reference_item_block = re.search(r"\.references-list li\s*\{(?P<body>[^}]*)\}", css)
        if reference_item_block is None:
            failures.append("assets/afml-book.css: references-list item style block is missing")
        else:
            reference_item_css = reference_item_block.group("body")
            for expected in ("font-size: .88rem;", "text-indent: -1.5rem;", "padding-left: 1.5rem;", "overflow-wrap: anywhere;"):
                if expected not in reference_item_css:
                    failures.append(f"assets/afml-book.css: reference item style missing `{expected}`")
        table_wrap_block = re.search(r"\.table-wrap\s*\{(?P<body>[^}]*)\}", css)
        if table_wrap_block is None:
            failures.append("assets/afml-book.css: table-wrap style block is missing")
        else:
            table_wrap_css = table_wrap_block.group("body")
            for expected in ("overflow-x: auto;", "border: 1px solid var(--code-line);"):
                if expected not in table_wrap_css:
                    failures.append(f"assets/afml-book.css: table-wrap style missing `{expected}`")
        semantic_table_block = re.search(r"\.semantic-table ul\s*\{(?P<body>[^}]*)\}", css)
        if semantic_table_block is None:
            failures.append("assets/afml-book.css: semantic table list style block is missing")
    if not JS.exists():
        failures.append("assets/afml-book.js: generated script is missing")
    else:
        js = JS.read_text(encoding="utf-8")
        for expected in ('THEME_STORAGE_KEY = "afml-theme"', "installThemeToggle", 'button.className = "theme-toggle"'):
            if expected not in js:
                failures.append(f"assets/afml-book.js: theme toggle logic missing `{expected}`")
        for expected in (
            'SELECTION_NOTES_STORAGE_KEY = "afml-selection-notes"',
            "installSelectionNotes",
            "selectionNotesToMarkdown",
            "refreshSelectionNoteHighlights",
            "applySelectionNoteHighlight",
            "openDialogForStoredNote",
            "highlighted: isZh",
            "selectionNoteRecord",
            "pendingSelectionData",
            "flushPendingSelectionNoteSave",
            "SELECTION_DIALOG_OPEN_EVENT",
            "announceSelectionDialogOpen",
            'button.className = "codex-selection-button selection-note-button"',
            'panel.className = "codex-selection-dialog selection-note-dialog"',
            'note.className = "codex-selection-question selection-note-textarea"',
            'highlight.className = "selection-note-highlight"',
        ):
            if expected not in js:
                failures.append(f"assets/afml-book.js: selection note logic missing `{expected}`")
        for disabled in ('DOMContentLoaded", installReaderNotes', "installReaderNotes();"):
            if disabled in js:
                failures.append(f"assets/afml-book.js: chapter-wide notes should not auto-install `{disabled}`")
        if "if (!dialog.panel.hidden) return;" in js:
            failures.append("assets/afml-book.js: selection buttons should still refresh while dialogs are open")
        for expected in (
            "installCodexSelectionPrompt",
            "codex://new?",
            "CODEX_SELECTION_LIMIT",
            "CODEX_APP_PROJECT_PATH",
            "codexAppEnabled",
            "isGithubPagesHost",
            "data-codex-selection",
            '!event.shiftKey && !event.isComposing',
            "buildCodexPrompt",
        ):
            if expected not in js:
                failures.append(f"assets/afml-book.js: Codex selection logic missing `{expected}`")

    for path in sorted(BOOK.glob("*.html")):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        ids_by_file[path.resolve()] = {tag.get("id") for tag in soup.select("[id]") if tag.get("id")}

    contents_path = BOOK / "index.html"
    front_matter_path = BOOK / "front-matter.html"
    if not contents_path.exists():
        failures.append("book/index.html: contents page is missing")
    else:
        contents_soup = BeautifulSoup(contents_path.read_text(encoding="utf-8"), "html.parser")
        if not contents_soup.select_one(".contents-home"):
            failures.append("book/index.html: web contents landing page is missing")
        if not contents_soup.select_one(".book-toc-panel .book-toc-list"):
            failures.append("book/index.html: book-style table of contents panel is missing")
        if contents_soup.select_one(".toc-card"):
            failures.append("book/index.html: old card-grid contents layout returned")
        toc_entries = contents_soup.select("[data-toc-entry]")
        if len(toc_entries) != 24:
            failures.append(f"book/index.html: expected 24 contents entries, found {len(toc_entries)}")
        toc_chapters = contents_soup.select(".toc-chapter")
        if len(toc_chapters) != 24:
            failures.append(f"book/index.html: expected 24 book-toc chapter rows, found {len(toc_chapters)}")
        details = contents_soup.select(".toc-chapter details.toc-details")
        if len(details) < 22:
            failures.append(f"book/index.html: expected chapter section details, found {len(details)}")
        for href in ("front-matter.html", "chapter-01.html", "book-index.html"):
            if not contents_soup.select_one(f'a[href="{href}"]'):
                failures.append(f"book/index.html: contents link missing: {href}")
        section_links = contents_soup.select(".toc-sections a[href*='#sec-']")
        if len(section_links) < 120:
            failures.append(f"book/index.html: expected rich section-level contents links, found {len(section_links)}")
        for href in ("chapter-02.html#sec-2-3", "chapter-20.html#sec-20-3", "chapter-22.html#sec-22-6"):
            if not contents_soup.select_one(f'a[href="{href}"]'):
                failures.append(f"book/index.html: section contents link missing: {href}")
    if not front_matter_path.exists():
        failures.append("book/front-matter.html: front matter page is missing")

    for path in sorted(BOOK.glob("*.html")):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        ids = [tag.get("id") for tag in soup.select("[id]") if tag.get("id")]
        headings = [h.get_text(" ", strip=True).upper() for h in soup.select("h1,h2,h3,h4")]

        duplicate_ids = len(ids) - len(set(ids))
        table_pre = len(soup.select("figure.table-figure pre"))
        reference_paragraph_nodes = soup.select(".references-heading ~ p")
        if path.name == "chapter-04.html":
            reference_paragraph_nodes = [
                p
                for p in reference_paragraph_nodes
                if not p.get_text(" ", strip=True).startswith("Sample weighting is a common topic")
            ]
        reference_paragraphs = len(reference_paragraph_nodes)
        exercise_headings = headings.count("EXERCISES")
        non_code_figures = soup.select("figure:not(.code-listing):not(.quote-snippet)")
        images = soup.select("img")

        if duplicate_ids:
            failures.append(f"{path.name}: duplicate ids={duplicate_ids}")
        if table_pre:
            failures.append(f"{path.name}: table fallback <pre>={table_pre}")
        if reference_paragraphs:
            failures.append(f"{path.name}: paragraphs after references heading={reference_paragraphs}")
        if exercise_headings:
            failures.append(f"{path.name}: exercise headings remain={exercise_headings}")
        if soup.select(".formula"):
            failures.append(f"{path.name}: legacy formula fallback remains={len(soup.select('.formula'))}")
        for math_node in soup.select(".math.inline,.math.display"):
            if not math_node.get_text("", strip=True):
                failures.append(f"{path.name}: empty MathJax node")
        for text_node in soup.find_all(string=True):
            if text_node.find_parent(class_="math") or text_node.find_parent(["script", "style", "code"]):
                continue
            if any(token in str(text_node) for token in RAW_TEX_DELIMITERS):
                failures.append(f"{path.name}: raw TeX delimiter outside MathJax span: {str(text_node).strip()[:120]}")
                break

        for image in images:
            src = image.get("src", "")
            if not src:
                failures.append(f"{path.name}: image without src")
                continue
            if not src.startswith(("http://", "https://", "data:")) and not (path.parent / src).exists():
                failures.append(f"{path.name}: image source missing: {src}")
            alt = image.get("alt")
            if alt is None or not alt.strip():
                failures.append(f"{path.name}: image alt text missing: {src}")

        for figure in non_code_figures:
            has_media = bool(figure.select_one("img,svg,canvas,table"))
            if not has_media:
                caption_text = figure.get_text(" ", strip=True)[:120]
                failures.append(f"{path.name}: non-code figure missing media: {caption_text}")
            if "book-cover" in (figure.get("class") or []):
                if not figure.select_one("img"):
                    failures.append(f"{path.name}: book cover figure has no image")
                if figure.select_one("figcaption"):
                    failures.append(f"{path.name}: book cover should not use a figure caption")
                continue
            caption = figure.select_one("figcaption")
            if has_media and caption is None and "book-figure" in (figure.get("class") or []):
                src = figure.select_one("img").get("src", "") if figure.select_one("img") else ""
                failures.append(f"{path.name}: book figure image missing figcaption: {src}")
            if caption and not caption.get_text(" ", strip=True):
                failures.append(f"{path.name}: empty figure/table caption")
            if caption:
                for text_node in caption.find_all(string=True):
                    if text_node.find_parent(class_="math"):
                        continue
                    if any(token in str(text_node) for token in RAW_TEX_DELIMITERS):
                        failures.append(f"{path.name}: raw TeX delimiter outside MathJax caption span: {caption.get_text(' ', strip=True)[:120]}")
                        break

        for fig in soup.select("figure.table-figure"):
            caption = fig.select_one("figcaption")
            label = caption.get_text(" ", strip=True) if caption else "unknown table"
            if caption is None or not caption.get_text(" ", strip=True):
                failures.append(f"{path.name}: table figure without non-empty figcaption")
            if fig.select_one(".table-wrap") is None:
                failures.append(f"{path.name}: {label}: table figure missing table-wrap")
            table = fig.select_one("table")
            if table is None:
                failures.append(f"{path.name}: {label}: table figure missing table element")
                continue
            if table.find("pre"):
                failures.append(f"{path.name}: {label}: table contains pre fallback")
            table_rows = table.select("tr")
            if len(table_rows) < 2:
                failures.append(f"{path.name}: {label}: table has fewer than two rows")
            if not table.select_one("thead") or not table.select_one("tbody"):
                failures.append(f"{path.name}: {label}: table should have thead and tbody")
            row_widths = [table_row_width(row) for row in table_rows]
            if len(set(row_widths)) > 1:
                failures.append(f"{path.name}: {label}: inconsistent table row widths {row_widths[:12]}")
            if not table.select("th"):
                failures.append(f"{path.name}: {label}: table has no header cells")
            for cell in table.select("th,td"):
                text = cell.get_text(" ", strip=True)
                if text in {"r", "•", "◦"}:
                    failures.append(f"{path.name}: {label}: table cell has PDF bullet artifact `{text}`")

        for fig in soup.select("figure.code-listing"):
            caption = fig.select_one("figcaption")
            code_el = fig.select_one("code")
            label = caption.get_text(" ", strip=True) if caption else "unknown snippet"
            if caption is None or not caption.get_text(" ", strip=True):
                failures.append(f"{path.name}: code listing without non-empty figcaption")
            if len(fig.select("button.copy-code")) != 1:
                failures.append(f"{path.name}: {label}: code listing should have exactly one copy button")
            if fig.select_one("div.sourceCode") is None:
                failures.append(f"{path.name}: {label}: code listing missing sourceCode frame")
            if fig.select_one("pre.sourceCode") is None:
                failures.append(f"{path.name}: {label}: code listing missing sourceCode pre")
            if code_el is None:
                failures.append(f"{path.name}: code listing without code element")
                continue
            code = code_el.get_text()
            if "sourceCode" not in (code_el.get("class") or []):
                failures.append(f"{path.name}: {label}: code element missing sourceCode class")
            if not code.strip():
                failures.append(f"{path.name}: {label}: empty code listing")
            blank_run = max_blank_run(code)
            if blank_run > 2:
                failures.append(f"{path.name}: {label}: extraction blank run {blank_run}")
            is_python = "python" in (code_el.get("class") or [])
            if is_python:
                try:
                    list(tokenize.generate_tokens(io.StringIO(code).readline))
                except Exception as exc:  # noqa: BLE001 - audit script reports exact parser failure
                    failures.append(f"{path.name}: {label}: {type(exc).__name__}: {exc}")
                for line_no, line in enumerate(code.splitlines(), 1):
                    if BAD_CODE_GLYPH_RE.search(line):
                        failures.append(f"{path.name}: {label}: non-ASCII code glyph on line {line_no}")
                    if line.strip().startswith(PROSE_PREFIXES):
                        failures.append(f"{path.name}: {label}: prose leaked into code on line {line_no}")

        for heading in soup.select(".references-heading"):
            next_sibling = next_element_sibling(heading)
            if next_sibling is None:
                failures.append(f"{path.name}: references heading has no following content: {heading.get_text(' ', strip=True)}")
            elif next_sibling.name == "p":
                paragraph = next_sibling.get_text(" ", strip=True)
                if not (path.name == "chapter-04.html" and paragraph.startswith("Sample weighting is a common topic")):
                    failures.append(f"{path.name}: references heading followed by paragraph instead of list: {paragraph[:120]}")
            elif next_sibling.name != "ul" or "references-list" not in (next_sibling.get("class") or []):
                failures.append(f"{path.name}: references heading not followed by references-list: {heading.get_text(' ', strip=True)}")

        for item in soup.select(".references-list li"):
            text = item.get_text(" ", strip=True)
            if not text:
                failures.append(f"{path.name}: empty reference list item")
            if BAD_REFERENCE_RE.search(text):
                failures.append(f"{path.name}: suspicious reference tail: {text[:160]}")

        for node in soup.select(".math.display,.math.inline"):
            text = node.get_text(" ", strip=True)
            if BAD_TEX_RE.search(text):
                failures.append(f"{path.name}: suspicious TeX conversion: {text[:160]}")

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not href or href.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target, _, anchor = href.partition("#")
            if ":" in target:
                continue
            target_path = (path.parent / (target or path.name)).resolve()
            if target_path not in ids_by_file:
                failures.append(f"{path.name}: local link target missing: {href}")
            elif anchor and anchor not in ids_by_file[target_path]:
                failures.append(f"{path.name}: local link anchor missing: {href}")

        rows.append(
            (
                path.name,
                len(soup.select("figure.code-listing")),
                len(soup.select("ul.references-list")),
                len(soup.select("ul.references-list li")),
                len(non_code_figures),
                len(images),
                reference_paragraphs,
                duplicate_ids,
                table_pre,
                exercise_headings,
                len(soup.select(".formula")),
            )
        )

    print("file\tcode\tref_lists\tref_items\tfigures\timages\tref_p\tdup_ids\ttable_pre\tex_head\tformula_fallback")
    for row in rows:
        print("\t".join(str(value) for value in row))

    if failures:
        print("\nFailures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
