# GitHub Pages Publishing

This repository is ready for GitHub Pages deployment through `.github/workflows/pages.yml`.

The Pages artifact intentionally includes only:

- `index.html`
- `.nojekyll`
- `assets/`
- `zh/`

The root `index.html` redirects to `zh/index.html`. The artifact does not publish the source PDF, generator scripts, review reports, skills, original English `book/`, or temporary files as site artifacts.

## Before Public Publishing

Do not make the repository or Pages site public unless you have the right to publish the converted book content.

## Enable Pages

After confirming publication rights:

1. Keep the default branch as `main`.
2. In GitHub, open **Settings -> Pages**.
3. Set **Build and deployment -> Source** to **GitHub Actions**.
4. Run the `Deploy GitHub Pages` workflow or push to `main`.

Equivalent GitHub CLI command:

```bash
gh api -X POST repos/akirayu101/afml-zh/pages -f build_type=workflow
```

If the repository should be public:

```bash
gh repo edit akirayu101/afml-zh --visibility public
```
