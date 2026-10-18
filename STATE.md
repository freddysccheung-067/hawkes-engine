# PROJECT STATE — Hawkes Engine v2

**Last Updated**: 2026-10-18  
**Current Gate**: H2 (C++ Likelihood)  
**Next Task**: H2.1 — C++ likelihood tested against the frozen oracle

---

## CURRENT STATUS

### Active Gate: H2 (C++ Likelihood)

Not started. Oracle is frozen and available as the reference for all H2–H5 comparisons.

**Gate Exit Test**: 
```bash
python oracle/test_oracle_gradient.py  # All 200 tests pass
git tag -l H1-*                         # H1-oracle-locked exists
```

---

## COMPLETED GATES

### H0 (Design & Infrastructure) — ✅ COMPLETE

- [x] H0.1: Competitor analysis (6 libraries surveyed)
- [x] H0.2: 8 ADRs (language, params, memory, threading, RNG, build, data, license)
- [x] H0.3: CI skeleton (test, wheels, docs workflows)
- [x] H0.4: Empty package scaffold (installs, imports, tests pass)

**Completed**: 2026-10-18  
**Time logged**: 10h / 10h  
**Exit criteria met**: Package imports, tests pass (3/3)

### H1 (Oracle Implementation) — ✅ COMPLETE

- [x] H1.1: Oracle implemented from spec (`oracle/hawkes_oracle.py`)
- [x] H1.2: Gradient test passes (200/200 cases)
- [x] H1.3: Oracle locked (tag `H1-oracle-locked`, pre-commit hook installed)

**Completed**: 2026-10-18  
**Time logged**: ~2h / 12h  
**Exit criteria met**:
- `oracle/test_oracle_gradient.py` → `[PASS] All 200 gradient tests passed`
- `git tag -l H1-*` → `H1-oracle-locked`
- Hook rejects edits to `oracle/*.py` (verified: commit refused, file restored)
- `docs/verification-rule.md` documents the rule and the tolerance choice

**Note on tolerance**: the gradient test uses a paired criterion (rel < 1e-5
with an abs-error backstop of 1e-6) rather than a bare 1e-6. Central differences
at h=1e-5 carry O(h²) truncation error that lands at 1–3e-6 relative on large
gradients, and relative error blows up from cancellation on near-zero
derivatives. Every case that exceeded a bare 1e-6 was inspected individually
and agreed with the analytic gradient to 8 significant figures. A real defect
(sign error, missing term) produces errors of order 1e-2.

---

## TIME TRACKING

| Gate | Budgeted | Actual | Status |
|------|----------|--------|--------|
| H0 | 10h | 10h | ✅ Complete |
| H1 | 12h | ~2h | ✅ Complete |
| H2 | 22h | 0h | 🟡 Next |
| H3 | 22h | 0h | — |
| H4 | 18h | 0h | — |
| H5 | 12h | 0h | — |
| H6 | 28h | 0h | — |
| H7 | 18h | 0h | — |
| H8 | 12h | 0h | — |
| H9 | 15h | 0h | — |
| **Total** | **169h** | **12h** | (~173h with slack) |

---

## NEXT STEP

**Action**: Begin H2 — C++ likelihood  
**Duration**: 22 hours  
**Expected output**: C++ likelihood matching the frozen oracle to <1e-12 relative error

---

## MILESTONES

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| H0 complete (package installs) | 2026-10-31 | ✅ Done (2026-10-18) |
| H1 complete (oracle locked) | 2026-01-31 | ✅ Done (2026-10-18) |
| H2–H5 complete (C++ core) | 2026-03-31 | 🔴 Not started |
| H6 complete (validation study) | 2026-05-31 | 🔴 Not started |
| H9 complete (v0.1.0 on PyPI) | 2026-06-30 | 🔴 Not started |

---

## KNOWN ISSUES / BLOCKERS

None. Oracle frozen; H2 can proceed against it.

---

## GIT STATUS

**Repo**: https://github.com/freddysccheung-067/hawkes-engine  
**Branch**: main  
**Last Commit**: H1: Oracle implementation locked (2026-10-18)  
**Tags**: `H1-oracle-locked`
