# AFML Chinese Static Web Book

Simplified Chinese static web edition of *Advances in Financial Machine Learning*.

## Local Preview

From this directory:

```bash
python3 -m http.server 8787
```

Then open:

```text
http://127.0.0.1:8787/zh/index.html
```

The Chinese reader is installable as a Progressive Web App. On supported mobile browsers, use the reader's **Install** button or the browser's **Add to Home Screen** action. The service worker caches the book shell, chapters, figures, and MathJax runtime for offline reading. The reader saves the current chapter, scroll position, theme, and font size locally, then restores those preferences the next time the installed app is opened.

## Build and Review

Regenerate the static site:

```bash
python3 scripts/build_web_book.py
```

Run the full acceptance review:

```bash
python3 scripts/full_book_review.py --write-report
```

Reports:

- `docs/full-book-review.md`
- `docs/browser-layout-review.md`

Regenerate the Chinese static site from the translation cache:

```bash
python3 scripts/translate_book_zh.py --cache-path translations/zh/cache.json
python3 scripts/audit_zh_translation.py
```

## GitHub Pages

The repository includes a GitHub Pages workflow at `.github/workflows/pages.yml`.

The deployed site artifact contains only the static website files: `index.html`, `manifest.webmanifest`, `service-worker.js`, `.nojekyll`, `assets/`, and `zh/`.

## OpenAI Sites

Build the Cloudflare Worker-compatible Sites artifact:

```bash
python3 scripts/build_sites_dist.py
```

The generated deployment entrypoint is `dist/server/index.js`, with the static reader under `dist/client/`.

See `docs/github-pages.md` before making the repository or site public.
