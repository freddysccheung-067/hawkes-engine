# EXECUTION GUIDE — Daily Workflow for Hawkes Engine

**Status**: Ready to begin H0  
**Timeline**: November 2026 → June 2027 (40 weeks)  
**Your role**: Execute planning, review math, manage scope  
**Claude's role**: Implement code, run tests, generate docs

---

## DAILY SESSION PROTOCOL

### 1. Start of Session (5 minutes)

```bash
cd /d/hawkes-engine-v2

# Read current state
cat STATE.md

# Read relevant gate file
cat gates/H0-design-infrastructure.md  # or current gate

# Check last commit in actual repo
cd /d/hawkes-engine  # actual GitHub repo
git log --oneline -5
git status
```

### 2. Execute Gate Task

**For each sub-task (e.g., H0.1, H0.2, ...):**

1. **Copy prompt** from gate file (e.g., `gates/H0-design-infrastructure.md` § H0.1)
2. **Paste into Claude Code** (PowerShell session)
3. **Let Claude execute** — no interruptions unless error
4. **Verify exit criteria** — run test, check file created
5. **Review output** — ensure no AI traces, fix if needed
6. **Commit** — use human-style message from CLAUDE.md rules

### 3. End of Session

```bash
# Update state
nano /d/hawkes-engine-v2/STATE.md
# Mark sub-task done, update SHA

# Push to GitHub
cd /d/hawkes-engine
git push
```

---

## GATE-BY-GATE WORKFLOW

### H0: Design and Infrastructure (10h, Week 1–2)

**Goal**: CI green, ADRs written, competitor analysis done, empty package builds

**Sub-tasks**:
1. H0.1 — Competitor deep dive (tick, hawkeslib, statsmodels) → `docs/competitor-analysis.md`
2. H0.2 — Write 8 ADRs (language, threading, memory layout, ...) → `docs/adr/ADR-00*.md`
3. H0.3 — CI skeleton (`.github/workflows/*.yml`) → 3 YAML files
4. H0.4 — Empty package scaffold (builds, imports) → `pip install -e .` works

**Exit criteria**: `pip install -e . && python -c "import hawkes_engine"` succeeds

**Time allocation**:
- H0.1: 3h (research, write analysis)
- H0.2: 4h (write ADRs, review)
- H0.3: 2h (create workflows)
- H0.4: 1h (setup files, test build)

**Model routing**:
- Sonnet 5.5 for H0.1 (research), H0.2 (design)
- Haiku 5.5 for H0.3 (boilerplate YAML)
- Sonnet for H0.4 (build config)

---

### H1: Mathematics and Oracle (12h, Week 3–4) — **CLAUDE IMPLEMENTS**

**Goal**: Oracle written by Claude from spec, verified against finite differences, locked

**Workflow** (smooth vibe coding):
1. Claude reads frozen math spec (`docs/spec/mathematics.md`)
2. Claude implements `oracle/hawkes_oracle.py` (O(N²) NumPy) directly from spec
3. Claude writes gradient test vs finite differences (self-verification)
4. Claude runs test → should pass immediately (spec is clear)
5. If test fails, Claude debugs and fixes (NOT you)
6. Once passing, Claude locks oracle with git tag + pre-commit hook

**Your role**: Review final oracle for clarity, approve lock

**Exit criteria**: Oracle gradient passes findiff test (200 cases, rel err <1e-6), oracle locked

**Time allocation**:
- Implement oracle from spec: 5h
- Write gradient test: 2h
- Debug if needed: 3h
- Lock and verify: 2h

**Model routing**: Sonnet 5.5 (implementation), Opus 5.5 if stuck

---

### H2: C++ Likelihood (22h, Week 6–8)

**Goal**: C++ loglik matches oracle on 1000 random cases (<1e-12 rel err)

**Sub-tasks**:
1. H2.1 — Write C++ header contracts (`cpp/include/hawkes/*.hpp`)
2. H2.2 — Implement loglik.cpp (O(NM²) recursion)
3. H2.3 — Test C++ vs oracle (1000 cases)
4. *If stuck after 2 attempts*: Escalate to Opus 5.5

**Exit criteria**: `pytest tests/test_oracle_agreement.py -v` → 1000/1000 pass

**Time allocation**:
- H2.1: 6h (write contracts, compile-check)
- H2.2: 10h (implement, debug)
- H2.3: 6h (write test, run, fix failures)

