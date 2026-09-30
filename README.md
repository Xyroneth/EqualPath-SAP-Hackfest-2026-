# EQUALPATH: Capability Confidence Engine for Inclusive Hiring

**SAP Hackfest 2026 · Theme 2: Inclusive Workforce · Round 2 (Grand Finale) functional prototype · Team Blitzkrieg, SRMIST Kattankulathur**

EQUALPATH is a skills-first, multi-agent **Career Orchestrator**. It turns a non-traditional candidate's real work (projects, work samples, certificates, learning records) into evidence-backed capabilities. It also checks whether the employer's role is ready for that candidate. Six specialised AI agents and one human approval layer produce a transparent **Mutual Readiness Passport**.

The demo persona is **Priya Sharma**: 31, from Lucknow (a tier-2 city), a former junior software tester returning to work after a four-year caregiving break.

---

## 1. Quick start

| Option | Command | Then open |
|---|---|---|
| Docker (one command) | `docker compose up --build` | http://localhost:8000 |
| No Docker (one command) | `./scripts/start.sh` | http://localhost:8000 |
| Development (hot reload) | `./scripts/dev.sh` | http://localhost:5173 |
| Tests | `./scripts/test.sh` | pytest + Playwright |

Requirements: Python 3.12+ and Node 20+ (or just Docker). **No credentials are needed.** Without them, EQUALPATH runs in *deterministic demo mode* and says so in the header. To use an LLM, copy `.env.example` to `.env` and fill in SAP AI Core or an OpenAI-compatible key.

Click **Start Priya's demo** and follow [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) (about 4 minutes). Each step ends with a **Next** button, and the side menu still lets you jump anywhere.

### Who am I acting as? (sign-in)

The coloured **role bar** under the top bar always shows the current role. Candidate needs no password. The three staff roles each need their own:

