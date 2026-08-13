# Automix Configuration schema version 1

Create a complete TOML configuration with `podcast-automix --write-config automix.toml`. Existing
files are protected unless `--overwrite` is supplied. Load it with
`podcast-automix --config automix.toml host.wav guest.wav`; explicit setting flags take precedence.
Configuration writing cannot be combined with inputs, preview options, `--output-dir`, or
`--diagnostics`.

Version 1 accepts only `schema_version = 1` and one `[settings]` table. Unknown keys, duplicate
keys, non-finite values, wrong scalar types, and files larger than 64 KiB are rejected. Settings
may be omitted to inherit defaults:

```toml
schema_version = 1

[settings]
attenuation_db = -6.0
frame_ms = 20
ambiguity_db = 9.0
preroll_ms = 150
hold_ms = 400
open_ms = 50.0
close_ms = 500.0
segment_seconds = 30
```

`attenuation_db` must be zero or less. `ambiguity_db`, `preroll_ms`, and `hold_ms` must be zero or
greater. All other values must be greater than zero; `frame_ms`, `preroll_ms`, `hold_ms`, and
`segment_seconds` are integers.

Readers reject schema versions other than `1`. Additive settings therefore require a new schema
version rather than silently changing version 1. Configuration files contain engine settings only:
input paths, output destinations, preview bounds, overwrite behavior, diagnostics, JSON mode, UI
preferences, presets, and environment-specific values are deliberately excluded.
