# Gain-envelope math for the podcast automixer

## Question and conclusion

The automixer currently converts the inactive attenuation from decibels to a linear amplitude multiplier, then smooths each 20 ms target with an asymmetric first-order recurrence. It is an exponential/asymptotic approach in the **linear-amplitude domain**, not a finite linear ramp and not an S-curve.

That is sound, conventional de-zippering math, but its coefficient is only an approximation tied to the control-frame interval. For this offline podcast application, the strongest next design would be sample-rate-invariant coefficients and sample-level interpolation during rendering. Use either:

- an asymmetric one-pole smoother for easy re-targeting; or
- a finite-duration ramp, preferably linear in dB for perceptually even fades, optionally raised-cosine when zero endpoint slopes are worth the added shaping.

There is no universally best curve. The decision depends on whether `open_ms` and `close_ms` mean a filter time constant or a promised completion time. Airwindows supports the one-pole approach; it does not establish that Airwindows distortion or compression should be added to a transparent podcast automixer.

## What the current code does

In [`make_gain_envelopes`](../../src/podcast_automixer/core.py), the inactive target is

```text
floor_gain = 10^(attenuation_db / 20)
```

Thus `-6 dB` becomes approximately `0.5012`, and the rendered sample is multiplied by a gain between that value and `1.0`.

Preroll and hold first expand the binary activity mask. The code then chooses separate opening and closing coefficients:

```text
alpha_open  = min(1, frame_ms / open_ms)
alpha_close = min(1, frame_ms / close_ms)
gain[n] = gain[n-1] + alpha * (target[n] - gain[n-1])
```

This is a first-order IIR/one-pole smoother. For a constant target, the remaining error is multiplied by `(1 - alpha)` on every 20 ms frame, so the curve is exponential and never mathematically reaches the target unless `alpha = 1`. It is not an S-curve: its slope is greatest immediately after a target change and then decays toward zero.