| Role | Password | What they see | What they do |
|---|---|---|---|
| Candidate | none (default) | Priya's own profile, evidence, skills, roles, plan and passport | Approves her skills, chooses a role, uploads proof |
| Counsellor | `Counsel@2026` | Priya's evidence and skills (for review) | Makes the **final passport decision** (approve, edit, reject, ask for more proof) and reviews milestone proof |
| HR Reviewer | `HRreview@2026` | The job ad and the **employer copy** of the passport. No raw evidence | Speaks for the employer. Three tasks on *Employer tasks*: approve or edit the fairer job ad, answer the employer claims that conflict with the evidence, then **respond to the candidate** (invite to interview with agreed adjustments, keep in the talent pool, or decline, always with a reason Priya sees) |
| Auditor | `Audit@2026` | Fairness check and the audit log. No personal data (Priya's real details are hidden even in the fairness twins) | Four tasks on *Agent activity*: re-verify the hash-chained log, **sign off the fairness check** (or raise a concern that the counsellor and passport show), check who opened the evidence, download a CSV audit report |

The HR Reviewer cannot make the passport decision: they speak for the employer, so that would be a conflict of interest. The API enforces it (403).

These are demo passwords. Change them with `ROLE_PASSWORD_COUNSELLOR`, `ROLE_PASSWORD_HR_REVIEWER`, `ROLE_PASSWORD_AUDITOR` and `SESSION_SECRET` in `.env`. Access is enforced by the **backend** (the API returns 403 or removes data), not just hidden in the UI. Five wrong passwords lock sign-in for 60 seconds. Behind XSUAA on SAP BTP, roles come from role collections instead.

**Languages and theme:** English and Hindi (globe menu), light and dark mode (moon button). The `/practice` sandbox stays in English on purpose so test scripts stay stable.

**Evidence:** the six sample files (resume, test cases, bug reports, Python repo, Excel defect tracker, course certificate) are real PDFs and an Excel workbook with charts and screenshots. **View** opens a formatted PDF or spreadsheet viewer in a new tab through a 5-minute link. Priya can add PDF, DOCX, PPTX, XLSX, CSV, TXT, MD, JSON, code files (PY, JS, TS, Java) and PNG/JPG images (up to 8 MB; images need a one-line description). Old `.doc`, `.xls` and `.ppt` files must be saved in the new format first. Text is extracted at runtime and used by Skills Discovery.

---

## 2. What the prototype does

```
Candidate evidence ──► Skills Discovery Agent ──► [HUMAN 1: Priya reviews and corrects] ──► Market Intelligence Agent
   ──► [Priya chooses role] ──► Learning Pathway Agent ∥ Employer Readiness Agent ──► Inclusive Matching Agent
   ──► Bias Audit Agent ──► review routing (local queue or SAP Build Process Automation)
   ──► [HUMAN 2: counsellor / HR approves, edits, rejects or requests evidence] ──► Mutual Readiness Passport
```

One **LangGraph** workflow (`backend/app/graph.py`) with shared typed state, SQLite checkpoints (runs survive restarts), retry policies on agent nodes, a parallel fan-out/fan-in, and `interrupt()` human pauses. Every node records status, inputs, outputs, duration, confidence and an audit event, and the **Agent activity** screen shows all of it live.

| Agent | What it does | Implementation |
|---|---|---|
| **Skills Discovery** (functional core agent) | One record per capability: skill, normalised key, proficiency, evidence type, **verbatim evidence quote**, source id, recency, extraction confidence, **verification status**, adjacent skills | Calls SAP AI Core / an OpenAI-compatible LLM after PII redaction. The output is validated with Pydantic, every quote must be found verbatim in the cited source, and verification status is **derived in code from the source type**, so the model cannot upgrade it. Resume-only claims stay `self_declared`. On invalid output it retries, then falls back to the deterministic engine and labels the fallback. `app/agents/skills_discovery.py` |
| **Market Intelligence** | Top 3 roles from a labelled local catalog, each with 5 visible weighted components | Only allow-listed features are inputs, so protected attributes and career-break duration are **not inputs** (0 points). `market_intelligence.py` |
| **Learning Pathway** (functional supporting agent) | Classifies each requirement as verified / developing / missing and creates the smallest useful milestone: gap, learning asset, hours, practice task, required evidence, completion rule, why it matters (EN + हिं) | Deterministic gap rules. LLM-drafted milestone wording is validated: the asset must come from the curated catalog, effort is bounded, and completion is always a human review. `learning_pathway.py` |
| **Inclusive Matching** | Mutual-fit **components** (no single score): capability coverage, evidence strength, work mode / location / language / schedule / accommodation fit, gap feasibility | An unconfirmed employer condition becomes an *employer action*, never a candidate penalty. `inclusive_matching.py` |
| **Employer Readiness** | Scans the job ad **of the role Priya chose** (each of the 5 roles has its own fictional employer, original ad and published improved ad) for 10 barrier categories: degree/college prestige, career-gap rules, age limits or "freshers only", gender or marital preferences, unneeded physical requirements, vague wording, unclear work mode or hours, inaccessible interviews, no accommodation process, no return-to-work support. Classifies the employer's 5 claims (`declared` / `document_verified` / `experience_validated` / `conflicting_evidence`) against its own ad, policies and consented candidate feedback, and drafts a fairer ad (every change listed) that **an HR reviewer must approve** | Rule-based and explainable. Candidate feedback counts only with consent, and 3 or more consistent reports are required. The rewrite never invents facts: missing hours stay as a placeholder for HR. `employer_readiness.py`, `data/jobs.json` |
| **Bias Audit** | **Twin test**: 9 twins of the profile that each change one personal detail (a man's name, a name from another community, age 24, age 45, no break, 8-year break, disclosed disability, IIT college, home town spelt differently), with the real scores before and after. **Control test**: a switch runs the same twins through a deliberately biased, simulated résumé filter (gap penalty, age cut-off, college bonus); the test catches it on 4 of 9 twins and names the rule behind each difference, proving it can detect bias. **Try your own twin**: change any detail live and see EQUALPATH (never moves) next to the biased filter (moves when a rule applies). Plus a feature-use audit with perturbation | States plainly that one person is not statistical proof. The simulated filter is never used for decisions. Also includes a clearly labelled *synthetic* monitoring dashboard (four-fifths rule, small-cell suppression). `bias_audit.py` |
| **Human-in-the-loop** (not an AI agent) | Pause 1: Priya accepts, edits, removes or adds skills and sets sharing. Pause 2: the counsellor approves, edits, rejects or requests evidence, and **a reason is required for every override** | The passport API returns **409** until approval. |

**Passport outcomes** are limited to *Ready to Proceed*, *Ready with Learning Milestone*, *Employer Action Required* and *Human Review Required*. The demo ends with **Ready with Learning Milestone** (candidate side) **+ Employer Action Required** (employer side). The passport is printable and downloadable (HTML/JSON), and has candidate and employer copies (the employer copy withholds unshared sections).

---

## 3. SAP technology: honest integration status

The **Architecture & SAP** screen (`/architecture`, API `/api/system/status`) shows the live state at runtime.

| SAP technology | Used for | Status out of the box | To make it live |
|---|---|---|---|
| **SAP UI5 Web Components** (`@ui5/webcomponents-react`, Horizon theme) | Entire UI | **Used in the prototype** | - |
| **SAP Learning Hub, student edition** | Curated catalog (`backend/app/data/learning_assets.json`, 13 assets, 9 from SAP), deep links, milestones, evidence upload, human review | **Curated catalog + deep links**. No API, scraping or progress sync. | Team fills `team_verified_on` after checking each asset in their student-edition account |
| **SAP AI Core: generative AI hub** | Skills Discovery and Learning Pathway prompts (orchestration or foundation-model mode; optional SAP Data Privacy Integration masking) | Adapter implemented and unit-tested with mocked HTTP. Not connected without a key. | `AICORE_SERVICE_KEY` + `AICORE_ORCHESTRATION_DEPLOYMENT_URL` (or bind `aicore` on BTP) |
| **SAP Build Process Automation** | Final human review as an approval process. The decision returns via an action and callback, and the graph resumes. | Adapter, callback endpoint, OpenAPI action spec, trigger payload and destination in [`sap-build/`](sap-build/README.md) | `SBPA_*` variables |
| **SAP Build Apps / SAP Build Work Zone** | Counsellor review app / launchpad tile | Deployment-ready guides (`sap-build/`) | BTP subaccount |
| **SAP BTP, Cloud Foundry runtime** | Hosting | `manifest.yml` (quick `cf push`) and `mta.yaml` (approuter + XSUAA + AI Core) | `cf push` or `mbt build && cf deploy` |
| **XSUAA / SAP Cloud Identity Services** | Candidate, Counsellor, HR Reviewer, Auditor roles | `xs-security.json`, `XSUAAIdentity` adapter. Local demo roles are active. | `IDENTITY_PROVIDER=xsuaa` behind the approuter |
| **SAP HANA Cloud** | Enterprise persistence | `HANARepository` (hdbcli) + `deploy/hana/schema.sql`. SQLite is active. | `REPOSITORY=hana` + `HANA_*` |
| SuccessFactors, Talent Intelligence Hub, Joule, Business Data Cloud | Enterprise roadmap | **Not integrated.** Listed as roadmap only. | - |

Nothing in the UI claims a live SAP connection unless the adapter really connected.

### Deploying to SAP BTP (Cloud Foundry)

```bash
# quick: single app, no XSUAA
npm ci --prefix frontend && npm run build --prefix frontend   # writes backend/app/static
cf login -a https://api.cf.<region>.hana.ondemand.com
cf push                                                        # uses manifest.yml
cf set-env equalpath AICORE_SERVICE_KEY "$(cat aicore-key.json)"; cf restage equalpath

# full: approuter + XSUAA + AI Core binding
mbt build && cf deploy mta_archives/equalpath_1.0.0.mtar
```
HTTPS is terminated by the Cloud Foundry router. On CF the container disk is ephemeral: use `REPOSITORY=hana` for data. LangGraph checkpoints use SQLite and should move to a managed database (see Limitations).

---

## 4. Privacy, security and responsible AI

- **Consent first**: processing is refused (403) without explicit consent. Sharing with an employer is a separate opt-in that Priya confirms again at checkpoint 1.
- **Data minimisation**: matching sees only an allow-listed feature set (`privacy.MATCHING_FEATURE_ALLOWLIST`). The SAP Build process context carries IDs and summaries only.
- **PII redaction before any external LLM call**: names, e-mail, phone, Aadhaar/PAN-like numbers, profile URLs, PIN codes and demographic phrases are removed (`privacy.redact`). SAP AI Core's DPI masking can be enabled as a second layer.
- **Sensitive accessibility information is kept separately** and encrypted (Fernet) in its own collection. It is never sent to an LLM or shown to employers. Employers only see **candidate-approved work accommodations**, never a diagnosis.
- **Immutable audit**: an append-only table (SQLite triggers block UPDATE and DELETE; on HANA, INSERT/SELECT-only grants) with a SHA-256 hash chain, verified on every read. It logs agent executions, candidate corrections, consent changes, approvals, overrides with reasons, evidence reviews and JD rewrite decisions.
- **Candidate controls**: correct (checkpoint 1), export (JSON) and delete (removes documents and graph checkpoints; the PII-free audit trail is kept).
- **Role-based access**: every mutating endpoint checks the role (for example, a candidate cannot approve the final review).
- **Secrets only via environment variables.** No candidate or employer data is used for model training.
- **AI limitations are shown**: extraction confidence is labelled separately from verification, the provider is shown on every run, and fallbacks are labelled.

---

## 5. Evaluation traceability (Round 2 rubric)

| Evaluation area | Working evidence in the prototype |
|---|---|
| **Persona Development** | Priya's demographics (31, Lucknow tier-2, Hindi/English), context (3 years testing, 4-year caregiving break), behaviours (evening learning, bilingual, approves sharing), goals and pain points: Home screen and `persona_priya.json` |
| **Problem Statement Clarity** | The *confidence gap*: recruiters cannot verify non-traditional evidence, and candidates cannot tell whether a role is ready for them (Home, Employer check) |
| **User Needs Identification** | Evidence visibility (quotes + sources), fair consideration (feature allow-list, bias audit), flexible-work information (work-condition fit), targeted learning (milestones), consent (profile, checkpoint 1), explainability (component breakdowns) |
| **Solution Alignment** | Each need maps to an agent, a screen and a demo step. See the table below. |
| **Functional Core Agent** | Skills Discovery: LLM call → Pydantic schema → quote-in-source validator → code-derived verification → retry/fallback. Tests: `test_llm_output_is_validated_and_cannot_upgrade_verification`, `test_every_skill_has_a_verbatim_quote_and_valid_schema` |
| **Full-System Showcase** | Live LangGraph run on the Agent activity screen: 12 nodes, a parallel branch, handoff messages and durations |
| **Human Safeguards** | Two interrupts, candidate corrections with reasons, final approve/edit/reject/request-evidence with required reasons, HR approval of the JD rewrite, human review of milestone evidence |
| **SAP Learning Hub Integration** | Curated catalog, `Open in SAP Learning` deep link, *Mark as started*, evidence upload, reviewer acceptance changes the status to `assessed` |
| **SAP Technology** | Active provider shown in the header and on the Architecture screen. SAP UI5 in use. SAP AI Core, SAP Build Process Automation, HANA Cloud and XSUAA adapters. BTP `manifest.yml` / `mta.yaml` |

| User need | Agent | Screen | Demo step |
|---|---|---|---|
| Make informal evidence visible | Skills Discovery | Evidence, Skills | 2 |
| Stay in control / consent | Human checkpoint 1 | Profile, Skills | 1, 3 |
| Realistic roles, not black boxes | Market Intelligence | Role options | 4 |
| Know exactly what is missing | Learning Pathway | Skill gaps | 5 |
| Short, practical, evening-friendly learning | Learning Pathway + SAP Learning catalog | Learning plan | 6 |
| Know whether the role fits (hybrid, schedule, breaks) | Employer Readiness + Inclusive Matching | Employer check, Passport | 7 |
| Fair consideration | Bias Audit | Fairness check | 8 |
| Accountable decision | Human checkpoint 2 | Human review | 9 |
| One shareable, explainable result | Passport composer | Your passport | 10 |

### Handbook Round 2 requirements → where they are met

| Handbook requirement (Theme 2, Grand Finale) | Where |
|---|---|
| *Single Agent Prototype: build a functional core agent (e.g. Skills Discovery or Learning Pathway) using vibecoding and AI frameworks* | Skills Discovery (core) and Learning Pathway (supporting), both LLM-backed with validators; LangGraph + FastAPI + Pydantic |
| *Full System Showcase: complete multi-agent Career Orchestrator end-to-end via a real-world persona (a woman re-entering the workforce in a tier-2 city)* | Priya demo, Agent activity |
| *Seamless agent collaboration* | Handoff messages, parallel Learning Pathway ∥ Employer Readiness, shared state |
| *Human-in-the-loop safeguards* | Two interrupts + evidence and JD reviews |
| *SAP Learning Hub, student edition integration* | Curated catalog, deep links, milestones, evidence review |
| *Functional prototype leveraging SAP technologies* | SAP UI5 Web Components (live), SAP AI Core / SAP Build Process Automation / HANA Cloud / XSUAA adapters, BTP deployment descriptors |

---

## 6. Acceptance tests

`./scripts/test.sh` runs 54 pytest tests and 5 Playwright journeys (guided demo with the HR and Auditor tasks, staff sign-in, blocked pages, dark mode and Hindi, menu access):
- Every role has its own employer ad; each improved ad and each suggested rewrite scans clean; new barrier types (age, gender or marital preference, physical requirement, walk-in interviews) are found and removed.
- HR can answer conflicting claims and respond to the candidate only after the passport is issued and only with her consent; HR cannot make the passport decision; the auditor alone verifies the log and signs off fairness.
- The fairness twins keep identical scores, the biased control filter is caught, and the candidate's real details are hidden from HR and the auditor.
- Role passwords and access: a candidate token cannot read staff data, HR never receives raw evidence, the auditor never receives personal data, and failed sign-ins lock out.
- Evidence files are real PDFs/XLSX, uploads are validated, and uploaded text feeds Skills Discovery.

- The whole Priya demo runs locally without credentials (`e2e/priya-demo.spec.ts`).
- LLM output is schema-validated and quote-checked; inflated statuses are blocked (fake LLM); the SAP AI Core request shape is tested with mocked HTTP.
- Unsupported claims remain `self_declared`.
- The graph pauses for candidate approval and for final human approval; the passport returns 409 before approval; a reject never yields a passport.
- Career break and protected attributes do not change the scores.
- All seeded JD barriers are identified; the improved JD and the approved rewrite scan clean.
- The pathway has at least one SAP Learning asset and evidence tasks; evidence changes a status only after review.
- The provider is shown; no SAP service claims to be connected without credentials.
- Agent and human events are in the hash-chained, append-only audit log.

---

## 7. Limitations and assumptions

- **Seeded and simulated data**: the persona is fictional; roles, JDs, employer questionnaire, policy documents and candidate feedback are seeded or simulated and labelled on screen. There is no job-site scraping.
- **Deterministic demo mode** uses an auditable rule-based extractor with the same schema and validators. Live LLM quality depends on the configured model.
- **SAP Learning Hub**: links were checked automatically on 2026-09-29 (public landing pages return HTTP 200). *The team must still confirm each asset in its student-edition account* and set `team_verified_on` in `learning_assets.json`. There is no progress API; "started" is self-reported.
- **Evidence upload** accepts PDF, DOCX, PPTX, XLSX, CSV, text, code and PNG/JPG (max 8 MB). Images cannot be read automatically, so the candidate describes them. Scanned PDFs without a text layer produce no text.
- **Checkpoints** use SQLite. On Cloud Foundry, move them to a managed store (e.g. a Postgres LangGraph checkpointer) for durability.
- **XSUAA mode**: the password sign-in is for local demos only. Behind XSUAA, roles come from role collections.
- **Bias audit**: a single-person twin test is not statistical proof. The biased reference filter and group monitoring are labelled synthetic examples.
- **Employers and job ads**: all five employers, their ads, policies and candidate feedback are fictional seed data.
- **Employer Readiness** flags and classifies evidence. It does not certify an employer as inclusive.
- **Persona details**: the pitch deck (slide 7) said "29" and a "three-year" break. The prototype follows the master prompt (31, four years). The corrected deck uses the same values.

## 8. Repository map

```
backend/app/        FastAPI app, LangGraph workflow, agents, providers (llm, repository, identity, learning catalog, review workflow)
backend/app/data/   Seed data: persona, taxonomy, roles, jobs + employer, SAP learning catalog
backend/scripts/    generate_evidence.py builds the sample PDFs and Excel tracker
backend/tests/      pytest (agents, workflow/API, providers, access control)
frontend/src/       React + SAP UI5 Web Components (guided journey, role bar, English + Hindi, dark mode, and a practice sandbox)
frontend/e2e/       Playwright journeys
frontend/src/locales/  en.json and hi.json (edit English in frontend/scripts/build-en.py)
sap-build/          SAP Build Process Automation / Build Apps / Work Zone artifacts and guide
approuter/, mta.yaml, manifest.yml, xs-security.json, deploy/hana/   SAP BTP deployment
DEMO_SCRIPT.md, JUDGE_QA.md, PRESENTATION_NOTES.md
```
