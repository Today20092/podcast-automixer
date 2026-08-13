# Comparison diagnostic timeline prototype verdict

## Decision

Prototype D, the **Decision + response timeline**, is accepted as the primary visual reference for production implementation.

## Preserve

- Widescreen editorial timeline with one synchronized lane per microphone.
- Separate detected-speech and Automix-target strips above a filled applied-gain curve.
- A shared playhead and an inspector that explains speech, target, applied gain, and response state.
- A prominent green outline and subtle halo on open microphone lanes.
- Stable per-microphone colors, text labels, and non-color state cues.

## Implementation boundary

The prototype uses deterministic representative data to validate layout and interaction. Production code must consume real Recording Set and preview diagnostic data; prototype-generated state is reference material only and must not be promoted directly.
