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

**Speech Evidence**:
The time-aligned indication of whether a microphone contains detected speech during a Preview Run.
_Avoid_: Activity bar, voice strip

**Automix Target**:
The time-aligned open-or-attenuate decision the Automix Engine asks a microphone's gain to approach.
_Avoid_: Gate state, active bar

**Applied Gain**:
The time-varying gain actually applied to a microphone as it moves toward the Automix Target, with 0 dB representing open.
_Avoid_: Gain reduction, attenuation graph

**Diagnostic Timeline**:
The synchronized review surface where the Podcast Editor compares microphone audio, Speech Evidence, Automix Targets, and Applied Gain without editing or retiming the Recording Set.
_Avoid_: Timeline editor, multitrack editor, diagnostics page

**Input Waveform**:
The visible amplitude history of an original microphone recording before the Automix Engine applies gain.
_Avoid_: Raw waveform, source graph

**Gain-Adjusted Waveform**:
The Input Waveform scaled by Applied Gain, shown against the original silhouette so attenuated passages visibly darken and contract.
_Avoid_: Output waveform, ducked bar

**Evidence Gap**:
A time interval for which the Diagnostic Timeline cannot establish Speech Evidence, an Automix Target, or Applied Gain; it represents unavailable knowledge, not an open microphone or 0 dB gain.
_Avoid_: Silence, zero, no activity

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
