# TanStack Charts for audio gain-reduction visualizations

Research date: 2026-08-13. Sources are limited to TanStack's official documentation, the published `@tanstack/charts` 0.11.0 package installed in this repository, and the existing repository integration.

## Recommendation

For the desktop Editorial Timeline, use TanStack Charts for gain-reduction history and related analytical views, but keep playback/scrubbing and the high-density audio waveform application-owned.

The primary gain-reduction view should be aligned per-track small multiples. Each lane should layer:

1. `areaY` from a fixed `0 dB` baseline down to the negative attenuation value;
2. `lineY` on the same samples for a crisp boundary;
3. `ruleY([0])` as the common no-reduction reference;
4. an application-owned vertical playhead over every lane.

This matches the actual reader task: follow control action over ordered time, compare tracks at the same instant, and see magnitude from a meaningful zero baseline. TanStack recommends line for change over time, area for magnitude against a baseline, aligned small multiples instead of dual axes, and application-owned controls for time navigation. [Choosing a Chart](https://tanstack.com/charts/latest/docs/guides/choosing-a-chart)

Do not stack the tracks: stacking answers contribution-to-total questions and makes interior series hard to compare. Gain reduction per microphone is independent and needs a common baseline.

## Three worthwhile prototypes

### 1. Attenuation lanes (recommended production direction)

- One short lane per microphone, all with an identical x domain and y domain such as `[-24, 0]` dB.
- Filled negative area plus boundary line.
- Stable track colors, labels, current GR, average GR, and maximum GR.
- `focus: 'group-x'` for one value per series at the nearest time and a synchronized external playhead/scrubber.
- A single common time ruler can sit below the lane stack. The application should keep the lane definitions on the same explicit scale domains.

Use this to judge simultaneous attenuation, overlap, handoffs, pumping, and release tails.

### 2. Overview heatmap

- Rows are microphones, columns are bounded time buckets, and color encodes attenuation magnitude.
- Preserve a textual value/tooltip and a visible scale legend; color must not be the only carrier of essential state.
- Use this as a compact overview above or beside the detailed lanes, not as the only diagnostic view.

This is valuable when many tracks would make full lanes too tall. It should use a bounded representation sized to available pixels rather than drawing every automation sample. [Large Data](https://tanstack.com/charts/latest/docs/guides/large-data)

### 3. Distribution/summary view

- Per-track histograms or box/violin marks for “how much time did this track spend at each attenuation?”
- Add explicit mean and maximum reduction numbers.
- This complements, rather than replaces, the timeline because it loses temporal attack/release behavior.

## Composition, scales, and facets

TanStack marks paint in declaration order, so areas belong first, then reference rules, then lines and highlights. Explicit mark IDs and datum keys are important when definitions update or layers are conditional, because they preserve reconciliation identity. [Marks and Layering](https://tanstack.com/charts/latest/docs/concepts/marks-and-layering)

`facet`/`facetChart` can repeat one chart by microphone, with `columns`, `minWidth`, `gap`, `label`, and `axes: 'outer' | 'cell'`. However, for the selected wide desktop transport, separately rendered lane charts may be easier to align with track headers, collapse controls, scrolling, and one application-owned playhead. The product should use facets only if their layout remains compatible with the transport grid. [Faceting and Composition](https://tanstack.com/charts/latest/docs/guides/faceting-and-composition)

Shared comparability must be explicit:

- Use the same x domain for all lanes (preview start through preview end).
- Use the same y domain for all tracks so lane heights are comparable.
- Keep zero visible at the top and attenuation extending downward.
- Do not auto-domain each microphone independently.

The installed 0.11.0 project currently imports `scaleLinear` from `@tanstack/charts/scales/linear`; the latest public docs instead describe application-owned D3 scale imports. For work on the current dependency, follow the installed 0.11.0 exports and existing report implementation, then revisit imports only as part of an intentional package upgrade. [Scales and D3](https://tanstack.com/charts/latest/docs/concepts/scales-and-d3)

## Focus, tooltips, and transport interaction

Use native chart focus for sample inspection and keyboard navigation. `group-x` is designed for comparing multiple series at the same x value. The React adapter exposes `onFocusChange`, `onFocusGroupChange`, and `onSelect`; grouped callbacks return the original typed data for all focused points. The tooltip can show timestamp plus per-track attenuation. [Tooltips and Focus](https://tanstack.com/charts/latest/docs/guides/tooltips-and-focus)

Playback navigation is a different interaction contract. TanStack explicitly assigns free cursors, synchronized views, scrollable resource lanes, and playback scrubbers to controlled application state. Therefore:

- audio time is the source of truth;
- the app draws the common playhead and translates pointer position to time;
- clicking/dragging the timeline seeks audio;
- chart focus remains inspection-only, or is disabled while a scrub gesture owns the surface;
- keyboard transport shortcuts remain application controls rather than chart point navigation.

[Interactions and Selections](https://tanstack.com/charts/latest/docs/guides/interactions-and-selections)

## Dynamic data and performance

- Prepare and downsample automation rows in application code, memoized by source data and viewport width.
- Bound vertices to the useful horizontal pixel resolution. Preserve extrema when bucketing so short deep reductions do not disappear.
- Keep stable datum keys across updates; do not rebuild rows on every playhead animation frame.
- Move the playhead independently of chart data. Recompiling all charts at audio-frame cadence would waste work and risk jitter.
- SVG is appropriate for bounded analytical lanes. Canvas is useful only after measurement shows scene painting is the bottleneck; it does not fix an over-dense representation.
- For many focusable points, first reduce to a meaningful bounded representation; only then consider a spatial index.

These follow TanStack's guidance to count source, represented, prepared, and rendered complexity separately and to treat representation as the first performance decision. [Large Data](https://tanstack.com/charts/latest/docs/guides/large-data) [Bundle Size and Performance](https://tanstack.com/charts/latest/docs/guides/bundle-size-and-performance) [Transforms and Reactivity](https://tanstack.com/charts/latest/docs/guides/transforms-and-reactivity)

## Custom marks and renderers

Do not start with a custom mark. The desired GR geometry is already expressible as `areaY + lineY + ruleY`, and built-in composition retains type inference, focus metadata, animation, and package boundaries. Use `createMark` only if a genuinely new geometry cannot be built from standard marks; custom marks must emit deterministic keyed scene nodes and typed interaction points. A custom renderer is a larger commitment for changing the mounted surface, not a shortcut for ordinary styling. [Custom Marks and Renderers](https://tanstack.com/charts/latest/docs/guides/custom-marks-and-renderers)

The audio waveform is the exception: it is a dense transport surface with specialized peak-envelope preparation and application-owned scrubbing. Keeping that renderer separate avoids forcing chart datum focus onto playback behavior while still allowing the analytical GR lanes to use TanStack.

## Verified 0.11.0 public API in this repository

The installed package is exactly `@tanstack/charts` 0.11.0. Its published `package.json` and declaration files confirm these imports:

```tsx
import {
  areaY,
  defineChart,
  facet,
  facetChart,
  lineY,
  ruleX,
  ruleY,
} from '@tanstack/charts'
import { scaleLinear } from '@tanstack/charts/scales/linear'
import { tooltip } from '@tanstack/charts/tooltip'
import { Chart } from '@tanstack/charts/react/tooltip'
```

Relevant 0.11.0 options confirmed from its public declarations:

- `areaY`: `x`, `y`, `y1`, `y2`, `z`, `color`, `key`, `fill`, `fillOpacity`, `stroke`, `strokeWidth`, `curve`, `layout`, `states`.
- `lineY`: `x`, `y`, `z`, `color`, `key`, `stroke`, `strokeOpacity`, `strokeWidth`, `strokeDasharray`, `points`, `curve`, `states`.
- `facet`/`facetChart`: `by`, `chart`, `columns`, `minWidth`, `gap`, `label`, `axes`.
- React `Chart`: `definition`, `ariaLabel`, optional sizing, and `onFocusChange`, `onFocusGroupChange`, `onSelect`, `onRender`.

The current report already proves the compatible 0.11.0 integration pattern in `report-ui/src.tsx`: it defines grouped gain lines with `focus: 'group-x'`, spreads the `tooltip` extension into the tooltip definition, and renders via `@tanstack/charts/react/tooltip`. Treat that local implementation and the installed declaration files as authoritative for the prototype until dependency upgrade work is explicitly scheduled.

## Prototype acceptance checks

- Every lane uses the identical dB and time domains.
- Zero reduction is visually explicit; attenuation direction is unambiguous.
- Hovering one time shows all tracks at that time.
- Pointer and keyboard users can reach equivalent inspected values.
- The playhead remains smooth without chart recompilation.
- Seeking is usable independently of datum focus.
- Short reduction peaks survive downsampling.
- Track identity is stable across lanes, tooltip, legend, and report.
- Exact mean/max values remain available in text.
- The widest expected track count remains legible on the desktop target.