**Model routing**: Sonnet 5.5 (default) → Opus 5.5 (if Sonnet stuck after 2 attempts)

---

### H3: Gradient and Fit Driver (22h, Week 9–11)

**Sub-tasks**:
1. H3.1 — Implement C++ gradient
2. H3.2 — Numerical Hessian
3. H3.3 — Python fit() driver (L-BFGS-B)

**Exit criteria**: `pytest tests/test_api.py::test_fit_recovery` → 95% within 2 SE

**Time allocation**: 8h, 6h, 8h

---

### H4: Simulators (18h, Week 12–13)

**Sub-tasks**:
1. H4.1 — Simulator header contracts
2. H4.2 — Ogata thinning
3. H4.3 — Cluster simulator (INDEPENDENT of thinning)
4. H4.4 — Test two simulators agree

**Exit criteria**: `pytest tests/test_simulators_agreement.py -v` → all KS tests pass

---

### H5: Bindings and Wheels (12h, Week 14–15)

**Sub-tasks**:
1. H5.1 — pybind11 bindings
2. H5.2 — Test zero-copy
3. H5.3 — Test GIL release
4. H5.4 — cibuildwheel config
5. H5.5 — CI wheels workflow

**Exit criteria**: Wheels install cleanly, 10M events zero-copy, GIL released

---

### H6: Validation Study (28h, Week 16–22) — **RESEARCH CORE**

**Goal**: Trust map computed, shipped, paper drafted

**Sub-tasks**:
1. H6.1 — YOU write pre-registration (6 hypotheses from P03.09)
2. H6.2 — Grid design (n, βδ, βT)
3. H6.3 — Run 10k replications × 50 grid cells (parallel, may take days)
4. H6.4 — Plot trust map, analyze results
5. H6.5 — Paper draft

**Exit criteria**: `data/trust/v1_excitation_only.parquet` exists, paper draft complete

**Time allocation**:
- H6.1: 8h (YOU write pre-registration)
- H6.2: 4h (design grid, test small run)
- H6.3: 8h (setup parallel, run, monitor)
- H6.4: 4h (plot, analyze)
- H6.5: 4h (draft paper)

**Model routing**: Sonnet + Fable (study design), YOU (hypotheses)

---

### H7: Live Ingestion (18h, Week 23–25) — **OPTIONAL**

**Can cut to protect H6 time.**

**Sub-tasks**:
1. Binance WebSocket client
2. Order book reconstruction
3. Event classifier (v1, v2, v3)
4. Replay test (bit-identical)
5. 24h soak test with fault injection

**Exit criteria**: `pytest tests/test_stream.py::test_replay_bitwise` → exact match

---

### H8: Benchmarks (12h, Week 26–27)

**Sub-tasks**:
1. Install tick, hawkeslib
2. Generate identical test cases
3. Run benchmarks (time, memory)
4. Flame graph of our hot loop
5. Benchmark table and plot

**Exit criteria**: `benchmarks/results/benchmark_table.csv` published, honest wins and losses

---

### H9: Docs and Launch (15h, Week 28–29)

**Sub-tasks**:
1. README (hero, quickstart, benchmarks)
2. Sphinx docs (API reference, user guide)
3. Notebooks (3–5)
4. CHANGELOG, CITATION.cff
5. Tag v0.1.0, publish to PyPI
6. Launch (HN, Reddit, Twitter, arXiv)

**Exit criteria**: `pip install hawkes-engine==0.1.0` works, paper submitted

---

## MODEL ROUTING REFERENCE

| Task Type | Model | When |
|-----------|-------|------|
| **Planning, design, ADR critique** | Fable 5.1 | H0 (ADRs), H1 (review YOUR math), H6 (study design) |
| **Implementation (C++, Python)** | Sonnet 5.5 | H2–H5, H7–H9 (default workhorse) |
| **Hard debugging** | Opus 5.5 | When Sonnet stuck after 2 attempts (oracle disagreement) |
| **Scaffolding (CI, boilerplate)** | Haiku 5.5 | H0 (CI skeleton), H9 (docs formatting) |

**Rule**: Start with Sonnet. Escalate to Opus after 2 failed attempts on same task.

---

## VERIFICATION AT EACH GATE

