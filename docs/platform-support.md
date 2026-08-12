# Platform support

Podcast Automixer supports Python 3.11 through 3.13 on these targets:

| Operating system | CPU architecture | Minimum version |
| --- | --- | --- |
| Windows | x86-64 (AMD64) | Windows 10 |
| macOS | Apple Silicon (arm64) | macOS 14 Sonoma |
| Linux | x86-64 or arm64 | glibc 2.28 |

The macOS minimum and Apple Silicon requirement come from the wheels published for the
locked PyTorch release. PyTorch and torchaudio do not publish compatible Intel macOS
wheels in this resolution, so Intel Macs are unsupported. Windows on ARM and Linux
distributions using musl, including Alpine, are also outside the supported matrix.

On an unsupported target, `uv` may report that PyTorch has no source distribution or
compatible wheel. Use one of the supported OS and architecture combinations above; do
not bypass the locked dependencies, because the resulting installation is not tested.
