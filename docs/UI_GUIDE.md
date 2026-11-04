# ReachAI UI guide

Every page should look like the Creators page and the creator panel. Use the shared pieces below instead of
styling controls by hand, and never use the browser's own dropdowns (they ignore our font and theme).

## Look
- **Font:** Geist (the app default). **Mono only for numbers in data** (scores, %, views in rows and tiles);
  never for words like "No price yet".
- **Colours:** zinc neutrals. Page `bg-zinc-50` / dark `#08090a`; surfaces `bg-white` / dark `#0c0d0e`;
  tiles `bg-zinc-100` / dark `#121314`. Borders `zinc-200` / dark `zinc-800`. Accent blue only for links and
  focus; emerald = good, amber = watch, rose = bad.
- **Radius:** 6px (`rounded-md`) for controls, 8px (`rounded-lg`) for cards and rows, 4px for badges.
- **Motion:** Motion springs via `components/Feel.tsx`; press feedback is automatic; respect reduced motion.

## Type scale
| Use | Class |
|---|---|
| Page title | `text-[14px] font-medium` |
| Body, list names | `text-[13px]` |
| Controls, secondary text | `text-xs` (12px) |
| Meta, hints, field labels | `text-[11px] text-zinc-500` (sentence case) |
| Panel section header | `SectionHeader` (11px, semibold, uppercase, icon) |
| Tile label | `StatTile` label (10px, semibold, uppercase, wide tracking) |

Uppercase is only for panel section headers and tile labels. Everything else is sentence case.

## Controls (all 30px tall, `text-xs`)
| Need | Use |
|---|---|
| Button | `btn` / `btnPrimary` from `lib/ui.ts` |
| Text or number input | `Input` (`components/ui/field.tsx`), optional `prefix="$"` |
| Pick one of a few | `Segmented` (`components/ui/segmented.tsx`) |
| Pick one of many | `Select` (`components/ui/select.tsx`) |
| Labelled form field | `Field label="…"` around the control |
| Long text | `TextArea` |
| Numbers in a row of tiles | `StatStrip` + `StatTile` (`components/ui/stat.tsx`) |
| Section in a panel | `SectionHeader icon={…}` |
| Side panel | `Sheet` + `SheetContent`, header block `p-5 bg-zinc-50 dark:bg-[#08090a]` |

## Words
Plain, short, sentence case. Say what happens ("Add to deals"), not how ("Create deal record").
Empty states say what to do next. Errors say what went wrong and what to try.
