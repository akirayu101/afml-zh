const THEME_STORAGE_KEY = "afml-theme";
const THEME_DARK = "dark";
const THEME_LIGHT = "light";
let activeTheme = THEME_DARK;

const safeReadTheme = () => {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
};

const safeWriteTheme = theme => {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Ignore storage failures; the button still works for this page view.
  }
};

const themeLabels = () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");
  return {
    dark: isZh ? "深色" : "Dark",
    light: isZh ? "浅色" : "Light",
    label: isZh ? "切换深色/浅色模式" : "Toggle light and dark mode",
  };
};

const updateThemeToggle = button => {
  if (!button) return;
  const labels = themeLabels();
  button.textContent = activeTheme === THEME_DARK ? labels.dark : labels.light;
  button.setAttribute("aria-label", labels.label);
  button.setAttribute("aria-checked", String(activeTheme === THEME_DARK));
};

const applyTheme = theme => {
  activeTheme = theme === THEME_LIGHT ? THEME_LIGHT : THEME_DARK;
  document.documentElement.dataset.theme = activeTheme;
  updateThemeToggle(document.querySelector(".theme-toggle"));
};

applyTheme(safeReadTheme());

const installThemeToggle = () => {
  const nav = document.querySelector(".book-topbar nav");
  if (!nav || nav.querySelector(".theme-toggle")) return;
  const button = document.createElement("button");
  button.className = "theme-toggle";
  button.type = "button";
  button.setAttribute("role", "switch");
  button.addEventListener("click", () => {
    const nextTheme = activeTheme === THEME_DARK ? THEME_LIGHT : THEME_DARK;
    applyTheme(nextTheme);
    safeWriteTheme(nextTheme);
  });
  nav.appendChild(button);
  updateThemeToggle(button);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", installThemeToggle);
} else {
  installThemeToggle();
}

const NOTES_STORAGE_KEY = "afml-reader-notes";
const NOTES_SAVE_DELAY_MS = 450;
let notesSaveTimer = 0;

const noteLabels = () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");
  return {
    locale: isZh ? "zh-CN" : "en",
    open: isZh ? "笔记" : "Notes",
    openLabel: isZh ? "打开读书笔记" : "Open reading notes",
    panel: isZh ? "读书笔记" : "Reading Notes",
    close: isZh ? "关闭" : "Close",
    current: isZh ? "本章笔记" : "Chapter note",
    savedNotes: isZh ? "已保存笔记" : "Saved notes",
    noNotes: isZh ? "暂无笔记" : "No notes yet",
    emptyStatus: isZh ? "未保存" : "Not saved",
    saving: isZh ? "保存中" : "Saving",
    saved: isZh ? "已保存" : "Saved",
    failed: isZh ? "无法保存" : "Unable to save",
    copy: isZh ? "复制" : "Copy",
    copied: isZh ? "已复制" : "Copied",
    export: isZh ? "导出" : "Export",
    clear: isZh ? "清空" : "Clear",
    cleared: isZh ? "已清空" : "Cleared",
    clearConfirm: isZh ? "清空本章笔记？" : "Clear this chapter note?",
    exportTitle: isZh ? "AFML 读书笔记" : "AFML Reading Notes",
    page: isZh ? "页面" : "Page",
    updated: isZh ? "更新" : "Updated",
    untitled: isZh ? "本页" : "Untitled page",
  };
};

const notePageKey = () => location.pathname.replace(/\/$/, "/index.html");

const readNotesStore = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(NOTES_STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
};

const writeNotesStore = notes => {
  try {
    localStorage.setItem(NOTES_STORAGE_KEY, JSON.stringify(notes));
    return true;
  } catch {
    return false;
  }
};

const currentNoteTitle = labels => {
  const heading = document.querySelector("h1");
  return (heading && heading.textContent.trim()) || document.title || labels.untitled;
};

const formatNoteTime = (iso, labels) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(labels.locale, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const writeClipboardText = async text => {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
};

const noteStoreEntries = notes => Object.values(notes)
  .filter(note => note && typeof note.text === "string" && note.text.trim())
  .sort((left, right) => (right.updatedAt || "").localeCompare(left.updatedAt || ""));

const notesToMarkdown = (notes, labels) => {
  const entries = noteStoreEntries(notes);
  const chunks = [`# ${labels.exportTitle}`];
  for (const note of entries) {
    chunks.push([
      `## ${note.title || labels.untitled}`,
      "",
      `- ${labels.page}: ${note.url || ""}`,
      `- ${labels.updated}: ${formatNoteTime(note.updatedAt, labels)}`,
      "",
      note.text.trim(),
    ].join("\n"));
  }
  return `${chunks.join("\n\n")}\n`;
};

const renderNotesList = (container, labels) => {
  const entries = noteStoreEntries(readNotesStore());
  container.textContent = "";
  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "reader-notes-empty";
    empty.textContent = labels.noNotes;
    container.appendChild(empty);
    return;
  }
  for (const note of entries) {
    const item = document.createElement("article");
    item.className = "reader-notes-entry";
    const link = document.createElement("a");
    link.href = note.url || "#";
    link.textContent = note.title || labels.untitled;
    const time = document.createElement("time");
    if (note.updatedAt) time.dateTime = note.updatedAt;
    time.textContent = formatNoteTime(note.updatedAt, labels);
    const excerpt = document.createElement("p");
    excerpt.textContent = note.text.trim().replace(/\s+/g, " ").slice(0, 140);
    item.append(link, time, excerpt);
    container.appendChild(item);
  }
};

