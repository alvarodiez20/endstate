// Copy the current page's Markdown source to the clipboard.
//
// The source lives next to the page as `<path>.md.txt`, written at build time
// by hooks/page_source.py. Fetching it beats scraping the rendered DOM: the
// reader gets the code fences and tables back, not a flattened transcript.
(function () {
  var RESET_MS = 2000;

  function label(button, text) {
    var el = button.querySelector(".endstate-copy-page__label");
    if (el) el.textContent = text;
  }

  async function copy(button) {
    var source = button.getAttribute("data-source");
    if (!source) return;

    button.disabled = true;
    try {
      var response = await fetch(source, { cache: "no-store" });
      if (!response.ok) throw new Error(response.status + " " + response.statusText);
      await navigator.clipboard.writeText(await response.text());
      button.dataset.state = "done";
      label(button, "Copied");
    } catch (error) {
      // Clipboard writes need a secure context; a file:// build has none.
      console.error("[endstate] copy page failed:", error);
      button.dataset.state = "failed";
      label(button, "Copy failed");
    }
    setTimeout(function () {
      delete button.dataset.state;
      label(button, "Copy page");
      button.disabled = false;
    }, RESET_MS);
  }

  // One delegated listener, so it survives Material's instant navigation
  // swapping the content out from under us.
  document.addEventListener("click", function (event) {
    var button = event.target.closest(".endstate-copy-page");
    if (button) copy(button);
  });
})();
