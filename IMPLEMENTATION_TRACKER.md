# Deliberate AI — Implementation Tracker

**Session started:** 2026-05-03
**Branch:** `dev`
**Status:** IN PROGRESS

---

## Goals

1. Replace 12-persona "illusion debate" with 6-persona genuine debate system
2. Add SQLite-backed persistent persona memory for real multi-round interaction
3. Add decision structure detection (binary, multi-option, open-ended, analysis)
4. Implement deliberate diversity axes (epistemic type, diversity role, option alignment)
5. Add "Deep Debate" mode (SQLite-backed) alongside existing "Simultaneous" mode
6. Update UI to reflect new architecture
7. Update documentation with research citations

---

## Completed

### Phase 0: Infrastructure (DONE)
- [x] Created `main` and `dev` branches per AGENTS.md
- [x] Secured `settings.json` from git tracking (added to `.gitignore`)
- [x] Added security rules to `Agents.md` (never push private data)
- [x] Configured local `settings.json` with vLLM endpoint (`http://100.72.20.54:8000/v1`) and SearXNG (`http://100.72.20.54:8080`)
- [x] Added model autodetection (`Pipeline.fetch_available_models()`) via `/v1/models` endpoint
- [x] Updated Settings dialog with editable combo box + "Fetch Models" button
- [x] Detected model: `Qwen/Qwen3.6-27B-FP8`

### Phase 1: SQLite Memory Layer (DONE)
- [x] Created `memory.py` — SQLite-backed persistent memory module
- [x] Tables: `personas`, `responses`, `positions`, `influence`, `decision_context`
- [x] Methods implemented:
  - `init_session()` — creates session database
  - `store_decision_context()` / `get_decision_context()` — decision structure storage
  - `store_persona()` / `get_all_personas()` — persona profiles
  - `store_response()` — per-round responses
  - `get_persona_history()` — own history for a persona
  - `get_current_round_responses()` — what others said this round
  - `get_relevant_counterarguments()` — responses that challenged a persona
  - `store_position()` / `get_position_trajectory()` — stance tracking across rounds
  - `store_influence()` / `get_influence_graph()` — influence tracking
  - `get_option_convergence()` — how personas distribute across options
  - `build_debate_context()` — targeted context assembly for a persona
  - `cleanup_session()` — removes session database

### Phase 2: Pipeline Refactor (PARTIAL)
- [x] **Stage 1 (Situation Extraction)** — Overhauled to detect decision structure:
  - New fields: `question_type` (binary|multi_option|open_ended|analysis), `options`, `evaluation_criteria`, `decision_structure_notes`
  - Rules for each question type with extraction guidance
- [x] **Stage 2 (Persona Generation)** — Replaced entirely:
  - Reduced from 12 → **6 personas**
  - New diversity axes per persona:
    - `diversity_role`: Proponent, Opponent, Option Champion, Cross-Option Evaluator, Adversarial Challenger, Synthesist, Empiricist, Option Generator, Surface Interpreter, Deep Interpreter, Contextualizer
    - `epistemic_type`: Empiricist, Pragmatist, Principled, Systemic, Adversarial, Synthesist
    - `option_alignment`: Which option(s) the persona leans toward
  - Role assignment varies by `question_type`:
    - `multi_option`: 2 option champions + cross-evaluator + challenger + synthesist + empiricist
    - `binary`: 2 proponents + 2 opponents + synthesist + empiricist
    - `open_ended`: 2 option generators + 2 critics + synthesist + empiricist
    - `analysis`: 2 interpreters + contextualizer + critic + synthesist + empiricist
  - Personas stored in SQLite via `memory.store_persona()`
  - Removed dead code from old 12-persona generation

---

## Remaining Work

### Phase 2 (cont.): Pipeline Refactor (TODO)
- [ ] **Stage 0 (Initial Positions)** — Update to work with 6 personas (prompt adjustments)
- [ ] **Stage 3 Simultaneous** — Update `stage3_simulation_round()` for 6 personas
- [ ] **Stage 3 Sequential** — Update `stage3_sequential_round()` for 6 personas
- [ ] **Stage 3 Deep Debate** — NEW: `stage3_deep_debate()` method
  - Uses SQLite for targeted context per persona
  - Each persona sees: own history + current round responses + relevant counterarguments
  - Stores responses in SQLite after each call
  - Extracts stance vector and stores in `positions` table
  - Tracks influence via `influenced_by` field
- [ ] **Stage 4 (Round Compression)** — May need adjustment for 6 personas
- [ ] **Stage 5 (Report Generation)** — Update for new structure:
  - Add "Diversity Analysis" section
  - Use SQLite trajectory data for genuine shifts (not LLM-generated)
  - Show option convergence for multi-option questions
  - Adjust persona count references (12 → 6)
- [ ] **`ensure_distinct_personas()`** — Update for 6 personas (or remove if no longer needed)
- [ ] **`calculate_majority_voting()`** — Update for option-based voting (multi-option)
- [ ] **`calculate_confidence_score()`** — Review for compatibility

