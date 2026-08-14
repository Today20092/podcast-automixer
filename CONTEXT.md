# Podcast Automixer

Podcast Automixer helps podcast editors turn synchronized microphone recordings into a balanced mix while retaining control over what they review and render.

## Language

**Podcast Editor**:
The person who selects synchronized microphone recordings, judges the automated mix, and decides whether to render it.
_Avoid_: User, operator

**Recording Set**:
Two or more synchronized microphone recordings selected together for one podcast mix.
_Avoid_: Upload, batch, file collection

**Preview Run**:
A short automix of a section chosen by the Podcast Editor, used to judge the result before committing to a full render.
_Avoid_: Sample, demo, test mix

**Full Render**:
An automix of the entire Recording Set that produces processed microphone recordings and a visual report for the Podcast Editor's existing editing workflow.
_Avoid_: Final episode, mixdown, export

**Mix Report**:
The visual explanation of an automix, including microphone ownership, attenuation, gain, balance, loudness, and moments the Podcast Editor may want to review.
_Avoid_: Diagnostics page, analytics dashboard

**Comparison Playback**:
Loudness-matched playback that switches between the original and automixed versions at the same position so the Podcast Editor can judge the processing rather than a volume difference.
_Avoid_: A/B test, before-and-after files

**Monitoring Mix**:
The equal combination of the original microphone recordings used only for Comparison Playback, with anti-clipping protection and playback loudness matching but no change to source files.
_Avoid_: Original render, raw mix

**Automix Engine**:
The existing application capability that validates a Recording Set and produces Preview Runs, Full Renders, and Mix Reports.
_Avoid_: Backend, audio pipeline

**Desktop Shell**:
The local application surface that manages recordings, playback, progress, cancellation, and the Podcast Editor's journey while delegating audio work to the Automix Engine.
_Avoid_: GUI, frontend wrapper

**Safe Defaults**:
The standard mixing choices intended to produce a useful Preview Run without requiring the Podcast Editor to understand advanced audio parameters.
_Avoid_: Basic mode, beginner settings
