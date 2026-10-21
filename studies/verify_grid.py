"""Final verification of the frozen H6 design. Read-only; reports, never writes."""

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from hawkes_engine import _core

REPO = Path(__file__).resolve().parent.parent
EXPECTED = "f735ae4113563f53ce992d4fc767bdc0439e72731af130f3b57d33720a291887"


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout.strip()


ok = True


def check(label, condition, detail=""):
    global ok
    ok = ok and condition
    print(f"{'PASS' if condition else 'FAIL'}  {label}{('  ' + detail) if detail else ''}")


# 1. The tag exists, is annotated, and points at a commit whose text predates the amendment.
tag_target = git("rev-parse", "H6-preregistration^{commit}")
tag_type = git("cat-file", "-t", "H6-preregistration")
check("tag is annotated", tag_type == "tag", tag_type)
check("tag target is 7bb8fae", tag_target.startswith("7bb8fae"), tag_target[:12])
tagged = git("show", f"{tag_target}:docs/preregistration.md")
check("tagged text has no amendment", "Amendment 1" not in tagged)
head = (REPO / "docs" / "preregistration.md").read_text(encoding="utf-8")
check("working text has the amendment", "Amendment 1" in head)

# 2. The tag commit precedes every commit that reports an H6 measurement.
#
#    Walk the tag's own ancestors, not `--all`: `git log` is newest-first, so
#    reading down from the top until the tag is reached collects the commits that
#    came AFTER it. That is what this check did before, and it failed on the
#    analysis commits it was meant to permit.
#
#    Test what a commit TOUCHED, not what its subject says. A keyword list over
#    subjects matches unrelated work ("Run the slow recovery studies nightly"
#    is H3) and misses real results. Any commit that writes an H6 result artifact
#    is a violation whatever its subject.
tag_target_short = tag_target[:7]
RESULT_PATHS = (
    "studies/results/analysis/",
    "studies/results/cells/",
    "data/trust/",
    "paper/",
    "studies/figures/",
    "studies/RUN_REPORT.md",
)
ancestors = git("log", "--format=%h %s", tag_target).splitlines()
before_tag = [line for line in ancestors if not line.startswith(tag_target_short)]
touching = []
for line in before_tag:
    short = line.split()[0]
    files = git("show", "--pretty=", "--name-only", short)
    if any(f.startswith(RESULT_PATHS) for f in files.splitlines()):
        touching.append(line)
check("no commit before the tag writes an H6 result", not touching, "; ".join(touching))

# 3. The grid digest matches, computed from the committed blob.
blob = subprocess.run(
    ["git", "cat-file", "blob", "HEAD:studies/theta0.json"], capture_output=True, check=True
).stdout
parsed = json.loads(blob.decode("utf-8"))
body = json.dumps(parsed, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
check("canonical digest matches the preregistration", digest == EXPECTED, digest[:16])
check("digest appears in the preregistration", EXPECTED in head)

# 4. Every cell reproduces its declared rho, and the anchor reproduces H3.
MU = np.array([0.5, 0.3])
A_H3 = np.array([[0.20, 0.10], [0.15, 0.25]])
B_A = np.array([[1.0, 1.2], [1.1, 1.3]])
worst = 0.0
for cell in parsed["cells"]:
    a = np.asarray(cell["alpha"], dtype=float)
    b = np.asarray(cell["beta"], dtype=float)
    if b.ndim == 1:
        b = np.tile(b, (b.size, 1)).T
    mu = np.asarray(cell["mu"], dtype=float)
    worst = max(worst, abs(float(_core.spectral_radius(mu, a, b)) - cell["rho"]))
check("every cell has its declared rho", worst < 1e-9, f"worst deviation {worst:.2e}")

anchor = next(
    c
    for c in parsed["cells"]
    if not c["satellite"]
    and c["N_target"] == 2000
    and c["rho"] == 0.3028
    and c["r"] == 0.0
    and c["c"] == 1.0
)
a0 = np.asarray(anchor["alpha"], dtype=float)
rel = float((np.abs(a0 - A_H3) / A_H3).max())
# Amendment 2 states the anchor reproduces H3 to within 8e-5 relative, not
# exactly. The check pins the documented tolerance, so a change to either the
# grid point or the amendment breaks the test.
check(
    "anchor reproduces H3 within the documented 8e-5",
    rel <= 8e-5,
    f"max rel dev {rel:.3e}",
)
check("anchor beta reproduces H3", np.allclose(anchor["beta"], B_A.tolist(), atol=1e-12))
check(
    "anchor T matches the preregistration",
    abs(anchor["T"] - 1722.6) < 1.0,
    f"T={anchor['T']:.1f}",
)

# 5. Cell counts.
n_sat = sum(1 for c in parsed["cells"] if c["satellite"])
check(
    "120 M=2 cells + 8 satellite cells",
    len(parsed["cells"]) == 128 and n_sat == 8,
    f"{len(parsed['cells'])} total, {n_sat} satellite",
)

# 6. R and the fingerprint of the design are stated where the paper will find them.
for needle in ("R = 2000", "Holm", "inconclusive by design", "exploratory"):
    check(f"preregistration states {needle!r}", needle in head)

# 7. Prior evidence covers H3, H4 and H5.
prior = (REPO / "studies" / "PRIOR_EVIDENCE.md").read_text(encoding="utf-8")
for needle in (
    "4.63",
    "4.44",
    "2.00",
    "0.67",
    "0.46",
    "0.21",
    "0.3028235666139891",
    "never been measured",
):
    check(f"prior evidence contains {needle!r}", needle in prior)

print()
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
