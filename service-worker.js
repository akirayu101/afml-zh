const CACHE_PREFIX = "afml-webbook-";
const CACHE_NAME = "afml-webbook-20260721-font-size-controls";
const RUNTIME_CACHE = `${CACHE_NAME}-runtime`;
const CORE_URLS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./zh/index.html",
  "./zh/front-matter.html",
  "./zh/chapter-01.html",
  "./zh/chapter-02.html",
  "./zh/chapter-03.html",
  "./zh/chapter-04.html",
  "./zh/chapter-05.html",
  "./zh/chapter-06.html",
  "./zh/chapter-07.html",
  "./zh/chapter-08.html",
  "./zh/chapter-09.html",
  "./zh/chapter-10.html",
  "./zh/chapter-11.html",
  "./zh/chapter-12.html",
  "./zh/chapter-13.html",
  "./zh/chapter-14.html",
  "./zh/chapter-15.html",
  "./zh/chapter-16.html",
  "./zh/chapter-17.html",
  "./zh/chapter-18.html",
  "./zh/chapter-19.html",
  "./zh/chapter-20.html",
  "./zh/chapter-21.html",
  "./zh/chapter-22.html",
  "./zh/book-index.html",
  "./assets/afml-book.css?v=20260721-font-size-controls",
  "./assets/afml-book-zh.css?v=20260721-font-size-controls",
  "./assets/afml-book.js?v=20260721-font-size-controls",
  "./assets/afml-book-zh.js?v=20260721-font-size-controls",
  "./assets/icons/pwa-192.png",
  "./assets/icons/pwa-512.png",
  "./assets/icons/apple-touch-icon.png"
];
const OFFLINE_MEDIA_URLS = [
  "./zh/media/afml-108_1.jpg",
  "./zh/media/afml-108_2.jpg",
  "./zh/media/afml-110_1.jpg",
  "./zh/media/afml-122_1.jpg",
  "./zh/media/afml-124_1.jpg",
  "./zh/media/afml-127_1.jpg",
  "./zh/media/afml-131_1.jpg",
  "./zh/media/afml-134_1.jpg",
  "./zh/media/afml-135_1.jpg",
  "./zh/media/afml-147_1.jpg",
  "./zh/media/afml-152_1.jpg",
  "./zh/media/afml-153_1.jpg",
  "./zh/media/afml-153_2.jpg",
  "./zh/media/afml-160_1.jpg",
  "./zh/media/afml-162_1.jpg",
  "./zh/media/afml-170_1.jpg",
  "./zh/media/afml-172_1.jpg",
  "./zh/media/afml-184_1.jpg",
  "./zh/media/afml-1_1.jpg",
  "./zh/media/afml-204_1.jpg",
  "./zh/media/afml-205_1.jpg",
  "./zh/media/afml-206_1.jpg",
  "./zh/media/afml-206_2.jpg",
  "./zh/media/afml-207_1.jpg",
  "./zh/media/afml-208_1.jpg",
  "./zh/media/afml-208_2.jpg",
  "./zh/media/afml-209_1.jpg",
  "./zh/media/afml-210_1.jpg",
  "./zh/media/afml-210_2.jpg",
  "./zh/media/afml-211_1.jpg",
  "./zh/media/afml-211_2.jpg",
  "./zh/media/afml-212_1.jpg",
  "./zh/media/afml-212_2.jpg",
  "./zh/media/afml-213_1.jpg",
  "./zh/media/afml-213_2.jpg",
  "./zh/media/afml-214_1.jpg",
  "./zh/media/afml-215_1.jpg",
  "./zh/media/afml-215_2.jpg",
  "./zh/media/afml-216_1.jpg",
  "./zh/media/afml-216_2.jpg",
  "./zh/media/afml-217_1.jpg",
  "./zh/media/afml-217_2.jpg",
  "./zh/media/afml-218_1.jpg",
  "./zh/media/afml-218_2.jpg",
  "./zh/media/afml-229_1.jpg",
  "./zh/media/afml-231_1.jpg",
  "./zh/media/afml-232_1.jpg",
  "./zh/media/afml-242_1.jpg",
  "./zh/media/afml-243_1.jpg",
  "./zh/media/afml-252_1.jpg",
  "./zh/media/afml-258_1.jpg",
  "./zh/media/afml-260_1.jpg",
  "./zh/media/afml-264_1.jpg",
  "./zh/media/afml-264_2.jpg",
  "./zh/media/afml-280_1.jpg",
  "./zh/media/afml-283_1.jpg",
  "./zh/media/afml-284_1.jpg",
  "./zh/media/afml-284_2.jpg",
  "./zh/media/afml-299_1.jpg",
  "./zh/media/afml-299_2.jpg",
  "./zh/media/afml-300_1.jpg",
  "./zh/media/afml-300_2.jpg",
  "./zh/media/afml-301_1.jpg",
  "./zh/media/afml-315_1.jpg",
  "./zh/media/afml-316_1.jpg",
  "./zh/media/afml-317_1.jpg",
  "./zh/media/afml-334_1.jpg",
  "./zh/media/afml-336_1.jpg",
  "./zh/media/afml-349_1.jpg",
  "./zh/media/afml-359_1.jpg",
  "./zh/media/afml-360_1.jpg",
  "./zh/media/afml-365_1.jpg",
  "./zh/media/afml-366_1.jpg",
  "./zh/media/afml-372_1.jpg",
  "./zh/media/afml-373_1.jpg",
  "./zh/media/afml-374_1.jpg",
  "./zh/media/afml-375_1.jpg",
  "./zh/media/afml-55_1.jpg",
  "./zh/media/afml-62_1.jpg",
  "./zh/media/afml-67_1.jpg",
  "./zh/media/afml-74_1.jpg",
  "./zh/media/afml-74_2.jpg",
  "./zh/media/afml-79_1.jpg",
  "./zh/media/afml-88_1.jpg",
  "./zh/media/afml-95_1.jpg",
  "./zh/media/chapter-04-figure-4-3.png",
  "./zh/media/chapter-05-figure-5-1.png",
  "./zh/media/chapter-05-figure-5-2.png",
  "./zh/media/chapter-05-figure-5-3.png",
  "./zh/media/chapter-05-figure-5-4.png",
  "./zh/media/chapter-05-figure-5-5.png",
  "./zh/media/chapter-10-figure-10-3.png",
  "./zh/media/chapter-11-figure-11-1.png",
  "./zh/media/chapter-11-figure-11-2.png",
  "./zh/media/chapter-13-figure-13-1.png",
  "./zh/media/chapter-13-figure-13-10.png",
  "./zh/media/chapter-13-figure-13-11.png",
  "./zh/media/chapter-13-figure-13-12.png",
  "./zh/media/chapter-13-figure-13-13.png",
  "./zh/media/chapter-13-figure-13-14.png",
  "./zh/media/chapter-13-figure-13-15.png",
  "./zh/media/chapter-13-figure-13-16.png",
  "./zh/media/chapter-13-figure-13-17.png",
  "./zh/media/chapter-13-figure-13-18.png",
  "./zh/media/chapter-13-figure-13-19.png",
  "./zh/media/chapter-13-figure-13-2.png",
  "./zh/media/chapter-13-figure-13-20.png",
  "./zh/media/chapter-13-figure-13-21.png",
  "./zh/media/chapter-13-figure-13-22.png",
  "./zh/media/chapter-13-figure-13-23.png",
  "./zh/media/chapter-13-figure-13-24.png",
  "./zh/media/chapter-13-figure-13-25.png",
  "./zh/media/chapter-13-figure-13-3.png",
  "./zh/media/chapter-13-figure-13-4.png",
  "./zh/media/chapter-13-figure-13-5.png",
  "./zh/media/chapter-13-figure-13-6.png",
  "./zh/media/chapter-13-figure-13-7.png",
  "./zh/media/chapter-13-figure-13-8.png",
  "./zh/media/chapter-13-figure-13-9.png",
  "./zh/media/chapter-15-figure-15-1.png",
  "./zh/media/chapter-16-figure-16-1.png",
  "./zh/media/chapter-16-figure-16-2.png",
  "./zh/media/chapter-16-figure-16-3.png",
  "./zh/media/chapter-16-figure-16-5.png",
  "./zh/media/chapter-16-figure-16-7-ab.png",
  "./zh/media/chapter-16-figure-16-7-c.png",
  "./zh/media/chapter-17-figure-17-1.png",
  "./zh/media/chapter-17-figure-17-2.png",
  "./zh/media/chapter-17-figure-17-3.png",
  "./zh/media/chapter-18-figure-18-1-ab.png",
  "./zh/media/chapter-18-figure-18-1-cd.png",
  "./zh/media/chapter-18-figure-18-2.png",
  "./zh/media/chapter-19-figure-19-1.png",
  "./zh/media/chapter-19-figure-19-2.png",
  "./zh/media/chapter-19-figure-19-3.png",
  "./zh/media/chapter-20-figure-20-1.png",
  "./zh/media/chapter-20-figure-20-2.png",
  "./zh/media/chapter-21-figure-21-1.png",
  "./zh/media/chapter-22-figure-22-1.png",
  "./zh/media/chapter-22-figure-22-3.png",
  "./zh/media/chapter-22-figure-22-6-ab.png",
  "./zh/media/chapter-22-figure-22-6-cd.png",
  "./zh/media/chapter-22-figure-22-6-ef.png"
];
const MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js";

