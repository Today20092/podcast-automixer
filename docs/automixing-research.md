# Offline podcast stem automixing research

## Decision summary

For three synchronized, isolated podcast microphone stems, use a **hybrid speech-and-ownership detector** to drive a deliberately shallow gain rider:

1. Preserve each 48 kHz stem as its own output. Analyze a temporary mono 16 kHz sidechain, but never resample the output audio.
2. Run a voice activity detector (VAD) on each sidechain to estimate whether speech is present.
3. In short overlapping windows, compare smoothed, speech-band-weighted energy across all three microphones. The microphone(s) that are plausibly close to the strongest channel own the speech; a much quieter correlated copy is probably bleed.
4. Keep every plausible active microphone at exactly unity gain. When uncertain, keep it open.
5. Move only clearly inactive microphones toward -6 dB, using fast opening, look-ahead/pre-roll, hold, and slow release.
6. Do not normalize, compress, limit, transcribe, or apply a full Dugan gain-share to these replacement stems.

This is not conventional loudness leveling. It is conservative, offline microphone activity automation designed to reduce bleed without changing the intended speaker level.

## What “voice detection” means

Voice activity detection classifies short frames as speech or non-speech. It does **not** transcribe words and, by itself, does not know which person is speaking. The official WebRTC VAD API returns active/non-active voice for fixed 10, 20, or 30 ms frames.[^webrtc] Silero VAD instead provides a small neural VAD and utilities that produce speech timestamps; its official implementation supports 8 kHz and 16 kHz analysis audio.[^silero]

For these files, a VAD solves only half the problem. Bleed from person A can contain perfectly valid speech on microphones B and C, so all three independent VADs may correctly report “speech.” The second half is **source ownership**: compare synchronized channels to decide which microphone captured the voice directly and which captured a quieter copy.

This is a documented difficulty in wearable/personal-microphone meeting recordings: simple per-channel approaches can fail because of crosstalk and channel variation. In one multichannel meeting study, feature normalization plus cross-correlation post-processing reduced frame error by 35% relative to its baseline.[^icsi] A later distributed-microphone speech-activity study similarly uses relative speech/non-speech energy and cross-correlation between channels as localization evidence.[^room-sad]

## Comparison of candidate control signals

### Peak level

Peak level is useful for clipping checks, not speaker activity. A click, plosive, handling noise, or consonant can dominate a peak measurement while conveying little evidence about sustained speech. It is too unstable to be the primary control signal.

**Use:** optional transient guard in the detector.  
**Do not use:** as the automixer's main activity measurement.

### Short-window RMS or power envelope

RMS/power over roughly 20–50 ms is cheap, deterministic, and directly useful for comparing the same acoustic event across synchronized microphones. Smoothing and a speech-band sidechain make it less sensitive to rumble and isolated peaks. Relative dB differences across microphones are more useful than a single absolute threshold because recording levels and speakers vary.

However, RMS alone cannot distinguish speech from laughter, table bumps, HVAC, or music. Fixed thresholds also fail when quiet speakers and noise floors differ. Therefore RMS should provide the **ownership score**, not the complete speech decision.

### LUFS / BS.1770 loudness

ITU-R BS.1770 is a programme-loudness and true-peak measurement standard using K-weighting and mean-square energy; EBU Mode defines 400 ms Momentary, 3 s Short-term, and Integrated measurements.[^bs1770][^ebu-loudness] Those windows and goals are appropriate for loudness metering and delivery normalization, not syllable-level microphone decisions. Even 400 ms Momentary loudness is slower than the desired opening behavior, while Integrated LUFS describes a programme or long region rather than who owns a word.

**Use:** final programme QC elsewhere in the Resolve workflow if desired.  
**Do not use:** as the activity gate or to equalize these stems.

### Classic Dugan-style gain sharing

