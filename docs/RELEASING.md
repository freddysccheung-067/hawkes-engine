# Releasing hawkes-engine

This is the maintainer's checklist. It is written for one person and one release
at a time. Read it to the end before starting: steps 4, 6 and 9 cannot be undone.

A session that prepares a release stops before step 1. Steps 1 to 9 are the owner's,
because a PyPI account, a tag, a publish and a DOI are public actions that cannot be
taken back, and a preparing session has no credentials for any of them.

## What is irreversible

| Step | Action | Reversible? |
|---|---|---|
| 1 | Creating the PyPI project and trusted publisher | Yes, until the first upload; the name is then taken |
| 2 | Creating the `pypi` environment | Yes |
| 3 | Merging `release/X.Y.Z` into `main` | Yes, but the branch is public once pushed |
| 4 | Pushing the tag `vX.Y.Z` | **No.** Published tags are used to build wheels |
| 5 | Watching the workflow | Yes, nothing is published yet |
| 6 | Approving the publish environment | **No.** PyPI rejects a re-upload of the same version |
| 7 | Installing from PyPI to verify | Yes |
| 8 | Creating the GitHub Release | Yes, by deleting it, but the tag stays |
| 9 | Registering the Zenodo DOI | **No.** A DOI is permanent |

PyPI and Zenodo both treat a version as immutable. A defect found after step 6 is
fixed by a new patch version, never by replacing the file.

## Before you start

- `main` is green: the Tests and Docs workflows pass on the commit you are about to
  release.
- `release/X.Y.Z` exists, is pushed, and its version check passes.
- `docs/release_notes_X.Y.Z.md` exists and every figure in it is pinned by
  `tests/test_docs_claims.py`.
- Replace `<!-- RELEASE_DATE -->` in `docs/release_notes_X.Y.Z.md` and
  `CHANGELOG.md` with the date of the tag, and set `date-released` in
  `CITATION.cff` to the same date. That field holds a real date rather than a
  marker, because CFF requires a valid date there and a comment would fail
  validation. These three are the only hand-written values in the release.
- The paper is still a draft. If it has been submitted anywhere, stop: the release
  notes say it has not, and that sentence would become false.

## 1. Create the PyPI project and register the trusted publisher

Only once, for the first release. Later releases reuse it.

On <https://pypi.org/manage/account/publishing/>, under "Add a new pending
publisher", enter exactly:

| Field | Value |
|---|---|
| PyPI Project Name | `hawkes-engine` |
| Owner | `freddysccheung-067` |
| Repository name | `hawkes-engine` |
| Workflow name | `wheels.yml` |
| Environment name | `pypi` |

The workflow name is the file name, `wheels.yml`, not the workflow's `name:` line
("Build Wheels"). The environment name is the `environment:` key in the
`upload_pypi` job. All three must match the repository or PyPI refuses the token
and the job fails with a 403 that names none of them.

This creates a *pending* publisher. It becomes active on the first successful
upload, so it needs no separate confirmation.

## 2. Create the `pypi` environment with required reviewers

In the repository, Settings, Environments, "New environment", name it `pypi`.
Then:

- Enable **Required reviewers** and add yourself.
- Leave "Prevent self-review" off: this is a single-maintainer project, and turning
  it on would make the environment impossible to approve.
- Restrict deployment branches and tags to `v*` if the interface allows a tag
  pattern. The workflow already refuses anything that is not a `v*` tag, so this is
  a second lock rather than the only one.

Without this environment the job would still publish (the OIDC token is enough),
so the approval gate is the only thing standing between a pushed tag and a live
release. Do not skip it.

## 3. Merge `release/X.Y.Z` into `main`

Open a pull request from `release/X.Y.Z` to `main`, read the diff, and merge it.
The version test runs in CI, so a version that disagrees with any of its six copies
fails here rather than after the tag.

## 4. Tag

From an up-to-date `main`:

```bash
git checkout main
git pull
git tag -a vX.Y.Z -m "hawkes-engine X.Y.Z"
git push origin vX.Y.Z
```

