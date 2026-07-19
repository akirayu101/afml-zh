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

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "book"
ZH = ROOT / "zh"
ASSETS = ROOT / "assets"
TRANSLATIONS = ROOT / "translations" / "zh"
CACHE_PATH = TRANSLATIONS / "cache.json"
GLOSSARY_PATH = TRANSLATIONS / "glossary.json"
ERROR_PATH = TRANSLATIONS / "last-error.json"
CHAPTER_OVERRIDES = TRANSLATIONS / "chapters"
ZH_CSS = ASSETS / "afml-book-zh.css"
ZH_JS = ASSETS / "afml-book-zh.js"
EXCLUDED_PAGES: set[str] = set()
ZH_FIGURE_CAPTION_HTML = {
    "14.1": "图 14.1：回撤（DD）与水下时间（TuW）示例",
    "14.2": "图 14.2：PSR 作为偏度和样本长度的函数",
    "14.3": '图 14.3：<span class="math inline">\\(SR^*\\)</span> 作为 <span class="math inline">\\(\\mathbb{V}[\\{\\widehat{SR}_n\\}]\\)</span> 和 <span class="math inline">\\(N\\)</span> 的函数',
    "15.2": '图 15.2：隐含命中率关于 <span class="math inline">\\(n\\)</span> 和 <span class="math inline">\\(\\pi_-\\)</span> 的热力图，其中 <span class="math inline">\\(\\pi_+=0.1\\)</span> 且 <span class="math inline">\\(\\theta^*=1.5\\)</span>',
    "15.3": '图 15.3：隐含下注频率关于 <span class="math inline">\\(p\\)</span> 和 <span class="math inline">\\(\\pi_-\\)</span> 的函数，其中 <span class="math inline">\\(\\pi_+=0.1\\)</span> 且 <span class="math inline">\\(\\theta^*=1.5\\)</span>',
    "16.1": "图 16.1：马科维茨诅咒示意图",
    "16.5": "图 16.5：聚类形成的树状图",
    "16.7": "图 16.7：（a）IVP、（b）HRP、（c）CLA 的权重时间序列",
    "17.3": '图 17.3：（a）<span class="math inline">\\((SADF_t-C_{t,q})/\\dot C_{t,q}\\)</span> 随时间变化；（b）<span class="math inline">\\((SADF_t-C_{t,q})/\\dot C_{t,q}\\)</span>（纵轴）随 <span class="math inline">\\(SADF_t\\)</span>（横轴）变化',
    "20.1": "图 20.1：将 20 个原子任务线性划分为 6 个分子任务",
    "22.1": "图 22.1：Magellan 集群示意图（约 2010 年），HPC 计算集群示例",
    "22.2": "图 22.2：云平台运行科学计算应用的速度明显慢于 HPC 系统（约 2010 年）",
    "22.6": "图 22.6：梯度树提升（GTB）过度拟合近期用电数据，因此无法像新开发的 LTAP 方法那样预测基线用电量。（a）GTB 对照组；（b）LTAP 对照组；（c）GTB 被动组；（d）LTAP 被动组；（e）GTB 主动组；（f）LTAP 主动组",
    "22.10": "图 22.10：2012 年天然气期货合约交易价格的傅里叶频谱。非均匀 FFT 识别出显著的日频（频率 = 366）、半日频（频率 = 732）和分钟频（频率 = 527040 = 366×24×60）活动。",
}

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
    "Front Matter": "封面",
    "Back Matter": "书后内容",
    "Index": "索引",
    "Start Reading": "开始阅读",
    "Start with Chapter 1": "从第 1 章开始",
    "Open Front Matter": "查看封面",
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
    "Overlapping Outcomes": "结果重叠",
    "Number Of Concurrent Labels": "同期标签数量",
    "Dollar Bars": "成交额 bar",
    "Tick Runs Bars": "Tick 连续同向流 bar",
    "Volume/Dollar Imbalance Bars": "成交量／成交额不平衡 bar",
    "Volume/Dollar Runs Bars": "成交量／成交额连续同向流 bar",
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


