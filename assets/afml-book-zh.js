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
  button.textContent = "已复制";
  window.setTimeout(() => {
    button.textContent = previous || "复制";
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
