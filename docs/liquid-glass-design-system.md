# Liquid Glass design system

This is the presentation contract for every public frontend page. It keeps the
product quiet, factual and dense enough for admission decisions while making
depth and interaction state easy to read.

## Semantic colour and type

The neutral light palette is defined once in `frontend/src/index.css`:

- page `#f2f3f5` and elevated page `#f7f7f8`;
- primary text `#1d1d1f`, secondary `#5f6065`, tertiary `#76777d`;
- action blue `#0071e3`, hover blue `#005bb8`, focus blue `#006edb`;
- success `#237a3b`, warning `#9a5c00`, danger `#be2a31`;
- observed chart data `#2c2c2e`, projected values `#b06a00` and
  `#d39a3a`, neutral grid `#d8d9dd`.

Blue means an action, navigation target or focus. Green is reserved for a
confirmed successful state. Warning and danger colours are not decorative.
Tailwind utilities map to these semantic names; page code must not reintroduce
the former `ink`, `moss`, `mint` or `cream` aliases.

The font stack is `-apple-system`, `BlinkMacSystemFont`, optional locally
available `SF Pro Display`, `Segoe UI`, Roboto, Helvetica, Arial and sans-serif.
No Apple font is downloaded or bundled. Display, page and section headings use
semibold weight, compact leading and restrained negative tracking. Body copy
uses 1.6 line height and semantic secondary text.

## Surfaces and hierarchy

Use translucent material only where it communicates layering:

1. **Compact glass** — sticky application chrome and compact toolbars. It is
   white at 58% opacity with `blur(22px) saturate(170%)`, a fine white border
   and compact shadow.
2. **Strong glass** — a small number of high-emphasis summary surfaces. It is
   white at 64% opacity with `blur(30px) saturate(165%)`, a stronger shadow and
   a slightly larger radius.
3. **Solid panel** — dense data, forms, tables, repeated cards, warnings and
   long reading surfaces. It is effectively opaque and uses a quiet border and
   low shadow.
4. **Sunken surface** — secondary groups inside a solid panel. It uses a faint
   graphite tint, not another layer of glass.

The no-glass-on-glass rule is strict: children of glass surfaces use solid or
sunken treatment. Repeated list items and dense data never become translucent
just to look decorative. Without backdrop-filter support, both materials fall
back to the 97% solid material.

The page background is a static cool-gray, low-chroma blue composition. It
provides enough spatial variation for blur to be visible without gradients that
imply status or compete with content.

## Motion

Shared curves and durations are exact:

| Purpose | Duration | Easing |
| --- | ---: | --- |
| press feedback | 120 ms | `cubic-bezier(0.23, 1, 0.32, 1)` |
| colour/focus state | 160 ms | `cubic-bezier(0.23, 1, 0.32, 1)` |
| occasional state crossfade | 200 ms | `cubic-bezier(0.23, 1, 0.32, 1)` |
| initial materialisation | 220 ms | `cubic-bezier(0.23, 1, 0.32, 1)` |
| mobile drawer | 240 ms | `cubic-bezier(0.32, 0.72, 0, 1)` |

Use motion only when it explains an appearance, disappearance, state change or
direct manipulation. Every pressable gets immediate opacity and 0.98 scale
feedback. Home's two explanatory glass surfaces materialise once with opacity
and a very small 0.985-to-1 scale. The mobile navigation uses the same small
scale with opacity. Save feedback and errors crossfade. Monitor state changes
may crossfade, but chart data itself never animates.

Frequency matters more than novelty: navigation motion may occur on explicit
open/close, press feedback only during a press, entrance motion once per mount,
and data feedback only when its state changes. No animation is allowed merely
because an element is visible or hovered.

Rejected categories are bouncing, floating, pulsing skeletons, looping
decoration, animated ranks or recommendation results, large translation,
spring overshoot, scale from zero, cursor-following effects, scroll hijacking,
blur/filter animation, layout-property animation and hover movement.

CSS transitions and `@starting-style` are preferred for predetermined motion.
`motion/react` is reserved for React lifecycle transitions that need presence
coordination: the mobile navigation and save feedback. WAAPI is reserved for a
future imperative sequence that cannot be expressed clearly in CSS; this
milestone needs none.

The React Bits `GlassSurface`, `FluidGlass`, `GradualBlur`, `FadeContent` and
`AnimatedContent` implementations were inspected. Only the general material and
edge-separation ideas were retained. SVG displacement, WebGL/Three scenes,
continuous effects, GSAP wrappers and copied components were rejected as too
expensive or unnecessary for a low-resource information product.

## Preferences, accessibility and performance

- `prefers-reduced-motion` removes transforms and delays while retaining short
  opacity and colour feedback; loading spinners and pulse effects stop.
- `prefers-reduced-transparency` replaces glass with a 98% solid surface and
  disables backdrop filters.
- `prefers-contrast: more` strengthens text, dividers, borders and active
  navigation without turning focus blue into selection state.
- Keyboard focus is a separate 3 px blue outline. Active navigation uses a
  neutral fill and graphite underline.
- Buttons, selects and icon controls have at least 44 px targets. Focus order,
  native semantics, headings, labels and live regions remain intact.
- Only `opacity` and `transform` may animate geometrically. Backdrop blur is
  static. Charts opt out of Recharts animation and expose an accessibility
  layer.
- No font payload, image payload, WebGL scene or animation library other than
  `motion` is added.

## Page guidance

- Home: limited strong glass for the two coverage explanations; one clear
  primary action and one secondary action; solid disclaimer.
- Universities: compact glass may hold the search toolbar; filters, results and
  pagination stay solid and dense.
- University and Program detail: one strong-glass summary header; all offering,
  provenance and fact groups are solid or sunken.
- University and Program comparison: solid columns and tables, neutral facts,
  no winner colour or animated ranking.
- Recommendations: inputs are visually separate from results; explanations and
  uncertainty stay primary; results do not animate.
- My List: saved entries, score and Telegram controls use solid panels; only
  confirmed states use success colour.
- Monitor: graphite is observed data, amber is cutoff/projected data, and the
  grid is neutral. Data keys, calculations and series meaning must not change
  during presentation work.
