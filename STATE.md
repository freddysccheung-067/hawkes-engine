# PROJECT STATE — Hawkes Engine v2

**Last Updated**: 2026-10-18  
**Current Gate**: H0 (Design and Infrastructure)  
**Next Task**: H0.1 — Competitor Deep Dive

---

## CURRENT STATUS

### Active Gate: H0

- [ ] H0.1: Competitor analysis (`docs/competitor-analysis.md`)
- [ ] H0.2: Write 8 ADRs (`docs/adr/ADR-001.md` through `ADR-008.md`)
- [ ] H0.3: CI skeleton (`.github/workflows/*.yml`)
- [ ] H0.4: Empty package scaffold (`pip install -e .` works)

**Gate Exit Test**: `pip install -e . && python -c "import hawkes_engine"` → no errors

---

## LAST GREEN COMMIT

```
Repo: https://github.com/freddysccheung-067/hawkes-engine
Branch: main
SHA: (not yet created — will update after first commit)
Date: 2026-10-18
Message: Initial commit with planning docs
```

---

## NEXT STEP

**Action**: Copy H0.1 prompt from `gates/H0-design-infrastructure.md`  
**Paste into**: Claude Code (PowerShell)  
**Expected output**: `docs/competitor-analysis.md` (1000–1500 words, table)  
**Verify**: All 5+ libraries surveyed (tick, hawkeslib, statsmodels, PyMC, R packages)  
**Commit**: "H0.1: Competitor analysis — tick, hawkeslib, statsmodels"

---

## COMPLETED GATES

None yet.

---

## KNOWN ISSUES / BLOCKERS

None currently.

---

## SCOPE DECISIONS

| Decision | Date | Rationale |
|----------|------|-----------|
| v0.1 = excitation-only (α ≥ 0) | 2026-10-18 | Inhibition breaks thinning bound, defer to v0.2 |
| Shared-decay fast path (β_ij = β_j) | 2026-10-18 | O(NM) not O(NM²), default for M≥6 |
| Trust map is non-negotiable | 2026-10-18 | Core research deliverable, unique feature |

---

## HOURS LOGGED

| Gate | Planned | Actual | Notes |
|------|---------|--------|-------|
| H0 | 10h | 0h | Not started |
| H1 | 12h | 0h | — |
| H2 | 22h | 0h | — |
| H3 | 22h | 0h | — |
| H4 | 18h | 0h | — |
| H5 | 12h | 0h | — |
| H6 | 28h | 0h | — |
| H7 | 18h | 0h | Optional — can cut |
| H8 | 12h | 0h | — |
| H9 | 15h | 0h | — |
| **Total** | **169h** | **0h** | (~175h with slack) |

---

## TIMELINE CHECKPOINTS

| Checkpoint | Target Date | Status |
|------------|-------------|--------|
| H0 complete | 2026-11-30 | 🟡 Not started |
| H1 complete (oracle locked) | 2027-01-31 | 🔴 Not started |
| H2 complete (C++ vs oracle) | 2027-03-31 | 🔴 Not started |
| H3–H5 complete (fit + sims + wheels) | 2027-05-31 | 🔴 Not started |
| H6 complete (validation study) | 2027-09-30 | 🔴 Not started |
| H9 complete (v0.1.0 launch) | 2027-12-31 | 🔴 Not started |

---

## NOTES FOR NEXT SESSION

(Update this section at end of each session with:
- What worked / didn't work
- Any surprises or lessons
- Decisions made
- Next session's focus)

**Session 1 (2026-10-18)**:
- Created planning structure in `/d/hawkes-engine-v2`
- Ready to begin H0.1 (competitor analysis)
- Actual GitHub repo will be at `/d/hawkes-engine` (separate from old folder)

---

**Keep this file updated after every session and commit.**
