---
status: accepted
---

# Use pywebview for the first desktop shell

Build the Windows-first Desktop Shell with React, TypeScript, Tailwind, shadcn/ui, and TanStack Charts inside pywebview, using a narrow in-process bridge to the Python Automix Engine. This preserves the existing engine and avoids introducing Rust or Electron plus a Python sidecar before evidence requires that complexity; the packaged prototype must validate startup, accessibility, progress, responsive cancellation, playback, and WebView reliability, with Tauri as the fallback if pywebview fails those tests.
