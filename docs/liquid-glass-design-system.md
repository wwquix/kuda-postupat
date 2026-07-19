# Liquid Glass design foundation

`M-APPLE-LIQUID-GLASS-FOUNDATION-01` establishes the light visual foundation for «Куда поступать». It changes the global shell and HomePage; internal catalog, comparison, monitor, recommendation and profile pages keep their detailed layouts until `M-APPLE-LIQUID-GLASS-PAGES-01`.

## Semantic tokens

- `background` and `elevated` provide the cool near-white page and solid content layers.
- `text-primary` and `text-secondary` provide near-black body hierarchy with sufficient contrast.
- `accent` and `focus` use a restrained system blue for actions, active navigation and focus.
- `border` separates surfaces without a decorative outline.
- `success`, `warning` and `danger` are reserved for data and system meaning.
- `glass-compact` and `glass-strong` identify the two supported translucent material levels.
- `shadow-elevated`, `shadow-glass-compact` and `shadow-glass-strong` encode elevation consistently.

Legacy Tailwind names remain aliases for these semantic tokens so internal pages inherit the neutral palette without a detailed redesign in this milestone.

## Typography

The application uses the local system stack: `-apple-system`, `BlinkMacSystemFont`, optional locally available `SF Pro Display`, `Segoe UI`, Roboto, Helvetica, Arial and `sans-serif`. No external font request or proprietary font file is used. Display text has tighter tracking and leading; body copy keeps a comfortable line height; compact uppercase labels use slightly wider tracking.

## Materials

- Compact glass is for the floating site header, navigation and similarly small controls. It uses an 18 px blur, restrained saturation, a light edge and the compact shadow.
- Strong glass is for the two major HomePage information surfaces. It uses a 26 px blur, a more opaque fill and the deeper strong shadow.
- `.panel` remains a solid elevated surface for dense internal content.

Never place a large translucent glass surface inside another glass surface. Plain text, solid or lightly tinted controls, separators and non-glass status pills may sit inside glass. Warnings, errors, long reading sections, tables and dense lists stay solid.

## Interaction and motion

Interactive controls respond on pointer-down through a short opacity response. Important buttons, navigation and text controls also scale to `0.98` over roughly 100 ms; click behavior is never delayed. Hover treatments are limited to hover-capable fine pointers. New primary controls and navigation targets are at least approximately 44 px high.

Only key HomePage materials use the one-time `materialize` effect: a short opacity, tiny scale and subtle blur transition. There are no loops, parallax, decorative springs or layout-dimension animations.

## Accessibility and fallbacks

- `prefers-reduced-motion: reduce` removes material movement and scale response while preserving immediate opacity feedback.
- `prefers-reduced-transparency: reduce` disables both backdrop filters and makes glass opaque.
- `prefers-contrast: more` strengthens text, borders, active navigation and material opacity.
- Browsers without `backdrop-filter` receive the default 96–97% opaque surfaces, with the same border, shadow and hierarchy.
- Keyboard focus uses the semantic blue focus ring. The skip link, landmarks, active-route state, mobile disclosure labels, `aria-expanded` state and Escape-to-close behavior remain explicit.

## Migrating internal pages

Use glass only when a surface floats above the page and the material communicates hierarchy or interaction. Keep dense `.panel` content solid. Do not replace all cards mechanically, nest glass, put critical alerts on translucent surfaces or create one-off blur values. The next milestone should migrate internal pages deliberately and verify data semantics, readability and responsive behavior page by page.