const installReaderNotes = () => {
  const nav = document.querySelector(".book-topbar nav");
  if (!nav || nav.querySelector("[data-reader-notes='toggle']")) return;
  const labels = noteLabels();
  const pageKey = notePageKey();

  const toggle = document.createElement("button");
  toggle.className = "notes-toggle";
  toggle.type = "button";
  toggle.dataset.readerNotes = "toggle";
  toggle.textContent = labels.open;
  toggle.setAttribute("aria-label", labels.openLabel);
  toggle.setAttribute("aria-expanded", "false");
  nav.appendChild(toggle);

  const panel = document.createElement("aside");
  panel.className = "reader-notes-panel";
  panel.dataset.readerNotes = "panel";
  panel.hidden = true;
  panel.setAttribute("aria-label", labels.panel);

  const header = document.createElement("div");
  header.className = "reader-notes-header";
  const title = document.createElement("h2");
  title.className = "reader-notes-title";
  title.textContent = labels.panel;
  const status = document.createElement("span");
  status.className = "reader-notes-status";
  const close = document.createElement("button");
  close.className = "reader-notes-close";
  close.type = "button";
  close.textContent = "x";
  close.setAttribute("aria-label", labels.close);
  header.append(title, status, close);

  const body = document.createElement("div");
  body.className = "reader-notes-body";
  const noteLabel = document.createElement("label");
  noteLabel.className = "reader-notes-label";
  noteLabel.textContent = labels.current;
  const textarea = document.createElement("textarea");
  textarea.className = "reader-notes-textarea";
  textarea.rows = 10;
  textarea.spellcheck = true;
  textarea.setAttribute("aria-label", labels.current);
  noteLabel.appendChild(textarea);

  const actions = document.createElement("div");
  actions.className = "reader-notes-actions";
  const copy = document.createElement("button");
  copy.className = "reader-notes-command";
  copy.type = "button";
  copy.textContent = labels.copy;
  const exportNotes = document.createElement("button");
  exportNotes.className = "reader-notes-command";
  exportNotes.type = "button";
  exportNotes.textContent = labels.export;
  const clear = document.createElement("button");
  clear.className = "reader-notes-command";
  clear.type = "button";
  clear.textContent = labels.clear;
  actions.append(copy, exportNotes, clear);

  const listTitle = document.createElement("h3");
  listTitle.className = "reader-notes-list-title";
  listTitle.textContent = labels.savedNotes;
  const list = document.createElement("div");
  list.className = "reader-notes-list";
  body.append(noteLabel, actions, listTitle, list);
  panel.append(header, body);
  document.body.appendChild(panel);

  const setPanelOpen = open => {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    if (open) textarea.focus();
  };

  const updateToggleState = () => {
    toggle.classList.toggle("has-notes", Boolean(textarea.value.trim()));
  };

  const saveCurrentNote = () => {
    const notes = readNotesStore();
    const text = textarea.value.trimEnd();
    if (text.trim()) {
      notes[pageKey] = {
        key: pageKey,
        title: currentNoteTitle(labels),
        url: location.href.split("#")[0],
        text,
        updatedAt: new Date().toISOString(),
      };
    } else {
      delete notes[pageKey];
    }
    status.textContent = writeNotesStore(notes) ? (text.trim() ? labels.saved : labels.emptyStatus) : labels.failed;
    renderNotesList(list, labels);
    updateToggleState();
  };

  const refreshCurrentNote = () => {
    const note = readNotesStore()[pageKey];
    textarea.value = note && typeof note.text === "string" ? note.text : "";
    status.textContent = textarea.value.trim() ? labels.saved : labels.emptyStatus;
    renderNotesList(list, labels);
    updateToggleState();
  };

  textarea.addEventListener("input", () => {
    window.clearTimeout(notesSaveTimer);
    status.textContent = textarea.value.trim() ? labels.saving : labels.emptyStatus;
    notesSaveTimer = window.setTimeout(saveCurrentNote, NOTES_SAVE_DELAY_MS);
    updateToggleState();
  });
  toggle.addEventListener("click", () => setPanelOpen(panel.hidden));
  close.addEventListener("click", () => setPanelOpen(false));
  copy.addEventListener("click", async () => {
    if (!textarea.value.trim()) return;
    const previous = copy.textContent;
    await writeClipboardText(textarea.value);
    copy.textContent = labels.copied;
    window.setTimeout(() => {
      copy.textContent = previous || labels.copy;
    }, 1200);
  });
  exportNotes.addEventListener("click", () => {
    const notes = readNotesStore();
    if (!noteStoreEntries(notes).length) return;
    const blob = new Blob([notesToMarkdown(notes, labels)], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `afml-reading-notes-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  });
  clear.addEventListener("click", () => {
    if (!textarea.value.trim() || !window.confirm(labels.clearConfirm)) return;
    textarea.value = "";
    saveCurrentNote();
    status.textContent = labels.cleared;
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !panel.hidden) setPanelOpen(false);
  });
  window.addEventListener("beforeunload", () => {
    if (notesSaveTimer) {
      window.clearTimeout(notesSaveTimer);
      saveCurrentNote();
    }
  });
  window.addEventListener("storage", event => {
    if (event.key === NOTES_STORAGE_KEY) refreshCurrentNote();
  });
  refreshCurrentNote();
};

// Selection-scoped notes are installed below. The older chapter-wide note panel
// stays unused so existing localStorage data is not destroyed.

const CODEX_SELECTION_LIMIT = 2200;
const CODEX_APP_PROJECT_PATH = "D:/code/github/afml-zh";
let codexSelectionTimer = 0;

const isGithubPagesHost = hostname => hostname === "github.io" || hostname.endsWith(".github.io");

const codexAppEnabled = () => {
  if (isGithubPagesHost(location.hostname)) return false;
  if (typeof window.AFML_CODEX_APP_ENABLED === "boolean") return window.AFML_CODEX_APP_ENABLED;
  return true;
};

const codexSelectionLabels = () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");
  return {
    ask: isZh ? "问 Codex" : "Ask Codex",
    askLabel: isZh ? "用所选文字向 Codex 提问" : "Ask Codex about the selected text",
    panel: isZh ? "问 Codex" : "Ask Codex",
    close: isZh ? "关闭" : "Close",
    selectedText: isZh ? "选中文字" : "Selected text",
    question: isZh ? "问题" : "Question",
    placeholder: isZh ? "你想问这段文字的什么？" : "What do you want to ask about this passage?",
    open: isZh ? "打开 Codex" : "Open Codex",
    copyPrompt: isZh ? "复制提示词" : "Copy prompt",
    copied: isZh ? "已复制提示词" : "Prompt copied",
    opening: isZh ? "已复制提示词，并尝试打开 Codex。" : "Prompt copied. Opening Codex.",
    fallback: isZh ? "如果浏览器没有打开 Codex，请直接粘贴已复制的提示词。" : "If Codex did not open, paste the copied prompt manually.",
    defaultQuestion: isZh ? "请解释这段话，并指出我应该重点理解什么。" : "Please explain this passage and identify what I should understand first.",
    instruction: isZh
      ? "请基于下面《金融机器学习进阶》网页摘录回答我的问题。回答时先解释关键概念，再结合本书上下文说明含义。"
      : "Answer my question using the excerpt below from Advances in Financial Machine Learning. Explain the key concept first, then connect it to the book context.",
    pageTitle: isZh ? "页面标题" : "Page title",
    pageUrl: isZh ? "页面链接" : "Page URL",
    myQuestion: isZh ? "我的问题" : "My question",
    truncated: isZh ? "[选区较长，已截断]" : "[Selection was long and has been truncated]",
  };
};

const cleanSelectedText = text => text
  .replace(/\r\n/g, "\n")
  .replace(/\n{3,}/g, "\n\n")
  .trim();

const elementFromNode = node => {
  if (!node) return null;
  return node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
};

const isIgnoredSelectionElement = element => Boolean(element && element.closest(
  "input, textarea, button, nav, .reader-notes-panel, .codex-selection-dialog, .codex-selection-button, .selection-note-dialog, .selection-note-button"
));

const currentPageHeading = labels => {
  const heading = document.querySelector("h1");
  return (heading && heading.textContent.trim()) || document.title || labels.pageTitle;
};

const normalizeSelectionNoteText = text => cleanSelectedText(String(text || "")).replace(/\s+/g, " ");

const selectionNoteTextNodes = article => {
  const nodes = [];
  const ignoredSelector = [
    "script",
    "style",
    "textarea",
    "input",
    "button",
    "nav",
    "pre",
    "code",
    "mjx-container",
    ".MathJax",
    ".reader-notes-panel",
    ".codex-selection-dialog",
  ].join(",");
  const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || !node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      return parent.closest(ignoredSelector) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    },
  });
  let node = walker.nextNode();
  while (node) {
    nodes.push(node);
    node = walker.nextNode();
  }
  return nodes;
};

const selectionNoteTextIndex = article => {
  const map = [];
  let text = "";
  let sawWhitespace = false;
  for (const node of selectionNoteTextNodes(article)) {
    const value = node.nodeValue || "";
    for (let offset = 0; offset < value.length; offset += 1) {
      const char = value[offset];
      if (/\s/.test(char)) {
        if (!sawWhitespace) {
          text += " ";
          map.push({ node, offset });
          sawWhitespace = true;
        }
      } else {
        text += char;
        map.push({ node, offset });
        sawWhitespace = false;
      }
    }
  }
  return { text, map };
};

const selectionNoteQuoteIndex = (article, range, quote) => {
  const normalizedQuote = normalizeSelectionNoteText(quote);
  if (!normalizedQuote) return -1;
  const { text } = selectionNoteTextIndex(article);
  const beforeRange = range.cloneRange();
  beforeRange.selectNodeContents(article);
  beforeRange.setEnd(range.startContainer, range.startOffset);
  const beforeLength = normalizeSelectionNoteText(beforeRange.toString()).length;
  const nearbyStart = Math.max(0, beforeLength - 8);
  const nearbyMatch = text.indexOf(normalizedQuote, nearbyStart);
  if (nearbyMatch >= 0 && nearbyMatch <= beforeLength + 8) return nearbyMatch;
  return text.indexOf(normalizedQuote);
};

const codexWorkspacePath = () => {
  const configured = window.AFML_CODEX_PROJECT_PATH || window.AFML_CODEX_WORKSPACE_PATH || CODEX_APP_PROJECT_PATH;
  return typeof configured === "string" ? configured.trim() : "";
};

const selectedArticleText = labels => {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
  const article = document.querySelector("article");
  if (!article) return null;

  const range = selection.getRangeAt(0);
  const startElement = elementFromNode(range.startContainer);
  const endElement = elementFromNode(range.endContainer);
  if (!startElement || !endElement || !article.contains(startElement) || !article.contains(endElement)) return null;
  if (isIgnoredSelectionElement(startElement) || isIgnoredSelectionElement(endElement)) return null;

  const fullText = cleanSelectedText(selection.toString());
  if (fullText.replace(/\s+/g, "").length < 2) return null;
  const rects = [...range.getClientRects()].filter(rect => rect.width > 0 && rect.height > 0);
  const rect = rects[0] || range.getBoundingClientRect();
  if (!rect || (rect.width === 0 && rect.height === 0)) return null;
  const wasTruncated = fullText.length > CODEX_SELECTION_LIMIT;
  const text = wasTruncated ? fullText.slice(0, CODEX_SELECTION_LIMIT).trimEnd() : fullText;
  const quoteIndex = selectionNoteQuoteIndex(article, range, text);
  return { text, wasTruncated, rect, quoteIndex, title: currentPageHeading(labels), url: location.href.split("#")[0] };
};

const buildCodexPrompt = (selectionData, question, labels) => {
  const excerpt = selectionData.wasTruncated
    ? `${selectionData.text}\n${labels.truncated}`
    : selectionData.text;
  const promptQuestion = question.trim() || labels.defaultQuestion;
  return [
    labels.instruction,
    "",
    `${labels.pageTitle}: ${selectionData.title}`,
    `${labels.pageUrl}: ${selectionData.url}`,
    "",
    `${labels.selectedText}:`,
    "<<<",
    excerpt,
    ">>>",
    "",
    `${labels.myQuestion}: ${promptQuestion}`,
  ].join("\n");
};

const codexDeepLinkForPrompt = prompt => {
  const params = new URLSearchParams({ prompt });
  const workspacePath = codexWorkspacePath();
  if (workspacePath) params.set("path", workspacePath);
  return `codex://new?${params.toString()}`;
};

const openCodexLink = href => {
  const link = document.createElement("a");
  link.href = href;
  link.rel = "noreferrer";
  document.body.appendChild(link);
  link.click();
  link.remove();
};

const positionCodexSelectionButton = (button, rect, slot = 0) => {
  const margin = 8;
  const gap = 8;
  const buttonWidth = button.offsetWidth || 108;
  const buttonHeight = button.offsetHeight || 32;
  const centeredLeft = rect.left + rect.width / 2 - buttonWidth / 2 + slot * (buttonWidth + gap);
  const maxLeft = Math.max(margin, window.innerWidth - buttonWidth - margin);
  const left = Math.min(Math.max(centeredLeft, margin), maxLeft);
  const below = rect.bottom + margin;
  const top = below + buttonHeight + margin <= window.innerHeight
    ? below
    : Math.max(margin, rect.top - buttonHeight - margin);
  button.style.left = `${Math.round(left)}px`;
  button.style.top = `${Math.round(top)}px`;
};

const createCodexSelectionDialog = labels => {
  const panel = document.createElement("aside");
  panel.className = "codex-selection-dialog";
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", labels.panel);

  const header = document.createElement("div");
  header.className = "codex-selection-header";
  const title = document.createElement("h2");
  title.className = "codex-selection-title";
  title.textContent = labels.panel;
  const close = document.createElement("button");
  close.className = "codex-selection-close";
  close.type = "button";
  close.textContent = "x";
  close.setAttribute("aria-label", labels.close);
  header.append(title, close);

  const body = document.createElement("div");
  body.className = "codex-selection-body";
  const excerptLabel = document.createElement("p");
  excerptLabel.className = "codex-selection-label";
  excerptLabel.textContent = labels.selectedText;
  const excerpt = document.createElement("blockquote");
  excerpt.className = "codex-selection-excerpt";

  const questionLabel = document.createElement("label");
  questionLabel.className = "codex-selection-label";
  questionLabel.textContent = labels.question;
  const question = document.createElement("textarea");
  question.className = "codex-selection-question";
  question.rows = 5;
  question.placeholder = labels.placeholder;
  question.spellcheck = true;
  question.setAttribute("aria-label", labels.question);
  questionLabel.appendChild(question);

  const actions = document.createElement("div");
  actions.className = "codex-selection-actions";
  const open = document.createElement("button");
  open.className = "codex-selection-command primary";
  open.type = "button";
  open.textContent = labels.open;
  const copy = document.createElement("button");
  copy.className = "codex-selection-command";
  copy.type = "button";
  copy.textContent = labels.copyPrompt;
  actions.append(open, copy);

  const status = document.createElement("span");
  status.className = "codex-selection-status";
  body.append(excerptLabel, excerpt, questionLabel, actions, status);
  panel.append(header, body);
  document.body.appendChild(panel);
  return { panel, excerpt, question, status, open, copy, close };
};

const installCodexSelectionPrompt = () => {
  if (!codexAppEnabled()) return;
  const article = document.querySelector("article");
  if (!article || document.querySelector("[data-codex-selection='ask']")) return;
  const labels = codexSelectionLabels();
  let selectionData = null;

  const button = document.createElement("button");
  button.className = "codex-selection-button";
  button.type = "button";
  button.hidden = true;
  button.setAttribute("data-codex-selection", "ask");
  button.textContent = labels.ask;
  button.setAttribute("aria-label", labels.askLabel);
  document.body.appendChild(button);

  const dialog = createCodexSelectionDialog(labels);

  const hideButton = () => {
    button.hidden = true;
  };

  const refreshSelectionButton = () => {
    if (!dialog.panel.hidden) return;
    selectionData = selectedArticleText(labels);
    if (!selectionData) {
      hideButton();
      return;
    }
    button.hidden = false;
    positionCodexSelectionButton(button, selectionData.rect);
  };

  const scheduleSelectionRefresh = () => {
    window.clearTimeout(codexSelectionTimer);
    codexSelectionTimer = window.setTimeout(refreshSelectionButton, 80);
  };

  const closeDialog = () => {
    dialog.panel.hidden = true;
    dialog.status.textContent = "";
    scheduleSelectionRefresh();
  };

  const promptFromDialog = () => {
    if (!selectionData) return "";
    return buildCodexPrompt(selectionData, dialog.question.value, labels);
  };

  const copyDialogPrompt = async message => {
    const prompt = promptFromDialog();
    if (!prompt) return;
    await writeClipboardText(prompt);
    dialog.status.textContent = message;
  };

  const openCodexPrompt = async () => {
    const prompt = promptFromDialog();
    if (!prompt) return;
    await writeClipboardText(prompt);
    openCodexLink(codexDeepLinkForPrompt(prompt));
    dialog.status.textContent = labels.opening;
    window.setTimeout(() => {
      if (!dialog.panel.hidden) dialog.status.textContent = labels.fallback;
    }, 1500);
  };

  button.addEventListener("mousedown", event => {
    event.preventDefault();
  });
  button.addEventListener("click", () => {
    selectionData = selectedArticleText(labels) || selectionData;
    if (!selectionData) return;
    hideButton();
    dialog.excerpt.textContent = selectionData.wasTruncated
      ? `${selectionData.text}\n${labels.truncated}`
      : selectionData.text;
    dialog.question.value = "";
    dialog.status.textContent = "";
    dialog.panel.hidden = false;
    dialog.question.focus();
  });
  dialog.close.addEventListener("click", closeDialog);
  dialog.copy.addEventListener("click", () => copyDialogPrompt(labels.copied));
  dialog.open.addEventListener("click", openCodexPrompt);
  dialog.question.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      openCodexPrompt();
    }
  });
  document.addEventListener("selectionchange", scheduleSelectionRefresh);
  document.addEventListener("mouseup", scheduleSelectionRefresh);
  document.addEventListener("touchend", scheduleSelectionRefresh);
  document.addEventListener("keyup", event => {
    if (event.key === "Escape") {
      if (!dialog.panel.hidden) closeDialog();
      hideButton();
      return;
    }
    scheduleSelectionRefresh();
  });
  window.addEventListener("scroll", () => {
    if (!button.hidden) refreshSelectionButton();
  }, { passive: true });
  window.addEventListener("resize", scheduleSelectionRefresh);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", installCodexSelectionPrompt);
} else {
  installCodexSelectionPrompt();
}