### Phase 3: UI Updates (TODO)
- [ ] Add "Deep Debate" mode to debate mode combo box (3 modes: Simultaneous, Sequential, Deep)
- [ ] Update persona count references in UI (12 → 6)
- [ ] Show decision structure in progress log (question type, options detected)
- [ ] Add real-time shift visualization (using SQLite data)
- [ ] Update Settings dialog model name handling (already done for fetch, but verify)
- [ ] Update `SimulationWorker` to pass `session_id` and support deep debate mode
- [ ] Update `run_simulation()` method to handle deep debate mode

### Phase 4: Documentation (TODO)
- [ ] Update `README.md`:
  - Change "12 personas" → "6 personas" throughout
  - Add explanation of decision structure detection
  - Add explanation of diversity axes
  - Add explanation of SQLite-backed debate
  - Add research citations (Argyle & Cook, Janis, Surowiecki, Google Project Aristotle, OpenAI Self-Play Debate, Choi et al. NeurIPS 2025)
- [ ] Update `HOW_IT_WORKS.md`:
  - Change "12 personas" → "6 personas" throughout
  - Add section on question types and how the system adapts
  - Add section on diversity axes (epistemic type, diversity role)
  - Add section on SQLite memory and genuine debate
  - Update research citations with actual sources
  - Update example reports to reflect 6 personas

### Phase 5: Testing & Cleanup (TODO)
- [ ] Test simultaneous mode with 6 personas
- [ ] Test sequential mode with 6 personas
- [ ] Test deep debate mode (when implemented)
- [ ] Test multi-option question handling
- [ ] Test open-ended question handling
- [ ] Test analysis question handling
- [ ] Verify SQLite session cleanup after simulation
- [ ] Verify no sensitive data in commits
- [ ] Commit all changes with conventional commit messages

---

## Key Design Decisions

1. **6 personas, not 12** — Based on research: Argyle & Cook (1976), Janis (groupthink), Surowiecki (wisdom of crowds), Google Project Aristotle (2015), OpenAI Self-Play Debate
2. **SQLite per session** — Each debate gets its own `debate_<session_id>.db` in `debate_data/` directory
3. **Question type detection** — Stage 1 now detects binary, multi-option, open-ended, or analysis questions and adapts persona roles accordingly
4. **Diversity axes** — Three orthogonal axes: diversity_role (debate behavior), epistemic_type (how they know), option_alignment (which options they lean toward)
5. **Backward compatibility** — Simultaneous and Sequential modes kept (just reduced to 6 personas). Deep mode is new.
6. **No global SQLite** — Each session is isolated. Cleanup happens after simulation completes.

---

## File Inventory

| File | Status | Notes |
|------|--------|-------|
| `memory.py` | NEW — DONE | SQLite memory layer |
| `pipeline.py` | MODIFIED — PARTIAL | Stage 1, 2 done. Stage 0, 3, 4, 5 remain |
| `ui.py` | MODIFIED — PARTIAL | Settings dialog model fetch done. Debate mode, persona count, deep mode remain |
| `search.py` | UNCHANGED | No changes needed |
| `tts_client.py` | UNCHANGED | No changes needed |
| `error_tracker.py` | UNCHANGED | No changes needed |
| `settings.json` | LOCAL ONLY | Not tracked by git |
| `.gitignore` | MODIFIED — DONE | Removed `!settings.json` exception |
| `Agents.md` | MODIFIED — DONE | Added security rules |
| `README.md` | TODO | Update persona count, add research citations |
| `HOW_IT_WORKS.md` | TODO | Update persona count, add diversity explanation |

---

## Pick-Up Instructions

If this session drops, here's where we left off:

1. **memory.py** is complete and committed
2. **pipeline.py** Stage 1 and Stage 2 are done but NOT YET COMMITTED
3. Next step: Update Stage 0 (initial positions) and Stage 3 (debate rounds) in `pipeline.py`
4. After pipeline is complete, move to UI updates
5. After UI is complete, move to documentation

**Current git state:** Uncommitted changes in `pipeline.py` (~560 lines changed). Run `git diff pipeline.py` to review.

**To resume:**
```
git stash  # if needed
git checkout dev
# Then continue with remaining pipeline.py edits
```

---

## Research Citations (for documentation)

- **Argyle & Cook (1976)** — "The Study of Interaction": Optimal group size for decision-making is 4-6
- **Janis (1972)** — "Victims of Groupthink": Larger groups more prone to conformity
- **Surowiecki (2004)** — "The Wisdom of Crowds": Groups of 3-5 outperform larger groups when independent
- **Google Project Aristotle (2015)** — Team effectiveness peaks at 5-7 members
- **OpenAI Self-Play Debate** — Used 2-4 agents, debate format improved reasoning
- **Choi et al. (NeurIPS 2025)** — Debate alone doesn't improve accuracy without external facts (martingale process)
- **Longino (2002)** — "The Fate of Knowledge": Epistemic diversity outperforms raw demographic diversity
- **Godfrey-Smith (2003)** — "Relevance Boundaries of Scientific Theories": Diversity of perspectives in scientific communities
