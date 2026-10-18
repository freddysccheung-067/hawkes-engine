# HAWKES ENGINE v2 — START HERE

**Project**: High-performance Hawkes process library with trust calibration  
**Timeline**: 40 weeks (November 2026 → June 2027)  
**Target**: 10k+ GitHub stars, publishable validation study  
**Your Role**: Execute gates H0–H9, Claude does implementation

---

## QUICK START (5 minutes)

```bash
# 1. Navigate to project
cd /d/hawkes-engine-v2

# 2. Read execution guide
cat EXECUTION-GUIDE.md

# 3. Start H0.1 (competitor analysis)
# Copy prompt from gates/H0-design-infrastructure.md
# Paste into Claude Code, execute

# 4. Check off task
# Edit STATE.md when done
```

---

## DOCUMENT MAP

| File | Purpose | When to read |
|------|---------|--------------|
| **00-START-HERE.md** | This file — orientation | First time only |
| **EXECUTION-GUIDE.md** | Your daily workflow, gate overview | Every session start |
| **STATE.md** | Volatile: current gate, next step, last green SHA | Every session start/end |
| **gates/** | One file per gate H0–H9 with prompts | During gate execution |
| **docs/** | Frozen specs, ADRs, mathematics | Reference during implementation |
| **repo-template/** | Complete file tree for GitHub repo | H0 — copy to actual repo |

---

## ONE-PAGE PHILOSOPHY

**What makes this different:**

1. **Trust map** — no other library ships "when to trust your fit"
2. **Dual simulators** — thinning + branching cross-check each other
3. **Zero AI traces** — commits look human-authored, no tool trailers
4. **10k star-worthy** — engineered for GitHub virality + substance

**Engineering principles:**

- Correctness is non-negotiable (C++ vs NumPy oracle <1e-12 error)
- You derive the math (H1), Claude implements from your oracle
- Reproducibility by default (same seed → same output, always)
- Ship calibration, not just fits (trust map is the research)

**Success metrics:**

- Technical: wheels install first try, 10^7 events <30s
- Research: validation study published, trust map shipped
- Community: 1k+ stars (stretch: 10k), 500 downloads/month

---

## GATES OVERVIEW

| Gate | Time | What | Who | Exit test |
|------|------|------|-----|-----------|
| H0 | 10h | Design, ADRs, CI skeleton | Claude (Sonnet + Haiku) | Empty package imports |
| H1 | 12h | Claude implements oracle from spec | Claude (Sonnet → Opus) | Oracle passes findiff |
| H2 | 22h | C++ loglik vs oracle | Sonnet → Opus if stuck | <1e-12 rel err, 1000 cases |
| H3 | 22h | Gradient, Hessian, fit driver | Sonnet | Recovers params within 2 SE |
| H4 | 18h | Two simulators (thinning + cluster) | Sonnet | Both agree, KS passes |
| H5 | 12h | Bindings, wheels, packaging | Sonnet + Haiku | pip install works, zero-copy |
| H6 | 28h | **Validation study** (research core) | Sonnet + You (pre-reg) | Trust map computed |
| H7 | 18h | Live Binance feed (optional) | Sonnet + Opus | Replay equals live |
| H8 | 12h | Benchmarks vs competitors | Sonnet + Fable | Table published, honest wins/losses |
| H9 | 15h | Docs, README, launch | Sonnet + Haiku | v0.1.0 on PyPI, paper submitted |

**Critical path**: H1 → H2 → H3 → H6 (research). If time slips, cut H7 or H8 first.

---

## NO AI TRACES STRATEGY

**Git config** (set at H0):
```bash
git config user.name "Freddy"
git config user.email "your-email@example.com"
git config commit.gpgsign false
```

**Commit style** (enforced in CLAUDE.md):
- Imperative mood, <72 chars: "Add loglik recursion"
- Body explains why, cites spec sections
- No tool trailers: disable in `.claude/settings.json`

**Code style**:
- No boilerplate comments ("This function does X")
- No emoji, no filler docstrings, no generic helper names
- Comments explain WHY, cite equations, stay sparse

---

## VISUAL & STRUCTURAL STAR-WORTHINESS

**README design** (H9):
- Hero: animated intensity spike/decay (SVG, reproducible script)
- Quickstart: 5 lines, runs offline on bundled data
- Benchmarks: chart with cases where we lose (honesty signal)
- Trust map: figure + 2-sentence explanation non-quants understand

**Repo structure**:
- Clean tree: cpp/, python/, tests/, docs/, benchmarks/, studies/
- Data segregated: sample/ (committed), raw/ (gitignored)
- ADRs visible: docs/adr/ with 16 decision records
- Badges: CI status, coverage, PyPI version, license

**Documentation**:
- Sphinx/mkdocs with API reference (auto-generated)
- 3–5 Jupyter notebooks (quickstart, diagnostics, real data)
- Theory section: brief Hawkes intro, not a textbook

---

## VERIFICATION RULE (CRITICAL)

**H1 Gate — Claude implements oracle from spec:**

1. Claude reads frozen math spec (`docs/spec/mathematics.md`)
2. Claude writes `oracle/hawkes_oracle.py` (O(N²) NumPy, clean reference impl)
3. Claude writes self-verification test (gradient vs finite differences)
4. Test must pass <1e-6 error before proceeding
5. Lock oracle with git tag + pre-commit hook

**After H1:**
- Oracle is frozen (hook rejects edits)
- C++ implementation tested against oracle (<1e-12 error)
- Two simulators cross-check each other (thinning vs cluster)
- Tests are never weakened to pass

---

## SCOPE CUTS (IF TIMELINE SLIPS)

**Cut order** (protect research, cut distribution):

1. H7 (live ingestion) → ship v0.1 replay-only, live in v0.2
2. H8 competitor benchmarks → internal benchmarks only
3. v3 event dimensions → ship v1 (M=2) and v2 (M=4) only
4. Pair-specific β_ij → shared-decay only (β_ij = β_j)
5. Windows wheels → Linux + macOS only initially

**NEVER CUT:**
- H1 (oracle — authorship rule)
- H6 (validation study — the research)
- H9 core (README, basic docs, PyPI release)

---

## NEXT STEP

**Read**: `EXECUTION-GUIDE.md` (detailed workflow, 5 min)  
**Then**: `gates/H0-design-infrastructure.md` (copy H0.1 prompt)  
**Execute**: Paste prompt into Claude Code, let it run  
**Verify**: Check exit criteria, commit, update STATE.md

---

**Let's build the definitive Hawkes process library.**
