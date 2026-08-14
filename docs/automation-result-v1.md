# Automation Result schema version 1

`podcast-automix --json` is the noninteractive automation interface. It writes exactly one
UTF-8 JSON object and one newline to standard output. Handled outcomes leave standard error
empty. Do not combine `--json` with `--help` or `--version`.

Every result contains these keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Always `1` for this schema. |
| `cli_version` | string | Installed Podcast Automixer version. |
| `status` | string | `success` or `error`. |
| `inputs` | string array | Normalized input paths, or an empty array before validation. |
| `run` | object | `kind` is `automix` or `configuration`; automix runs may include preview bounds. |
| `settings` | object | Effective Automix Engine settings. |
| `artifacts` | string array | Normalized paths written by the command. |
| `warnings` | string array | Non-fatal notices. |
| `error` | object or null | On error, stable `code` and explanatory `message`. |

Exit status `0` means success, `2` means an expected input, configuration, collision, or processing
failure, `1` means an unexpected internal failure, and `130` means cancellation.
Stable error codes are `invalid_arguments`, `invalid_configuration`, `invalid_inputs`,
`output_collision`, `processing_failed`, `cancelled`, and `internal_failure`. Consumers must not
parse message text.

Version 1 may gain keys without changing `schema_version`; consumers must ignore unknown keys.
Existing keys retain their type and meaning. A future incompatible change increments the schema
version. JSON never contains non-finite numbers.

```json
{"schema_version":1,"cli_version":"0.2.0","status":"success","inputs":[],"run":{"kind":"configuration"},"settings":{"frame_ms":20},"artifacts":["/tmp/automix.toml"],"warnings":[],"error":null}
```

This contract excludes progress events, streaming output, shell completion, presets, and a public
Python API. Human-readable CLI output and messages are not part of the contract.
