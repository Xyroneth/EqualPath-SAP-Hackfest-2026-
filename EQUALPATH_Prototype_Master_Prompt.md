# EQUALPATH Functional Prototype - Master Vibecoding Prompt

Copy the prompt below into Cursor, Replit Agent, Bolt, Lovable, Windsurf, Claude Code, or another full-stack coding agent. The agent must generate working code, not only a design or product specification.

---

## MASTER PROMPT

You are a senior full-stack engineer, AI systems architect, UX designer, and responsible-AI engineer. Build a complete, locally runnable hackathon prototype named **EQUALPATH**.

### 1. Product purpose

EQUALPATH is a skills-first, multi-agent career orchestrator for people overlooked by conventional hiring, especially women returning after career breaks, persons with disabilities, rural and tier-2-city candidates, workers without formal credentials, and people who need reskilling.

The system must convert a candidate's projects, work samples, certifications, learning records, and experience into evidence-backed capabilities. It must identify realistic roles, explain missing capability or evidence gaps, create a short learning pathway, check work-condition compatibility, inspect the employer and job description for avoidable barriers, run fairness checks, pause for human approval, and generate a transparent **Mutual Readiness Passport**.

This prototype is for the SAP Hackfest 2026 final round. The prototype must satisfy these non-negotiable requirements:

1. Implement at least one genuinely functional core agent. Make the **Skills Discovery Agent** the primary functional agent. It must call an LLM, return validated structured output, quote the evidence supporting every extracted skill, and never mark an unsupported resume claim as verified.
2. Also implement a functional **Learning Pathway Agent** that converts role gaps into small learning and evidence-building milestones.
3. Demonstrate a complete multi-agent Career Orchestrator from candidate intake to final passport.
4. Use a realistic persona: a woman re-entering the workforce in a tier-2 Indian city.
5. Show visible collaboration among specialized agents.
6. Include a genuine human-in-the-loop pause. The final passport must not be issued until a human reviews and approves or edits the recommendation.
7. Integrate SAP Learning Hub, student edition honestly. Use a curated catalog of verified SAP learning assets and deep links. Do not invent a private API or claim automatic completion tracking unless credentials and a documented API are available.
8. Leverage SAP technology through an adapter-based architecture. Prefer SAP AI Core generative AI hub when credentials exist, prepare the application for SAP BTP Cloud Foundry deployment, and provide an optional SAP HANA Cloud persistence adapter. The application must still run locally without SAP credentials.
9. Clearly label live integrations, locally seeded data, and simulated data. Never show a simulated API call as a successful live SAP integration.

### 2. Recommended technical stack

Use the following stack unless the existing repository already has an equivalent:

- Frontend: React, TypeScript, Vite, and SAP UI5 Web Components for a clean Fiori-inspired interface.
- Backend: Python FastAPI with Pydantic schemas.
- Agent orchestration: LangGraph with an explicit shared state, checkpoints, retries, and a human interrupt node.
- AI provider layer: `SAPAIProvider` for SAP AI Core generative AI hub, plus an OpenAI-compatible provider and a deterministic demo provider. Choose the provider using environment variables.
- Local persistence: SQLite through a repository interface.
- Enterprise persistence adapter: SAP HANA Cloud when credentials exist.
- Deployment: Dockerfile plus SAP BTP Cloud Foundry `manifest.yml`. Add documented placeholders for XSUAA or SAP Cloud Identity Services, but do not block the local demo on authentication setup.
- Testing: Pytest for backend logic and Playwright for the critical user journey.

The project must start with one simple command such as `docker compose up` and also support separate frontend and backend development commands.

### 3. Seed persona and demo data

Preload the following fictional persona, while allowing manual editing:

- Name: Priya Sharma
- Age: 31
- Location: Lucknow, Uttar Pradesh
- Languages: Hindi and English
- Background: Former junior software tester with three years of experience
- Career break: Four years for caregiving
- Existing evidence: Resume, sample test cases, bug reports, a small Python practice repository, an Excel-based defect tracker, and a course certificate
- Goal: Return to a stable technology role
- Work conditions: Prefers remote or hybrid work, cannot relocate immediately, needs predictable interview scheduling
- Target role for the demo: QA Automation Associate supporting enterprise applications
- Pain points: Her experience looks outdated, her career break is penalized, employers cannot compare her informal learning, and many job descriptions do not clearly state work mode or return-to-work support
- Behaviour: Learns in short evening sessions, prefers bilingual explanations, and wants to approve anything shared with employers

Create two seeded job descriptions:

1. A problematic job description containing an unnecessary degree filter, an uninterrupted-experience requirement, vague wording such as "fast-paced culture fit," and no clear work-mode or accommodation information.
2. An improved version containing only role-essential requirements, a clear hybrid policy, an accessible interview contact, and fair treatment of career breaks.

