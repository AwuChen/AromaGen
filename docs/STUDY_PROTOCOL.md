# Death Sentence — User Study Protocol (v2)

**Purpose:** Measure whether AI-composed scent sequences match personal memories, whether iterative feedback improves them, and whether an accumulating example bank improves **new** compositions — using **forced-choice identification**, not Likert ratings.

**Duration:** 50–70 min per participant depending on condition.

---

## 0. What the June sessions actually collected (honest audit)

Use this section when writing up prior work. Do **not** claim training or improvement unless you run the designs in Section 5–6.

### Did we collect qualitative feedback?

**Partially — raw, not structured.**

| What exists | Where | Count (Jun 3–17 logs) |
|-------------|-------|------------------------|
| Spoken critique transcripts | `logs/dialogue/*.jsonl` → `feedback` events, `human_input` | **85** feedback rounds |
| Rich utterances (>50 chars) | same | **63** |
| Accepted pair summaries | `learned_examples.json` → `feedback_summary` | **8** accepts had ≥1 feedback round |
| Debrief / interview | nowhere | **0** |
| Formal qualitative coding | nowhere | **0** |
| Accept ratings | `accept` events → `rating` field | **11 accepts, all `null`** |

So: you have **mineable qualitative material** in dialogue logs (directives like “less spice,” “more sea,” “savory punch,” facilitator co-talk). You do **not** have a qualitative study arm — no coding scheme applied, no debrief captured, no participant reflections beyond what was accidentally recorded during feedback.

**For the paper:** either (a) post-hoc code a stratified sample of ~30 feedback utterances, or (b) treat June as exploratory logs only and collect qualitative data properly in v2 (Section 14).

### Did we train the model on all feedback?

**No.**

- **No weight fine-tuning.** The model weights never change.
- **In-session refinement only:** all 85 feedback rounds went to `POST /feedback` and updated that session’s sequence live.
- **Persistent “learning”:** only **`POST /accept`** writes to `learned_examples.json`. **11 entries** total; **~74 feedback rounds were never stored** for future sessions.
- **RAG at compose only:** `find_similar()` injects accepted examples into the compose prompt. The feedback endpoint does **not** use the example bank (and you do **not** need to add that — see Section 16).

### Did we show the trained system is substantially better?

**No. There is no valid before/after or A/B evidence.**

| Expected if learning worked | What the logs show |
|----------------------------|-------------------|
| Accept rate rises as bank grows | Accept rate **fell**: Jun 15 **13%** → Jun 16 **11%** → Jun 17 **6%** (noisy, but not improvement) |
| Similar prompts retrieve good examples | Token overlap misses novel wording (e.g. “Enoshima seaside” → **no** match) |
| Controlled RAG on vs off | **Never run** |
| Forced-choice discrimination | **Never run** |

**Bottom line:** June data supports “people give feedback” and “some sessions end in accept.” It does **not** support “learning from feedback makes the system substantially better.” That requires Section 6.

---

## 1. Research questions

### Primary (quantitative)
1. **Discrimination:** Can participants pick their own (refined) sequence among distractors above chance?
2. **Refinement:** Does the post-feedback sequence get picked more often than the pre-feedback (first compose) sequence?
3. **Example bank:** For matched probe memories, does compose **with** the bank produce sequences that win forced-choice comparisons vs compose **without** the bank?

### Secondary
4. Which **distractor types** are confused most often (generic floral, theme-mismatch, random)?
5. Which memory themes (food, nature, place, emotion) yield the highest discrimination scores?
6. Does facilitator-guided feedback increase discrimination vs free-form speech?

### Qualitative (optional arm)
7. What do participants say the system cannot represent (texture, smoke, ocean, etc.)?

---

## 2. Primary measure — forced-choice identification (MFC)

**Replace Likert ratings.** Do not ask “how close is this 1–5?”

### Task (participant-facing)

> “You described a memory. We made several 30-second scent sequences. They are labeled A, B, C, … — you won’t know which is which. Smell each one. **Pick the one closest to your memory.** If none are close, pick ‘none of these.’”

### Procedure
1. Facilitator builds a **candidate set** of k sequences (Section 4).
2. Sequences are **blinded** (letters only; order randomized per participant).
3. Play each sequence on device with **≥30 s ventilation** between options (or longer if room needs it).
4. Participant selects one label (or “none”).
5. Log: `participant_id`, `target_id`, `chosen_id`, `candidate_set_type`, `order_shown`, `reaction_time_optional`.

