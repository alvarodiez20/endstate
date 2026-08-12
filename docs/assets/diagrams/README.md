# Concepts diagrams

Nine self-contained animated diagrams, one per page in `docs/concepts/`. Each is an
`<iframe>` embedded from the Markdown; see `docs/stylesheets/diagrams.css` and
`docs/assets/diagrams/embed.js` for the wrapper and the theme bridge.

This file is excluded from the built site by `exclude_docs` in `mkdocs.yml`.

## What is in here

| File | What it is |
| --- | --- |
| `*.html` (nine) | One diagram each. Self-contained: markup, styles, and a small component at the bottom of the file. |
| `support.js` | Generated runtime that renders those components. Not written by hand — see below. |
| `embed.js` | Loaded by the parent page. Pushes the Material palette scheme into each iframe so the diagrams follow the light/dark toggle rather than only the OS setting. |
| `vendor/` | React 18.3.1 and ReactDOM 18.3.1 UMD production builds. |

## Why React is vendored

`support.js` loads React and ReactDOM from `unpkg.com` by default. A documentation site
should not make a third-party request on every page view, and the diagrams should render
with no network at all beyond the font stylesheet, so the two files are served from
`vendor/` instead. Each diagram sets `window.__resources` before loading `support.js`,
which is the runtime's own override hook for its pinned CDN URLs.

The vendored files were downloaded from unpkg and verified against the SRI hashes
embedded in `support.js`:

```
react-18.3.1.production.min.js      sha384-DGyLxAyjq0f9SPpVevD6IgztCFlnMF6oW/XQGmfe+IsZ8TqEiDrcHkMLKI6fiB/Z
react-dom-18.3.1.production.min.js  sha384-gTGxhz21lVGYNMcdJOyq01Edg0jhn/c22nsx0kyqP0TxaV5WVdsSH1fSDUf5YJj1
```

To re-verify:

```
openssl dgst -sha384 -binary vendor/react-18.3.1.production.min.js | openssl base64 -A
```

`support.js` also references `@babel/standalone` on unpkg, for runtime JSX imports. No
diagram here uses that path, so it is never fetched and is deliberately not vendored — if
a future diagram uses `x-import`, vendor it or accept the CDN call knowingly.

## Licensing

- React and ReactDOM are © Meta Platforms, Inc. and affiliates, MIT licensed. The upstream
  licence text ships in the npm packages at <https://www.npmjs.com/package/react>.
- `support.js` is a generated bundle (`dc-runtime`); its header records the build command.
  It is vendored as a build artifact, the same way the React UMD files are.

## Editing a diagram

Open the `.html` file directly in a browser — they run standalone, and `?theme=dark`
forces the dark palette. The component is the `<script type="text/x-dc">` block at the
bottom of each file; the markup above it is a template where `{{ name }}` interpolates the
values that component returns.

## Sizing

Each embed is a fixed-height iframe inside a `.endstate-diagram-scroll` wrapper. The
heights in the Markdown were measured against the tallest animation frame at the ~688px
Material content column, so changing a diagram's content means re-checking its height. The
layouts do not reflow below ~680px; the wrapper pans horizontally instead.
