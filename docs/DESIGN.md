# vlog-pipeline Studio — design direction

## Direction

The studio is a **professional desktop editing tool**: dark-first,
keyboard-centric, calm and precise. It should read like an instrument panel —
quiet surfaces, dense-but-breathable information, one restrained accent, and
color used almost exclusively to *mean something* (cut reasons, status). No
marketing gradients, no oversized hero type, no default-framework look.

Reference feeling (not imitation): the confidence of a hardware mixer — matte
dark panels, precise tick marks, one glowing indicator. Every pixel either
shows the footage, shows a decision, or gets out of the way.

Three rules every screen must obey:

1. **The footage is the brightest thing on screen.** Chrome stays in the
   bg-0…bg-3 band; only video, waveform highlights, and the accent may pop.
2. **Color = meaning.** Categorical cut-reason colors are reserved for cut
   reasons; status colors for status; the accent for selection/focus/primary
   action. Decorative color is banned.
3. **Everything reachable by keyboard**, and the UI *shows* its shortcuts
   (kbd chips in buttons, tooltips, and the `?` overlay).

Dark-only in v1 — a deliberate scope decision (editing tools live in dark
rooms; a light theme would double the QA surface for no user demand yet).

## Tokens

Defined once in `studio/src/tokens.css` as CSS custom properties. Components
must reference tokens, never raw hex.

### Color — surfaces & ink

| token | value | use |
|---|---|---|
| `--bg-0` | `#101013` | app background, deepest chrome |
| `--bg-1` | `#16161a` | panels (inspector, library cards) |
| `--bg-2` | `#1d1d23` | raised elements: inputs, list rows, toolbar |
| `--bg-3` | `#26262e` | hover surface / active row |
| `--border-1` | `#2c2c35` | hairline dividers |
| `--border-2` | `#3d3d49` | interactive element borders |
| `--ink-1` | `#f2f2f4` | primary text, playhead |
| `--ink-2` | `#a6a6b2` | secondary text, labels |
| `--ink-3` | `#6c6c79` | muted: timecodes at rest, placeholders |

### Color — accent & status

| token | value | use |
|---|---|---|
| `--accent` | `#9085e9` | selection, focus ring, primary buttons, active tab |
| `--accent-hover` | `#a49af0` | hover on accent elements |
| `--accent-down` | `#7d72d8` | pressed |
| `--accent-dim` | `rgba(144,133,233,.14)` | selected-row tint, selection rects |
| `--good` | `#0ca30c` | export success, saved state |
| `--warn` | `#fab219` | unreviewed-after-reanalyze badge, dirty state |
| `--crit` | `#d03b3b` | destructive actions, errors |

Accent is violet from the same validated palette family as the categorical
set (slot 5, dark step) — deliberately *not* one of the cut-reason hues, so a
selected silence cut (blue fill + violet ring) stays unambiguous.

### Color — cut-reason categorical (reused from report.html, CVD-validated dark set)

| token | value | meaning |
|---|---|---|
| `--cut-silence` | `#3987e5` | silence / dead-air cut |
| `--cut-filler` | `#199e70` | filler-word cut |
| `--cut-mixed` | `#c98500` | merged silence+filler cut |
| `--cut-pacing` | `#008300` (45° hatch) | pacing-guard kept / restored |
| `--cut-manual` | `#d55181` | user-added manual cut |

Rejected cuts render as the same hue at 25% opacity with a strikethrough
hatch — reason stays readable even when declined. On the timeline, fills use
55% alpha over the waveform with a solid 1.5px top rail in the full hue.

### Type

System stack; no webfonts (offline rule + native feel).

| token | value | use |
|---|---|---|
| `--font-ui` | `-apple-system, "Segoe UI", system-ui, sans-serif` | everything |
| `--font-mono` | `ui-monospace, "SF Mono", Menlo, monospace` | timecodes, numbers, kbd |
| `--fs-xs` | 11px | badges, axis ticks, kbd chips |
| `--fs-sm` | 12px | secondary labels, table meta |
| `--fs-base` | 13px | body, lists, inputs (editor density) |
| `--fs-md` | 15px | panel titles |
| `--fs-lg` | 18px | run title in header |
| `--fs-xl` | 24px | library page title, big numbers |

