# Cross-platform path, terminal drag/drop, and uv audit

Date: 2026-08-11

## Executive summary

The ordinary command-line path flow is fundamentally portable: `argparse` receives already-tokenized arguments, `_path()` converts them to the host platform's concrete `pathlib.Path`, and output names are formed with `Path.with_name()`. Paths with spaces therefore work when users invoke `podcast-automix` normally and let their shell perform its native quoting.

The interactive no-argument drag/drop flow is **not yet cross-platform**. `parse_dropped_paths()` implements a small PowerShell-oriented language: it recognizes quotes and PowerShell's backtick escape, but not the POSIX backslash escaping documented for macOS Terminal. A Finder-dropped path such as `/Users/me/My\ Recording.wav` is consequently split into two paths. The same parser also consumes a literal backtick in a valid Windows or POSIX filename. This is the highest-priority fix.

The uv setup is broadly portable and CI exercises Ubuntu, Windows, and macOS. However, the lockfile currently has PyTorch and torchaudio wheels for Apple Silicon macOS only, not Intel macOS. Because these packages have no source distributions in the lock, Intel macOS is not actually supported by the current resolution. uv's `required-environments` feature is designed to make this kind of promised platform support fail during resolution instead of later on a user's machine.

## Repository findings

### 1. Normal CLI arguments are portable

