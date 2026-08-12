# Releasing Podcast Automixer

Releases are built and published to the
[Podcast Automixer PyPI project](https://pypi.org/project/podcast-automixer/) by
`.github/workflows/release.yml`. The workflow uses PyPI trusted publishing, so the
repository does not store a PyPI API token.

## Trusted publisher configuration

The trusted publisher is already configured. If it ever needs to be recreated, use these
values in PyPI's publishing settings:

- PyPI project name: `podcast-automixer`
- GitHub owner: `Today20092`
- GitHub repository: `podcast-automixer`
- Workflow filename: `release.yml`
- Environment name: `pypi`

The GitHub repository must also have an environment named `pypi` under **Settings →
Environments**. No PyPI API-token secret is required.

## Publish a release

1. Update `version` in `pyproject.toml` and `__version__` in
   `src/podcast_automixer/__init__.py` to the same new version.
2. Run the release checks:

   ```bash
   uv lock --check
   uv run pytest
   uv run ruff format --check .
   uv run ruff check .
   uv run ty check
   uv build
   ```

3. Commit and merge the version change to `main`.
4. Create and push an annotated tag matching the new package version. For example:

   ```bash
   git tag -a v0.2.0 -m "v0.2.0"
   git push origin v0.2.0
   ```

The workflow rejects a tag that does not match the version in `pyproject.toml`. After the
workflow succeeds:

1. Verify the release on PyPI and test it:

```bash
uvx --from podcast-automixer podcast-automix --help
```

2. Create a GitHub Release from the same tag. Give it a short, user-focused summary of the
   changes, including any upgrade notes or behavior changes. GitHub then notifies people who
   watch the repository's releases.

Do not announce a release before the PyPI workflow succeeds. The README points users to both
PyPI for the package and GitHub Releases for release notes and notifications.
