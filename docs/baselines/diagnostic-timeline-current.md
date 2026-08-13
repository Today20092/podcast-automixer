# Diagnostic Timeline baseline

Measured commit: `0928650c073237d15a8a8cd3031d5a28df3d2a8e`

Runtime: Node.js 24.4.1, Playwright 1.54.2, Microsoft Edge (Chromium)

Scene: eight microphones, five-minute deterministic Preview Run, 1440 × 1000 viewport, light theme

| Workload | FPS | Long tasks (>50 ms) | React commits | Timeline redraws | Red |
| --- | ---: | ---: | ---: | ---: | --- |
| 10-second playback | 153.89 | 0 | 103 | 0 | No |
| Continuous resize | 133.39 | 0 | 0 | 29,760 | No |

Method: Playwright drove the real development browser route. `requestAnimationFrame` intervals produced FPS; the Long Tasks API captured interaction tasks; the React DevTools hook counted commits; an SVG/canvas `MutationObserver` counted timeline redraws. Screenshot coverage contains empty, one-, three-, six-, and eight-microphone scenes at 1440 × 1000 and 980 × 900 in light and dark themes. The harness marks a result red below 45 FPS or when any task exceeds 50 ms, but the baseline is informational.
