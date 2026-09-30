# Judge Q&A: concise answers

**How do you detect skill gaps?**
Each target role has a capability map listing a capability, a required level and whether it is essential or preferred. The Learning Pathway Agent compares Priya's *approved* profile against it with deterministic, auditable rules. A capability is **verified** when the level is met *and* it is supported by evidence. It is **developing** when it is only self-declared, below the required level, or an adjacent skill is present. It is **missing** when there is no capability or evidence. Only developing or missing essentials become milestones.

**How do you verify evidence? Can the LLM hallucinate a skill?**
The LLM may *propose* a skill, but code decides whether it stands. (1) The output must match a Pydantic schema. (2) The quote must appear verbatim in the cited source, otherwise the record is rejected and listed. (3) The verification status is computed from the source type: a resume or candidate note gives `self_declared`, a work sample, project or certificate gives `source_supported`. (4) `assessed` is only set after a human accepts milestone evidence, and `externally_verified` needs an authorised external source (none is connected). The LLM's own claimed status is ignored, and any attempted upgrade is logged. Extraction confidence is shown separately from verification.

**How do you verify employer claims?**
We never take the candidate's word, or the employer's, as proof. Each questionnaire answer is **declared**. It becomes **document-verified** only if a job description or policy document supports it, and **experience-validated** only with three or more *consented*, consistent candidate reports. If statements and evidence disagree, it becomes **conflicting evidence** and must go to human review. For example, "career breaks are evaluated fairly" conflicts with "uninterrupted experience required". The agent flags and classifies evidence; it does not certify that an employer is inclusive.

**How do you test for bias?**
Four checks. (1) **Twin test**: we rerun ranking and matching on 9 twins that each change one personal detail (a man's name, a name from another community, age 24 or 45, no break or an 8-year break, a disclosed disability, an IIT degree, a differently written home town). We show the real scores before and after and flag any change in ranking or score (threshold 0.01). Where a twin changes the documents' wording, skill extraction is re-run too. (2) **Control test**: a test that always passes proves nothing, so a switch at the top of the page runs the same twins through a deliberately biased, simulated résumé filter (career-gap penalty, age cut-off, college bonus). The test catches it on 4 of 9 twins and names the rule behind each difference, so we know it can detect bias. A *Try your own twin* box lets anyone change a detail live (age, career break, college, name, gender, disability, home town) and see both systems side by side. (3) **Feature-use audit**: matching receives only an allow-list of features (languages, city, work modes, relocation, learning hours, total relevant experience, schedule needs). We assert protected attributes are absent, and perturbing them yields exactly 0 change. (4) The **auditor** reviews the result and signs it off or raises a concern that the counsellor and the passport show. One person is not statistical proof. For production we show a labelled mock-up of group monitoring: approval-rate impact ratios, four-fifths rule, small-cell suppression, aggregated data only.

**What do the HR Reviewer and the Auditor actually do?**
The HR Reviewer speaks for the employer: they approve or edit the fairer job ad, answer employer claims that conflict with the evidence ("fix the ad" or "correct our statement"), and respond to the candidate by inviting her to interview with the adjustments she asked for, keeping her in the talent pool or declining, always with a reason she sees. They never approve her passport, because that would be a conflict of interest. The Auditor re-verifies the hash-chained log, signs off the fairness check, sees who opened the candidate's documents and exports a CSV report. They never see her personal details. Every one of these actions is written to the audit log.

**Doesn't total experience penalise career breaks?**
No. We count *total* relevant experience, not continuity or recency, and career-break months are not a feature. The test suite asserts that a break of 0, 52 or 180 months gives identical scores.

**How is personal data protected?**
Explicit consent before processing, and sharing is a separate opt-in. Direct identifiers (name, e-mail, phone, profile URLs, Aadhaar/PAN-like numbers, PIN codes, demographic phrases) are **redacted before any LLM call**, and SAP AI Core's Data Privacy Integration masking can be added. Data minimisation applies throughout: matching sees an allow-list, and the SAP Build process gets IDs and summaries only. Accessibility or health notes are stored separately, never sent to an LLM, and never shown to employers; employers only see candidate-approved work accommodations. Candidates can export and delete their data. No data is used for model training.

**Encryption?**
In transit: HTTPS via the SAP BTP Cloud Foundry router and approuter, and TLS to SAP HANA Cloud (`encrypt=True`, certificate validation). At rest: sensitive notes are field-level encrypted with Fernet (AES-128-CBC + HMAC-SHA256) using a key from `DATA_ENCRYPTION_KEY`, and SAP HANA Cloud encrypts data volumes at rest. Secrets live only in environment variables or BTP service bindings.

**Can the audit log be tampered with?**
It is append-only: SQLite triggers abort UPDATE and DELETE, and on HANA the app user has INSERT/SELECT grants only. Each event is SHA-256 chained to the previous one, and the chain is verified on every read. Events contain IDs and summaries, not raw personal data, so they survive a candidate's deletion request.

**Why is human approval required?**
Career and hiring decisions are high-stakes and legally sensitive. Models can be wrong, and evidence can be incomplete or conflicting. So no agent decides alone. Priya approves what is said about her and what is shared (pause 1). A counsellor or HR reviewer owns the recommendation (pause 2) and can approve, edit, reject or request evidence, with a required reason for every override. The passport API refuses (409) until that approval exists. Milestone evidence and JD rewrites also need a human.

**What is actually SAP in this prototype?**
- *Used now:* SAP UI5 Web Components (the entire UI), and a curated SAP Learning Hub, student edition catalog with deep links, milestones and reviewed evidence.
- *Implemented adapters, live when credentials are set:* SAP AI Core generative AI hub (orchestration and foundation modes, unit-tested), SAP Build Process Automation (final-review approval process with callback), SAP HANA Cloud repository, and XSUAA.
- *Deployment:* SAP BTP Cloud Foundry `manifest.yml` / `mta.yaml` with approuter.
- *Roadmap only:* SuccessFactors, Talent Intelligence Hub, Joule and Business Data Cloud.
The Architecture screen shows exactly which are connected.

**Why multiple agents instead of one prompt?**
Each decision needs a different kind of evidence and a different owner: candidate evidence, market roles, learning, employer barriers and fairness. Narrow agents are individually testable and explainable, can run in parallel (Learning Pathway ∥ Employer Readiness), and hand off through shared state that humans can inspect and correct.

**What happens with real (non-seeded) data?**
Priya's profile and documents are editable, and new evidence can be pasted or uploaded as text. The Skills Discovery Agent runs on whatever is submitted, and the standalone endpoint `POST /api/agents/skills-discovery` accepts any documents. The role catalog and JDs are seeded for the demo; production would connect to SuccessFactors Recruiting (roadmap).
