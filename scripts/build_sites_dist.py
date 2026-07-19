#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CLIENT = DIST / "client"
SERVER = DIST / "server"

STATIC_FILES = (
    ROOT / "index.html",
    ROOT / "manifest.webmanifest",
    ROOT / "service-worker.js",
    ROOT / ".nojekyll",
)
STATIC_DIRS = (
    ROOT / "assets",
    ROOT / "zh",
)

WORKER_SOURCE = """const withHostingHeaders = (request, response) => {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  headers.set("X-Frame-Options", "SAMEORIGIN");

  const url = new URL(request.url);
  const contentType = headers.get("content-type") || "";
  if (
    contentType.includes("text/html") ||
    url.pathname === "/manifest.webmanifest" ||
    url.pathname === "/service-worker.js"
  ) {
    headers.set("Cache-Control", "no-cache");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
};

export default {
  async fetch(request, env) {
    if (!env?.ASSETS?.fetch) {
      return new Response("Static asset binding is unavailable", { status: 503 });
    }
    const response = await env.ASSETS.fetch(request);
    return withHostingHeaders(request, response);
  },
};
"""


def build() -> None:
    resolved_dist = DIST.resolve()
    if resolved_dist.parent != ROOT.resolve() or resolved_dist.name != "dist":
        raise RuntimeError(f"refusing to replace unexpected output directory: {resolved_dist}")

    missing = [path.relative_to(ROOT).as_posix() for path in (*STATIC_FILES, *STATIC_DIRS) if not path.exists()]
    if missing:
        raise RuntimeError(f"Sites build inputs are missing: {', '.join(missing)}")

    if DIST.exists():
        shutil.rmtree(DIST)
    CLIENT.mkdir(parents=True)
    SERVER.mkdir(parents=True)

    for source in STATIC_FILES:
        shutil.copy2(source, CLIENT / source.name)
    for source in STATIC_DIRS:
        shutil.copytree(source, CLIENT / source.name)

    (SERVER / "index.js").write_text(WORKER_SOURCE, encoding="utf-8")
    file_count = sum(1 for path in DIST.rglob("*") if path.is_file())
    size_bytes = sum(path.stat().st_size for path in DIST.rglob("*") if path.is_file())
    print(f"sites_dist_files={file_count} sites_dist_bytes={size_bytes}")


if __name__ == "__main__":
    build()
