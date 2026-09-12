/* Umash — imagery loader.
   Photos fade in only if they actually load; otherwise the on-brand SVG base
   underneath remains visible. Keeps the app dignified and never broken offline.
   Exposes Umash.wireImages() so dynamically rendered media get wired too. */
(function () {
  function wire(img) {
    if (img.dataset.wired) return;
    img.dataset.wired = "1";
    if (img.complete && img.naturalWidth > 0) { img.classList.add("loaded"); return; }
    img.addEventListener("load", () => img.classList.add("loaded"), { once: true });
    img.addEventListener("error", () => img.remove(), { once: true }); // fall back to SVG base
  }
  function wireAll() { document.querySelectorAll("img.media__photo").forEach(wire); }
  wireAll();
  window.Umash = window.Umash || {};
  window.Umash.wireImages = wireAll;
})();
