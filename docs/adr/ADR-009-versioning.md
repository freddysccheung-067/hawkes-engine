# ADR-009: Versioning and Release Policy

**Status**: Accepted
**Date**: 2026-10-21
**Deciders**: freddysccheung-067

## Context

There was no written versioning policy before the first release. H9 needs one,
because a release is a promise and the promise has to be the same one in every
place a stranger can read it. Three constraints shaped the choice:

- The public surface is small and pinned (`tests/test_api.py`), but the estimator
  is not settled: the H6 study found the reported standard errors understate
  sampling spread by a factor of `0.779`, and two of its six hypotheses were not
  confirmed. An API built on top of a number that may be revised is not stable.
- The version string is copied into six files for six mechanical reasons:
  PyPI reads `pyproject.toml`, CMake reads `CMakeLists.txt`, citation tooling
  reads `CITATION.cff`, Sphinx reads `docs/conf.py`, the compiled core can only
  report what was stamped into it at compile time, and users read `CHANGELOG.md`.
- CMake's `project() VERSION` accepts three numeric components and nothing else,
  so it cannot carry a `.devN` suffix.

## Decision

**Semantic versioning, with the 0.x caveat stated rather than implied.**

While the major version is 0, the minor version may break: `0.1` to `0.2` may
rename a public name, change a default, or change the shape of a returned object.
A patch release (`0.1.0` to `0.1.1`) fixes defects and does not break the
documented surface. `1.0.0` is reserved for the point at which the calibration
map has been extended beyond two types and one decay form, and the maintainer is
willing to promise the surface under 1.x rules.

**0.1.0 is a pre-alpha research release.** What it promises:

- The names in `hawkes_engine.__all__` exist and are documented.
- Every figure in the README and the published pages is copied from a committed
  output and pinned by `tests/test_docs_claims.py`.
- The estimator and the trust map are the ones the H6 preregistration describes,
  at the tag `H6-preregistration`, with its six amendments.
- The reported standard errors understate sampling spread in the measured
  regimes, and `trust_lookup` reports what was measured and where nothing was.

It does not promise a stable API, a coverage guarantee, or support outside the
measured box. Both are stated in the release notes and on the Limits page.

**One source for the string.** `python/hawkes_engine/_version.py` holds
`__version__`; `__init__.py` re-exports it. `docs/conf.py` reads it rather than
repeating it. Every other copy is checked against it by `tests/test_version.py`,
which also accepts exactly one development pair (`1.2.3.dev0` in Python,
`1.2.3` in CMake) and nothing else.

**The release is a tag, and the tag must match.** `v0.1.0` publishes; a version
that disagrees with `pyproject.toml` is refused by a guard job in `wheels.yml`
before any artefact reaches PyPI.

## Alternatives Considered

### Option 1: Calendar versioning (2026.10.0)
- **Pros**: No argument about what a number means
- **Cons**: Says nothing about whether an upgrade breaks a caller, which is the
  only question a user of a numerical library actually asks
- **Why rejected**: The surface does change between minors; the number should say so.

### Option 2: Start at 1.0.0
- **Pros**: Signals confidence, and some tools treat 0.x as unstable
- **Cons**: A 1.0 promise is a promise the estimator cannot keep while the H6
  map covers two types and one decay form, and the standard-error finding is
  still being responded to
- **Why rejected**: It would be the one unmeasured claim in a release built to
  avoid them.

### Option 3: Keep everything at `0.1.0.dev0` and publish a release candidate
- **Pros**: No version decision at all
- **Cons**: `.dev0` is not a shape CMake can carry, so the core and the metadata
  would disagree from the first wheel; and a `.dev0` on PyPI sorts below every
  later build, which makes the first release the hardest to supersede
- **Why rejected**: It does not remove the decision, it defers it to a worse moment.

## Consequences

**Positive**:
- A reader can tell what `0.1.0` promises without reading the source
- A bump that misses one of the six copies fails CI rather than shipping
- The major number stays honest: `1.0` will mean the map is wider, not that the
  project has been around longer

**Negative**:
- The 0.x rule means a `0.2.0` may break a caller without a deprecation cycle.
  The release notes say so; a user who needs stability should pin.
- CMake's inability to carry a prerelease suffix is a permanent small wrinkle in
  `tests/test_version.py`, which has to encode the exception.

**Neutral**:
- Zenodo mints a DOI per release, so every future version is its own citable
  object. The concept DOI covers all of them; the release notes name the version DOI.

## References

- Semantic Versioning 2.0.0: [semver.org](https://semver.org/spec/v2.0.0.html)
- `docs/preregistration.md` and the tag `H6-preregistration`
- `tests/test_version.py`, which holds the six copies equal
- [PEP 440](https://peps.python.org/pep-0440/), on `.devN` ordering