Dugan gain sharing continuously assigns each microphone a fraction of the available system gain based on its level relative to the combined input. Manufacturer documentation describes the channel automix gain as the channel level divided by the level of the summed inputs.[^yamaha-dugan] It maintains natural ambience and avoids hard gating; when several people speak, the gain is shared.[^dugan-manual] This is excellent for live sound, where controlling the number of open microphones and acoustic gain is central.

It does not precisely match this project's requirement. With two equally strong speakers, classic gain sharing attenuates both rather than leaving both replacement stems at unity. It can also apply far more than the requested -6 dB to quiet microphones. Therefore borrow its continuous, relative-level philosophy, but **do not implement its constant-total-gain rule**.

### Classical WebRTC VAD

Advantages: tiny, fast, deterministic, supports short frames, and has no model download. The official header documents binary decisions on 10/20/30 ms frames (the current upstream header lists 8, 16, and 32 kHz).[^webrtc]

Tradeoffs: binary output provides less confidence information for conservative ambiguity handling, and per-mic VAD still detects intelligible bleed as speech. It is a good fallback or lightweight mode.

### Neural VAD (Silero)

Advantages: produces a continuous speech probability that can be hysteresis-smoothed, is designed for local inference, and has an official Python-facing repository with speech timestamp utilities.[^silero] Because this is offline processing, modest model inference cost is acceptable.

Tradeoffs: the sidechain must be downsampled to a supported speech rate, model/runtime versions should be pinned for repeatability, and it still cannot identify the owning microphone on its own.

**Recommendation:** use Silero VAD first, with WebRTC VAD as a future lightweight fallback. Downsampling is analysis-only; automation is applied sample-accurately to the original-rate float audio.

### Speaker diarization or target-speaker VAD

Speaker diarization models can detect speech, speaker changes, overlaps, and speaker identity structure. The official pyannote.audio project exposes building blocks for speech activity, overlapped speech detection, speaker change detection, and embeddings.[^pyannote] These tools are valuable for a mixed recording where speaker identity is unknown.

Here, track identity is already supplied by Resolve: A01/A02/A03 each correspond to a microphone. Full diarization adds model size, inference time, tuning, and identity-assignment failure modes without replacing the need for cross-mic bleed handling. It is not justified for version 1.

### Transcription / ASR

ASR answers “what words were spoken,” not “which synchronized microphone is the clean owner at this frame.” OpenAI's official Whisper implementation processes files with sliding 30-second windows and performs autoregressive sequence-to-sequence decoding.[^whisper] That is vastly heavier and temporally coarser than a short-frame control sidechain. Word timestamps also require decoding/alignment machinery that is unnecessary for preserving consonant onsets when offline look-ahead is available.

ASR may become useful later for transcript-based editing, chaptering, or manual review markers. It should not control gain in version 1.

## Recommended detector and gain logic

### Analysis path

- Validate that the three files have compatible starts, sample rates, channel layouts, and expected durations.
- Keep original samples in floating point at their native sample rate.
- Build analysis-only mono sidechains, downsampled to 16 kHz for Silero.
- Compute VAD probabilities and a smoothed speech-band power envelope in overlapping short windows.
- Estimate per-channel baseline/noise and typical speech level so a naturally quiet microphone is not systematically penalized.

### Speech ownership

For each frame:

- If no channel has convincing VAD probability, treat all microphones as inactive.
- If speech is present, rank channels by normalized short-window energy.
- Keep the strongest plausible microphone at unity.
- Also keep any other microphone at unity when it has strong independent evidence or is close enough to the leader to represent genuine simultaneous speech.
- Treat a substantially quieter, highly similar/correlated copy as bleed and allow it to attenuate.
- Bias ambiguity toward unity. The cost of 100 ms of extra room tone is lower than suppressing a quiet word or overlap.

Cross-correlation can be added as a refinement after listening tests. It has research support for crosstalk detection,[^icsi] but version 1 can begin with VAD plus normalized relative energy because the attenuation is only 6 dB and the uncertainty rule is conservative.

### Gain envelope