def load_chapter_overrides(
    path: Path = CHAPTER_OVERRIDES,
    chapters: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Load human-reviewed chapter translations on top of the legacy cache.

    Each file keeps the English source beside its translation so reviewers can
    compare a chapter without reverse-mapping opaque cache hashes.  The source
    text is also checked against its stable key to catch stale or mistyped
    entries before a page is generated.
    """
    overrides: dict[str, dict[str, str]] = {}
    if not path.exists():
        return overrides
    for override_path in sorted(path.glob("*.json")):
        data = load_json(override_path, {})
        chapter = data.get("chapter") if isinstance(data, dict) else None
        if not isinstance(chapter, str) or not chapter.strip():
            raise ValueError(f"{override_path}: missing chapter")
        chapter = Path(chapter.strip()).stem
        if chapters is not None and chapter not in chapters:
            continue
        chapter_overrides = overrides.setdefault(chapter, {})
        units = data.get("units", []) if isinstance(data, dict) else []
        if not isinstance(units, list):
            raise ValueError(f"{override_path}: units must be a list")
        for index, unit in enumerate(units, start=1):
            if not isinstance(unit, dict):
                raise ValueError(f"{override_path}: unit {index} must be an object")
            key = unit.get("key")
            source = unit.get("source")
            translation = unit.get("translation")
            if not all(isinstance(value, str) and value.strip() for value in (key, source, translation)):
                raise ValueError(f"{override_path}: unit {index} has an empty key, source, or translation")
            expected_key = stable_key(source)
            if key != expected_key:
                raise ValueError(f"{override_path}: unit {index} key {key!r} does not match {expected_key!r}")
            previous = chapter_overrides.get(key)
            if previous is not None and previous != translation:
                raise ValueError(f"{override_path}: conflicting translation for {key}")
            chapter_overrides[key] = postprocess(translation)
    return overrides


def stable_key(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    return f"t_{digest}"


def should_skip_text(node: NavigableString) -> bool:
    if isinstance(node, Comment):
        return True
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
    text = re.sub(r"\bFigure\s+(\d+\.\d+)", r"图 \1", text)
    text = re.sub(r"\bTable\s+(\d+\.\d+)", r"表 \1", text)
    text = re.sub(r"\bSnippet\s+(\d+\.\d+)", r"代码清单 \1", text)
    text = re.sub(r"代码片段\s*(\d+\.\d+)\s*[：:]", r"代码清单 \1：", text)
    text = re.sub(r"代码段\s*(\d+\.\d+)\s*[：:]", r"代码清单 \1：", text)
    text = re.sub(r"片段\s*(\d+\.\d+)\s*[：:]", r"代码清单 \1：", text)
    text = re.sub(r"代码片段\s*(\d+\.\d+)", r"代码清单 \1", text)
    text = re.sub(r"代码段\s*(\d+\.\d+)", r"代码清单 \1", text)
    text = re.sub(r"(?<!代)片段\s*(\d+\.\d+)", r"代码清单 \1", text)
    text = re.sub(r"图\s*(\d+\.\d+)", r"图 \1", text)
    text = re.sub(r"表\s*(\d+\.\d+)", r"表 \1", text)
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
    text = text.replace("均值精度下降（MDA）", "平均准确率下降（MDA）")
    text = text.replace("均值精度下降", "平均准确率下降（MDA）")
    text = text.replace("分数（而不是整数）微分序列", "分数阶（而非整数阶）差分序列")
    text = text.replace("分数微分", "分数阶差分")
    text = text.replace("包含一些内存", "保留一定记忆性")
    text = text.replace("基于返回的编码方案", "基于收益率的编码方案")
    text = text.replace("10 TB 条", "10 TB 数据")
    text = text.replace("APIs", "API")
    text = text.replace("CPUs", "CPU")
    text = text.replace("GPUs", "GPU")
    text = text.replace("精度率", "精确率")
    text = text.replace("隐含精度", "隐含精确率")
    text = text.replace("交易量条", "成交量条")
    text = text.replace("水下时间（TuW，TuW）", "水下时间（TuW）")
    text = text.replace("ADF统计量", "ADF 统计量")
    text = text.replace("关于d的函数", "关于 d 的函数")
    text = text.replace("基于E-mini", "基于 E-mini")
    text = text.replace("E-mini期货", "E-mini 期货")
    text = text.replace("ETF trick", "ETF trick")
    text = text.replace("图5.5", "图 5.5")
    text = text.replace("表5.1", "表 5.1")
    text = text.replace("图16.1", "图 16.1")
    text = text.replace("图16.7", "图 16.7")
    text = text.replace("Markowitz诅咒", "Markowitz 诅咒")
    text = text.replace("HRP优于", "HRP 优于")
    text = text.replace("CLA的", "CLA 的")
    text = text.replace("IVP的", "IVP 的")
    text = text.replace("HRP的", "HRP 的")
    text = text.replace("HRP可", "HRP 可")
    text = text.replace("20TB", "20 TB")
    text = text.replace("数百TB", "数百 TB")
    text = text.replace("HPC系统", "HPC 系统")
    text = text.replace("HPC技术", "HPC 技术")
    text = text.replace("HPC工具", "HPC 工具")
    text = text.replace("HPC环境", "HPC 环境")
    text = text.replace("HPC市场", "HPC 市场")
    text = text.replace("CPU和", "CPU 和")
    text = text.replace("CPU与", "CPU 与")
    text = text.replace("CPU可", "CPU 可")
    text = text.replace("GPU在", "GPU 在")
    text = text.replace("InfiniBand网络", "InfiniBand 网络")
    text = text.replace("PARATEC在", "PARATEC 在")
    text = text.replace("非均匀FFT", "非均匀 FFT")
    text = text.replace("。 There are at least two uses of this result.", "。这一结果至少有两个用途。")
    text = text.replace(
        "。 For example, Figure 18.1 plots the bootstrapped distributions of entropy estimates under 10, 7, 5, and 2 letter encodings, on messages of length 100, using Kontoyiannis' method.",
        "。例如，图 18.1 绘制了使用 Kontoyiannis 方法时，在长度为 100 的消息上，采用 10、7、5 和 2 字母编码得到的熵估计 bootstrap 分布。",
    )
    text = text.replace("为索引的交易价格，且", "，且")
    text = text.replace("U.S。", "美国")
    text = re.sub(r"\bU\.S\.?\s*国家实验室", "美国国家实验室", text)
    text = re.sub(r"\bU\.S\.?\s*股票市场", "美国股票市场", text)
    text = re.sub(r"\bU\.S\.?\s*金融股", "美国金融股", text)
    text = re.sub(r"\bU\.S\.?\s*银行", "美国银行", text)
    text = re.sub(r"\bU\.S\.?\s*美国国债", "美国国债", text)
    text = re.sub(r"\bU\.S\.?\s*国债", "美国国债", text)
    text = re.sub(r"\bU\.S\.?\s*美元计价", "美元计价", text)
    text = re.sub(r"\bU\.S\.?\s*制造业", "美国制造业", text)
    text = re.sub(r"\bU\.S\.?\s*科学与工程", "美国科学与工程", text)
    text = re.sub(r"\bU\.S\.?\s*能源部", "美国能源部", text)
    text = re.sub(r"\bU\.S\.?\s*科学办公室", "美国能源部科学办公室", text)
    text = re.sub(r"\bU\.S\.?\s*东部夏令时", "美国东部夏令时", text)
    text = text.replace("2点45分p.m（美国东部夏令时）", "美国东部夏令时下午 2:45")
    text = text.replace("2 时 45 p.m（美国东部夏令时）", "美国东部夏令时下午 2:45")
    text = text.replace("2 时 45 p.m（U.S，美国东部夏令时）", "美国东部夏令时下午 2:45")
    text = text.replace("2点45分p.m", "下午 2:45")
    text = text.replace("p.m（美国东部夏令时）", "（美国东部夏令时）")
    text = text.replace("e.g，例如", "例如，")
    text = text.replace("e.g，即", "例如，")
    text = text.replace("e.g，如", "例如，")
    text = text.replace("e.g。", "例如，")
    text = text.replace("e.g、", "例如，")
    text = text.replace("e.g.，", "例如，")
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
    text = text.replace("几何平均数:", "几何平均数：")
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
    localize_zh_punctuation(soup)


def localize_zh_punctuation(soup: BeautifulSoup) -> None:
    """Localize punctuation nodes left outside translatable text fragments."""
    punctuation = {
        ".": "。",
        ",": "，",
        ":": "：",
        ";": "；",
        "?": "？",
        "!": "！",
        "(": "（",
        ")": "）",
    }
    for node in list(soup.find_all(string=True)):
        if not isinstance(node, NavigableString):
            continue
        parent = node.parent
        if parent is None or parent.name in SKIP_ANCESTORS or node.find_parent(list(SKIP_ANCESTORS)):
            continue
        if node.find_parent(class_="sourceCode") or node.find_parent(class_="citation"):
            continue
        if node.find_parent(class_="references-list"):
            continue
        text = str(node)
        stripped = text.strip()
        if stripped and all(char in punctuation for char in stripped):
            node.replace_with(NavigableString("".join(punctuation[char] for char in stripped)))
            continue
        localized = re.sub(r"^\s+(?=[\u4e00-\u9fff，。；：！？、）])", "", text)
        localized = re.sub(r"(?<=[，。；：！？、）])\s+$", "", localized)
        if localized != text:
            node.replace_with(NavigableString(localized))


def remove_excluded_page_links(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    changed = False
    for excluded_page in EXCLUDED_PAGES:
        for link in list(soup.select(f'a[href="{excluded_page}"]')):
            toc_part = link.find_parent("li", class_="toc-part")
            if toc_part is not None:
                toc_part.decompose()
            else:
                toc_chapter = link.find_parent("li", class_="toc-chapter")
                if toc_chapter is not None:
                    toc_chapter.decompose()
                else:
                    link.decompose()
            changed = True
    if not changed:
        return html
    for pager in soup.select(".chapter-pager"):
        if not pager.get_text(" ", strip=True):
            pager.decompose()
    return str(soup)


def normalize_front_matter_labels(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    changed = False
    for link in soup.select('a[href="front-matter.html"]'):
        number = link.select_one(".toc-number")
        spans = link.find_all("span", recursive=False)
        if number is not None and spans:
            number.string = "封"
            spans[-1].string = "封面"
        else:
            text = link.get_text(" ", strip=True)
            if text.startswith("查看"):
                link.string = "查看封面"
            elif text in {"上一章", "Previous"}:
                link.string = "上一章"
            elif text.startswith(("上一章：", "上一章:", "Previous:")):
                link.string = "上一章：封面"
            else:
                link.string = "封面"
        changed = True
        toc_part = link.find_parent("li", class_="toc-part")
        heading = toc_part.select_one(".toc-part-heading p") if toc_part is not None else None
        if heading is not None:
            heading.string = "封面"
        toc_chapter = link.find_parent("li", class_="toc-chapter")
        if toc_chapter is not None:
            toc_chapter["data-search"] = "cover front matter"
    return str(soup) if changed else html


def simplify_front_matter(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.body is not None:
        classes = soup.body.get("class", [])
        if "cover-page" not in classes:
            soup.body["class"] = [*classes, "cover-page"]
    if soup.title is not None:
        soup.title.string = "封面 | 金融机器学习进阶"
    topbar_label = soup.select_one(".book-topbar > div > span")
    if topbar_label is not None:
        topbar_label.string = "封面"

    article = soup.select_one("article")
    cover = soup.select_one("figure.book-cover")
    if article is None or cover is None:
        return str(soup)

    img = cover.find("img")
    if img is not None:
        img["alt"] = "《金融机器学习进阶》封面"

    article.clear()
    header = soup.new_tag("header", **{"class": "chapter-header"})
    kicker = soup.new_tag("p")
    kicker.string = "金融机器学习进阶"
    title = soup.new_tag("h1")
    title.string = "封面"
    header.append(kicker)
    header.append(title)
    article.append(header)
    article.append(cover)

    pager = soup.new_tag("div", **{"class": "chapter-pager"})
    next_link = soup.new_tag("a", href="chapter-01.html")
    next_link.string = "下一章：金融机器学习作为独立学科"
    pager.append(next_link)
    article.append(pager)
    return str(soup)


def sync_index_labels(html: str) -> str:
    """Keep the Chinese contents page aligned with reviewed chapter headings."""
    soup = BeautifulSoup(html, "html.parser")
    target_cache: dict[str, BeautifulSoup] = {}

    def target_soup(page: str) -> BeautifulSoup | None:
        if page not in target_cache:
            path = ZH / page
            if not path.exists():
                return None
            target_cache[page] = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        return target_cache[page]

    for link in soup.select("a.toc-entry[href]"):
        href = str(link.get("href", ""))
        page = href.split("#", 1)[0]
        if not re.fullmatch(r"chapter-\d{2}\.html", page):
            continue
        target = target_soup(page)
        heading = target.select_one("article h1") if target is not None else None
        spans = link.find_all("span", recursive=False)
        if heading is not None and spans:
            spans[-1].string = heading.get_text(" ", strip=True)

    for link in soup.select("li.toc-section > a[href]"):
        href = str(link.get("href", ""))
        if "#" not in href:
            continue
        page, fragment = href.split("#", 1)
        target = target_soup(page)
        heading = target.find(id=fragment) if target is not None else None
        if heading is not None:
            link.string = heading.get_text(" ", strip=True)

    description_replacements = {
        "赌注大小、回测风险、综合数据、统计、策略风险和分配。": "仓位规模、回测的危险、合成数据、回测统计、策略风险和资产配置。",
        "结构断裂、熵和微观结构特征。": "结构突变、熵与市场微观结构特征。",
        "并行化、强力搜索、量子计算和 HPC 应用程序。": "多进程、暴力搜索、量子计算和 HPC 应用。",
    }
    for description in soup.select(".toc-part-heading > span"):
        text = description.get_text(" ", strip=True)
        if text in description_replacements:
            description.string = description_replacements[text]
    return str(soup)


def sync_front_matter_navigation(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    target = ZH / "chapter-01.html"
    if target.exists():
        target_soup = BeautifulSoup(target.read_text(encoding="utf-8"), "html.parser")
        heading = target_soup.select_one("article h1")
        link = soup.select_one('.chapter-pager a[href="chapter-01.html"]')
        if heading is not None and link is not None:
            link.string = f"下一章：{heading.get_text(' ', strip=True)}"
    return str(soup)


def normalize_formula_join_artifacts(html: str) -> str:
    math_inline = r'(<span class="math inline">.*?</span>)'
    code_inline = r"(<code>.*?</code>)"
    html = re.sub(rf"{math_inline}\s*的均值，\s*{math_inline}", r"\1 和 \2", html, flags=re.S)
    html = re.sub(rf"{code_inline}\s*的均值，\s*{code_inline}", r"\1 且 \2", html, flags=re.S)
    html = re.sub(rf"([>。；，])的均值，\s*{math_inline}", r"\1且 \2", html, flags=re.S)
    html = re.sub(r"的值\s+(<span class=\"math inline\">.*?</span>)\s+需要", r"\1 的值需要", html, flags=re.S)
    html = re.sub(r"(图|表)\s*(\d+\.\d+)", r"\1 \2", html)
    return html


def normalize_translation_artifacts(html: str) -> str:
    replacements = {
        "U.S 美国国债": "美国国债",
        "U.S美国国债": "美国国债",
        "U.S 股票市场": "美国股票市场",
        "U.S股票市场": "美国股票市场",
        "U.S 金融股": "美国金融股",
        "U.S金融股": "美国金融股",
        "U.S 银行": "美国银行",
        "U.S银行": "美国银行",
        "U.S 制造业": "美国制造业",
        "U.S制造业": "美国制造业",
        "U.S 科学与工程": "美国科学与工程",
        "U.S科学与工程": "美国科学与工程",
        "U.S 能源部": "美国能源部",
        "U.S能源部": "美国能源部",
        "U.S 科学办公室": "美国能源部科学办公室",
        "U.S科学办公室": "美国能源部科学办公室",
        "U.S 东部夏令时": "美国东部夏令时",
        "U.S东部夏令时": "美国东部夏令时",
        "U.S 及欧洲": "美国及欧洲",
        "U.S及欧洲": "美国及欧洲",
        "2点45分p.m（美国东部夏令时）": "美国东部夏令时下午 2:45",
        "2点45分p.m": "下午 2:45",
        "每日产生的数据超过 10 TB 条": "每日生成超过 10 TB 数据",
        "均值精度下降（MDA）": "平均准确率下降（MDA）",
        "均值精度下降": "平均准确率下降（MDA）",
        "分数（而不是整数）微分序列": "分数阶（而非整数阶）差分序列",
        "分数微分": "分数阶差分",
        "包含一些内存": "保留一定记忆性",
        "基于返回的编码方案": "基于收益率的编码方案",
        "APIs": "API",
        "CPUs": "CPU",
        "GPUs": "GPU",
        "精度率": "精确率",
        "隐含精度": "隐含精确率",
        "交易量条": "成交量条",
        "e.g。": "例如，",
        "e.g、": "例如，",
        "e.g.，": "例如，",
        "几何平均数:": "几何平均数：",
        "Tick 连续同向流 bar（Tick 连续同向流 bar）": "Tick 连续同向流 bar",
        "成交量／成交额不平衡 bar（成交量／成交额不平衡 bar）": "成交量／成交额不平衡 bar",
        "成交量／成交额连续同向流 bar（成交量／成交额连续同向流 bar）": "成交量／成交额连续同向流 bar",
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    html = re.sub(r"U\.S\.?\s*国家实验室", "美国国家实验室", html)
    html = re.sub(r"U\.S\.?\s*股票市场", "美国股票市场", html)
    html = re.sub(r"U\.S\.?\s*金融股", "美国金融股", html)
    html = re.sub(r"U\.S\.?\s*银行", "美国银行", html)
    html = re.sub(r"U\.S\.?\s*美国国债", "美国国债", html)
    html = re.sub(r"U\.S\.?\s*国债", "美国国债", html)
    html = re.sub(r"U\.S\.?\s*美元计价", "美元计价", html)
    html = re.sub(r"U\.S\.?\s*制造业", "美国制造业", html)
    html = re.sub(r"U\.S\.?\s*科学与工程", "美国科学与工程", html)
    html = re.sub(r"U\.S\.?\s*能源部", "美国能源部", html)
    html = re.sub(r"U\.S\.?\s*科学办公室", "美国能源部科学办公室", html)
    html = re.sub(r"U\.S\.?\s*东部夏令时", "美国东部夏令时", html)
    html = re.sub(r"(?<!代)片段\s*(\d+\.\d+)\s*[：:]", r"代码清单 \1：", html)
    html = re.sub(r"(?<!代)片段\s*(\d+\.\d+)", r"代码清单 \1", html)
    html = re.sub(r"代码清单\s*(\d+\.\d+)", r"代码清单 \1", html)
    html = re.sub(r">(\d+(?:\.\d+){1,3})(?=[\u4e00-\u9fffA-Za-z])", r">\1 ", html)
    return html


def move_footnotes_to_endnotes(html: str, page_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article")
    if article is None:
        return html
    footnotes = list(article.select("p.footnote"))
    if not footnotes:
        return html

    section = soup.new_tag("section", **{"class": "footnotes", "role": "doc-endnotes", "aria-label": "脚注"})
    heading = soup.new_tag("p", **{"class": "footnotes-heading"})
    heading.string = "脚注"
    section.append(heading)
    footnote_list = soup.new_tag("ol", **{"class": "footnotes-list"})
    section.append(footnote_list)

    page_slug = page_name.removesuffix(".html")
    footnote_numbers: set[str] = set()
    footnote_items: dict[str, Tag] = {}
    for footnote in footnotes:
        sup = footnote.find("sup")
        number = sup.get_text("", strip=True) if sup is not None else str(len(footnote_numbers) + 1)
        footnote_numbers.add(number)
        li = soup.new_tag("li", id=f"fn-{page_slug}-{number}", **{"class": "footnote-item"})
        if sup is not None:
            sup.extract()
        for child in list(footnote.contents):
            li.append(child.extract())
        footnote_items[number] = li
        footnote_list.append(li)
        footnote.decompose()

    ref_counts: dict[str, int] = {}
    for sup in article.find_all("sup"):
        if sup.find_parent("section", class_="footnotes"):
            continue
        number = sup.get_text("", strip=True)
        if number not in footnote_numbers:
            continue
        ref_counts[number] = ref_counts.get(number, 0) + 1
        ref_id = f"fnref-{page_slug}-{number}" if ref_counts[number] == 1 else f"fnref-{page_slug}-{number}-{ref_counts[number]}"
        sup["id"] = ref_id
        sup["class"] = [*sup.get("class", []), "footnote-ref"]
        sup.clear()
        link = soup.new_tag("a", href=f"#fn-{page_slug}-{number}", **{"aria-label": f"脚注 {number}"})
        link.string = number
        sup.append(link)

    for number, li in footnote_items.items():
        if ref_counts.get(number, 0) == 0:
            continue
        backref = soup.new_tag("a", href=f"#fnref-{page_slug}-{number}", **{"class": "footnote-backref", "aria-label": "返回正文"})
        backref.string = "返回正文"
        li.append(" ")
        li.append(backref)

    target = article.select_one(".references-heading") or article.select_one(".chapter-pager")
    if target is not None:
        target.insert_before(section)
    else:
        article.append(section)
    return str(soup)


def fix_chapter_01(html: str) -> str:
    replacements = {
        "将50位主观型PMs聚集在一起，他们</p>\n<p>终将相互影响": "将50位主观型PMs聚集在一起，他们终将相互影响",
        "多线程、multiprocessing、图形处理单元": "多线程、多进程、图形处理单元",
        "以 multiprocessing 架构思考问题": "以多进程架构思考问题",
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    html = re.sub(
        r"(将50位主观型PMs聚集在一起，他们)</p>\s*<span class=\"pdf-page-anchor\"[^>]*></span>\s*<p>(终将相互影响)",
        r"\1\2",
        html,
    )
    return html


def fix_chapter_10(html: str) -> str:
    replacements = {
        "两种策略均产生了最终被证明正确的预测（价格在 <span class=\"math inline\">\\(p_1\\)</span> 的均值， <span class=\"math inline\">\\(p_3\\)</span>之间上涨了25%）": "两种策略均产生了最终被证明正确的预测（价格在 <span class=\"math inline\">\\(p_1\\)</span> 和 <span class=\"math inline\">\\(p_3\\)</span> 之间上涨了 25%）",
        "与 <span class=\"math inline\">\\(z\\in(-\\infty,+\\infty)\\)</span>，且 <span class=\"math inline\">\\(Z\\)</span> 表示标准正态分布。": "其中 <span class=\"math inline\">\\(z\\in(-\\infty,+\\infty)\\)</span>，且 <span class=\"math inline\">\\(Z\\)</span> 表示标准正态分布。",
        "其中 <span class=\"math inline\">\\(m\\in[-1,1]\\)</span> 的均值， <span class=\"math inline\">\\(Z[\\cdot]\\)</span> 是 CDF 的 <span class=\"math inline\">\\(Z\\)</span>.": "其中 <span class=\"math inline\">\\(m\\in[-1,1]\\)</span>，且 <span class=\"math inline\">\\(Z[\\cdot]\\)</span> 是 <span class=\"math inline\">\\(Z\\)</span> 的 CDF。",
        "我们定义 <span class=\"math inline\">\\(\\tilde p=\\max_i\\{p_i\\}\\)</span> 为……的概率 <span class=\"math inline\">\\(x\\)</span>，并希望检验": "我们将 <span class=\"math inline\">\\(\\tilde p=\\max_i\\{p_i\\}\\)</span> 定义为 <span class=\"math inline\">\\(x\\)</span> 的概率，并希望检验",
        "其中 <span class=\"math inline\">\\(m\\in[-1,1]\\)</span> 的均值， <span class=\"math inline\">\\(Z[z]\\)</span> 用于调节预测结果对应的仓位规模": "其中 <span class=\"math inline\">\\(m\\in[-1,1]\\)</span>，且 <span class=\"math inline\">\\(Z[z]\\)</span> 用于调节预测结果对应的仓位规模",
        "其中 <span class=\"math inline\">\\(j\\in[i+1,I]\\)</span> 的均值， <span class=\"math inline\">\\(t_{j,0}\\le t_{i,1}\\)</span>。": "其中 <span class=\"math inline\">\\(j\\in[i+1,I]\\)</span> 且 <span class=\"math inline\">\\(t_{j,0}\\le t_{i,1}\\)</span>。",
        "<span class=\"math inline\">\\(\\operatorname{int}[x]\\)</span> 为…的整数值 <span class=\"math inline\">\\(x\\)</span>。": "<span class=\"math inline\">\\(\\operatorname{int}[x]\\)</span> 为 <span class=\"math inline\">\\(x\\)</span> 的整数值。",
        "其中 <span class=\"math inline\">\\(L[f_i,\\omega,m]\\)</span> 为…的反函数 <span class=\"math inline\">\\(m[\\omega,f_i-p_t]\\)</span> 关于…的 <span class=\"math inline\">\\(p_t\\)</span>,": "其中 <span class=\"math inline\">\\(L[f_i,\\omega,m]\\)</span> 是 <span class=\"math inline\">\\(m[\\omega,f_i-p_t]\\)</span> 关于 <span class=\"math inline\">\\(p_t\\)</span> 的反函数，",
        "给定用户自定义的参数对 <span class=\"math inline\">\\((x,m^*)\\)</span>，使得 <span class=\"math inline\">\\(x=f_i-p_t\\)</span> 的均值， <span class=\"math inline\">\\(m^*=m[\\omega,x]\\)</span>，其逆函数为 <span class=\"math inline\">\\(m[\\omega,x]\\)</span> 关于…的 <span class=\"math inline\">\\(\\omega\\)</span> 为": "给定用户自定义的参数对 <span class=\"math inline\">\\((x,m^*)\\)</span>，使得 <span class=\"math inline\">\\(x=f_i-p_t\\)</span> 且 <span class=\"math inline\">\\(m^*=m[\\omega,x]\\)</span>，则 <span class=\"math inline\">\\(m[\\omega,x]\\)</span> 关于 <span class=\"math inline\">\\(\\omega\\)</span> 的反函数为",
        "代码清单 10.4 实现了以下算法：以特定变量为函数，计算动态仓位规模和限价 <span class=\"math inline\">\\(p_t\\)</span> 的均值， <span class=\"math inline\">\\(f_i\\)</span>。": "代码清单 10.4 实现了以 <span class=\"math inline\">\\(p_t\\)</span> 和 <span class=\"math inline\">\\(f_i\\)</span> 为输入计算动态仓位规模和限价的算法。",
        "对应最大仓位 <span class=\"math inline\">\\(Q=100\\)</span>, <span class=\"math inline\">\\(f_i=115\\)</span> 的均值， <span class=\"math inline\">\\(p_t=100\\)</span>。": "对应最大仓位 <span class=\"math inline\">\\(Q=100\\)</span>、<span class=\"math inline\">\\(f_i=115\\)</span> 且 <span class=\"math inline\">\\(p_t=100\\)</span>。",
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    return html


def fix_chapter_02(html: str) -> str:
    replacements = {
        "一组金融工具的时间序列": "一组金融标的的时间序列",
        "不到期的现金工具": "不到期的现金类产品",
        "直接交易单一工具": "直接交易单一标的",
        "假设我们已有一段 bar 历史数据，这些 bar 由第 2.3 节所述的任意方法生成，包含以下字段：": "假设我们已经获得了一段 bar 历史数据，这些 bar 可以由第 2.3 节介绍的任意方法生成。每个 bar 包含以下字段：",
        r'<ul><li><span class="math inline">\(o_{i,t}\)</span> 是工具 <span class="math inline">\(i=1,\ldots,I\)</span> 在 bar <span class="math inline">\(t=1,\ldots,T\)</span>.</li><li><span class="math inline">\(p_{i,t}\)</span> 是工具 <span class="math inline">\(i=1,\ldots,I\)</span> 在 bar <span class="math inline">\(t=1,\ldots,T\)</span>.</li><li><span class="math inline">\(\varphi_{i,t}\)</span> 是工具 <span class="math inline">\(i=1,\ldots,I\)</span> 在 bar <span class="math inline">\(t=1,\ldots,T\)</span>的每点  价值，包含外汇汇率。</li><li><span class="math inline">\(v_{i,t}\)</span> 是工具 <span class="math inline">\(i=1,\ldots,I\)</span> 在 bar <span class="math inline">\(t=1,\ldots,T\)</span>.</li><li><span class="math inline">\(d_{i,t}\)</span> 是工具 i 在 bar t 时支付的持仓收益、股息或票息。该变量也可用于计提保证金成本或融资成本。</li></ul>': r'<ul><li><span class="math inline">\(o_{i,t}\)</span>：标的 <span class="math inline">\(i=1,\ldots,I\)</span> 在 bar <span class="math inline">\(t=1,\ldots,T\)</span> 的原始开盘价。</li><li><span class="math inline">\(p_{i,t}\)</span>：标的 <span class="math inline">\(i=1,\ldots,I\)</span> 在 bar <span class="math inline">\(t=1,\ldots,T\)</span> 的原始收盘价。</li><li><span class="math inline">\(\varphi_{i,t}\)</span>：标的 <span class="math inline">\(i=1,\ldots,I\)</span> 在 bar <span class="math inline">\(t=1,\ldots,T\)</span> 中一个点位对应的美元价值，其中包含外汇汇率换算。</li><li><span class="math inline">\(v_{i,t}\)</span>：标的 <span class="math inline">\(i=1,\ldots,I\)</span> 在 bar <span class="math inline">\(t=1,\ldots,T\)</span> 的成交量。</li><li><span class="math inline">\(d_{i,t}\)</span>：标的 i 在 bar t 支付的持仓收益、股息或票息。这个变量也可用于计入保证金成本或融资成本。</li></ul>',
        "其中所有工具 <span class=\"math inline\">\\(i=1,\\ldots,I\\)</span> 在 bar 时均可交易 <span class=\"math inline\">\\(t=1,\\ldots,T\\)</span>。换言之，即使某些工具在整个时间区间内并非始终可交易 <span class=\"math inline\">\\([t-1,t]\\)</span>，至少在 t − 1 和 t 时刻它们是可交易的（市场在这些时刻开放并能够执行订单）。": "其中所有标的 <span class=\"math inline\">\\(i=1,\\ldots,I\\)</span> 在 bar <span class=\"math inline\">\\(t=1,\\ldots,T\\)</span> 时均可交易。换言之，即使某些标的在整个时间区间 <span class=\"math inline\">\\([t-1,t]\\)</span> 内并非始终可交易，至少在 t − 1 和 t 时刻它们是可交易的（市场在这些时刻开放并能够执行订单）。",
        "<p>的均值， <span class=\"math inline\">\\(K_0=1\\)</span> 在初始 AUM 中。变量 <span class=\"math inline\">\\(h_{i,t}\\)</span> 表示工具的持仓量（证券或合约数量） <span class=\"math inline\">\\(i\\)</span> 在时刻 <span class=\"math inline\">\\(t\\)</span>。变量 <span class=\"math inline\">\\(\\delta_{i,t}\\)</span> 是市场价值在 <span class=\"math inline\">\\(t-1\\)</span> 的均值， <span class=\"math inline\">\\(t\\)</span> 之间针对工具的变化量 <span class=\"math inline\">\\(i\\)</span>。": "<p>且初始 AUM 中 <span class=\"math inline\">\\(K_0=1\\)</span>。变量 <span class=\"math inline\">\\(h_{i,t}\\)</span> 表示标的 <span class=\"math inline\">\\(i\\)</span> 在时刻 <span class=\"math inline\">\\(t\\)</span> 的持仓量（证券或合约数量）。变量 <span class=\"math inline\">\\(\\delta_{i,t}\\)</span> 表示从 <span class=\"math inline\">\\(t-1\\)</span> 到 <span class=\"math inline\">\\(t\\)</span> 期间标的 <span class=\"math inline\">\\(i\\)</span> 的市场价值变化。",
        "变量 <span class=\"math inline\">\\(h_{i,t}\\)</span> 表示工具的持仓量（证券或合约数量）<span class=\"math inline\">\\(i\\)</span> 在时刻 <span class=\"math inline\">\\(t\\)</span> 的值。变量 <span class=\"math inline\">\\(\\delta_{i,t}\\)</span> 是市场价值在 <span class=\"math inline\">\\(t-1\\)</span> 与 <span class=\"math inline\">\\(t\\)</span> 之间、针对工具 <span class=\"math inline\">\\(i\\)</span> 的变化量。": "变量 <span class=\"math inline\">\\(h_{i,t}\\)</span> 表示标的 <span class=\"math inline\">\\(i\\)</span> 在时刻 <span class=\"math inline\">\\(t\\)</span> 的持仓量（证券或合约数量）。变量 <span class=\"math inline\">\\(\\delta_{i,t}\\)</span> 表示从 <span class=\"math inline\">\\(t-1\\)</span> 到 <span class=\"math inline\">\\(t\\)</span> 期间标的 <span class=\"math inline\">\\(i\\)</span> 的市场价值变化。",
        "<p>的目的 <span class=\"math inline\">\\(\\omega_{i,t}(\\sum_{i=1}^{I}|\\omega_{i,t}|)^{-1}\\)</span> 在 <span class=\"math inline\">\\(h_{i,t}\\)</span> 中是对配置进行去杠杆化。": "<p><span class=\"math inline\">\\(\\omega_{i,t}(\\sum_{i=1}^{I}|\\omega_{i,t}|)^{-1}\\)</span> 在 <span class=\"math inline\">\\(h_{i,t}\\)</span> 中的作用是降低配置杠杆。",
        "对于期货系列，展期时我们可能不知道 <span class=\"math inline\">\\(p_{i,t}\\)</span> 新合约的 <span class=\"math inline\">\\(t\\)</span>，因此我们使用 <span class=\"math inline\">\\(o_{i,t+1}\\)</span> 作为时间上最接近的替代。": "对于期货系列，展期时我们可能不知道 <span class=\"math inline\">\\(p_{i,t}\\)</span>，也就是新合约在 <span class=\"math inline\">\\(t\\)</span> 时的价格，因此使用 <span class=\"math inline\">\\(o_{i,t+1}\\)</span> 作为时间上最接近的替代。",
        "令 <span class=\"math inline\">\\(\\tau_i\\)</span> 为交易工具 $1 所产生的交易成本 <span class=\"math inline\">\\(i\\)</span>，例如， <span class=\"math inline\">\\(\\tau_i=1E-4\\)</span> （一个基点）。": "令 <span class=\"math inline\">\\(\\tau_i\\)</span> 为交易标的 <span class=\"math inline\">\\(i\\)</span> 的 1 美元名义金额所对应的交易成本，例如 <span class=\"math inline\">\\(\\tau_i=1E-4\\)</span>（一个基点）。",
        "令 <span class=\"math inline\">\\(\\tau_i\\)</span> 为交易工具 $1 所产生的交易成本 <span class=\"math inline\">\\(i\\)</span>，e.g。， <span class=\"math inline\">\\(\\tau_i=1E-4\\)</span> （一个基点）。": "令 <span class=\"math inline\">\\(\\tau_i\\)</span> 为交易标的 <span class=\"math inline\">\\(i\\)</span> 的 1 美元名义金额所对应的交易成本，例如 <span class=\"math inline\">\\(\\tau_i=1E-4\\)</span>（一个基点）。",
        "令 <span class=\"math inline\">\\(\\tau_i\\)</span> 为交易工具 $1 所产生的交易成本 <span class=\"math inline\">\\(i\\)</span>，例如，， <span class=\"math inline\">\\(\\tau_i=1E-4\\)</span> （一个基点）。": "令 <span class=\"math inline\">\\(\\tau_i\\)</span> 为交易标的 <span class=\"math inline\">\\(i\\)</span> 的 1 美元名义金额所对应的交易成本，例如 <span class=\"math inline\">\\(\\tau_i=1E-4\\)</span>（一个基点）。",
        "策略在每个观测数据条/bar 上还需要了解三个额外变量 <span class=\"math inline\">\\(t\\)</span>:": "策略在每个观测 bar <span class=\"math inline\">\\(t\\)</span> 上还需要了解三个额外变量：",
        "令 <span class=\"math inline\">\\(v_{i,t}\\)</span> 为工具 <span class=\"math inline\">\\(i\\)</span> 在数据条/bar <span class=\"math inline\">\\(t\\)</span>内的成交量。": "令 <span class=\"math inline\">\\(v_{i,t}\\)</span> 为标的 <span class=\"math inline\">\\(i\\)</span> 在 bar <span class=\"math inline\">\\(t\\)</span> 内的成交量。",
        "<p>和 <span class=\"math inline\">\\(K_0=1\\)</span>，并以此作为初始资产管理规模（AUM）的起点。": "<p>其中 <span class=\"math inline\">\\(K_0=1\\)</span>，并以此作为初始资产管理规模（AUM）的起点。",
        '<p>其中，连续同向成交的预期规模由 max{<span class="math inline">\\(P[b_t=1]\\)</span><span class="math inline">\\(\\mathbb{E}_0[v_t|b_t=1]\\)</span>, (1 − <span class="math inline">\\(P[b_t=1]\\)</span>）<span class="math inline">\\(\\mathbb{E}_0[v_t|b_t=-1]\\)</span>} 给出。当 <span class="math inline">\\(\\theta_T\\)</span>表示的连续同向成交规模超过预期时，较小的 T 就能满足条件。</p>': '<p>上式 max 项给出的预期规模，是 <span class="math inline">\\(P[b_t=1]\\)</span><span class="math inline">\\(\\mathbb{E}_0[v_t|b_t=1]\\)</span> 与（1 − <span class="math inline">\\(P[b_t=1]\\)</span>）<span class="math inline">\\(\\mathbb{E}_0[v_t|b_t=-1]\\)</span> 两者中的较大值。当 <span class="math inline">\\(\\theta_T\\)</span> 表示的连续同向成交规模超过预期时，较小的 T 就能满足条件。</p>',
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    return html


def fix_chapter_03(html: str) -> str:
    return html.replace(
        "假设 <span class=\"math inline\">\\(I=1E6\\)</span> 的均值， <span class=\"math inline\">\\(h=1E3\\)</span>，",
        "假设 <span class=\"math inline\">\\(I=1E6\\)</span> 且 <span class=\"math inline\">\\(h=1E3\\)</span>，",
    )


def fix_chapter_05(html: str) -> str:
    return html.replace(
        '，且 <span class="math inline">\\(\\omega_k=0\\)</span> （后者对应上述条件不成立的情形）。',
        '；若上述条件不成立，则 <span class="math inline">\\(\\omega_k=0\\)</span>。',
    )


def fix_chapter_08(html: str) -> str:
    return html.replace(
        '<span class="math inline">\\(\\mu_n\\)</span>是 <span class="math inline">\\(\\{X_{t,n}\\}_{t=1,\\ldots,T}\\)</span> 和 <span class="math inline">\\(\\sigma_n\\)</span>是',
        '<span class="math inline">\\(\\mu_n\\)</span>是 <span class="math inline">\\(\\{X_{t,n}\\}_{t=1,\\ldots,T}\\)</span> 的均值，变量 <span class="math inline">\\(\\sigma_n\\)</span>是',
    )


def fix_chapter_12(html: str) -> str:
    return html.replace(
        '<span class="math inline">\\(\\varphi[N,k]\\)</span>，</p><div class="math display">',
        '<span class="math inline">\\(\\varphi[N,k]\\)</span>：</p><div class="math display">',
    )


def fix_chapter_11(html: str) -> str:
    replacements = {
        "构建训练集 <span class=\"math inline\">\\(J\\)</span>，通过合并 <span class=\"math inline\">\\(S/2\\)</span> 子矩阵 <span class=\"math inline\">\\(M_s\\)</span> 构成……的 <span class=\"math inline\">\\(c\\)</span>. <span class=\"math inline\">\\(J\\)</span> 是一个阶数为 <span class=\"math inline\">\\((T/S)(S/2)\\times N=(T/2)\\times N\\)</span>.": "构建训练集 <span class=\"math inline\">\\(J\\)</span>：合并 <span class=\"math inline\">\\(S/2\\)</span> 个子矩阵 <span class=\"math inline\">\\(M_s\\)</span>，这些子矩阵构成 <span class=\"math inline\">\\(c\\)</span>。<span class=\"math inline\">\\(J\\)</span> 是阶数为 <span class=\"math inline\">\\((T/S)(S/2)\\times N=(T/2)\\times N\\)</span> 的矩阵。",
        "构建测试集 <span class=\"math inline\">\\(\\bar J\\)</span>，作为……的补集 <span class=\"math inline\">\\(J\\)</span> 在 <span class=\"math inline\">\\(M\\)</span>。换言之， <span class=\"math inline\">\\(\\bar J\\)</span> 是 <span class=\"math inline\">\\((T/2)\\times N\\)</span> 矩阵，由……的所有行构成 <span class=\"math inline\">\\(M\\)</span> 但不属于 <span class=\"math inline\">\\(J\\)</span>.": "构建测试集 <span class=\"math inline\">\\(\\bar J\\)</span>：它是 <span class=\"math inline\">\\(J\\)</span> 在 <span class=\"math inline\">\\(M\\)</span> 中的补集。换言之，<span class=\"math inline\">\\(\\bar J\\)</span> 是阶数为 <span class=\"math inline\">\\((T/2)\\times N\\)</span> 的矩阵，由 <span class=\"math inline\">\\(M\\)</span> 中所有不属于 <span class=\"math inline\">\\(J\\)</span> 的行构成。",
        "构建向量 <span class=\"math inline\">\\(R\\)</span> ，包含阶数为……的绩效统计量 <span class=\"math inline\">\\(N\\)</span>，其中第 <span class=\"math inline\">\\(n\\)</span>项 <span class=\"math inline\">\\(R\\)</span> 报告与第 <span class=\"math inline\">\\(n\\)</span>列相关的绩效，该列来自 <span class=\"math inline\">\\(J\\)</span> （训练集）。": "构建向量 <span class=\"math inline\">\\(R\\)</span>，即阶数为 <span class=\"math inline\">\\(N\\)</span> 的绩效统计量，其中第 <span class=\"math inline\">\\(n\\)</span> 项 <span class=\"math inline\">\\(R\\)</span> 报告与第 <span class=\"math inline\">\\(n\\)</span> 列相关的绩效，该列来自 <span class=\"math inline\">\\(J\\)</span>（训练集）。",
        "构建向量 <span class=\"math inline\">\\(\\bar R\\)</span> ，包含阶数为……的绩效统计量 <span class=\"math inline\">\\(N\\)</span>，其中第 <span class=\"math inline\">\\(n\\)</span>项 <span class=\"math inline\">\\(\\bar R\\)</span> 报告与第 <span class=\"math inline\">\\(n\\)</span>列相关的绩效，该列来自 <span class=\"math inline\">\\(\\bar J\\)</span> （测试集）。": "构建向量 <span class=\"math inline\">\\(\\bar R\\)</span>，即阶数为 <span class=\"math inline\">\\(N\\)</span> 的绩效统计量，其中第 <span class=\"math inline\">\\(n\\)</span> 项 <span class=\"math inline\">\\(\\bar R\\)</span> 报告与第 <span class=\"math inline\">\\(n\\)</span> 列相关的绩效，该列来自 <span class=\"math inline\">\\(\\bar J\\)</span>（测试集）。",
        "确定……的相对排名 <span class=\"math inline\">\\(\\bar R_{n^*}\\)</span> 在……之中 <span class=\"math inline\">\\(\\bar R\\)</span>。": "确定 <span class=\"math inline\">\\(\\bar R_{n^*}\\)</span> 在 <span class=\"math inline\">\\(\\bar R\\)</span> 中的相对排名。",
        "当 <span class=\"math inline\">\\(\\bar R_{n^*}\\)</span> 与……的中位数重合时 <span class=\"math inline\">\\(\\bar R\\)</span>。": "当 <span class=\"math inline\">\\(\\bar R_{n^*}\\)</span> 与 <span class=\"math inline\">\\(\\bar R\\)</span> 的中位数重合时。",
        "第五步，通过收集所有的 <span class=\"math inline\">\\(\\lambda_c\\)</span>，对于 <span class=\"math inline\">\\(c\\in C_S\\)</span>。概率分布函数 <span class=\"math inline\">\\(f(\\lambda)\\)</span> 随后被估计为以下情况出现的相对频率： <span class=\"math inline\">\\(\\lambda\\)</span> 在所有……中出现的 <span class=\"math inline\">\\(C_S\\)</span>，其中": "第五步，收集所有 <span class=\"math inline\">\\(\\lambda_c\\)</span>，其中 <span class=\"math inline\">\\(c\\in C_S\\)</span>，以计算 OOS 排名分布。随后将概率分布函数 <span class=\"math inline\">\\(f(\\lambda)\\)</span> 估计为 <span class=\"math inline\">\\(\\lambda\\)</span> 在所有 <span class=\"math inline\">\\(C_S\\)</span> 个组合中出现的相对频率，其中",
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    return html


def fix_chapter_18_domain(html: str) -> str:
    replacements = {
        "估计熵需要对消息进行编码。在本节中，我们将回顾文献中使用的一些基于收益率的编码方案。尽管下面没有讨论，但建议对来自分数阶（而非整数阶）差分序列的信息进行编码（第 4 章），因为它们仍然保留一定记忆性。": "估计熵需要对消息进行编码。在本节中，我们将回顾文献中使用的一些基于收益率的编码方案。尽管下文没有展开讨论，但建议对来自分数阶（而非整数阶）差分序列的信息进行编码（第 5 章），因为它们仍保留一定记忆性。",
        "让 <span class=\"math inline\">\\(V_\\tau^B\\)</span> 是成交量条中包含的买入报价的交易量总和 <span class=\"math inline\">\\(\\tau\\)</span>，且 <span class=\"math inline\">\\(V_\\tau^S\\)</span> 成交量条内卖出价格变动的成交量总和 <span class=\"math inline\">\\(\\tau\\)</span>。": "令 <span class=\"math inline\">\\(V_\\tau^B\\)</span> 为成交量条 <span class=\"math inline\">\\(\\tau\\)</span> 内买方主动 tick 的成交量之和，<span class=\"math inline\">\\(V_\\tau^S\\)</span> 为成交量条 <span class=\"math inline\">\\(\\tau\\)</span> 内卖方主动 tick 的成交量之和。",
        "Easley 等人 [2012a, 2012b] 注意到 <span class=\"math inline\">\\(\\mathbb{E}[|V_\\tau^B-V_\\tau^S|]\\approx\\alpha\\mu\\)</span> 预期总体积为 <span class=\"math inline\">\\(\\mathbb{E}[V_\\tau^B+V_\\tau^S]=\\alpha\\mu+2\\varepsilon\\)</span>。": "Easley 等人 [2012a, 2012b] 指出 <span class=\"math inline\">\\(\\mathbb{E}[|V_\\tau^B-V_\\tau^S|]\\approx\\alpha\\mu\\)</span>，且预期总成交量为 <span class=\"math inline\">\\(\\mathbb{E}[V_\\tau^B+V_\\tau^S]=\\alpha\\mu+2\\varepsilon\\)</span>。",
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    return html


def fix_chapter_19(html: str) -> str:
    replacements = {
        "Roll 推导出 <span class=\"math inline\">\\(c\\)</span> 的均值， <span class=\"math inline\">\\(\\sigma_u^2\\)</span> 的值如下：": "Roll 推导出 <span class=\"math inline\">\\(c\\)</span> 与 <span class=\"math inline\">\\(\\sigma_u^2\\)</span> 的取值如下：",
        "U.K 及欧洲股票市场": "英国及欧洲股票市场",
        "美国 股票市场": "美国股票市场",
        "利用U.S股票": "利用美国股票",
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    return html


def fix_chapter_21(html: str) -> str:
    replacements = {
        "<span class=\"math inline\">\\(C_h=\\{c_{n,h}\\}_{n=1,\\ldots,N}\\)</span> 随……变化 <span class=\"math inline\">\\(h\\)</span>": "<span class=\"math inline\">\\(C_h=\\{c_{n,h}\\}_{n=1,\\ldots,N}\\)</span> 会随时间段 <span class=\"math inline\">\\(h\\)</span> 变化",
        "<span class=\"math inline\">\\(\\mu_h\\)</span> 和 <span class=\"math inline\">\\(V_h\\)</span> 随……变化 <span class=\"math inline\">\\(h\\)</span>": "<span class=\"math inline\">\\(\\mu_h\\)</span> 和 <span class=\"math inline\">\\(V_h\\)</span> 会随 <span class=\"math inline\">\\(h\\)</span> 变化",
        "<span class=\"math inline\">\\(\\mu_h\\)</span> 和 <span class=\"math inline\">\\(V_h\\)</span> 随……变化 <span class=\"math inline\">\\(h\\)</span>。": "<span class=\"math inline\">\\(\\mu_h\\)</span> 和 <span class=\"math inline\">\\(V_h\\)</span> 会随 <span class=\"math inline\">\\(h\\)</span> 变化。",
        "<span class=\"math inline\">\\(\\tau_h[\\omega]\\)</span> 在零点不可微且随……变化 <span class=\"math inline\">\\(h\\)</span>": "<span class=\"math inline\">\\(\\tau_h[\\omega]\\)</span> 在零点不可微，且会随 <span class=\"math inline\">\\(h\\)</span> 变化",
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    return html


def fix_chapter_13(html: str) -> str:
    replacements = {
        "随后按各个机会的先后顺序构造向量：<span class=\"math inline\">\\(X\\)</span>，<span class=\"math inline\">\\(Y\\)</span>；而 <span class=\"math inline\">\\(Z\\)</span>则按同样顺序构造：": "随后按各个机会的先后顺序构造向量 <span class=\"math inline\">\\(X\\)</span>、<span class=\"math inline\">\\(Y\\)</span> 和 <span class=\"math inline\">\\(Z\\)</span>：",
        "其中 <span class=\"math inline\">\\(\\mathbb{E}[\\cdot]\\)</span> 的均值， <span class=\"math inline\">\\(\\sigma[\\cdot]\\)</span> 分别为……的期望值与标准差 <span class=\"math inline\">\\(\\pi_{i,T_i}\\)</span>，以交易规则为条件 <span class=\"math inline\">\\(R\\)</span>，在 <span class=\"math inline\">\\(i=1,\\ldots,I\\)</span>。公式（13.1）最大化……的夏普比率 <span class=\"math inline\">\\(S\\)</span> 在备选交易规则空间上 <span class=\"math inline\">\\(R\\)</span>。": "其中 <span class=\"math inline\">\\(\\mathbb{E}[\\cdot]\\)</span> 和 <span class=\"math inline\">\\(\\sigma[\\cdot]\\)</span> 分别为 <span class=\"math inline\">\\(\\pi_{i,T_i}\\)</span> 的期望值与标准差，条件为交易规则 <span class=\"math inline\">\\(R\\)</span>，并在 <span class=\"math inline\">\\(i=1,\\ldots,I\\)</span> 上计算。公式（13.1）最大化 <span class=\"math inline\">\\(S\\)</span> 的夏普比率，搜索空间为备选交易规则 <span class=\"math inline\">\\(R\\)</span>。",
        "其中 <span class=\"math inline\">\\(j=I+1,\\ldots,J\\)</span> 的均值， <span class=\"math inline\">\\(\\operatorname{Me}_{\\Omega}[\\cdot]\\)</span> 是中位数。": "其中 <span class=\"math inline\">\\(j=I+1,\\ldots,J\\)</span>，且 <span class=\"math inline\">\\(\\operatorname{Me}_{\\Omega}[\\cdot]\\)</span> 是中位数。",
        "取 <span class=\"math inline\">\\(\\underline{\\pi}=\\{-\\frac{1}{2}\\sigma,-\\sigma,\\ldots,-10\\sigma\\}\\)</span> 的均值， <span class=\"math inline\">\\(\\bar{\\pi}=\\{\\frac{1}{2}\\sigma,\\sigma,\\ldots,10\\sigma\\}\\)</span> 的笛卡尔积可得 20×20 个节点": "取 <span class=\"math inline\">\\(\\underline{\\pi}=\\{-\\frac{1}{2}\\sigma,-\\sigma,\\ldots,-10\\sigma\\}\\)</span> 和 <span class=\"math inline\">\\(\\bar{\\pi}=\\{\\frac{1}{2}\\sigma,\\sigma,\\ldots,10\\sigma\\}\\)</span> 的笛卡尔积可得 20×20 个节点",
        "其中 <span class=\"math inline\">\\(\\mathbb{E}_0[P_{i,T_i}]=10\\)</span> 的均值， <span class=\"math inline\">\\(\\tau\\)</span> 从5增至100。": "其中 <span class=\"math inline\">\\(\\mathbb{E}_0[P_{i,T_i}]=10\\)</span>，且 <span class=\"math inline\">\\(\\tau\\)</span> 从 5 增至 100。",
    }
    for src, dst in replacements.items():
        html = html.replace(src, dst)
    return html


def fix_chapter_16(html: str) -> str:
    # The source encodes note 1 as a literal digit and separates note 2's
    # lead-in from its links. Normalize both before collecting endnotes.
    html = html.replace(
        "本章介绍分层风险平价（Hierarchical Risk Parity，HRP）方法。HRP 组合",
        "本章介绍分层风险平价（Hierarchical Risk Parity，HRP）方法。<sup>1</sup>HRP 组合",
        1,
    )
    html = html.replace(
        '<p>2 更多距离度量参见：</p>\n<p class="footnote"><sup>2</sup> ',
        '<p class="footnote"><sup>2</sup> 更多距离度量参见：',
        1,
    )
    return html


def fix_chapter_20(html: str) -> str:
    html = html.replace(
        '<span class="math inline">\\(r_1\\)</span>其中 <span class="math inline">\\(r_{m-1}=r_0=0\\)</span>',
        '<span class="math inline">\\(r_1\\)</span>，其中 <span class="math inline">\\(r_{m-1}=r_0=0\\)</span>',
        1,
    )
    html = html.replace(
        '<code>joblib</code>，<sup>2</sup>后者',
        '<code>joblib</code><sup>2</sup>，后者',
        1,
    )
    return html


def fix_chapter_22_image_alts(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    labels = {
        "media/chapter-22-figure-22-6-ab.png": "图 22.6（a）（b）：GTB 与 LTAP 对照组的基线用电量预测",
        "media/chapter-22-figure-22-6-cd.png": "图 22.6（c）（d）：GTB 与 LTAP 被动组的基线用电量预测",
        "media/chapter-22-figure-22-6-ef.png": "图 22.6（e）（f）：GTB 与 LTAP 主动组的基线用电量预测",
    }
    for img in soup.select("figure.chapter-22-figure-6 img[src]"):
        src = str(img.get("src", ""))
        if src in labels:
            img["alt"] = labels[src]
    return str(soup)


def set_inner_html(tag: Tag, html: str) -> None:
    tag.clear()
    fragment = BeautifulSoup(html, "html.parser")
    for child in list(fragment.contents):
        tag.append(child)


def normalize_zh_figure_captions(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for caption in soup.select("figure.book-figure figcaption, figure.cpcv-figure figcaption"):
        text = caption.get_text(" ", strip=True)
        match = re.match(r"图\s*(\d+\.\d+)", text)
        if not match:
            continue
        number = match.group(1)
        if number.startswith("13.") and "热力图" not in text:
            math = caption.select_one("span.math.inline")
            if math is not None:
                set_inner_html(caption, f"图 {number}：热力图，参数为 {math}")
                continue
        replacement = ZH_FIGURE_CAPTION_HTML.get(number)
        if replacement:
            set_inner_html(caption, replacement)
    return str(soup)


def finalize_html(html: str, page_name: str) -> str:
    html = remove_excluded_page_links(html)
    html = normalize_front_matter_labels(html)
    if page_name == "front-matter.html":
        html = sync_front_matter_navigation(html)
    if page_name == "index.html":
        html = sync_index_labels(html)
    if page_name == "chapter-01.html":
        html = fix_chapter_01(html)
    if page_name == "chapter-02.html":
        html = fix_chapter_02(html)
    if page_name == "chapter-03.html":
        html = fix_chapter_03(html)
    if page_name == "chapter-05.html":
        html = fix_chapter_05(html)
    if page_name == "chapter-08.html":
        html = fix_chapter_08(html)
    if page_name == "chapter-10.html":
        html = fix_chapter_10(html)
    if page_name == "chapter-11.html":
        html = fix_chapter_11(html)
    if page_name == "chapter-12.html":
        html = fix_chapter_12(html)
    if page_name == "chapter-13.html":
        html = fix_chapter_13(html)
    if page_name == "chapter-16.html":
        html = fix_chapter_16(html)
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
        html = fix_chapter_18_domain(html)
    if page_name == "chapter-19.html":
        html = fix_chapter_19(html)
    if page_name == "chapter-21.html":
        html = fix_chapter_21(html)
    html = normalize_formula_join_artifacts(html)
    if page_name == "chapter-08.html":
        html = fix_chapter_08(html)
    if page_name == "chapter-12.html":
        html = fix_chapter_12(html)
    if page_name == "chapter-21.html":
        html = fix_chapter_21(html)
    html = normalize_translation_artifacts(html)
    if page_name == "chapter-13.html":
        html = fix_chapter_13(html)
    if page_name == "chapter-16.html":
        html = fix_chapter_16(html)
    if page_name == "chapter-20.html":
        html = fix_chapter_20(html)
    html = normalize_zh_figure_captions(html)
    if page_name == "chapter-22.html":
        html = fix_chapter_22_image_alts(html)
    html = move_footnotes_to_endnotes(html, page_name)
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
html[lang="zh-CN"] body.cover-page article {
  max-width: 34rem;
  text-align: center;
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
html[lang="zh-CN"] sup.footnote-ref {
  font-size: 0.72em;
  line-height: 0;
}
html[lang="zh-CN"] sup.footnote-ref a {
  color: var(--link);
  text-decoration: none;
}
html[lang="zh-CN"] .footnotes {
  margin: 2.5rem 0 1.75rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.9rem;
}
html[lang="zh-CN"] .footnotes-heading {
  margin-bottom: 0.5rem;
  color: var(--ink);
  font-size: 0.95rem;
  font-weight: 650;
}
html[lang="zh-CN"] .footnotes-list {
  margin: 0;
  padding-left: 1.25rem;
}
html[lang="zh-CN"] .footnote-item,
html[lang="zh-CN"] .footnote-item li {
  font-size: 0.9rem;
  line-height: 1.58;
}
html[lang="zh-CN"] .footnote-backref {
  color: var(--muted);
  font-size: 0.86rem;
  text-decoration: none;
}
html[lang="zh-CN"] body.cover-page .chapter-header {
  text-align: center;
}
html[lang="zh-CN"] body.cover-page .book-cover {
  margin: 0 auto 1.5rem;
}
html[lang="zh-CN"] body.cover-page .book-cover img {
  max-width: min(100%, 24rem);
}
html[lang="zh-CN"] body.cover-page .chapter-pager {
  justify-content: center;
}
html[lang="zh-CN"] .book-figure figcaption,
html[lang="zh-CN"] figure.table-figure figcaption {
  margin-top: 0.75rem;
  color: var(--muted);
  font-size: 0.92rem;
  font-weight: 500;
  line-height: 1.55;
}
html[lang="zh-CN"] .book-figure figcaption {
  text-align: center;
}
html[lang="zh-CN"] figure.table-figure figcaption,
html[lang="zh-CN"] figure.code-listing figcaption {
  color: var(--ink);
  font-size: 0.95rem;
  font-weight: 650;
  line-height: 1.5;
  text-align: left;
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
    pages = [page for page in sorted(BOOK.glob("*.html")) if page.name not in EXCLUDED_PAGES]
    if args.pages:
        wanted = set(args.pages)
        pages = [page for page in pages if page.name in wanted or page.stem in wanted]
    if args.limit_pages:
        pages = pages[: args.limit_pages]
    chapter_overrides = load_chapter_overrides(chapters={page.stem for page in pages})

    all_units: dict[str, Unit] = {}
    soups: dict[Path, BeautifulSoup] = {}
    for page in pages:
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        soups[page] = soup
        page_cache = cache.copy()
        page_cache.update(chapter_overrides.get(page.stem, {}))
        for unit in collect_units(soup, page_cache):
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
        page_cache = cache.copy()
        page_cache.update(chapter_overrides.get(page.stem, {}))
        apply_cache_to_soup(soup, page_cache)
        (ZH / page.name).write_text(finalize_html(str(soup), page.name), encoding="utf-8")

    (ROOT / "index.html").write_text(
        """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="theme-color" content="#0f1318">
    <meta name="color-scheme" content="dark light">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="AFML 中文">
    <link rel="manifest" href="manifest.webmanifest">
    <link rel="icon" type="image/png" sizes="192x192" href="assets/icons/pwa-192.png">
    <link rel="apple-touch-icon" sizes="180x180" href="assets/icons/apple-touch-icon.png">
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