### 4. Multi-agent architecture

Implement the following nodes in one LangGraph workflow. Display every node's status, inputs, outputs, duration, confidence, and audit event in the UI.

#### A. Skills Discovery Agent - functional core agent

Inputs:

- Resume/profile text
- Project descriptions
- Certificates and learning records
- Work-sample text or metadata
- Candidate corrections

Output one structured record per skill:

```json
{
  "skill_name": "Manual software testing",
  "normalized_skill": "software_testing.manual",
  "category": "technical",
  "proficiency": "intermediate",
  "evidence_type": "work_sample",
  "evidence_quote": "Created and executed 42 regression test cases...",
  "source_id": "test-cases.pdf",
  "recency": "2026-08",
  "confidence": 0.87,
  "verification_status": "source_supported",
  "adjacent_skills": ["test automation", "quality assurance"]
}
```

Use these verification statuses:

- `self_declared`: mentioned without supporting evidence
- `source_supported`: supported by a submitted document or work sample
- `assessed`: demonstrated through an in-app task or assessment
- `externally_verified`: confirmed through an authorized external source

Rules:

- Preserve a short evidence quote and source reference for every extracted capability.
- Never upgrade `self_declared` to verified merely because the LLM sounds confident.
- Separate confidence in extraction from verification status.
- Let Priya accept, edit, remove, or add evidence before the workflow continues.
- Record every correction in the audit log.

#### B. Market Intelligence Agent

Use a small, clearly labelled local role catalog for the prototype. Match Priya to roles using required skills, evidence coverage, location/work-mode fit, and realistic entry requirements. Do not scrape job websites during the demo.

Return the top three roles with an explainable component breakdown. Protected attributes must contribute zero points to the role ranking. Career-break duration must not reduce the score. For the main demo, recommend QA Automation Associate and explain why.

#### C. Learning Pathway Agent - functional supporting agent

Compare Priya's capability profile with the selected role's capability map. Classify each requirement as:

- `verified`: required proficiency is met and supported by evidence
- `developing`: an adjacent skill or lower proficiency exists
- `missing`: no adequate capability or evidence exists

For each developing or missing capability, create the smallest useful milestone. Every milestone must include:

- Capability gap
- Learning asset
- Estimated effort
- Practical task
- Evidence the candidate must submit
- Completion rule
- Why the milestone matters for the target role

Example:

```json
{
  "gap": "Browser test automation",
  "status": "developing",
  "learning_asset": "Verified catalog entry",
  "estimated_hours": 6,
  "practice_task": "Automate login and form validation for the provided sample application",
  "required_evidence": ["test script", "execution screenshot", "short reflection"],
  "completion_rule": "Human reviewer accepts the submitted evidence"
}
```

#### D. Inclusive Matching Agent

Calculate a transparent mutual-fit assessment using:

- Capability coverage
- Strength of evidence
- Work-mode, schedule, language, location, and accessibility fit
- Feasibility of closing the remaining gaps

Show the component values instead of one unexplained score. Do not use gender, age, disability, college prestige, or career-break duration as negative ranking features. Accessibility requirements are constraints controlled by the candidate, not penalties.

#### E. Employer Readiness Agent

Scan the job description and employer questionnaire for:

- Unnecessary degree or institution requirements
- Career-gap or uninterrupted-experience requirements
- Exclusionary or vague wording
- Unclear work mode, schedule, or location expectations
- Missing accessible interview information
- Missing accommodation request process
- Missing return-to-work support

For employer claims, show one of these evidence levels:

- `declared`: employer answered the questionnaire
- `document_verified`: a policy or job document supports the claim
- `experience_validated`: repeated, consented candidate feedback supports the claim
- `conflicting_evidence`: statements and evidence disagree

Candidate feedback is a signal, not verified fact. Conflicts must trigger human review. Produce a suggested rewrite of the problematic job description, but require an HR reviewer to approve it.

#### F. Bias Audit Agent

For the single-person demonstration, do not pretend that one record proves statistical fairness. Implement two defensible checks:

1. Counterfactual test: rerun matching with equivalent profiles where only name, gender marker, age, location wording, or career-break wording changes. Flag material ranking changes.
2. Feature-use audit: confirm that protected attributes and career-break duration do not contribute negatively to the match score.

Also include a clearly labelled prototype dashboard showing how production monitoring would compare recommendation, approval, and rejection rates across groups using aggregated and privacy-protected data.

#### G. Human-in-the-Loop safeguard

Pause the graph twice:

1. Candidate review: Priya confirms extracted skills, evidence, work preferences, and what may be shared.
2. Final review: a counsellor or HR reviewer can approve, edit, reject, or request more evidence. Require a reason for every override.