### Core metrics

| Metric | Definition | Chance baseline |
|--------|------------|-----------------|
| **Top-1 accuracy** | Chose the designated target | **1/k** |
| **Target vs first-compose** | Target is final refined; distractor includes initial compose — did they pick final? | 1/2 in pairwise block |
| **Bank vs no-bank** | Target is compose-with-bank; distractor is compose-without-bank for same sentence | 1/2 in pairwise block |
| **“None of these” rate** | System failure / palette ceiling | — |

**Success criterion (pilot):** Top-1 accuracy **≥ 0.40** for k=4 (chance = 0.25) with **≥ 24** participants, **or** pairwise bank-vs-no-bank **≥ 65%** prefer bank.

### UI / engineering needed
- [ ] **MFC panel:** play blinded candidates; log choice (new UI + `POST /mfc_choice` or manual sheet for pilot)
- [ ] **Candidate builder:** assemble target + distractors from session history without revealing labels to participant

Pilot can run MFC with facilitator playing sequences manually and logging on paper; implement UI before main N.

---

## 3. Distractor library (build before study)

Pre-generate and store distractors so MFC sets are reproducible.

| Code | Distractor type | Source | Tests |
|------|-----------------|--------|-------|
| **D1** | First compose | Same session, before feedback | Did refinement help? |
| **D2** | Generic floral | Fixed: Citronelly + Lavendar + Eucalipto (10s each) | Palette default bias |
| **D3** | Theme mismatch | Compose model on **wrong-theme** one-liner (food memory → nature sentence) | Semantic alignment |
| **D4** | Random valid | Random catalog scents, 30s total | Low-level discrimination |
| **D5** | Other participant | Accepted sequence from bank, same theme, different sentence | False positive control |
| **D6** | No-bank compose | Re-compose same sentence with `LEARNED_EXAMPLES_ENABLED=false` | Bank effect |
| **D7** | Feedback round t−1 | Previous revision in same session | Step-wise improvement |

Store in `aromagen/mfc_distractors/` or DB: `{id, type, scent_sequence, source_session, theme}`.

---

## 4. MFC set configurations (mix and match)

Choose one **primary set** per study phase; optional secondary sets for substudies.

| Set name | k | Candidates | Primary question |
|----------|---|------------|------------------|
| **MFC-4-refine** | 4 | Target=final, D1, D2, D4 | Does refinement beat first compose + generic? |
| **MFC-4-bank** | 4 | Target=with-bank compose, D6, D2, D4 | Does example bank help first compose? |
| **MFC-6-full** | 6 | Target=final, D1, D2, D3, D5, D4 | Hard discrimination |
| **MFC-2-pairwise** | 2 | Target vs D1 **or** Target vs D6 | Quick block; repeat for multiple pairs |
| **MFC-3-lineup** | 3 | Target, D1, D2 | Shorter sessions / elderly participants |

**Recommendation:** Main study uses **MFC-4-refine** every session. Bank evaluation uses **MFC-2-pairwise** (bank vs no-bank) on **held-out probe sentences** (Section 6).

---

## 5. Study conditions — expanded matrix

Run a **factorial-style** design. Not every cell needs equal N; prioritize shaded cells first.

### Factor A — Example bank at compose
| Level | Setting |
|-------|---------|
| **Bank-OFF** | `LEARNED_EXAMPLES_ENABLED=false` |
| **Bank-ON** | Default; bank frozen or growing per phase |

### Factor B — Feedback mode
| Level | Allowed rounds | Facilitator |
|-------|----------------|-------------|
| **Compose-only** | 0 | No feedback prompts |
| **Free feedback** | ≤2 | Minimal script |
| **Guided feedback** | ≤2 | Section 9 script |

### Factor C — Calibration
| Level | |
|-------|--|
| **No cal** | |
| **Cal** | Single-scent previews (Section 8) |

### Factor D — Memory entry
| Level | |
|-------|--|
| **Free recall** | Participant chooses memory |
| **Prompt card** | Food / nature / place / emotion (Section 10) |
| **Probe sentence** | Fixed sentence for bank A/B only (Section 6) |

### Suggested minimum cells (pilot → main)

