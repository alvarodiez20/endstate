// docs/assets/diagrams/embed.js
// Pushes the Material palette scheme into every diagram iframe, and keeps
// each iframe's height in step with the reader's window width.
(function () {
  function scheme() {
    return document.body.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "light";
  }
  function frames() {
    return document.querySelectorAll("iframe.endstate-diagram");
  }
  function push() {
    var s = scheme();
    frames().forEach(function (f) {
      try { f.contentWindow.postMessage({ type: "endstate-theme", scheme: s }, "*"); } catch (e) {}
    });
  }
  addEventListener("message", function (e) {
    if (e.data && e.data.type === "endstate-diagram-ready") push();
  });
  new MutationObserver(push).observe(document.body, {
    attributes: true, attributeFilter: ["data-md-color-scheme"],
  });
  document.addEventListener("DOMContentLoaded", push);
  push();
})();