- `src/podcast_automixer/cli.py` declares `files` with `nargs="*"` and `type=_path`. The shell parses quoting before Python receives `sys.argv`; `argparse` then applies the `type` callable to each argument ([Python `argparse` documentation](https://docs.python.org/3/library/argparse.html#type)).
- `_path()` uses `Path(...).expanduser().resolve()`. A concrete `Path` selects the host path flavor, `expanduser()` expands `~`, and `resolve(strict=False)` makes the path absolute, removes `..`, and resolves as much as possible without requiring the final path to exist ([Python `pathlib` documentation](https://docs.python.org/3/library/pathlib.html#pathlib.Path.expanduser), [Python `Path.resolve`](https://docs.python.org/3/library/pathlib.html#pathlib.Path.resolve)).
- `inspect_inputs()` subsequently calls `Path.is_file()` before opening audio, so the non-strict resolution is followed by explicit validation.
- `output_path()` uses `path.with_name(f"{path.stem}{suffix}")`; it does not assemble paths using hard-coded `/` or `\\` separators.

Assessment: no change is required for paths passed as separate CLI arguments. Documentation examples should nevertheless show shell quoting for paths containing spaces.

### 2. Interactive drag/drop parsing fails for macOS/POSIX escaping

Apple documents that dragging a Finder file into Terminal inserts its absolute path, and separately documents backslash escaping or quotes for pathnames containing spaces ([Apple: Drag items into a Terminal window](https://support.apple.com/guide/terminal/drag-items-into-a-terminal-window-trml106/mac), [Apple: Specify files and folders in Terminal](https://support.apple.com/guide/terminal/specify-files-and-folders-apd3cf6fe02/mac)).

`parse_dropped_paths()` currently:

- treats a backtick as an escape everywhere;
- recognizes single and double quotes;
- treats a backslash as an ordinary character;
- splits on every unquoted whitespace character.

Therefore `/Users/me/My\ Recording.wav` becomes two tokens rather than one. It also changes a valid literal filename such as `take\`1.wav` into `take1.wav`. The prompt text says only that Windows pastes quoted paths, even though the README claims Windows, macOS, and Linux support.

The only focused test, `test_parse_powershell_drag_drop_paths_with_backtick_spaces`, covers three unquoted Windows paths whose spaces are backtick-escaped. There are no cases for:

- POSIX backslash-escaped spaces;
- single- or double-quoted POSIX paths;
- quoted Windows paths;
- Unicode, apostrophes, quotes, backticks, trailing backslashes, UNC paths, or extended-length Windows paths;
- malformed escape sequences;
- multiple paths produced by actual Finder/Terminal, Linux terminal, Command Prompt, and PowerShell drag/drop behavior.

Do not replace this parser wholesale with `shlex.split()` on every OS. Python explicitly states that `shlex` is designed for Unix shells and warns that its quoting is not guaranteed for Windows shells ([Python `shlex` documentation](https://docs.python.org/3/library/shlex.html)).

Recommended design, in priority order:

1. Define the interactive input as an application-owned format instead of trying to emulate every shell. The strongest portable contract is **one path per prompt/line, repeated exactly three times**. Dragging one file at a time avoids ambiguous shell tokenization and permits the entered text to be treated as one path after removing only one matching outer quote pair.
2. If one-line multi-file drop must remain, select parsing rules based on `os.name`: POSIX `shlex.split(..., posix=True)` for macOS/Linux and a separately tested Windows parser for PowerShell/Command Prompt forms. Preserve literal backticks except where Windows parsing rules conclusively identify them as escapes.
3. Convert tokens to `Path` only after lexical parsing. Do not strip arbitrary quote characters with `strip('"')`, because `str.strip()` removes any matching characters from both ends and can alter a legitimate filename.
4. Catch parser `ValueError` explicitly and turn it into a concise user-facing `AutomixError`/prompt retry; malformed pasted input should not rely on the broad outer exception path.
5. Update the prompt and README with platform-neutral instructions and quoted examples for PowerShell, Command Prompt, and POSIX shells.

Linux terminal drag/drop output is terminal- and desktop-dependent; Python and uv cannot make the terminal's paste representation universal. That is another reason to own a simple input contract rather than infer an arbitrary shell grammar.

Windows Terminal's official drag/drop documentation describes dropping a file or folder on the **New Tab button** to open a profile at that location; it does not promise macOS-style insertion into an active prompt ([Microsoft: Windows Terminal tips and tricks](https://learn.microsoft.com/windows/terminal/tips-and-tricks#drag-and-drop-file-or-folder-to-open)). The UI therefore should describe active-prompt drag/drop only for terminal/shell combinations verified by tests, and otherwise offer paste instructions or a file picker.

### 3. Native path operations are otherwise sound

No manual path separator concatenation was found in the Python package. The report JavaScript bundle is loaded relative to `Path(__file__).with_name(...)`, audio paths are passed as path-like objects to SoundFile, existence checks use `Path.is_file()`/`exists()`, and generated outputs remain beside each source file. These are good cross-platform practices.

Two behavior choices deserve explicit documentation rather than code changes:

- Relative CLI paths resolve against the process's current working directory, which is conventional command-line behavior.
- `resolve()` follows symlinks. Output files are therefore placed beside the resolved target, not necessarily beside the spelling of a symlink supplied by the user.

### 4. uv is cross-platform, but the support promise is not enforced

uv itself supports macOS, Linux, and Windows, and its `uv.lock` is a universal/cross-platform lockfile containing marker-specific resolutions ([uv overview](https://docs.astral.sh/uv/), [uv project layout and lockfile](https://docs.astral.sh/uv/concepts/projects/layout/)). `uv run` also checks that the project lock and environment are current before running the command ([uv project guide](https://docs.astral.sh/uv/guides/projects/)).

This repository has useful CI coverage:

- Ubuntu with Python 3.11, 3.12, and 3.13;
- Windows with Python 3.13;
- macOS with Python 3.13;
- locked dependency installation, tests, formatting, linting, package builds, and isolated wheel/sdist smoke tests.

Gaps:

- Windows and macOS exercise only Python 3.13 even though metadata promises 3.11 through 3.13.
- `macos-latest` does not prove both Apple Silicon and Intel compatibility.
- CI does not test path syntax cases representative of each shell/terminal.
- No `[tool.uv].required-environments` entries make the advertised OS/architecture set an invariant of dependency resolution.

uv documents `required-environments` specifically for packages such as PyTorch that publish wheels but no source distribution; resolution fails when a required platform lacks a compatible wheel ([uv project configuration](https://docs.astral.sh/uv/concepts/projects/config/#required-environments), [uv resolution](https://docs.astral.sh/uv/concepts/resolution/#required-environments)). Add entries only for architectures the project genuinely promises, for example Windows AMD64, Linux x86_64, and macOS ARM64. Add Intel macOS only after selecting a PyTorch-compatible dependency set.

### 5. Current PyTorch resolution excludes Intel macOS

`silero-vad` brings in PyTorch and torchaudio transitively. In the current `uv.lock`:

- `torch 2.13.0` has CPython 3.11-3.13 wheels for macOS ARM64, Linux x86_64/AArch64, and Windows AMD64, but no macOS x86_64 wheel and no source distribution;
- `torchaudio 2.11.0` likewise has macOS ARM64 wheels but no macOS x86_64 wheel and no source distribution;
- NumPy, SciPy, and SoundFile do include Intel macOS artifacts, so they are not the immediate Intel blocker.

PyTorch's installation guidance says macOS is supported and lists its current macOS/Python prerequisites, but actual installability still depends on a matching published wheel ([PyTorch: Start Locally](https://docs.pytorch.org/get-started/locally/)). The lockfile is the decisive evidence for this exact resolved version set.

Recommendation: decide whether “macOS” means Apple Silicon only. If yes, state that minimum architecture (and the wheel's macOS deployment target) in README/project support metadata and enforce it with `required-environments`. If Intel macOS is promised, constrain PyTorch/torchaudio (or the upstream `silero-vad` dependency) to versions that publish compatible x86_64 macOS wheels, then lock and test on an Intel runner. Do not claim Intel support based only on generic Python portability.

## Recommended implementation order

1. Replace or platform-split the interactive multi-path parser; add fixtures for observed Windows, macOS, and Linux paste forms.
2. Add unit tests for spaces, Unicode, quotes, literal backticks, trailing backslashes, and Windows UNC paths using `PureWindowsPath`/`PurePosixPath` where host-independent lexical assertions are needed.
   Also test filenames beginning with `-`; ordinary CLI users must place `--` before such positional paths so `argparse` does not interpret them as options.
3. Declare the supported OS/architecture matrix and add matching uv `required-environments`.
4. Align CI with that matrix, including architecture and at least dependency-sync smoke coverage for each promised Python minor.
5. Update prompt/README instructions and document current-working-directory and symlink-output behavior.

## Bottom line

Python plus uv removes much of the platform burden, but it cannot normalize text that different shells paste before Python sees it, and a universal lockfile does not guarantee wheels exist for every architecture. The repository is close for Windows AMD64, Linux x86_64, and Apple Silicon macOS; the drag/drop parser and the unqualified Intel-macOS promise are the two material cross-platform issues.
