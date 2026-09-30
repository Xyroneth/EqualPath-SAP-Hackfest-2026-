# Final-pitch deck: what changed

`EQUALPATH_SAP_Hackfest_2026_Final.pptx` is generated from the original deck by `scripts/build_final_deck.py`. The original file is not modified. Re-run the script after editing the original:

```bash
backend/.venv/bin/python scripts/build_final_deck.py docs/architecture-diagram.png
```

| # | Correction from the master prompt | Change made |
|---|---|---|
| 1 | Slide 5: not "Seven Agents" | Title is now **"Six Specialized AI Agents and One Human Approval Layer"**. The HITL row is relabelled *Human approval layer (not an AI agent)*, and the colour key is updated to match. |
| 2 | Slide 4: Employer Readiness evidence | **"Declared / document-verified / experience-validated"**. The other three cards now show their real statuses (*Self-declared / source-supported / assessed*, *Verified / developing / missing*, *Candidate-controlled constraints*). |
| 3 | Slide 6: flags, does not certify | Quote box adds: *"The agent flags and classifies evidence; it does not independently certify that an employer is inclusive."* A footnote explains the evidence levels and labels the seeded/simulated data. |
| 4 | Slide 7: complete persona + two pauses | 31, Lucknow (tier-2), 3 years of testing, **four-year** break, goal, constraints, pain points and behaviours. Step 2 is marked *⏸ Pause 1: Priya approves*; step 6 is now *Human approval: ⏸ Pause 2 → passport issued*. The result line names both outcomes. |
| 5–6 | Slide 8: used vs roadmap; honest Learning Hub | Rows split into **✓ Used in the prototype** (SAP UI5, SAP Learning Hub curated catalog + deep links + milestones + evidence upload with no progress-sync API, and SAP AI Core / SAP Build / SAP BTP adapters that go live when bound) and **◇ Enterprise roadmap** (Talent Intelligence Hub, SuccessFactors · Joule, People Intelligence / Data Cloud). |
| 7 | Slide 9: present tense, name the parts | Title is *"The Live Prototype Demonstrates the Full Career Orchestrator"*. It lists the Skills Discovery Agent (functional core), LangGraph, the two interrupts, the SAP services and the Passport. |
| 8 | Slide 9: architecture proof | The architecture diagram rendered from the running prototype replaces the business-model boxes. Business value and revenue move to **slide 11 (Backup)**. |
| 9 | Timing | Speaker notes are rewritten with per-slide timings (about 5.5 min in total), followed by a 4–4.5 min demo (`DEMO_SCRIPT.md`). |
| 10 | Honest claims | Seeded, simulated and synthetic data is labelled on slides 6 and 9 and on every prototype screen. The bias test is described as single-person, not statistical proof. |

**Persona mismatch fixed:** the original slide 7 said *29* with a *three-year* break. The prototype follows the master prompt (*31*, *four-year*), and the deck now matches.

## Before the finale (30 Sept 2026)

1. **Open the Final deck in PowerPoint and skim slides 5, 7, 8 and 9.** The new text is longer in places, and it was not rendered here (no PowerPoint or LibreOffice was available), so check for wrapping or overlap.
2. **Verify the SAP Learning assets in your SAP Learning Hub, student edition account.** Then set `team_verified_on` for each one in `backend/app/data/learning_assets.json` (the links were only checked automatically).
3. **Optional, but it strengthens "SAP technology":** put an SAP AI Core service key in `.env` (`AICORE_SERVICE_KEY` + `AICORE_ORCHESTRATION_DEPLOYMENT_URL`). The header will then show *SAP AI Core - generative AI hub* and Skills Discovery runs on the LLM. Rehearse once in that mode.
4. **Keep a fallback:** the screenshots in `docs/screenshots/` (regenerate them with `EQUALPATH_SHOTS=$PWD/docs/screenshots npx playwright test` from `frontend/`) or a screen recording of the demo.