**After completing each gate**, run its exit test:

```bash
# After H2
pytest tests/test_oracle_agreement.py -v
# Expected: 1000/1000 pass, rel err < 1e-12

# After H4
pytest tests/test_simulators_agreement.py -v
# Expected: All KS tests pass (p > 0.01)

# After H5
pip install -e . --no-build-isolation
python -c "import hawkes_engine; print(hawkes_engine.__version__)"
# Expected: 0.0.1.dev

# After H6
ls data/trust/v1_excitation_only.parquet
# Expected: File exists, >50 rows

# After H9
pip install hawkes-engine==0.1.0
# Expected: Success
```

**DO NOT** proceed to next gate until current gate's exit test passes.

---

## WHEN STUCK

### Sonnet Stuck (After 2 Attempts)

1. Document what Sonnet tried (2 attempts, what failed)
2. Copy "Escalate to Opus" prompt from gate file
3. Paste into Claude Code with Opus 5.5
4. Opus debugs with minimal failing case

### Opus Stuck

1. Escalate to YOU (human)
2. Provide: full failing case, Opus findings, next steps
3. You decide: fix manually, cut scope, or defer to v0.2

### Gate Unclear

1. Re-read MASTER-BLUEPRINT (relevant ADR or spec section)
2. Check P03 docs in this folder's `docs/` directory
3. Ask Fable 5.1 for design review

---

## SCOPE MANAGEMENT

### If Timeline Slips

**Cut order** (protect research, cut distribution):

1. **H7 (live ingestion)** → ship v0.1 replay-only, live in v0.2
2. **H8 competitor benchmarks** → internal benchmarks only
3. **v3 event dimensions** → ship v1 (M=2) and v2 (M=4) only
4. **Pair-specific β_ij** → shared-decay only (β_ij = β_j)
5. **Windows wheels** → Linux + macOS only initially

**NEVER CUT:**
- H1 (oracle — authorship rule)
- H6 (validation study — the research)
- H9 core (README, basic docs, PyPI release)

### If Ahead of Schedule

**Add from v0.2 roadmap:**
1. EM-based MLE (H4 extension, 15h) — independent estimator
2. Parametric bootstrap intervals (H3 extension, 8h) — better SEs near ridge
3. Sum-of-exponentials kernels (H2 extension, 18h) — power-law approximation

---

## COMMIT STYLE (NO AI TRACES)

**Format**:
```
H2.3: C++ loglik vs oracle passes 1000 cases

Implemented O(NM²) recursion from P03.02 §4. Uses Eigen for state matrices.
Returns -inf (not NaN) when λ ≤ 0. Zero heap allocations inside loop (verified).

Test: tests/test_oracle_agreement.py - all 1000 cases pass, rel err < 1e-12.

Next: H3.1 gradient implementation.
```

**Rules**:
- Subject: `<Gate>.<Task>: <What>` [imperative, <72 chars]
- Body: What was done, why, how (cite spec sections)
- Test: What test proves it works
- Next: What's next (optional)
- **No tool trailers** (disable in `.claude/settings.json`)
- **No emoji**, no vague subjects ("update code", "fixes")

---

## FINAL CHECKLIST (Before Launch)

- [ ] All gates H0–H9 complete (exit tests pass)
- [ ] Oracle locked (git tag `H1-oracle-locked`, pre-commit hook)
- [ ] Trust map shipped (`data/trust/v1_excitation_only.parquet`)
- [ ] Paper drafted and submitted
- [ ] README has: hero visual, quickstart, benchmarks, trust map
- [ ] CHANGELOG.md updated
- [ ] CITATION.cff with Zenodo DOI
- [ ] All ADRs (001–008 minimum) written
- [ ] Wheels for Linux/macOS/Win build in CI
- [ ] Test suite green (C++ + Python, all platforms)
- [ ] Git tag v0.1.0 created
- [ ] PyPI upload successful
- [ ] GitHub release created
- [ ] Launch posts drafted (HN, Reddit, Twitter)

---

## NEXT STEP

**Right now**: Copy H0.1 prompt from `gates/H0-design-infrastructure.md`  
**Paste into Claude Code**: Let it execute competitor analysis  
**Verify**: `docs/competitor-analysis.md` created, review completeness  
**Commit**: Update STATE.md, push to GitHub

---

**You're ready. Let's build this.**
