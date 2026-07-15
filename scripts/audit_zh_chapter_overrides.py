#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import translate_book_zh as translator  # noqa: E402


def expected_units(chapter: str) -> dict[str, str]:
    page = ROOT / "book" / f"{chapter}.html"
    if not page.exists():
        raise FileNotFoundError(page)
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    expected: dict[str, str] = {}
    for node in soup.find_all(string=True):
        if not isinstance(node, NavigableString) or translator.should_skip_text(node):
            continue
        text = str(node)
        expected[translator.stable_key(text)] = text.strip()
    for tag in soup.find_all(True):
        if tag.name in translator.SKIP_ANCESTORS or tag.find_parent(list(translator.SKIP_ANCESTORS)):
            continue
        if tag.find_parent(class_="references-list"):
            continue
        for attr in translator.TRANSLATABLE_ATTRS:
            value = tag.get(attr)
            if (
                isinstance(value, str)
                and value.strip()
                and translator.TEXT_RE.search(value)
                and not translator.URL_RE.match(value.strip())
            ):
                expected[translator.stable_key(value)] = value.strip()
    return expected


def load_override_groups() -> dict[str, list[tuple[Path, dict[str, object]]]]:
    groups: dict[str, list[tuple[Path, dict[str, object]]]] = defaultdict(list)
    directory = ROOT / "translations" / "zh" / "chapters"
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        chapter = data.get("chapter") if isinstance(data, dict) else None
        if not isinstance(chapter, str) or not chapter:
            raise ValueError(f"{path}: missing chapter")
        groups[chapter].append((path, data))
    return groups


def audit_chapter(chapter: str, files: list[tuple[Path, dict[str, object]]]) -> list[str]:
    expected = expected_units(chapter)
    actual: dict[str, tuple[Path, str, str]] = {}
    failures: list[str] = []
    occurrences = 0
    for path, data in files:
        units = data.get("units")
        if not isinstance(units, list):
            failures.append(f"{path}: units must be a list")
            continue
        for index, unit in enumerate(units, start=1):
            occurrences += 1
            if not isinstance(unit, dict):
                failures.append(f"{path}: unit {index} must be an object")
                continue
            key = unit.get("key")
            source = unit.get("source")
            translation = unit.get("translation")
            if not all(isinstance(value, str) and value.strip() for value in (key, source, translation)):
                failures.append(f"{path}: unit {index} has an empty key, source, or translation")
                continue
            expected_key = translator.stable_key(source)
            if key != expected_key:
                failures.append(f"{path}: unit {index} key {key!r} != {expected_key!r}")
            if key in actual:
                previous_path, previous_source, previous_translation = actual[key]
                if source != previous_source or translation != previous_translation:
                    failures.append(f"{path}: conflicting duplicate {key} first seen in {previous_path}")
                else:
                    failures.append(f"{path}: duplicate {key} first seen in {previous_path}")
            else:
                actual[key] = (path, source, translation)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    for key in missing:
        failures.append(f"{chapter}: missing {key} {expected[key]!r}")
    for key in extra:
        failures.append(f"{chapter}: extra {key} {actual[key][1]!r}")
    for key in sorted(set(expected) & set(actual)):
        source = actual[key][1]
        if source.strip() != expected[key]:
            failures.append(f"{chapter}: source mismatch for {key}: {source!r} != {expected[key]!r}")
    status = "PASS" if not failures else "FAIL"
    names = ",".join(path.name for path, _ in files)
    print(
        f"{chapter}\t{status}\tsource={len(expected)}\toverrides={len(actual)}"
        f"\toccurrences={occurrences}\tfiles={names}"
    )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit complete per-chapter Chinese translation override files.")
    parser.add_argument("--chapter", action="append", help="Chapter stem, for example chapter-01. Repeatable.")
    args = parser.parse_args()
    try:
        groups = load_override_groups()
        chapters = args.chapter or sorted(groups)
        failures: list[str] = []
        for chapter in chapters:
            failures.extend(audit_chapter(chapter, groups.get(chapter, [])))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if failures:
        print("\nFailures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
