"""The files a release says things about itself in must agree.

Three files describe the release to the outside world and are read by three
different services: ``pyproject.toml`` by PyPI, ``CITATION.cff`` by citation
tooling and GitHub, ``.zenodo.json`` by Zenodo at deposit time. They carry the same
facts in three formats, and only one of them is checked by anything when it is
uploaded. Zenodo metadata is written once, at deposit, and is not editable without
a new version.

Two failure modes are worth a test. A DOI claimed before one exists turns into a
permanent citation pointing at nothing. A creator name or license that differs
between the deposit and the package is a mismatch nobody notices until a reader
tries to cite the software.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 has no tomllib; tomli is the same parser
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _cff_field(field: str) -> str:
    # The author fields are indented under `authors:` and preceded by a list
    # dash, so neither the indent nor the dash is part of the field name.
    found = re.search(rf"^\s*(?:-\s*)?{field}:\s*(.+)$", _read("CITATION.cff"), re.M)
    assert found, f"CITATION.cff has no {field}"
    return found.group(1).strip().strip("\"'")


def test_zenodo_metadata_is_valid_and_complete() -> None:
    data = json.loads(_read(".zenodo.json"))
    for key in ("title", "description", "creators", "license", "upload_type"):
        assert key in data, f".zenodo.json has no {key}"
    assert data["upload_type"] == "software"
    assert data["access_right"] == "open"
    assert data["creators"], "a deposit with no creator cannot be cited"
    for creator in data["creators"]:
        assert creator.get("name"), "every creator needs a name"


def test_zenodo_title_names_the_package() -> None:
    assert "hawkes-engine" in json.loads(_read(".zenodo.json"))["title"]


def test_the_license_agrees_across_the_three_files() -> None:
    project = tomllib.loads(_read("pyproject.toml"))["project"]
    package_license = project["license"]["text"]
    citation_license = _cff_field("license")
    zenodo_license = json.loads(_read(".zenodo.json"))["license"]
    assert package_license == citation_license == zenodo_license == "MIT", (
        f"pyproject says {package_license}, CITATION.cff {citation_license}, "
        f".zenodo.json {zenodo_license}"
    )


def test_the_author_name_agrees_across_the_three_files() -> None:
    project_author = tomllib.loads(_read("pyproject.toml"))["project"]["authors"][0]["name"]
    cff_family = _cff_field("family-names")
    cff_given = _cff_field("given-names")
    zenodo_name = json.loads(_read(".zenodo.json"))["creators"][0]["name"]
    # pyproject writes "Given Family"; CFF splits them; Zenodo writes "Family, Given".
    assert project_author == f"{cff_given} {cff_family}", project_author
    assert zenodo_name == f"{cff_family}, {cff_given}", zenodo_name


def test_no_doi_is_claimed_anywhere_until_one_exists() -> None:
    """A DOI in the metadata is a citation to a record that may not exist yet.

    The release notes say there is none. This test is what keeps that sentence true
    until the follow-up commit that adds the Zenodo DOI, which must change both at
    once.
    """
    citation = _read("CITATION.cff")
    has_doi = re.search(r"^doi:", citation, re.M) is not None
    notes_say_none = "This release has no DOI" in _read("docs/release_notes_0.1.0.md")
    assert has_doi == (not notes_say_none), (
        "CITATION.cff claims a DOI and the release notes say there is none, "
        "or the reverse; add the DOI and update the notes in one commit"
    )


def test_the_paper_is_described_as_a_draft() -> None:
    notes = _read("docs/release_notes_0.1.0.md")
    assert "has not been submitted or published" in notes


def test_releasing_checklist_names_the_trusted_publisher_values() -> None:
    """The values are entered by hand into PyPI and must be in the document."""
    guide = _read("docs/RELEASING.md")
    for value in ("hawkes-engine", "freddysccheung-067", "wheels.yml", "pypi"):
        assert value in guide, f"RELEASING.md does not mention {value}"
