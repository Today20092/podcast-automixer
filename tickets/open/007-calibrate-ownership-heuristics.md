---
id: 007
title: Calibrate ownership heuristics on representative sessions
status: open
priority: medium
triage: ready-for-human
assignee: null
---

## Problem

The 75th-percentile microphone calibration, 9 dB ambiguity window, 12 dB noise-floor margin, and default Silero thresholds are reasonable heuristics but are not validated against representative podcast recordings.

The current noise-floor estimate is one global 20th percentile of each stem's K-weighted frame energy. It is inexpensive and robust to loud outliers, but it can mistake digital silence, quiet speech, bleed, reverberation, or changing room noise for the background baseline. The estimator should be selected from downstream ownership evidence rather than sophistication alone.

## Scope

Build an evaluation corpus and compare ownership, overlap preservation, missed utterances, false openings, and audible pumping across parameter combinations.

Benchmark these noise-floor candidates behind a common evaluation interface:

1. The existing global, unconditional 20th-percentile baseline.
2. A time-varying, VAD-conditioned local quantile, using globally quiet frames from the synchronized stems, explicit speech guard intervals, digital-silence rejection, temporal smoothing, and a fallback for windows with insufficient eligible audio.
3. Median and median absolute deviation over VAD-rejected frames, including evaluation of a hybrid that uses a local low quantile for the floor and MAD to adapt the energetic margin.
4. A deterministic, regularized two-component Gaussian mixture over log-energy, with minimum component weight/separation rules and explicit handling of degenerate or single-population fits.
5. Kernel-density estimation of the low-energy mode if the preceding candidates do not clearly settle the choice, with documented bandwidth, minimum mode mass, and digital-silence rules.

Reserve multifeature robust clustering and spectral minimum-statistics/IMCRA estimation for a demonstrated failure of the simpler broadband candidates. Do not select them solely because they are more sophisticated. If escalation is justified, document the failing cases and the additional features or spectral decision rule required.

Treat estimator selection and production implementation as separate decisions. This ticket chooses and calibrates an approach; create a follow-up implementation ticket only after the results identify a winner.

## Acceptance criteria

- [ ] The corpus covers clean, noisy, reverberant, quiet-speaker, loud-speaker, overlap, laughter, breath, cough, and crosstalk cases.
- [ ] The corpus also covers changing HVAC or fan noise, electrical hum, keyboard/transient noise, long talk-heavy passages, short recordings, digital silence or edited gaps, muted microphones, and windows with few or no globally quiet frames.
- [ ] Expected ownership regions are annotated independently of implementation output.
- [ ] The existing global 20th percentile, VAD-conditioned local quantile, VAD-conditioned median/MAD, and regularized two-component GMM are evaluated through the same interface; KDE is included when the first comparison is inconclusive.
- [ ] VAD-conditioned candidates define whether eligibility requires per-mic or global silence, the speech guard interval, local window length, temporal smoothing, digital-silence rejection, boundary behavior, and fallback behavior when eligible evidence is insufficient.
- [ ] Every estimator reports a confidence signal derived from eligible duration/sample count and any method-specific fit quality; low-confidence behavior is explicit and tested.
- [ ] Current defaults and candidate settings are scored with documented metrics for ownership accuracy, false openings, missed speech and nonverbal human sounds, overlap preservation, gain-state churn, audible pumping, and robustness to changing noise.
- [ ] Runtime, determinism, diagnostic clarity, parameter sensitivity, and failure/fallback behavior are compared alongside accuracy.
- [ ] Percentile, local-window, guard-interval, smoothing, MAD-multiplier, mixture-regularization, and 12 dB energetic-margin choices are selected from corpus results rather than assumed defaults.
- [ ] Recommended defaults and known tradeoffs are recorded.
- [ ] Calibration behavior for stems with no detected speech is explicitly decided and tested.
- [ ] Any recommendation to adopt multifeature clustering, minimum statistics, or IMCRA identifies corpus failures that simpler broadband estimators cannot resolve and defines how its richer output feeds the ownership decision.
- [ ] The results explicitly decide whether to retain the current estimator, implement a selected replacement, or gather more representative data; any production change is deferred to a separately scoped implementation ticket.

## Verification

Publish a repeatable evaluation command, machine-readable per-session scores, and a concise results artifact containing aggregate metrics, representative failure cases, confidence behavior, listening-test observations, runtime, selected defaults, and the evidence supporting the chosen estimator.

Background research: [Noise-floor estimator comparison](../../docs/research/noise-floor-estimator-comparison.md).

## Log

- 2026-08-11: Created from the audio-analysis audit.
- 2026-08-12: Expanded noise-floor calibration into a comparative estimator evaluation. Added VAD-conditioned local quantile, median/MAD, regularized GMM, optional KDE, confidence/fallback requirements, adversarial corpus cases, downstream ownership metrics, and an evidence gate before any implementation ticket.