| Cell ID | Bank | Feedback | Cal | MFC set | N (main) | Priority |
|---------|------|----------|-----|---------|----------|----------|
| **P1** | ON | Guided | Yes | MFC-4-refine | 12 | **Primary** — core product loop |
| **P2** | OFF | Guided | Yes | MFC-4-refine | 12 | Refinement without bank |
| **P3** | ON | Compose-only | Yes | MFC-4-refine | 12 | First-compose quality |
| **B1** | ON vs OFF | Compose-only | Yes | MFC-2-pairwise (D6) | 24 | **Bank claim** (Section 6) |
| **F1** | ON | Free vs Guided | Yes | MFC-4-refine | 24 | Facilitator effect |
| **Q1** | ON | Guided | Yes | MFC-6-full | 8 | Hard discrimination (optional) |

**Total main N (minimum credible):** ~60–80 across cells, plus **24** for dedicated bank probe block.

Log on every session: `cell_id`, `participant_id`, `bank_version` (hash of `learned_examples.json`), `cartridge_set_id`, `mfc_set`, `chosen_id`, `target_id`.

---

## 6. Example bank evaluation — how to actually claim “substantially better”

This is the only design that can support a learning claim. **June logs cannot.**

### Phase 1 — Build bank (1–2 weeks)
- Run **P1** cells; accept only sequences that win **MFC-4-refine** (participant picks final over D1/D2/D4).
- Goal: **≥20 validated accepts**, tagged by theme.
- Export frozen bank: `learned_examples_v1.json`.

### Phase 2 — Held-out probe test (between-subjects)

**Participants:** new N=24+ (never in Phase 1).

**Stimuli:** 8–12 **probe sentences** written by researchers (not copied from Phase 1), balanced across themes. Pre-generate two sequences per probe:
- **S_bank:** compose with `learned_examples_v1.json`
- **S_nobank:** compose with bank disabled

**Counterbalance:** order of play, blind labels.

**Task — MFC-2-pairwise:** “Which smell is closer to **this** memory?” (read probe sentence again).

**Primary endpoint:** % trials where participant chooses **S_bank** over **S_nobank**.

**Claim threshold (example):** **≥65%** bank wins (binomial p<0.05 vs 50%) across **≥192** paired trials (24 p × 8 probes).

**Secondary:** Top-1 in MFC-4-bank (target=S_bank vs D6, D2, D4).

### Phase 3 — Feedback loop value (within-session)

Already in **MFC-4-refine:** target=final, D1=first compose.

**Endpoint:** % participants who pick **final** over **first compose** in pairwise comparison.

**Claim threshold:** **≥70%** prefer final (vs 50% null).

### What you still cannot claim without more work
- True model fine-tuning
- Improvement from **all** feedback (only accepts enter bank)
- Cross-session improvement if bank and participant pool confound

---

## 7. Session structure (50 min — standard P1 cell)

| Block | Time | Activity |
|-------|------|----------|
| Welcome + consent | 3 min | Explain memory → compose → smell → feedback → **pick closest among several** |
| Calibration | 5 min | If cell includes Cal (Section 8) |
| Memory capture | 5 min | Section 9.1 |
| First compose + play | 4 min | Compose → play once (participant knows this is “version 1”) |
| Feedback × ≤2 | 15 min | Section 9.2–9.3 |
| **MFC block** | 12 min | Section 2; **MFC-4-refine** |
| Optional accept | 2 min | “This works” **only if** they picked their final sequence in MFC (or log mismatch) |
| Debrief | 4 min | Section 14 (qualitative arm) |

**70 min variant:** second memory + second MFC; or **MFC-6-full**.

---

## 8. Calibration block

Same as v1: Garlic → Citronelly → Eucalipto preview; confirm device works. Abort if no smell.

---

## 9. Facilitator script

### 9.1 Memory capture

> “Describe a specific moment — include what you smelled or want to smell again.”

Block single-word inputs. Read transcript back before first play.

### 9.2 Guided feedback (two rounds max)

1. “What did you smell?”
2. “What’s missing?”
3. “More or less of what — sweet, fresh, spicy, earthy?”

Redirect narratives: “What should change about **the smell you just smelled**?”

### 9.3 MFC block (read aloud)

> “Next you’ll smell several sequences, labeled A through D. They might include earlier versions. Take your time between each. Tell me which letter is **closest to your memory** — or ‘none’ if nothing fits.”

Facilitator must not hint. Ventilate between plays.

---

## 10. Memory prompts & probe sentences

### Prompt cards (Factor D — prompt card)
Food / nature / place / emotion — same as v1.

### Probe sentences (Factor D — probe; Phase 2 only)
Researcher-written, e.g.:
- “Steaming bowl of ramen at a counter seat in Tokyo, salty broth and ginger.”
- “Cut grass and hot pavement after summer rain.”
- “Old paperback book opened in a quiet library.”

