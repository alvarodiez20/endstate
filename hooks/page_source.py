"""Write each page's Markdown source into the built site.

The `Copy page` button in `overrides/main.html` fetches these, so a reader gets
the source rather than the rendered text — and gets it from this site, with no
request to GitHub and no dependence on a branch name.

The `.md.txt` suffix is deliberate: MkDocs treats a `.md` file in the output
tree as a page to render, and GitHub Pages serves an unknown extension as a
download rather than inline text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def on_post_page(output: str, page: Any, config: Any, **kwargs: Any) -> str:
    src = getattr(page.file, "src_uri", "")
    if not src.endswith(".md"):
        return output

    markdown = page.markdown
    if markdown is None:
        return output

    target = Path(config["site_dir"]) / f"{src}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return output
