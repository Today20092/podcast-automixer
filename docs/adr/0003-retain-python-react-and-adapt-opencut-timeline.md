# Retain Python and React while adapting the OpenCut timeline

Podcast Automixer will keep its Python Automix Engine and React Desktop Shell while rebuilding the Diagnostic Timeline with attributed, MIT-licensed patterns and compatible code adapted from OpenCut Classic commit `cf5e79e`. The application processes synchronized recordings offline, so moving to JUCE, Rust, or Tauri would replace validated behavior and packaging without solving the current browser rendering bottleneck; JUCE remains a future option only if live audio or DAW plug-ins become committed product requirements.

## Consequences

Dense waveforms and Applied Gain plots use canvas, cached summaries, visible-range rendering, an imperative shared playhead, and animation-frame-coalesced resize work. Substantially adapted OpenCut code must retain its MIT notice in third-party notices, identify its pinned source in comments, and be acknowledged in the README.
