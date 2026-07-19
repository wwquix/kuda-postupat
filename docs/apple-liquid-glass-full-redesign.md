# Apple-inspired Liquid Glass full redesign result

Milestone: `M-APPLE-LIQUID-GLASS-FULL-REDESIGN-01`

## Audit and direction

The initial frontend mixed warm cream and green brand aliases, opaque nested
cards, inconsistent spacing, small icon targets and page-specific interaction
styles. Glass was limited to the shell and Home, so internal pages did not read
as one product. Loading pulse, abrupt conditional mounts and default chart
animation also conflicted with a restrained information interface.

The final direction is a neutral Apple-inspired light system: cool static page
depth, graphite typography, action blue, sparse translucent material and solid
dense data surfaces. Active navigation and focus are deliberately different.
Missing or uncertain admissions data keeps its existing honest wording.

## Redesigned pages

The shared shell and all public routes now use the same semantic system:

- Home and mobile/desktop navigation;
- University catalog and University detail;
- University comparison;
- Program detail and Program comparison;
- Recommendations;
- My List, including score, watch and Telegram states;
- Monitor, including loading, stale, collector and error states;
- not-found route.

Routing, URL state, API requests, anonymous-profile ownership, calculations,
chart data keys and admission semantics were preserved. No backend, API, model,
migration or SQLite file was changed.

## Motion result

Accepted motion is limited to purposeful state communication:

- all pressables: 120 ms direct feedback, on each press;
- Home coverage surfaces: one 220 ms opacity/small-scale materialisation per
  mount with a 40 ms stagger;
- mobile navigation: 240 ms opacity/small-scale enter and exit per explicit
  toggle, using the drawer curve;
- saved confirmation and request errors: 180 ms opacity presence transition per
  state change;
- occasional monitor/state panels: 200 ms opacity crossfade.

Looping skeletons, large page entrances, rank/result movement, chart drawing,
hover translation, spring overshoot, scale-from-zero, WebGL distortion and
decorative continuous motion were rejected. CSS handles predetermined motion;
`motion/react` handles only lifecycle presence for the mobile menu and save
feedback. WAAPI was not needed.

## Dependencies and references

`motion` 12.42.2 was added as the only animation dependency and React imports
come from `motion/react`. No `framer-motion` package was installed.

React Bits material, blur and entrance examples were inspected. Their material
layering and edge-separation principles informed the local CSS, while SVG
displacement, Three/WebGL FluidGlass, GSAP wrappers and direct component copies
were rejected. The resulting implementation is local CSS plus two narrow
Motion presence boundaries.

## Accessibility and performance

The redesign retains semantic controls, headings, live regions, skip link,
keyboard menu behavior and focus restoration. It adds 44 px minimum controls,
visible blue focus, neutral active navigation, chart accessibility layers and
explicit reduced-motion, reduced-transparency and increased-contrast modes.
Recharts series animation is disabled.

Production bundle baseline before the milestone:

| Asset | Raw | Gzip |
| --- | ---: | ---: |
| CSS | 32,743 B | 6.99 kB |
| JavaScript | 801,128 B | 224.17 kB |

Post-redesign production build:

| Asset | Raw | Gzip | Change from baseline |
| --- | ---: | ---: | ---: |
| CSS | 33,458 B | 7.45 kB | +715 B raw; +0.46 kB in Vite output |
| JavaScript | 880,884 B | 251.93 kB | +79,756 B raw; +27.76 kB in Vite output |

The current files compress to 7,353 B CSS and 248,407 B JavaScript with Python
gzip level 9. `LazyMotion` with `domAnimation` is used instead of the full
`motion` component feature set; this reduced the first redesigned build from
927.21 kB / 265.28 kB gzip in Vite output to the final 880.88 kB / 251.93 kB.

## Browser QA and screenshots

QA used the documented development-safe backend mode with a disposable copied
and migrated database outside the repository. The project database counters
were identical before and after. All nine public page types were inspected at
1280 px, required mobile pages at 375 px, and all nine routes at 320 px. No
route had document-level horizontal overflow. The mobile menu was opened and
closed with Escape, with focus returned to its trigger.

Browser preference emulation confirmed:

- reduced motion: transform `none`, retained 160 ms opacity/colour feedback;
- reduced transparency: backdrop filter `none`, 98% solid white material;
- increased contrast: secondary text `#3a3a3e`, stronger 34% border token.

Screenshots are outside tracked source files under:

`C:/Users/Yura/.codex/visualizations/2026/07/19/019f7b8b-5358-7e03-84c9-9030250161c7/liquid-glass-qa/`

Exact files:

- `desktop-home-1280.png`
- `desktop-universities-1280.png`
- `desktop-university-comparison-1280.png`
- `desktop-program-comparison-1280.png`
- `desktop-recommendations-1280.png`
- `desktop-my-list-1280.png`
- `desktop-monitor-1280.png`
- `desktop-university-detail-1280.png`
- `desktop-program-detail-1280.png`
- `mobile-home-375.png`
- `mobile-universities-375.png`
- `mobile-my-list-375.png`
- `mobile-monitor-375.png`
- `mobile-navigation-open-375.png`
- `preference-reduced-motion-375.png`
- `preference-reduced-transparency-375.png`
- `preference-increased-contrast-375.png`