Do not generate a final passport until the final review is approved. Persist the checkpoint so the workflow can resume after human action.

### 5. Mutual Readiness Passport

Generate a printable and downloadable final passport containing:

1. Capability Evidence
2. Role Gap Map
3. Work-Condition Fit
4. Employer Readiness
5. Bias Audit Result
6. Human Review Decision and reason
7. Next action and responsible party

Allow only these final outcomes:

- Ready to Proceed
- Ready with Learning Milestone
- Employer Action Required
- Human Review Required

Show source references and evidence status beside every important claim. The passport is a decision-support document, not a job guarantee or certification.

### 6. SAP Learning Hub, student edition integration

Create a `learning_assets.json` or database table with manually verified assets from SAP Learning Hub, student edition. Each record must contain title, capability tags, level, estimated effort, public landing-page URL, whether a student-edition login is required, and the date the team verified the link.

Seed the catalog with relevant assets that the team has personally checked in its student-edition account. The handbook suggests learning areas such as SAP BTP, SAP Build, SAP Business Application Studio, SAP HANA Cloud, SAP Analytics Cloud, and SAP Generative AI Hub.

In the product:

- Recommend a relevant SAP learning asset when it supports a genuine gap.
- Provide an `Open in SAP Learning` button.
- Let Priya mark the activity as started.
- Require her to upload a project, screenshot, assessment result, or reflection as evidence.
- Route the evidence to a human reviewer before changing the capability status.

Do not scrape SAP Learning Hub, request the user's SAP password, claim access to a private progress API, or claim automatic course completion synchronization unless a documented authorized integration is actually configured.

### 7. SAP technology integration

Implement clean provider interfaces:

- `LLMProvider`: SAP AI Core generative AI hub, OpenAI-compatible fallback, deterministic demo provider
- `CandidateRepository`: SQLite and optional SAP HANA Cloud
- `LearningCatalogProvider`: curated local SAP Learning catalog now, replaceable by an authorized connector later
- `IdentityProvider`: local demo roles now, XSUAA or SAP Cloud Identity Services configuration for BTP deployment

Add:

- `manifest.yml` for SAP BTP Cloud Foundry
- Optional `mta.yaml` if appropriate
- Environment-variable templates
- A deployment section in the README
- A visible About/Architecture page that states which SAP services are currently connected and which are deployment-ready adapters

When SAP AI Core credentials are configured, use its generative AI hub for the Skills Discovery and Learning Pathway prompts. Before sending a prompt, remove direct identifiers and unnecessary personal data. When credentials are absent, fall back gracefully and show the active provider in the demo UI.

### 8. Privacy, security, and responsible AI

Implement the following prototype safeguards:

- Explicit consent before processing or sharing candidate data
- Data minimization
- PII redaction before external LLM calls
- Environment variables for secrets
- HTTPS-ready deployment configuration
- Role-based demo access for Candidate, Counsellor, HR Reviewer, and Auditor
- Separate handling of sensitive accessibility information
- No medical diagnosis visible to an employer; share only candidate-approved work accommodations
- Immutable audit events for agent executions, edits, approvals, and overrides
- Candidate controls to correct, export, and delete their demo data
- No use of candidate or employer data for model training
- Clear AI limitations and confidence labels

### 9. Required user interface

Build these connected screens:

1. Landing page with one-sentence product explanation and `Start Priya Demo`
2. Candidate consent and profile intake
3. Evidence upload and sample-data loader
4. Skills Discovery review with evidence quotes and verification status
5. Role recommendations with transparent component breakdown
6. Role Gap Map
7. Learning Pathway with SAP Learning links and evidence submission
8. Employer Readiness scan with flagged text, evidence levels, and suggested rewrites
9. Bias Audit panel
10. Human Review queue with approve, edit, reject, and request-evidence actions
11. Multi-agent run timeline showing collaboration and audit events
12. Mutual Readiness Passport with print/download option
13. Architecture and data-flow page showing SAP and local-demo components

Use the EQUALPATH visual system:

- Navy `#0A1F44`
- SAP blue `#0A6ED1`
- Teal `#008A8A`
- Light background `#F4F8FC`
- Dark text `#1F2937`
- Amber `#F59E0B`
- Green `#188038`

Use accessible contrast, keyboard navigation, visible focus states, clear labels, and responsive layouts. Avoid robot illustrations, decorative dashboards, fake statistics, and black-box percentage scores.

### 10. Demo storyline

Create a `DEMO_SCRIPT.md` and make the seeded demo follow this flow in about four minutes:

