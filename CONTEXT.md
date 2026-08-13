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

**Comparison Program**:
One of the three synchronized listening views available during Comparison Playback: Original, Automixed, or Difference.
_Avoid_: Track, file, mode

**Comparison Waveform**:
The synchronized visual overview of Original and Automixed audio used for seeking and following Comparison Playback. Difference is shown as its own centered waveform.
_Avoid_: Progress bar, scrubber

**Gain Reduction Timeline**:
Aligned per-microphone views of the attenuation applied by the Automix Engine over the same episode clock and decibel scale.
_Avoid_: Compression curve, volume waveform

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

**Guided CLI**:
The human-oriented command-line surface that guides a Podcast Editor through an Automix Engine run with readable prompts, progress, and results.
_Avoid_: Interactive mode, terminal UI

**Automation Contract**:
The versioned command-line surface for scripts and external tools, with deterministic noninteractive behavior, machine-readable results, and stable exit semantics.
_Avoid_: JSON mode, headless mode, API

**Automation Result**:
The single machine-readable account of an Automation Contract run, covering its outcome, effective choices, warnings, errors, and produced artifacts.
_Avoid_: Console output, JSON report, response

**Automix Configuration**:
A versioned, reusable set of Automix Engine choices that can reproduce mixing behavior across Recording Sets without carrying run-specific recordings or destinations.
_Avoid_: Preset, profile, project file

**Artifact Set**:
The processed microphone recordings, Mix Reports, and optional diagnostics produced together by one successful run.
_Avoid_: Output files, export bundle
