#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag


ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "book"
ZH = ROOT / "zh"
ASSETS = ROOT / "assets"
TRANSLATIONS = ROOT / "translations" / "zh"
CACHE_PATH = TRANSLATIONS / "cache.json"
GLOSSARY_PATH = TRANSLATIONS / "glossary.json"
ERROR_PATH = TRANSLATIONS / "last-error.json"
ZH_CSS = ASSETS / "afml-book-zh.css"
ZH_JS = ASSETS / "afml-book-zh.js"

SKIP_ANCESTORS = {
    "script",
    "style",
    "code",
    "pre",
    "svg",
    "mjx-container",
    "math",
}
TRANSLATABLE_ATTRS = ("alt", "title", "placeholder", "aria-label")
TEXT_RE = re.compile(r"[A-Za-z\u4e00-\u9fff]")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
URL_RE = re.compile(r"^(?:https?://|mailto:|doi:|www\.)", re.I)
PLACEHOLDER_RE = re.compile(r"__AFML_KEEP_\d+__")
PROTECT_PATTERNS = [
    re.compile(r"https?://[^\s<>'\"]+"),
    re.compile(r"www\.[^\s<>'\"]+"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\b"),
    re.compile(r"\b[A-Za-z_]\w*=[A-Za-z0-9_.'\"-]+\b"),
    re.compile(r"\b[A-Za-z]+[A-Z][A-Za-z0-9_]*\b"),
    re.compile(r"\b[A-Za-z_]+_[A-Za-z0-9_]+\b"),
    re.compile(r"\b[A-Za-z0-9_.-]+\.(?:py|csv|txt|pdf|html|json|yaml|yml|xml|h5|hdf5|pkl)\b"),
    re.compile(r"\b(?:ISBN|DOI|URL|HTTP|HTTPS|API|CPU|GPU|HPC|MPI|HDF5|FIX|TAQ|ETF|CUSUM|PCA|SVM|RF|MDA|MDI|SFI|CV|CPCV|PBO|PSR|DSR|HRP|CLA|IVP|ADF|SADF|GSADF|CADF|BSADF|PIN|VPIN|TWAP|VWAP|IID|PDF|CDF|OOS|IS|TWRR|HHI|AUM|E-mini|S&P)\b"),
]
KNOWN_UNTRANSLATED = {
    "numpy",
    "pandas",
    "sklearn",
    "scipy",
    "statsmodels",
    "matplotlib",
    "multiprocessing",
    "itertools",
    "joblib",
    "mlfinlab",
    "RandomForestClassifier",
    "BaggingClassifier",
    "getEvents",
    "mpPandasObj",
    "rollGaps",
    "riskDist",
    "riskTarget",
    "matchEnd",
    "matchEnd=False",
    "ptSl",
    "minRet",
    "numThreads",
    "class_weight",
    "True",
    "False",
    "None",
}

UI_MAP = {
    "Contents | Advances in Financial Machine Learning": "目录 | 金融机器学习进阶",
    "Advances in Financial Machine Learning": "金融机器学习进阶",
    "Contents": "目录",
    "Book": "全书",
    "Front Matter": "前置内容",
    "Back Matter": "书后内容",
    "Index": "索引",
    "Start Reading": "开始阅读",
    "Start with Chapter 1": "从第 1 章开始",
    "Open Front Matter": "查看前置内容",
    "Search contents": "搜索目录",
    "Search chapters, parts, topics": "搜索章节、部分或主题",
    "Static web edition": "静态网页版",
    "Chapter pages stay focused on reading; this page provides the full book navigation.": "章节页专注阅读；本页提供全书导航。",
    "Table of contents": "目录",
    "Previous": "上一章",
    "Next": "下一章",
    "Copy": "复制",
    "Copied": "已复制",
    "Open Advances in Financial Machine Learning": "打开《金融机器学习进阶》",
}

TITLE_MAP = {
    "Financial Machine Learning as a Distinct Subject": "金融机器学习作为独立学科",
    "Financial Data Structures": "金融数据结构",
    "Labeling": "标签化",
    "Sample Weights": "样本权重",
    "Fractionally Differentiated Features": "分数阶差分特征",
    "Ensemble Methods": "集成方法",
    "Cross-Validation in Finance": "金融中的交叉验证",
    "Feature Importance": "特征重要性",
    "Hyper-Parameter Tuning with Cross-Validation": "使用交叉验证进行超参数调优",
    "Bet Sizing": "下注规模",
    "The Dangers of Backtesting": "回测的危险",
    "Backtesting through Cross-Validation": "通过交叉验证进行回测",
    "Backtesting on Synthetic Data": "在合成数据上回测",
    "Backtest Statistics": "回测统计",
    "Understanding Strategy Risk": "理解策略风险",
    "Machine Learning Asset Allocation": "机器学习资产配置",
    "Structural Breaks": "结构突变",
    "Entropy Features": "熵特征",
    "Microstructural Features": "微观结构特征",
    "Multiprocessing and Vectorization": "多进程与向量化",
    "Brute Force and Quantum Computers": "穷举法与量子计算机",
    "High-Performance Computational Intelligence and Forecasting Technologies": "高性能计算智能与预测技术",
}


@dataclass(frozen=True)
class Unit:
    key: str
    text: str


@dataclass(frozen=True)
class MaskedUnit:
    key: str
    text: str
    placeholders: dict[str, str]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def stable_key(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    return f"t_{digest}"


def should_skip_text(node: NavigableString) -> bool:
    text = str(node)
    if not text.strip():
        return True
    if not TEXT_RE.search(text):
        return True
    if URL_RE.match(text.strip()):
        return True
    parent = node.parent
    if parent is None:
        return True
    if parent.name == "[document]":
        return True
    if parent.name in SKIP_ANCESTORS:
        return True
    if node.find_parent(list(SKIP_ANCESTORS)):
        return True
    if node.find_parent(class_="math"):
        return True
    if node.find_parent(class_="sourceCode"):
        return True
    if node.find_parent(class_="citation"):
        return True
    if node.find_parent(class_="references-list"):
        return True
    if node.find_parent(class_="panel-label"):
        return True
    if parent.name == "a" and parent.get("href", "").startswith(("http://", "https://", "mailto:")):
        return True
    return False


def normalize_caption_label(text: str) -> str:
    text = re.sub(r"\bFigure\s+(\d+\.\d+)\s*:", r"图 \1：", text)
    text = re.sub(r"\bTable\s+(\d+\.\d+)\s*:", r"表 \1：", text)
    text = re.sub(r"\bSnippet\s+(\d+\.\d+)\s*:", r"代码清单 \1：", text)
    text = re.sub(r"代码片段\s+(\d+\.\d+)\s*[：:]", r"代码清单 \1：", text)
    text = re.sub(r"代码段\s+(\d+\.\d+)\s*[：:]", r"代码清单 \1：", text)
    return text


def normalize_ui_text(text: str) -> str | None:
    stripped = text.strip()
    if stripped in UI_MAP:
        return text.replace(stripped, UI_MAP[stripped])
    match = re.fullmatch(r"(\d+)\s+sections?", stripped)
    if match:
        return text.replace(stripped, f"{match.group(1)} 节")
    match = re.fullmatch(r"Previous:\s+(.+)", stripped)
    if match:
        return text.replace(stripped, f"上一章：{match.group(1)}")
    match = re.fullmatch(r"Next:\s+(.+)", stripped)
    if match:
        return text.replace(stripped, f"下一章：{match.group(1)}")
    return None


def postprocess(text: str) -> str:
    text = normalize_caption_label(text)
    for src, dst in sorted(TITLE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(src, dst)
    text = text.replace("内容 |金融机器学习的进展", "目录 | 金融机器学习进阶")
    text = text.replace("金融机器学习的进展", "金融机器学习进阶")
    text = text.replace("标准普通", "标准正态")
    text = text.replace("。 There are at least two uses of this result.", "。这一结果至少有两个用途。")
    text = text.replace(
        "。 For example, Figure 18.1 plots the bootstrapped distributions of entropy estimates under 10, 7, 5, and 2 letter encodings, on messages of length 100, using Kontoyiannis' method.",
        "。例如，图 18.1 绘制了使用 Kontoyiannis 方法时，在长度为 100 的消息上，采用 10、7、5 和 2 字母编码得到的熵估计 bootstrap 分布。",
    )
    text = text.replace("为索引的交易价格，且", "，且")
    text = text.replace("U.S。", "美国")
    text = text.replace("e.g，例如", "例如，")
    text = text.replace("e.g，即", "例如，")
    text = text.replace("e.g，如", "例如，")
    text = text.replace("e.g，", "例如，")
    text = text.replace("i.e，即", "即，")
    text = text.replace("i.e.，", "即，")
    text = text.replace("i.e，", "即，")
    text = text.replace("ML的", "ML 的")
    text = text.replace("ML算法", "ML 算法")
    text = text.replace("ML领域", "ML 领域")
    text = text.replace("金融ML", "金融 ML")
    text = text.replace("SVMs等", "SVMs 等")
    text = text.replace("RFs等", "RFs 等")
    text = text.replace("音量时钟", "成交量时钟")
    text = text.replace("音量条", "成交量条")
    text = text.replace("交易柱", "交易笔数 bar")
    text = text.replace("成交量柱", "成交量 bar")
    text = text.replace("请参阅", "参见")
    text = text.replace("等人。", "等人")
    text = text.replace(" :", "：")
    text = text.replace(" ,", "，")
    text = text.replace(" .", "。")
    text = text.replace(" ;", "；")
    return text


def mask_protected_tokens(text: str) -> MaskedUnit:
    placeholders: dict[str, str] = {}

    def replace_span(value: str) -> str:
        if value in placeholders.values():
            for key, existing in placeholders.items():
                if existing == value:
                    return key
        key = f"__AFML_KEEP_{len(placeholders)}__"
        placeholders[key] = value
        return key

    spans: list[tuple[int, int]] = []

    def add_span(start: int, end: int) -> None:
        if start == end:
            return
        for s, e in spans:
            if start < e and end > s:
                return
        spans.append((start, end))

    for token in sorted(KNOWN_UNTRANSLATED, key=len, reverse=True):
        for match in re.finditer(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", text):
            add_span(match.start(), match.end())
    for pattern in PROTECT_PATTERNS:
        for match in pattern.finditer(text):
            add_span(match.start(), match.end())
    spans.sort()
    if not spans:
        return MaskedUnit(stable_key(text), text, placeholders)
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(text[cursor:start])
        parts.append(replace_span(text[start:end]))
        cursor = end
    parts.append(text[cursor:])
    return MaskedUnit(stable_key(text), "".join(parts), placeholders)


def restore_protected_tokens(text: str, placeholders: dict[str, str]) -> str:
    for key, value in sorted(placeholders.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(key, value)
    return text


def collect_units(soup: BeautifulSoup, cache: dict[str, str]) -> list[Unit]:
    units: dict[str, Unit] = {}
    for node in soup.find_all(string=True):
        if not isinstance(node, NavigableString) or should_skip_text(node):
            continue
        text = str(node)
        replacement = normalize_ui_text(text)
        if replacement is not None:
            key = stable_key(text)
            cache.setdefault(key, postprocess(replacement))
            continue
        stripped = text.strip()
        if stripped in UI_MAP:
            continue
        key = stable_key(text)
        if key not in cache and key not in units:
            units[key] = Unit(key, stripped)
    for tag in soup.find_all(True):
        if tag.name in SKIP_ANCESTORS or tag.find_parent(list(SKIP_ANCESTORS)):
            continue
        if tag.find_parent(class_="references-list"):
            continue
        for attr in TRANSLATABLE_ATTRS:
            value = tag.get(attr)
            if not isinstance(value, str) or not value.strip() or not TEXT_RE.search(value) or URL_RE.match(value.strip()):
                continue
            replacement = normalize_ui_text(value)
            key = stable_key(value)
            if replacement is not None:
                cache.setdefault(key, postprocess(replacement))
            elif key not in cache and key not in units:
                units[key] = Unit(key, value.strip())
    return list(units.values())


def glossary_prompt(glossary: dict[str, Any]) -> str:
    terms = glossary.get("terms", {})
    selected = "\n".join(f"- {src} => {dst}" for src, dst in sorted(terms.items())[:120])
    rules = "\n".join(f"- {rule}" for rule in glossary.get("rules", []))
    return f"Rules:\n{rules}\n\nGlossary:\n{selected}"


def parse_claude_outer(output: str) -> str:
    outer = json.loads(output)
    result = outer.get("result", output) if isinstance(outer, dict) else output
    return str(result)


def parse_tsv_translations(text: str, units: list[Unit]) -> dict[str, str]:
    text = text.strip()
    text = re.sub(r"^```(?:tsv|text)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    valid_ids = {unit.key for unit in units}
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "\t" not in line:
            continue
        key, value = line.split("\t", 1)
        key = key.strip()
        if key in valid_ids:
            out[key] = value.strip()
    return out


def translate_batch(units: list[Unit], glossary: dict[str, Any], model: str, budget: float, timeout: int) -> dict[str, str]:
    masked = [mask_protected_tokens(unit.text) for unit in units]
    payload = [{"id": unit.key, "text": masked_unit.text} for unit, masked_unit in zip(units, masked, strict=True)]
    prompt = f"""You are translating a technical finance book into professional Simplified Chinese.
Return plain text only. Do not use Markdown fences. Do not return JSON.
Return exactly one line per input item in this format:
id<TAB>Chinese translation
Translate the text naturally and fluently for mainland Chinese quant finance readers.
Preserve all placeholders like __AFML_KEEP_0__, package names, function names, variable names, filenames, URLs, citations, acronyms, TeX-like fragments, and code/API identifiers.
Use full-width Chinese punctuation for Chinese prose. Keep English proper names and abbreviations where the glossary says to keep them.
Do not add explanations. Do not omit any id. Do not wrap translations in quotes.

{glossary_prompt(glossary)}

Input JSON:
{json.dumps(payload, ensure_ascii=False)}
"""
    command = [
        "claude",
        "-p",
        "--model",
        model,
        "--permission-mode",
        "dontAsk",
        "--tools",
        "",
        "--output-format",
        "json",
        "--max-budget-usd",
        f"{budget:.2f}",
    ]
    result = subprocess.run(command, input=prompt, text=True, capture_output=True, cwd=ROOT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"claude failed with {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    try:
        result_text = parse_claude_outer(result.stdout)
    except Exception as exc:
        write_json(
            ERROR_PATH,
            {
                "error": repr(exc),
                "stdout": result.stdout,
                "stderr": result.stderr,
                "units": payload,
            },
        )
        raise
    parsed_lines = parse_tsv_translations(result_text, units)
    out: dict[str, str] = {}
    mask_by_key = {unit.key: masked_unit.placeholders for unit, masked_unit in zip(units, masked, strict=True)}
    for key, value in parsed_lines.items():
        out[key] = postprocess(restore_protected_tokens(value, mask_by_key.get(key, {})))
    missing = [unit.key for unit in units if unit.key not in out]
    if missing:
        if len(units) > 1:
            retry_units = [unit for unit in units if unit.key in missing]
            retry = translate_batch(retry_units, glossary, model, budget, timeout)
            out.update(retry)
            missing = [unit.key for unit in units if unit.key not in out]
        if not missing:
            return out
        write_json(
            ERROR_PATH,
            {
                "error": f"translation missing ids: {missing[:10]}",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "result_text": result_text,
                "units": payload,
                "parsed": parsed_lines,
            },
        )
        raise RuntimeError(f"translation missing ids: {missing[:10]}")
    return out


def chunk_units(units: list[Unit], max_chars: int) -> list[list[Unit]]:
    chunks: list[list[Unit]] = []
    current: list[Unit] = []
    current_chars = 0
    for unit in units:
        size = len(unit.text) + 30
        if current and current_chars + size > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(unit)
        current_chars += size
    if current:
        chunks.append(current)
    return chunks


def apply_cache_to_soup(soup: BeautifulSoup, cache: dict[str, str]) -> None:
    if soup.html:
        soup.html["lang"] = "zh-CN"
    title = soup.find("title")
    if title and title.string:
        title.string.replace_with(postprocess(cache.get(stable_key(str(title.string)), str(title.string)).replace(" | Advances in Financial Machine Learning", " | 金融机器学习进阶")))
    for node in list(soup.find_all(string=True)):
        if not isinstance(node, NavigableString) or should_skip_text(node):
            continue
        text = str(node)
        key = stable_key(text)
        replacement = cache.get(key)
        if replacement is None:
            replacement = normalize_ui_text(text)
        if replacement is not None:
            prefix = text[: len(text) - len(text.lstrip())]
            suffix = text[len(text.rstrip()) :]
            node.replace_with(NavigableString(prefix + postprocess(replacement.strip()) + suffix))
    for tag in soup.find_all(True):
        if tag.name in SKIP_ANCESTORS or tag.find_parent(list(SKIP_ANCESTORS)) or tag.find_parent(class_="references-list"):
            continue
        for attr in TRANSLATABLE_ATTRS:
            value = tag.get(attr)
            if not isinstance(value, str) or not value.strip() or URL_RE.match(value.strip()):
                continue
            replacement = cache.get(stable_key(value)) or normalize_ui_text(value)
            if replacement is not None:
                tag[attr] = postprocess(replacement)
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href and "afml-book.css" in href:
            zh_link = soup.new_tag("link", rel="stylesheet", href=href.replace("afml-book.css", "afml-book-zh.css"))
            link.insert_after(zh_link)
    for script in soup.find_all("script", src=True):
        src = script.get("src", "")
        if "afml-book.js" in src:
            script["src"] = src.replace("afml-book.js", "afml-book-zh.js")
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if src.startswith("media/"):
            img["src"] = src
    for node in soup.find_all(string=True):
        if isinstance(node, NavigableString) and PLACEHOLDER_RE.search(str(node)):
            node.replace_with(NavigableString(PLACEHOLDER_RE.sub("", str(node))))


def finalize_html(html: str, page_name: str) -> str:
    if page_name == "chapter-18.html":
        replacements = {
            "从而使 <span class=\"math inline\">\\(|r_t|\\)</span> 并减少对大字母表的需求。": "从而使 <span class=\"math inline\">\\(|r_t|\\)</span> 的分布更加规则，并减少对大字母表的需求。",
            "有些编码覆盖 <span class=\"math inline\">\\(r_t\\)</span>的范围比其他人大。": "有些编码覆盖 <span class=\"math inline\">\\(r_t\\)</span> 取值范围的比例大于其他编码。",
            "每个代码覆盖相同的部分 <span class=\"math inline\">\\(r_t\\)</span>的范围。": "每个编码都覆盖 <span class=\"math inline\">\\(r_t\\)</span> 取值范围中相同长度的区间。",
            "这表明，熵可以解释为 <span class=\"math inline\">\\(p\\)</span>，其中 <span class=\"math inline\">\\(q\\to1\\)</span>。": "这表明，熵可以解释为列表 <span class=\"math inline\">\\(p\\)</span> 中有效项目数的对数，其中 <span class=\"math inline\">\\(q\\to1\\)</span>。",
            "还要注意，当 <span class=\"math inline\">\\(q\\)</span> 变大。": "还要注意，当 <span class=\"math inline\">\\(q\\)</span> 变大时，它们的行为也会趋于稳定。",
            "如果 <span class=\"math inline\">\\(p_i=1/k\\)</span> 为了 <span class=\"math inline\">\\(k\\in[1,n]\\)</span> 个不同索引，且 <span class=\"math inline\">\\(p_i=0\\)</span> 在其他位置，则权重均匀分布在 <span class=\"math inline\">\\(k\\)</span> 个不同项目上，且 <span class=\"math inline\">\\(N_q[p]=k\\)</span> 为了 <span class=\"math inline\">\\(q&gt;1\\)</span>。": "如果 <span class=\"math inline\">\\(p_i=1/k\\)</span> 对 <span class=\"math inline\">\\(k\\in[1,n]\\)</span> 个不同索引成立，且其他位置满足 <span class=\"math inline\">\\(p_i=0\\)</span>，则权重均匀分布在 <span class=\"math inline\">\\(k\\)</span> 个不同项目上，并且 <span class=\"math inline\">\\(N_q[p]=k\\)</span> 在 <span class=\"math inline\">\\(q&gt;1\\)</span> 时成立。",
            "在规模为 <span class=\"math inline\">\\(V\\)</span>，我们可以根据某种算法将价格变动分类为买入或卖出，例如价格变动规则或 Lee-Ready 算法。": "在规模为 <span class=\"math inline\">\\(V\\)</span> 的成交量 bar 内，我们可以根据某种算法将 tick 分类为买方主动或卖方主动，例如 tick rule 或 Lee-Ready 算法。",
            "我们可以设置的值 <span class=\"math inline\">\\(\\mathbb{E}[V_\\tau^B+V_\\tau^S]=\\alpha\\mu+2\\varepsilon=V\\)</span> 外生设定。": "我们可以将 <span class=\"math inline\">\\(\\mathbb{E}[V_\\tau^B+V_\\tau^S]=\\alpha\\mu+2\\varepsilon=V\\)</span> 的值外生设定。",
            "给定一系列以 <span class=\"math inline\">\\(\\tau=1,\\ldots,N\\)</span>，每个条形的大小 <span class=\"math inline\">\\(V\\)</span>，我们确定归类为买入的交易量部分，": "给定一系列以 <span class=\"math inline\">\\(\\tau=1,\\ldots,N\\)</span> 为索引、每个 bar 大小为 <span class=\"math inline\">\\(V\\)</span> 的成交量 bar，我们确定归类为买方主动成交量的比例，",
            "第二，计算 <span class=\"math inline\">\\(q\\)</span>- 分位数 <span class=\"math inline\">\\(\\{v_\\tau^B\\}\\)</span> 定义一个集合 <span class=\"math inline\">\\(K\\)</span> 中的元素 <span class=\"math inline\">\\(q\\)</span> 不相交的子集，": "第二，计算 <span class=\"math inline\">\\(q\\)</span> 个分位点来划分 <span class=\"math inline\">\\(\\{v_\\tau^B\\}\\)</span>，用它们定义集合 <span class=\"math inline\">\\(K\\)</span> 中的 <span class=\"math inline\">\\(q\\)</span> 个互不相交子集，",
            "第四，将 <span class=\"math inline\">\\(\\{v_\\tau^B\\}\\)</span> 通过分配给每个值 <span class=\"math inline\">\\(v_\\tau^B\\)</span> 子集的索引 <span class=\"math inline\">\\(K\\)</span> 它属于， <span class=\"math inline\">\\(f[v_\\tau^B]\\)</span>。这会导致订单不平衡集的转换 <span class=\"math inline\">\\(\\{v_\\tau^B\\}\\)</span> 转化为量化的消息": "第四，对 <span class=\"math inline\">\\(\\{v_\\tau^B\\}\\)</span> 进行量化：为每个 <span class=\"math inline\">\\(v_\\tau^B\\)</span> 分配其所属子集 <span class=\"math inline\">\\(K\\)</span> 的索引，即 <span class=\"math inline\">\\(f[v_\\tau^B]\\)</span>。这会把订单流不平衡集合 <span class=\"math inline\">\\(\\{v_\\tau^B\\}\\)</span> 转换为量化消息",
            "第五，我们估计熵 <span class=\"math inline\">\\(H[X]\\)</span> 使用 Kontoyiannis 的 Lempel-Ziv 算法。": "第五，使用 Kontoyiannis 的 Lempel-Ziv 算法估计熵 <span class=\"math inline\">\\(H[X]\\)</span>。",
        }
        for src, dst in replacements.items():
            html = html.replace(src, dst)
    return html


def write_zh_assets() -> None:
    ZH_CSS.write_text(
        """html[lang="zh-CN"] body {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", "Segoe UI", sans-serif;
  line-height: 1.78;
}
html[lang="zh-CN"] article {
  max-width: 52rem;
}
html[lang="zh-CN"] .contents-home article {
  max-width: 74rem;
}
html[lang="zh-CN"] p,
html[lang="zh-CN"] li {
  line-height: 1.78;
}
html[lang="zh-CN"] h1,
html[lang="zh-CN"] h2,
html[lang="zh-CN"] h3,
html[lang="zh-CN"] h4 {
  line-height: 1.28;
}
html[lang="zh-CN"] .chapter-pager {
  flex-wrap: wrap;
}
html[lang="zh-CN"] .chapter-pager a {
  min-width: 0;
  overflow-wrap: anywhere;
}
html[lang="zh-CN"] .book-figure figcaption,
html[lang="zh-CN"] figure.table-figure figcaption {
  line-height: 1.55;
}
html[lang="zh-CN"] figure.code-listing,
html[lang="zh-CN"] div.sourceCode,
html[lang="zh-CN"] pre.sourceCode {
  width: 100%;
  max-width: 100%;
}
@media (max-width: 760px) {
  html[lang="zh-CN"] .chapter-pager {
    display: grid;
  }
}
""",
        encoding="utf-8",
    )
    source = (ASSETS / "afml-book.js").read_text(encoding="utf-8")
    source = source.replace('"Copied"', '"已复制"').replace('"Copy"', '"复制"')
    ZH_JS.write_text(source, encoding="utf-8")


def translate_pages(args: argparse.Namespace) -> None:
    glossary = load_json(GLOSSARY_PATH, {})
    cache_path = Path(args.cache_path) if args.cache_path else CACHE_PATH
    if not cache_path.is_absolute():
        cache_path = ROOT / cache_path
    cache: dict[str, str] = load_json(cache_path, {})
    pages = sorted(BOOK.glob("*.html"))
    if args.pages:
        wanted = set(args.pages)
        pages = [page for page in pages if page.name in wanted or page.stem in wanted]
    if args.limit_pages:
        pages = pages[: args.limit_pages]

    all_units: dict[str, Unit] = {}
    soups: dict[Path, BeautifulSoup] = {}
    for page in pages:
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        soups[page] = soup
        for unit in collect_units(soup, cache):
            all_units.setdefault(unit.key, unit)

    pending = list(all_units.values())
    if args.limit_units:
        pending = pending[: args.limit_units]
    chunks = chunk_units(pending, args.max_chars)
    print(f"pages={len(pages)} pending_units={len(pending)} chunks={len(chunks)} cache_entries={len(cache)}")
    if args.dry_run:
        return

    for index, chunk in enumerate(chunks, start=1):
        print(f"translating chunk {index}/{len(chunks)} units={len(chunk)} chars={sum(len(u.text) for u in chunk)}", flush=True)
        translated = translate_batch(chunk, glossary, args.model, args.budget_per_call, args.timeout)
        cache.update(translated)
        write_json(cache_path, cache)

    if args.translate_only:
        return

    if ZH.exists() and not args.pages:
        shutil.rmtree(ZH)
    ZH.mkdir(parents=True, exist_ok=True)
    media_src = BOOK / "media"
    media_dst = ZH / "media"
    if media_src.exists() and (not media_dst.exists() or not args.pages):
        if media_dst.exists():
            shutil.rmtree(media_dst)
        shutil.copytree(media_src, media_dst)

    write_zh_assets()
    for page, soup in soups.items():
        apply_cache_to_soup(soup, cache)
        (ZH / page.name).write_text(finalize_html(str(soup), page.name), encoding="utf-8")

    (ROOT / "index.html").write_text(
        """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="0; url=zh/index.html">
    <title>金融机器学习进阶</title>
  </head>
  <body>
    <p><a href="zh/index.html">打开《金融机器学习进阶》</a></p>
  </body>
</html>
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate generated AFML HTML pages into a Simplified Chinese static site.")
    parser.add_argument("--pages", nargs="*", help="Specific page names or stems to translate.")
    parser.add_argument("--limit-pages", type=int)
    parser.add_argument("--limit-units", type=int)
    parser.add_argument("--max-chars", type=int, default=1500)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--budget-per-call", type=float, default=0.60)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cache-path", help="Translation cache path. Defaults to translations/zh/cache.json.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--translate-only", action="store_true")
    args = parser.parse_args()
    translate_pages(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