**Do not** reuse Phase 1 participant sentences verbatim.

---

## 11. Data collection

### Automatic
- Dialogue JSONL: compose, feedback, accept, transcribe
- **New:** MFC choice events with blind labels and ground-truth target

### Manual log sheet (minimum for pilot)

```
participant_id:
cell_id: P1 | P2 | ...
bank_version_hash:
memory_theme:
rounds_of_feedback:

MFC set: MFC-4-refine
candidates: [ids]
order_shown: e.g. A=D1, B=target, C=D2, D=D4
chosen_label:
correct: Y | N
chose_none: Y | N

accepted_after_mfc: Y | N
hardware_issue: Y | N
```

### Qualitative (optional)
- Record debrief audio **separately** (Section 14)
- Or post-hoc code feedback JSONL with scheme: `directive | descriptive | narrative | meta`

---

## 12. Analysis plan

### Quantitative primary
1. MFC top-1 accuracy vs chance (binomial test per k)
2. Pairwise final vs first-compose (McNemar or binomial)
3. Pairwise bank vs no-bank on probes (Section 6)
4. Mixed model: `correct ~ cell_id + theme + (1|participant)` if repeated measures

### Quantitative secondary
- Confusion matrix: which distractor steals choices from target
- Feedback rounds × MFC accuracy
- “None of these” rate by theme

### Qualitative
- Thematic analysis on debrief (n≥15) **or** retrospective coding of June logs (clearly labeled exploratory)

---

## 13. Success metrics

| Endpoint | Target | June baseline |
|----------|--------|---------------|
| MFC-4 top-1 (refined target) | **≥40%** (chance 25%) | not measured |
| Final beats first compose | **≥70%** pairwise | not measured |
| Bank beats no-bank (probes) | **≥65%** pairwise | not measured |
| Accept rate | secondary only | 11% |

---

## 14. Qualitative arm (proper collection in v2)

If you want qualitative claims in the paper:

1. **Debrief recording** (3 questions, separate file):
   - What could the device not capture?
   - When giving feedback, what worked?
   - How did you decide during the A/B/C/D task?

2. **Sample n≥15**, transcribe, code with 2 coders, report Cohen’s κ.

3. **June logs:** optional appendix — code 30 stratified feedback utterances; label as **retrospective / exploratory**, not preregistered.

---

## 15. Timeline

| Week | Activity |
|------|----------|
| W0 | Build distractor library; MFC UI or paper protocol |
| W1 | Pilot P1 n=6; verify MFC logistics |
| W2 | Phase 1 bank building (P1) |
| W3 | Phase 2 probe test (B1) |
| W4 | Analysis + optional qualitative coding |

---

## 16. Known limitations & non-goals

### Disclose in paper
- Learning = **accepted examples in compose prompt**, not weight fine-tuning
- Most feedback is **ephemeral** (in-session only) unless accepted
- Palette and 30s format cap fidelity
- MFC measures **perceived match**, not objective chemistry

### Explicit non-goals (per project direction)
- **Do not** extend RAG into the feedback/refinement endpoint — feedback already receives the current sequence, prior rounds, and catalog; adding examples there adds complexity without a demonstrated gap
- **Do not** use Likert ratings as primary outcome
- **Do not** claim “we train on all feedback” — only validated accepts enter the bank

---

## Appendix A — Facilitator cheat sheet

```
CAL → MEMORY → COMPOSE → PLAY → FEEDBACK (≤2) → MFC (blinded A–D) → log choice

MFC: never reveal which is which; ventilate between plays
Accept optional; log if they picked final in MFC
```

## Appendix B — Environment variables

```bash
# Bank off (P2, D6 generation, Phase 2 control)
export LEARNED_EXAMPLES_ENABLED=false

# Bank on (default)
export LEARNED_EXAMPLES_ENABLED=true
export LEARNED_EXAMPLES_TOP_K=3
# Point to frozen bank for Phase 2:
export LEARNED_EXAMPLES_PATH=/path/to/learned_examples_v1.json
```

## Appendix C — June data summary (for related work section)

| Item | Value |
|------|-------|
| Feedback rounds logged | 85 |
| Accepts / bank entries | 11 |
| Feedback rounds persisted in bank | 11 (summaries in 8 accepts) |
| Ratings collected | 0 |
| MFC trials | 0 |
| Controlled bank A/B | 0 |
| Evidence of substantial improvement | **None**