The tag must be `vX.Y.Z` with no suffix: `v0.1.0`, not `v0.1.0-final` and not
`0.1.0`. The `check_tag` job compares it against `pyproject.toml` and stops the run
if they differ, but a tag that has been pushed has to be deleted and re-pushed,
which is a public change of history even though it is permitted.

This is the first irreversible step.

## 5. Watch the workflow

The push starts `wheels.yml`. In order: `check_tag`, then `build_wheels` and
`build_sdist`, then `check_artefacts` (twine), then `upload_pypi`, which waits for
approval.

Read the `check_tag` log even when it is green. It prints the tag and the version it
compared, and that line is the evidence that the two agree.

If any build fails, do not re-run only the failed job: the wheels must all come from
one commit. Cancel, fix, and tag again from a new commit with a new patch version.

## 6. Approve the publish

Open the `upload_pypi` job in the run and approve the `pypi` environment. This is
the second irreversible step. Before approving, confirm:

- Every wheel in the run's artefacts is for version X.Y.Z.
- The `check_artefacts` job passed.
- The `check_tag` job passed.

## 7. Verify the install from PyPI

Wait for the upload to finish, then in a clean environment outside the repository:

```bash
python -m venv /tmp/verify && /tmp/verify/bin/pip install hawkes-engine==X.Y.Z
/tmp/verify/bin/python -c "import hawkes_engine as he; print(he.__version__)"
/tmp/verify/bin/python -c "from hawkes_engine import _core; print(_core.build_info())"
/tmp/verify/bin/python -m hawkes_engine._selftest
```

The version printed must be X.Y.Z and `build_info()["version"]` must match it. A
wheel whose core reports a different version than its metadata was built from a
tree that was not the tag.

If this fails, the release is already published. Fix forward with a patch release;
do not attempt to delete the PyPI files.

## 8. Create the GitHub Release

From the tag, using `docs/release_notes_X.Y.Z.md` as the body, with the title
`hawkes-engine X.Y.Z`. Do not mark it "latest" until step 7 has passed.

## 9. Register the Zenodo DOI and add it to `CITATION.cff`

1. Connect the repository to Zenodo (or use the GitHub integration once) and
   archive the release. `.zenodo.json` at the repository root supplies the title,
   description, creators, license and keywords, so the deposit reads correctly
   without hand-editing metadata on the Zenodo site.
2. Zenodo mints a **version DOI** for this release and a **concept DOI** for all
   versions. Record both. The concept DOI stays the same across versions; only the
   version DOI changes.

   **The integration does not always fire.** For 0.1.0 the deposit was made by hand,
   and publishing the v0.2.0 GitHub release produced no new Zenodo version: the
   concept record still listed one version, with `hawkes-engine-0.1.0.zip` as its
   only file. If that happens again, mint the deposit manually at zenodo.org and
   attach the release archive, or toggle the repository off and on in Zenodo's
   GitHub settings and re-publish the release. Check zenodo.org before assuming a
   DOI exists: the GitHub release existing is not evidence that it does.
3. In a follow-up commit on `main`, add to `CITATION.cff`:

   ```yaml
   doi: "10.5281/zenodo.XXXXXXX"        # the version DOI
   identifiers:
     - type: doi
       value: "10.5281/zenodo.XXXXXXX"
       description: "This version"
     - type: doi
       value: "10.5281/zenodo.YYYYYYY"
       description: "All versions"
   ```

4. Add a sentence to the release notes naming the DOI, and remove the sentence that
   says no DOI exists. Commit that with the `CITATION.cff` change: a file that says
   a DOI exists and notes that say it does not is the same defect as a stale figure.

This is the third irreversible step.

## After the release

- The next development version is set in `python/hawkes_engine/_version.py` to
  `X.(Y+1).0.dev0`. CMake cannot carry a `.devN` suffix; `tests/test_version.py`
  accepts that one pair and nothing else.
- `CHANGELOG.md` gets a new `## [Unreleased]` heading above the released section.
- Check that the docs site rebuilt from `main` and that the release notes page is
  live.

## What a preparing session must not do

A session that prepares a release has no credentials to do any of the
above and must not be given any. It stops before step 1. If it finds itself able to
push a tag or reach a PyPI token, that is a defect in the setup, not a shortcut.