A subtle naming issue follows: `open_ms` and `close_ms` are not exact fade durations. With the current `alpha = frame_ms / time_ms`, the setting behaves approximately like a time constant. A one-pole reaches about 63.2% of a step after one time constant and about 95% after three. The W3C Web Audio specification defines the same target-following behavior explicitly as `V1 + (V0 - V1)e^(-(t-T0)/tau)` and documents the 63.2% interpretation ([Web Audio `setTargetAtTime`](https://www.w3.org/TR/webaudio-1.0/#dom-audioparam-settargetattime)).

## Relevant Airwindows work

Only a few Airwindows components are directly relevant to transparent gain automation:

### PurestGain

`PurestGainProc.cpp` converts dB to amplitude with `pow(10, dB/20)` and chases the target per sample using the form

```text
gain[n] = (chase * gain[n-1] + target) / (chase + 1)
```

This rearranges to the same one-pole family used by the automixer. PurestGain adapts its chase speed and applies another smoothed fader stage. It is exponential smoothing in linear amplitude, not an S-curve ([PurestGain source](https://github.com/airwindows/airwindows/blob/master/plugins/LinuxVST/src/PurestGain/PurestGainProc.cpp)). Airwindows describes it as intended for aggressive, zipper-free fader motion ([Airwindopedia, PurestGain/PurestFade](https://github.com/airwindows/airwindows/blob/master/Airwindopedia.txt#L4167-L4195)).

### PurestFade

PurestFade uses the same one-pole chase but changes the speed as the target approaches silence, making it relevant to long fades rather than ordinary dialogue gating ([PurestFade source](https://github.com/airwindows/airwindows/blob/master/plugins/LinuxVST/src/PurestFade/PurestFadeProc.cpp)). Its target-dependent slowing is not needed for a floor of only -6 dB.

### EveryTrim and BitShiftGain

EveryTrim confirms the ordinary transparent trim operation: convert dB by `10^(dB/20)` and multiply the sample ([EveryTrim source](https://github.com/airwindows/airwindows/blob/master/plugins/LinuxVST/src/EveryTrim/EveryTrimProc.cpp)). BitShiftGain restricts gain to powers of two, roughly 6.02 dB steps; that is useful for exact binary scaling but unsuitable for smooth automation ([BitShiftGain source](https://github.com/airwindows/airwindows/blob/master/plugins/LinuxVST/src/BitShiftGain/BitShiftGainProc.cpp)).

Airwindows saturation, distortion, console, and compression plugins deliberately change timbre or dynamics. They solve different problems and should not be inserted into the automixer merely to improve gain interpolation.

## Curve comparison

| Method | Formula/behavior | Strength | Limitation | Fit here |
|---|---|---|---|---|
| Linear amplitude | `g = g0 + (g1-g0)u` | Exact duration, simple | Perceived loudness movement can bunch toward one end | Acceptable for short, shallow moves |
| One-pole amplitude | `g = target + a(g_prev-target)` | Re-targets smoothly; robust | Asymptotic; setting is a time constant, not completion time | Good, especially for changing decisions |
| Linear dB | interpolate dB, then `g=10^(dB/20)` | Perceptually regular gain change; exact duration | Cannot include true zero without a floor/special case | Very good here because the floor is -6 dB |
| Raised-cosine/S-curve | `u=(1-cos(pi*t))/2` | Exact duration; zero slope at both endpoints | Slower start/end; must define behavior when re-targeted mid-ramp | Optional polish, not inherently “best” |
| Equal-power crossfade | complementary sine/cosine gains | Helps maintain power when crossfading independent signals | Raises/combines gain and assumes a crossfade problem | Wrong default for independently attenuating correlated mic bleed |

The Web Audio specification separately defines finite linear ramps, finite exponential ramps, and target-following exponential smoothing, confirming these are different automation semantics rather than quality tiers ([Web Audio AudioParam automation](https://www.w3.org/TR/webaudio-1.0/#audioparam-automation)). JUCE likewise provides linear and multiplicative `SmoothedValue` modes, describing multiplicative smoothing as useful for logarithmic quantities such as volume in dB and noting that it cannot reach zero ([JUCE `SmoothedValue`](https://docs.juce.com/master/classjuce_1_1SmoothedValue.html)).

## Clicks and zipper noise

A discontinuous gain applied to nonzero audio creates a discontinuity in the output waveform; repeated coarse parameter steps produce zipper noise. The practical remedy is continuous sample-level gain or accurate interpolation between control points. The VST3 automation guidance requires processors to reconstruct automation curves from parameter points with sample accuracy ([Steinberg VST3 parameter automation](https://steinbergmedia.github.io/vst3_dev_portal/pages/Technical%2BDocumentation/Parameters%2BAutomation/Index.html)).

The current envelope changes only once per 20 ms analysis frame. If rendering holds each frame's value constant, that leaves small steps even though the control values themselves are smoothed. The most consequential improvement is therefore sample-level interpolation during render, not changing from an exponential curve to a fashionable easing curve.

## Recommended implementation direction

1. Keep the existing deterministic asymmetric attack/release design.
2. Define the setting semantics explicitly:
   - for a one-pole time constant, use `a = exp(-1/(tau * fs))` and `g[n] = target + a*(g[n-1]-target)` at audio sample rate; or
   - for exact transition time, generate a finite ramp between the current and target gains.
3. Because this automixer moves only between 0 dB and -6 dB, linear interpolation in dB is a strong finite-ramp default; it never encounters the zero-gain problem.
4. If listening tests show edge character, compare linear-dB against raised-cosine ramps using the same durations. Do not assume an S-curve wins without tests on speech and bleed.
5. Preserve continuity when a target changes during a ramp: begin the new ramp from the current gain, never from the previous target.
6. Apply gain sample by sample or interpolate it per sample from control-rate values. NumPy is sufficient; a custom recurrence is clearer than adding a dependency.

SciPy can implement a causal difference equation with state through [`scipy.signal.lfilter`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html), but for a single asymmetric, target-dependent smoother, a short NumPy/Python recurrence (or a compiled loop if profiling requires it) is easier to audit. SciPy window functions such as [`tukey`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.windows.tukey.html) can generate shaped windows, but those analysis windows are not a dedicated gain-automation system.

## Bottom line

The current math is legitimate and closely related to Airwindows PurestGain: dB-to-linear conversion followed by a linear-amplitude one-pole chase. It is already eased in the sense that it approaches the target exponentially, but it is not an S-curve. The priority improvement is sample-rate-invariant, sample-level smoothing with clearly defined timing semantics. For this conservative -6 dB podcast automixer, transparent gain multiplication is preferable to borrowing Airwindows coloration, compression, or distortion stages.