const cacheResponse = async (cacheName, request, response) => {
  if (response && (response.ok || response.type === "opaque")) {
    const cache = await caches.open(cacheName);
    await cache.put(request, response.clone());
  }
  return response;
};

const warmOptionalAsset = async (cache, url) => {
  try {
    const request = new Request(url, { cache: "reload", mode: url.startsWith("http") ? "no-cors" : "same-origin" });
    const response = await fetch(request);
    if (response.ok || response.type === "opaque") await cache.put(request, response);
  } catch {
    // Optional media can still be cached on demand later.
  }
};

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(CORE_URLS);
    await Promise.allSettled(OFFLINE_MEDIA_URLS.map(url => warmOptionalAsset(cache, url)));
    await warmOptionalAsset(await caches.open(RUNTIME_CACHE), MATHJAX_URL);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith(CACHE_PREFIX) && ![CACHE_NAME, RUNTIME_CACHE].includes(key)).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

const networkFirst = async request => {
  try {
    const response = await fetch(request);
    return cacheResponse(CACHE_NAME, request, response);
  } catch {
    return (await caches.match(request, { ignoreSearch: true })) || caches.match("./zh/index.html");
  }
};

const staleWhileRevalidate = async (event, request) => {
  const cached = await caches.match(request);
  const update = fetch(request)
    .then(response => cacheResponse(request.url.startsWith(self.location.origin) ? CACHE_NAME : RUNTIME_CACHE, request, response))
    .catch(() => null);
  if (cached) {
    event.waitUntil(update);
    return cached;
  }
  return update;
};

self.addEventListener("fetch", event => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (request.mode === "navigate" && url.origin === self.location.origin) {
    event.respondWith(networkFirst(request));
    return;
  }
  if (["http:", "https:"].includes(url.protocol)) {
    event.respondWith(staleWhileRevalidate(event, request));
  }
});
