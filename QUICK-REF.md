# QUICK REFERENCE CARD

**Location**: `D:\hawkes-engine-v2\`  
**Actual Repo**: `https://github.com/freddysccheung-067/hawkes-engine`

---

## START HERE

```bash
# 1. Read these files in order
cat D:\hawkes-engine-v2\00-START-HERE.md       # 5 min
cat D:\hawkes-engine-v2\EXECUTION-GUIDE.md     # 10 min

# 2. Check current state
cat D:\hawkes-engine-v2\STATE.md

# 3. Copy H0.1 prompt
cat D:\hawkes-engine-v2\gates\H0-design-infrastructure.md
# (copy the H0.1 prompt section)

# 4. Paste into Claude Code, execute
```

---

## FILE MAP

| File | Purpose |
|------|---------|
| `00-START-HERE.md` | Entry point, 1-page overview |
| `EXECUTION-GUIDE.md` | Daily workflow, all 10 gates detailed |
| `STATE.md` | Current status, hours logged, next step |
| `gates/H0-design-infrastructure.md` | H0 prompts (H0.1–H0.4) |
| `docs/spec/mathematics.md` | Frozen math spec (for H1) |
| `docs/adr/` | Architecture Decision Records (H0.2 creates) |
| `repo-template/` | Files to copy to actual GitHub repo |

---

## GATE EXECUTION PATTERN

```
1. Read STATE.md → know where you are
2. Open gate file → find next sub-task
3. Copy prompt → copy-paste exact text
4. Paste into Claude Code → let it execute
5. Verify exit criteria → run test command
6. Commit → update STATE.md, push
```

---

## MODEL ROUTING

| Task | Model |
|------|-------|
| Research, design | Sonnet 5.5 |
| Boilerplate (CI YAML) | Haiku 5.5 |
| Oracle implementation | Sonnet 5.5 |
| Hard debugging | Opus 5.5 (if Sonnet stuck 2×) |

---

## COMMIT STYLE (NO AI TRACES)

```
Subject: H2.3: C++ loglik vs oracle passes 1000 cases

Body: What, why, how (cite spec sections).
Test: What proves it works.
Next: What's next (optional).

NO tool trailers, NO emoji, NO vague subjects.
```

---

## EMERGENCY CONTACTS

- Sonnet stuck (2 attempts) → Escalate to Opus (prompt in gate file)
- Opus stuck → YOU (human) intervene
- Math unclear → Re-read `docs/spec/mathematics.md`
- Design unclear → Ask Fable 5.1 for review

---

## SUCCESS METRICS

**Technical**:
- C++ vs oracle <1e-12 error ✓
- Wheels install first try ✓
- 10^7 events <30s ✓

**Research**:
- Trust map shipped ✓
- Paper submitted ✓

**Community**:
- 1k+ stars (10k stretch)
- 500 downloads/month

---

## SCOPE CUTS (IF NEEDED)

Cut in this order:
1. H7 (live feed)
2. H8 (competitor benchmarks)
3. v3 dimensions
4. Pair β_ij
5. Windows wheels

NEVER CUT:
- H1 (oracle from spec)
- H6 (validation study)
- H9 core (README, PyPI)

---

## NEXT STEP

Execute H0.1 (competitor analysis) — prompt in `gates/H0-design-infrastructure.md`