1. Load Priya's profile and evidence.
2. Run Skills Discovery. Show evidence quotes and one self-declared skill that remains unverified.
3. Pause for Priya to correct and approve the profile.
4. Show three role options and select QA Automation Associate.
5. Show verified, developing, and missing capabilities.
6. Generate a short pathway and open one SAP Learning Hub student-edition asset.
7. Scan the problematic job description. Flag the uninterrupted-experience condition and unclear hybrid policy.
8. Run the bias counterfactual and feature-use checks.
9. Pause for human approval. Edit one recommendation and record the reason.
10. Generate the Mutual Readiness Passport with the result `Ready with Learning Milestone` and `Employer Action Required` clearly explained.

### 11. Evaluation traceability

Add a table to the README mapping the final-round evaluation areas to working evidence in the prototype:

- Persona Development: Priya's demographics, context, behaviours, goals, and pain points
- Problem Statement Clarity: the confidence gap affecting non-traditional candidates and employers
- User Needs Identification: evidence visibility, fair consideration, flexible work information, targeted learning, consent, and explainability
- Solution Alignment: each user need mapped to an agent, UI screen, and demo step
- Functional Core Agent: real Skills Discovery execution with validated output and evidence provenance
- Full-System Showcase: visible end-to-end LangGraph run
- Human Safeguards: two interrupts, corrections, approval, and override reasons
- SAP Learning Hub Integration: verified learning catalog, deep link, milestone, and evidence submission
- SAP Technology: active provider and deployment architecture shown honestly

### 12. Acceptance tests

The build is complete only when all of these pass:

- A fresh user can run the entire Priya demo locally without external credentials.
- With an LLM key configured, the Skills Discovery Agent returns schema-valid output with source quotes.
- Unsupported claims remain `self_declared`.
- The graph pauses for candidate approval and final human approval.
- The final passport cannot be produced before approval.
- Career-break duration and protected attributes do not reduce the matching result.
- The Employer Readiness Agent identifies all seeded barriers.
- The Learning Pathway includes at least one verified SAP Learning asset and one evidence-building task.
- The interface shows whether the AI provider is SAP AI Core, another configured provider, or deterministic demo mode.
- All agent actions and human changes appear in the audit log.
- The demo completes in four minutes without broken links or manual database edits.
- Unit and end-to-end tests pass.

### 13. Required deliverables

Generate:

- Complete source code
- `.env.example` with no secrets
- Seed data for Priya, role maps, jobs, and learning assets
- Docker configuration
- SAP BTP deployment configuration
- Tests
- `README.md` with setup, architecture, privacy, SAP integration status, limitations, and evaluation traceability
- `DEMO_SCRIPT.md`
- `JUDGE_QA.md` containing concise answers about skill-gap detection, evidence verification, employer-claim verification, bias testing, data protection, encryption, and why human approval is required

Build the application now. Do not stop at wireframes, pseudocode, or an implementation plan. Make reasonable assumptions, document them, and prioritize a reliable end-to-end demo over unnecessary breadth.

---

## Required presentation corrections before the final pitch

1. **Slide 5:** Replace “Seven Agents” with **“Six Specialized AI Agents and One Human Approval Layer.”** Human-in-the-loop is a safeguard and decision owner, not another autonomous AI agent.
2. **Slide 4:** Replace the repeated “Verified evidence” under Employer Readiness with **“Declared / document-verified / experience-validated.”** The candidate's statement alone cannot verify an employer claim.
3. **Slide 6:** State that the Employer Readiness Agent **flags and classifies evidence**. It does not independently certify that an employer is inclusive.
4. **Slide 7:** Add Priya's tier-2-city context, goal, behaviours, constraints, and pain points so the persona satisfies the evaluation rubric. Show the two human pauses in her journey.
5. **Slide 8:** Split SAP items into **“Used in the prototype”** and **“Enterprise roadmap.”** Do not imply that SuccessFactors, Joule, People Intelligence, or Data Cloud are integrated unless the demo actually calls them.
6. **Slide 8:** Describe SAP Learning Hub integration as a verified learning catalog, deep links, milestones, and evidence upload. Do not claim an undocumented progress-sync API.
7. **Slide 9:** Change future tense such as “we will prove” to present tense only after it works: **“The live prototype demonstrates…”** Name the functional core agent, orchestration framework, human interrupt, active SAP service, and final passport.
8. **Slide 9:** Add one architecture diagram or screenshot that proves the prototype is functional. Business-model content can move to a backup slide if necessary.
9. **Timing:** The current notes use almost all ten minutes before a demo. Target roughly **five and a half to six minutes of slides and four to four and a half minutes of live demonstration**. Keep a prerecorded fallback video or screenshots in case connectivity fails.
10. **Claims:** Label seeded job data, simulated employer data, and prototype bias tests honestly. Do not describe a single-person counterfactual test as statistical proof of fairness.

