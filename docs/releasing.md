# Releasing Podcast Automixer

Releases are built and published to PyPI by `.github/workflows/release.yml`. The workflow
uses PyPI trusted publishing, so the repository does not store a PyPI API token.

## One-time setup

1. Create a PyPI account and enable two-factor authentication.
2. In PyPI's publishing settings, add a pending trusted publisher with these values:
   - PyPI project name: `podcast-automixer`
   - GitHub owner: `Today20092`
   - GitHub repository: `podcast-automixer`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
3. In the GitHub repository, create an environment named `pypi` under **Settings →
   Environments**. Add required reviewers if releases should need manual approval.

## Publish a release

1. Update `version` in `pyproject.toml` and `__version__` in
   `src/podcast_automixer/__init__.py` to the same new version.
2. Run the release checks:

   ```bash
   uv lock --check
   uv run pytest
   uv run ruff format --check .
   uv run ruff check .
   uv build
   ```

3. Commit and merge the version change to `main`.
4. Create and push an annotated tag matching the package version:

   ```bash
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```

The workflow rejects a tag that does not match the version in `pyproject.toml`. After the
workflow succeeds, verify the release on PyPI and test
`uvx --from podcast-automixer podcast-automix --help`.