- Active target: 0 dB adjustment.
- Inactive target: -6 dB adjustment, user-adjustable later.
- Open/attack: about 50 ms.
- Offline pre-roll/look-ahead: about 150 ms.
- Hold after speech: about 400 ms.
- Release toward attenuation: about 500 ms.
- Smooth gain in the linear-amplitude domain or with a well-defined dB ramp; avoid block-edge discontinuities.

These values are starting points, not standards. Tune them by listening to the supplied recordings, especially breaths, low-level interjections, laughter, and crosstalk.

## File-format preservation

Read and write through a library that exposes the input format metadata and floating-point samples. libsndfile supports WAV through a common API and distinguishes floating-point file data; its documentation also notes WAV floating-point-specific behavior such as PEAK chunks.[^libsndfile-api][^libsndfile-command] For each output:

- retain the input sample rate (48 kHz for the supplied workflow);
- retain channel count;
- retain the input numerical subtype (`FLOAT` for 32-bit IEEE float WAV);
- retain frame count and alignment, padding a documented tiny mismatch only if policy allows;
- never quantize the main signal through an integer sidechain;
- write beside the original with `_auto-mixed.wav` and never overwrite silently.

“Same bit depth and sample rate” means the output encoding properties remain the same. The audio samples necessarily change wherever gain automation is applied, and non-audio WAV metadata chunks may require explicit copying if Resolve depends on them.

## Validation plan before locking thresholds

1. Render a diagnostic CSV or compact timeline showing VAD probability, relative channel energy, ownership state, and applied gain.
2. Audition known single-speaker, overlap, quiet-interjection, laughter, breath, and handling-noise regions.
3. Null-check each output against its input: differences should occur only where gain is below unity, with no timing offset or resampling.
4. Confirm sample rate, subtype, channel count, and exact frame count on every output.
5. Prefer missed attenuation over missed speech; adjust ownership margins before making VAD more aggressive.

## Sources

[^webrtc]: WebRTC source, [`webrtc_vad.h`](https://webrtc.googlesource.com/src/+/main/common_audio/vad/include/webrtc_vad.h).
[^silero]: Silero VAD, [official source repository](https://github.com/snakers4/silero-vad).
[^icsi]: Pfau, Ellis, and Stolcke, [“Multispeaker Speech Activity Detection for the ICSI Meeting Recorder”](https://www.sri.com/publication/speech-natural-language-pubs/multispeaker-speech-activity-detection-for-the-icsi-meeting-recorder/), IEEE ASRU 2001.
[^room-sad]: Zao et al., [“Room-localized speech activity detection in multi-microphone smart homes”](https://link.springer.com/article/10.1186/s13636-019-0158-8), EURASIP Journal on Audio, Speech, and Music Processing, 2019.
[^bs1770]: ITU-R, [Recommendation BS.1770-5: Algorithms to measure audio programme loudness and true-peak audio level](https://www.itu.int/rec/R-REC-BS.1770-5-202311-I), 2023.
[^ebu-loudness]: European Broadcasting Union, [Loudness specifications and EBU Mode overview](https://tech.ebu.ch/loudness/).
[^yamaha-dugan]: Yamaha Commercial Audio, [“Automatic Microphone Mixer” white paper](https://res.cloudinary.com/iwh/image/upload/q_auto,g_center/assets/1/26/Yamaha-DUGANMY16-White-Paper.pdf).
[^dugan-manual]: Dan Dugan Sound Design, [Model M User Guide: Theory of the Speech and Music Systems](https://www.dandugan.com/Assets/manuals/Model-M-User-Guide-v1.3.pdf).
[^pyannote]: pyannote, [official pyannote.audio repository](https://github.com/pyannote/pyannote-audio).
[^whisper]: OpenAI, [official Whisper repository](https://github.com/openai/whisper).
[^libsndfile-api]: libsndfile, [official API documentation](https://libsndfile.github.io/libsndfile/api.html).
[^libsndfile-command]: libsndfile, [official command documentation](https://libsndfile.github.io/libsndfile/command.html).