Weights: 400 body, 500 labels/buttons, 600 titles. Line-height 1.45 body,
1.2 titles. Timecodes always `--font-mono` with `font-variant-numeric:
tabular-nums`.

### Spacing, radii, shadows

- Spacing scale (4px grid): `--sp-1..6` = 4 / 8 / 12 / 16 / 24 / 32.
- Radii: `--r-sm` 4px (inputs, chips, kbd), `--r-md` 6px (buttons, list rows),
  `--r-lg` 8px (panels, cards, dialogs), `--r-pill` 999px.
- Shadows are for *floating* layers only (dialogs, drawer, toasts):
  `--shadow-float: 0 8px 24px rgba(0,0,0,.5), 0 0 0 1px var(--border-1)`.
  Flat panels never carry shadows — separation comes from bg steps.

### Interaction states (uniform everywhere)

| state | treatment |
|---|---|
| hover | surface steps up one bg level; 120ms ease-out |
| focus-visible | 2px `--accent` ring, 1px offset — never removed, keyboard is first-class |
| selected | `--accent-dim` fill + 1px `--accent` border (rows) or 1.5px ring (timeline cuts) |
| active/pressed | `--accent-down` on accent elements; bg-3 on neutral |
| disabled | 40% opacity, no pointer events |
| dirty/unsaved | small `--warn` dot next to the save indicator |
| destructive | `--crit` text + border; confirm before irreversible actions |

Motion: 120ms ease-out micro-interactions; 200ms panels/drawers; no springs,
no parallax. `prefers-reduced-motion` disables all transitions.

## Layout architecture

```
┌────────────────────────────────────────────────────────────────┐
│ header: ‹ library │ run name · duration    save-state · Export │ 48px
├──────────────────────────────────┬─────────────────────────────┤
│                                  │ inspector (tabs):           │
│   player (letterboxed, bg-0)     │  Cuts | Captions            │
│   transport bar under video      │  list synced to timeline,   │
│                                  │  batch ops, cut detail      │ fills
├──────────────────────────────────┴─────────────────────────────┤
│ timeline: ruler / waveform / cut track / zoom & mode controls  │ 176px
├────────────────────────────────────────────────────────────────┤
│ status bar: playhead tc · edited-duration math · hints · ?     │ 28px
└────────────────────────────────────────────────────────────────┘
```

- Settings is a right-side **drawer** over the inspector (never a page swap).
- Export progress is a **modal card** with a log line, not a page.
- Library view: centered 720px column, one card per run — name, topic,
  duration math, reviewed-state chip, thumbnail strip.

## Component conventions

- **Buttons**: primary (accent bg, ink-1 text), quiet (bg-2, border-2),
  destructive (transparent, crit border/text). Height 28px, `--fs-base`,
  radius `--r-md`, optional trailing kbd chip.
- **kbd chip**: mono `--fs-xs`, bg-2, border-2, radius `--r-sm`, 2px 5px pad.
- **Timecodes**: `m:ss.mmm` mono; ink-3 at rest, ink-1 when live/edited.
- **Badges** (cut reason): 8px dot + label in ink-2, or tinted pill at 14%
  alpha of the reason hue with the hue as text where space allows.
- **Empty/loading/error states**: every async surface has all three designed —
  centered ink-3 glyph + one sentence + one action; errors show a human
  sentence + retry, never a stack trace (raw detail behind a "details" fold).
- **Toasts**: bottom-right, bg-2 + shadow-float, auto-dismiss 4s, status dot.

## Quality bar checklist (applied before every phase gate)

- [ ] No raw hex in components — tokens only.
- [ ] Footage brighter than chrome; no decorative color.
- [ ] Every new action keyboard-reachable + listed in the `?` overlay.
- [ ] Hover/focus/selected/disabled all present, not just hover.
- [ ] Empty, loading, and error states designed for every async surface.
- [ ] Screenshot looks like a commercial tool, not a default-framework page.
