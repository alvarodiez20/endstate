# endstate brand assets

Direction: **Checkpoint** — flag reduced to bar + field, with the graded state inside the field.
Grid: 32×32, stroke 2.5, single flat color. No gradients, no rasters inside the SVGs.

## Files

    svg/endstate-mark.svg            black mark, 32×32
    svg/endstate-mark-white.svg      white mark, for #0d0d0d and darker
    svg/endstate-mark-mono.svg       fill: currentColor — inherits surrounding text color
    svg/endstate-mark-accent.svg     black mark, node in #0f766e
    svg/endstate-lockup.svg          mark + wordmark, black, 172×32
    svg/endstate-lockup-white.svg    mark + wordmark, white
    svg/favicon.svg                  same as endstate-mark.svg
    png/favicon-16/32/64.png         transparent background
    png/apple-touch-icon-180.png     black on white, padded
    png/icon-512.png                 black on white, padded
    png/icon-512-dark.png            white on #0d0d0d, padded
    png/endstate-lockup.png          256px-tall lockup, black on white
    png/endstate-lockup-dark.png     256px-tall lockup, white on #0d0d0d
    png/endstate-lockup-accent.png   256px-tall lockup, node in #0f766e
    png/endstate-lockup-transparent.png  256px-tall lockup, black on transparent
    png/og-image-1280x640.png        social preview
    svg/endstate-thesis.svg          animated: the transcript discarded, the sandbox graded

## endstate-thesis.svg

The one animated asset, used at the top of the README. It is an animated SVG rather than one of the
`docs/assets/diagrams/` files because those are React in an iframe, and neither GitHub nor PyPI will
run one — both will render an `<img>` pointing at an SVG, and both animate it.

Two things in it are deliberate and easy to break:

- A `@media (prefers-color-scheme: dark)` block inside the file supplies the dark palette. Browsers
  evaluate that even when the SVG is loaded as an `<img>`, so one file covers both themes with no
  `<picture>` element. The accent is lightened there rather than kept at `#0f766e`, which falls to
  about 2:1 against `#0d0d0d`.
- A `prefers-reduced-motion` block holds the finished frame instead of looping.

The known limit: inside an `<img>`, `prefers-color-scheme` resolves against the reader's **OS**
setting, not GitHub's own theme toggle. Someone browsing in GitHub dark mode on a light OS gets the
light artwork on a dark page. That is why the file paints an opaque `--surface` rectangle rather
than being transparent — a light card on a dark page is merely untidy, whereas transparent artwork
in that combination would be dark ink on a dark background and unreadable.

## Colors

    ink       #000000
    surface   #ffffff
    ink-dark  #0d0d0d
    accent    #0f766e   (optional, one element only — the node)

The mark must read with the accent removed. Never place the accent on the bar or the field.

## Clear space and minimum size

Clear space on all sides = the width of the bar × 4 (4 grid units at 32).
Minimum size: 16px for the mark. Below 24px use the mark alone, never the lockup.

## Wordmark

Lowercase "endstate", always one word, always lowercase — it is a CLI command name.
Set in Helvetica Neue Medium at -0.04em tracking (stand-in for Geist / Söhne).
**The lockup SVGs still contain a live `<text>` element.** Before using them outside a
browser, open in Inkscape/Illustrator and convert type to outlines, or ship the PNG lockups.

## mkdocs (material) wiring

Copy `svg/` and `png/` into `docs/assets/brand/`, then in `mkdocs.yml`:

```yaml
theme:
  name: material
  logo: assets/brand/svg/endstate-mark-white.svg
  favicon: assets/brand/svg/favicon.svg
extra:
  social_image: assets/brand/png/og-image-1280x640.png
```

Material's header is `primary: black`, so the header logo should be the white mark.

## README badge / GitHub

GitHub renders README images from the repo, so reference the raw path:

```markdown
<img src="brand/png/endstate-lockup-transparent.png" width="220" alt="endstate">
```

Transparent lockup reads on both GitHub themes.