const SELECTION_NOTES_STORAGE_KEY = "afml-selection-notes";
const SELECTION_NOTE_SAVE_DELAY_MS = 450;
let selectionNoteTimer = 0;
let selectionNoteSaveTimer = 0;

const selectionNoteLabels = () => {
  const isZh = document.documentElement.lang.toLowerCase().startsWith("zh");
  return {
    locale: isZh ? "zh-CN" : "en",
    add: isZh ? "记笔记" : "Note",
    addLabel: isZh ? "给选中文字添加笔记" : "Add a note to the selected text",
    openSaved: isZh ? "打开这条划词笔记" : "Open this selection note",
    panel: isZh ? "划词笔记" : "Selection Note",
    close: isZh ? "关闭" : "Close",
    selectedText: isZh ? "选中文字" : "Selected text",
    note: isZh ? "笔记" : "Note",
    placeholder: isZh ? "记录你对这段文字的理解、疑问或延伸想法..." : "Record your takeaways, questions, or follow-up thoughts...",
    save: isZh ? "保存" : "Save",
    saving: isZh ? "保存中" : "Saving",
    saved: isZh ? "已保存" : "Saved",
    empty: isZh ? "未保存" : "Not saved",
    failed: isZh ? "无法保存" : "Unable to save",
    copyQuote: isZh ? "复制原文" : "Copy quote",
    copied: isZh ? "已复制" : "Copied",
    export: isZh ? "导出全部" : "Export all",
    delete: isZh ? "删除此条" : "Delete",
    deleted: isZh ? "已删除" : "Deleted",
    deleteConfirm: isZh ? "删除这条划词笔记？" : "Delete this selection note?",
    exportTitle: isZh ? "AFML 划词笔记" : "AFML Selection Notes",
    pageUrl: isZh ? "页面链接" : "Page URL",
    quote: isZh ? "原文" : "Quote",
    updated: isZh ? "更新" : "Updated",
    untitled: isZh ? "本页" : "Untitled page",
    none: isZh ? "暂无划词笔记" : "No selection notes yet",
    truncated: isZh ? "[选区较长，已截断]" : "[Selection was long and has been truncated]",
  };
};

