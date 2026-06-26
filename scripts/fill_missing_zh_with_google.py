#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

import translate_book_zh as zh


ROOT = Path(__file__).resolve().parents[1]
WORD_RE = re.compile(r"[A-Za-z]{3,}")
LOCAL_PHRASES = {
    "Arithmetic mean:": "算术平均：",
    "Geometric mean:": "几何平均：",
    "Harmonic mean:": "调和平均：",
    "Quadratic mean:": "二次平均：",
    "Maximum:": "最大值：",
    "Minimum:": "最小值：",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill missing Chinese translation cache entries with GoogleTranslator fallback.")
    parser.add_argument("--cache-path", default="translations/zh/cache.json")
    parser.add_argument("--pages", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args()

    cache_path = Path(args.cache_path)
    if not cache_path.is_absolute():
        cache_path = ROOT / cache_path
    cache: dict[str, str] = zh.load_json(cache_path, {})
    pages = sorted((ROOT / "book").glob("*.html"))
    if args.pages:
        wanted = set(args.pages)
        pages = [page for page in pages if page.name in wanted or page.stem in wanted]

    units: dict[str, zh.Unit] = {}
    persisted = dict(cache)
    for page in pages:
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for unit in zh.collect_units(soup, cache):
            if unit.key not in persisted:
                units.setdefault(unit.key, unit)
    pending = list(units.values())
    if args.limit:
        pending = pending[: args.limit]
    print(f"pending={len(pending)} cache_entries={len(persisted)}")
    translator = GoogleTranslator(source="en", target="zh-CN")
    for index, unit in enumerate(pending, start=1):
        if unit.text in LOCAL_PHRASES:
            cache[unit.key] = LOCAL_PHRASES[unit.text]
            continue
        masked = zh.mask_protected_tokens(unit.text)
        try:
            translated = translator.translate(masked.text)
        except Exception as exc:
            match = re.match(r"^([^A-Za-z0-9_]*)(.*?)([^A-Za-z0-9_]*)$", masked.text)
            if match and match.group(2) and match.group(2) != masked.text:
                try:
                    translated = match.group(1) + translator.translate(match.group(2)) + match.group(3)
                except Exception:
                    translated = None
            else:
                translated = None
            if translated is not None:
                cache[unit.key] = zh.postprocess(zh.restore_protected_tokens(translated, masked.placeholders))
                continue
            if "\\" in unit.text or "__AFML_KEEP_" in masked.text or not WORD_RE.search(unit.text):
                cache[unit.key] = unit.text
                continue
            print(f"failed {unit.key}: {exc}", file=sys.stderr)
            return 1
        cache[unit.key] = zh.postprocess(zh.restore_protected_tokens(translated, masked.placeholders))
        if index % 10 == 0 or index == len(pending):
            zh.write_json(cache_path, cache)
            print(f"translated {index}/{len(pending)}", flush=True)
        if args.sleep:
            time.sleep(args.sleep)
    zh.write_json(cache_path, cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
