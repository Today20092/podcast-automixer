# Diagnostic Timeline baseline

Run `pnpm install`, `pnpm exec playwright install chromium`, then `pnpm baseline` from this directory.
The harness opens the development-only `?variant=B` Diagnostic Timeline in Chromium, creates deterministic empty/1/3/6/8-microphone five-minute scenes without audio or file selection, captures both viewport widths and themes, and writes screenshots plus `artifacts/baseline.json`.

The report records animation-frame intervals, Long Tasks, React commits, SVG/canvas redraws, runtime metadata, and a non-blocking `red` flag when sustained playback falls below 45 FPS or a task exceeds 50 ms. Current results are evidence, not a release gate.