const selectionNotesPageKey = () => location.pathname.replace(/\/$/, "/index.html");

const readSelectionNotes = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(SELECTION_NOTES_STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
};

const writeSelectionNotes = notes => {
  try {
    localStorage.setItem(SELECTION_NOTES_STORAGE_KEY, JSON.stringify(notes));
    return true;
  } catch {
    return false;
  }
};

const selectionNoteHash = text => {
  let hash = 2166136261;
  for (const char of text) {
    hash ^= char.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
};

const selectionNoteEntries = notes => Object.values(notes)
  .filter(note => note && typeof note.note === "string" && note.note.trim())
  .sort((left, right) => (right.updatedAt || "").localeCompare(left.updatedAt || ""));

const formatSelectionNoteTime = (iso, labels) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(labels.locale, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const selectionNotesToMarkdown = (notes, labels) => {
  const nl = String.fromCharCode(10);
  const chunks = [`# ${labels.exportTitle}`];
  for (const note of selectionNoteEntries(notes)) {
    chunks.push([
      `## ${note.title || labels.untitled}`,
      "",
      `- ${labels.pageUrl}: ${note.url || ""}`,
      `- ${labels.updated}: ${formatSelectionNoteTime(note.updatedAt, labels)}`,
      "",
      `${labels.quote}:`,
      "> " + (note.quote || "").split(/\r?\n/).join(`${nl}> `),
      "",
      note.note.trim(),
    ].join(nl));
  }
  return `${chunks.join(nl + nl)}${nl}`;
};

const selectionDataForNote = labels => {
  const data = selectedArticleText({ pageTitle: labels.untitled });
  if (!data) return null;
  const pageKey = selectionNotesPageKey();
  return {
    ...data,
    pageKey,
    id: `${pageKey}#${selectionNoteHash(data.text)}`,
  };
};

const pageSelectionNoteEntries = notes => {
  const pageKey = selectionNotesPageKey();
  return selectionNoteEntries(notes).filter(note => note.pageKey === pageKey && note.quote);
};

const clearSelectionNoteHighlights = article => {
  for (const highlight of [...article.querySelectorAll(".selection-note-highlight")]) {
    highlight.replaceWith(document.createTextNode(highlight.textContent || ""));
  }
  article.normalize();
};

const selectionNoteMatchStart = (indexedText, quote, quoteIndex) => {
  const normalizedQuote = normalizeSelectionNoteText(quote);
  if (!normalizedQuote) return -1;
  const preferredIndex = Number.isFinite(quoteIndex) ? Number(quoteIndex) : -1;
  if (preferredIndex >= 0) {
    const exact = indexedText.indexOf(normalizedQuote, preferredIndex);
    if (exact === preferredIndex) return exact;
    const windowStart = Math.max(0, preferredIndex - 120);
    const windowEnd = Math.min(indexedText.length, preferredIndex + normalizedQuote.length + 120);
    const nearby = indexedText.slice(windowStart, windowEnd).indexOf(normalizedQuote);
    if (nearby >= 0) return windowStart + nearby;
  }
  return indexedText.indexOf(normalizedQuote);
};

const selectionNoteSegments = (map, start, length) => {
  const segments = [];
  const end = start + length;
  for (let index = start; index < end; index += 1) {
    const point = map[index];
    if (!point) continue;
    const last = segments[segments.length - 1];
    if (last && last.node === point.node && last.end === point.offset) {
      last.end = point.offset + 1;
    } else {
      segments.push({ node: point.node, start: point.offset, end: point.offset + 1 });
    }
  }
  return segments;
};

const applySelectionNoteHighlight = (article, note, labels) => {
  const normalizedQuote = normalizeSelectionNoteText(note.quote);
  if (!normalizedQuote) return;
  const { text, map } = selectionNoteTextIndex(article);
  const start = selectionNoteMatchStart(text, normalizedQuote, note.quoteIndex);
  if (start < 0) return;
  const segments = selectionNoteSegments(map, start, normalizedQuote.length);
  for (const segment of segments.reverse()) {
    const parent = segment.node.parentNode;
    if (!parent) continue;
    let target = segment.node;
    if (segment.end < target.nodeValue.length) target.splitText(segment.end);
    if (segment.start > 0) target = target.splitText(segment.start);
    const highlight = document.createElement("mark");
    highlight.className = "selection-note-highlight";
    highlight.dataset.selectionNoteId = note.id;
    highlight.tabIndex = 0;
    highlight.setAttribute("role", "button");
    highlight.setAttribute("aria-label", labels.openSaved);
    highlight.title = labels.openSaved;
    target.parentNode.insertBefore(highlight, target);
    highlight.appendChild(target);
  }
};

const refreshSelectionNoteHighlights = labels => {
  const article = document.querySelector("article");
  if (!article) return;
  clearSelectionNoteHighlights(article);
  for (const note of pageSelectionNoteEntries(readSelectionNotes())) {
    applySelectionNoteHighlight(article, note, labels);
  }
};

const createSelectionNoteDialog = labels => {
  const panel = document.createElement("aside");
  panel.className = "codex-selection-dialog selection-note-dialog";
  panel.hidden = true;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", labels.panel);

  const header = document.createElement("div");
  header.className = "codex-selection-header";
  const title = document.createElement("h2");
  title.className = "codex-selection-title";
  title.textContent = labels.panel;
  const close = document.createElement("button");
  close.className = "codex-selection-close";
  close.type = "button";
  close.textContent = "x";
  close.setAttribute("aria-label", labels.close);
  header.append(title, close);

  const body = document.createElement("div");
  body.className = "codex-selection-body";
  const excerptLabel = document.createElement("p");
  excerptLabel.className = "codex-selection-label";
  excerptLabel.textContent = labels.selectedText;
  const excerpt = document.createElement("blockquote");
  excerpt.className = "codex-selection-excerpt";

  const noteLabel = document.createElement("label");
  noteLabel.className = "codex-selection-label";
  noteLabel.textContent = labels.note;
  const note = document.createElement("textarea");
  note.className = "codex-selection-question selection-note-textarea";
  note.rows = 6;
  note.placeholder = labels.placeholder;
  note.spellcheck = true;
  note.setAttribute("aria-label", labels.note);
  noteLabel.appendChild(note);

  const actions = document.createElement("div");
  actions.className = "codex-selection-actions";
  const save = document.createElement("button");
  save.className = "codex-selection-command primary";
  save.type = "button";
  save.textContent = labels.save;
  const copyQuote = document.createElement("button");
  copyQuote.className = "codex-selection-command";
  copyQuote.type = "button";
  copyQuote.textContent = labels.copyQuote;
  const exportNotes = document.createElement("button");
  exportNotes.className = "codex-selection-command";
  exportNotes.type = "button";
  exportNotes.textContent = labels.export;
  const remove = document.createElement("button");
  remove.className = "codex-selection-command";
  remove.type = "button";
  remove.textContent = labels.delete;
  actions.append(save, copyQuote, exportNotes, remove);

  const status = document.createElement("span");
  status.className = "codex-selection-status";
  body.append(excerptLabel, excerpt, noteLabel, actions, status);
  panel.append(header, body);
  document.body.appendChild(panel);
  return { panel, excerpt, note, status, save, copyQuote, exportNotes, remove, close };
};

const installSelectionNotes = () => {
  const article = document.querySelector("article");
  if (!article || document.querySelector(".selection-note-button")) return;
  const labels = selectionNoteLabels();
  let selectionData = null;

  const button = document.createElement("button");
  button.className = "codex-selection-button selection-note-button";
  button.type = "button";
  button.hidden = true;
  button.textContent = labels.add;
  button.setAttribute("aria-label", labels.addLabel);
  document.body.appendChild(button);

  const dialog = createSelectionNoteDialog(labels);

  const hideButton = () => {
    button.hidden = true;
  };

  const refreshSelectionButton = () => {
    if (!dialog.panel.hidden) return;
    selectionData = selectionDataForNote(labels);
    if (!selectionData) {
      hideButton();
      return;
    }
    button.hidden = false;
    positionCodexSelectionButton(button, selectionData.rect, codexAppEnabled() ? 1 : 0);
  };

  const scheduleSelectionRefresh = () => {
    window.clearTimeout(selectionNoteTimer);
    selectionNoteTimer = window.setTimeout(refreshSelectionButton, 80);
  };

  const saveCurrentSelectionNote = () => {
    if (!selectionData) return;
    const notes = readSelectionNotes();
    const text = dialog.note.value.trimEnd();
    if (text.trim()) {
      const existing = notes[selectionData.id];
      notes[selectionData.id] = {
        id: selectionData.id,
        pageKey: selectionData.pageKey,
        title: selectionData.title,
        url: selectionData.url,
        quote: selectionData.text,
        quoteIndex: Number.isFinite(selectionData.quoteIndex) ? selectionData.quoteIndex : (existing?.quoteIndex ?? null),
        note: text,
        createdAt: existing?.createdAt || new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
    } else {
      delete notes[selectionData.id];
    }
    const didWrite = writeSelectionNotes(notes);
    dialog.status.textContent = didWrite ? (text.trim() ? labels.saved : labels.empty) : labels.failed;
    if (didWrite) refreshSelectionNoteHighlights(labels);
  };

  const openDialogForSelection = data => {
    selectionData = data;
    const existing = readSelectionNotes()[selectionData.id];
    const nl = String.fromCharCode(10);
    dialog.excerpt.textContent = selectionData.wasTruncated
      ? `${selectionData.text}${nl}${labels.truncated}`
      : selectionData.text;
    dialog.note.value = existing?.note || "";
    dialog.status.textContent = existing?.note ? labels.saved : labels.empty;
    dialog.panel.hidden = false;
    dialog.note.focus();
  };

  const openDialogForStoredNote = note => {
    selectionData = {
      id: note.id,
      pageKey: note.pageKey || selectionNotesPageKey(),
      title: note.title || currentPageHeading(labels),
      url: note.url || location.href.split("#")[0],
      text: note.quote || "",
      wasTruncated: false,
      quoteIndex: Number.isFinite(note.quoteIndex) ? note.quoteIndex : -1,
    };
    hideButton();
    openDialogForSelection(selectionData);
  };

  const closeDialog = () => {
    if (selectionNoteSaveTimer) {
      window.clearTimeout(selectionNoteSaveTimer);
      saveCurrentSelectionNote();
    }
    dialog.panel.hidden = true;
    dialog.status.textContent = "";
    scheduleSelectionRefresh();
  };

  const exportAllSelectionNotes = () => {
    const notes = readSelectionNotes();
    if (!selectionNoteEntries(notes).length) {
      dialog.status.textContent = labels.none;
      return;
    }
    const blob = new Blob([selectionNotesToMarkdown(notes, labels)], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `afml-selection-notes-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  };

  button.addEventListener("mousedown", event => {
    event.preventDefault();
  });
  button.addEventListener("click", () => {
    selectionData = selectionDataForNote(labels) || selectionData;
    if (!selectionData) return;
    hideButton();
    openDialogForSelection(selectionData);
  });
  dialog.close.addEventListener("click", closeDialog);
  dialog.save.addEventListener("click", saveCurrentSelectionNote);
  dialog.copyQuote.addEventListener("click", async () => {
    if (!selectionData?.text) return;
    await writeClipboardText(selectionData.text);
    dialog.status.textContent = labels.copied;
  });
  dialog.exportNotes.addEventListener("click", exportAllSelectionNotes);
  dialog.remove.addEventListener("click", () => {
    if (!selectionData || !window.confirm(labels.deleteConfirm)) return;
    const notes = readSelectionNotes();
    delete notes[selectionData.id];
    writeSelectionNotes(notes);
    dialog.note.value = "";
    dialog.status.textContent = labels.deleted;
    refreshSelectionNoteHighlights(labels);
  });
  dialog.note.addEventListener("input", () => {
    window.clearTimeout(selectionNoteSaveTimer);
    dialog.status.textContent = dialog.note.value.trim() ? labels.saving : labels.empty;
    selectionNoteSaveTimer = window.setTimeout(saveCurrentSelectionNote, SELECTION_NOTE_SAVE_DELAY_MS);
  });
  dialog.note.addEventListener("keydown", event => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      saveCurrentSelectionNote();
    }
  });
  document.addEventListener("selectionchange", scheduleSelectionRefresh);
  document.addEventListener("mouseup", scheduleSelectionRefresh);
  document.addEventListener("touchend", scheduleSelectionRefresh);
  document.addEventListener("keyup", event => {
    if (event.key === "Escape") {
      if (!dialog.panel.hidden) closeDialog();
      hideButton();
      return;
    }
    scheduleSelectionRefresh();
  });
  window.addEventListener("scroll", () => {
    if (!button.hidden) refreshSelectionButton();
  }, { passive: true });
  window.addEventListener("resize", scheduleSelectionRefresh);
  article.addEventListener("click", event => {
    const highlight = event.target.closest(".selection-note-highlight");
    if (!highlight || !article.contains(highlight)) return;
    const note = readSelectionNotes()[highlight.dataset.selectionNoteId];
    if (!note) {
      refreshSelectionNoteHighlights(labels);
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    openDialogForStoredNote(note);
  });
  article.addEventListener("keydown", event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const highlight = event.target.closest(".selection-note-highlight");
    if (!highlight || !article.contains(highlight)) return;
    const note = readSelectionNotes()[highlight.dataset.selectionNoteId];
    if (!note) return;
    event.preventDefault();
    openDialogForStoredNote(note);
  });
  window.addEventListener("storage", event => {
    if (event.key === SELECTION_NOTES_STORAGE_KEY) refreshSelectionNoteHighlights(labels);
  });
  window.addEventListener("beforeunload", () => {
    if (selectionNoteSaveTimer) {
      window.clearTimeout(selectionNoteSaveTimer);
      saveCurrentSelectionNote();
    }
  });
  refreshSelectionNoteHighlights(labels);
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", installSelectionNotes);
} else {
  installSelectionNotes();
}

document.addEventListener("click", async event => {
  const button = event.target.closest(".copy-code");
  if (!button) return;
  const listing = button.closest(".code-listing");
  const code = listing && listing.querySelector("code");
  if (!code) return;
  const text = code.innerText;
  const previous = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  button.textContent = "Copied";
  window.setTimeout(() => {
    button.textContent = previous || "Copy";
  }, 1200);
});

const tocSearch = document.querySelector(".toc-search");
const tocEntries = [...document.querySelectorAll("[data-toc-entry]")];
if (tocSearch && tocEntries.length) {
  const filterContents = () => {
    const query = tocSearch.value.trim().toLowerCase();
    for (const entry of tocEntries) {
      const matches = !query || entry.dataset.search.includes(query);
      entry.hidden = !matches;
      const details = entry.querySelector(".toc-details");
      if (details) details.open = Boolean(query && matches);
    }
    for (const part of document.querySelectorAll(".toc-part")) {
      part.hidden = !part.querySelector("[data-toc-entry]:not([hidden])");
    }
  };
  tocSearch.addEventListener("input", filterContents);
}
