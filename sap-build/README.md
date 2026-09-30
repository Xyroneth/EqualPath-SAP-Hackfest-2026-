# SAP Build in EQUALPATH

EQUALPATH uses SAP Build in four places. The table says plainly what runs today and what still needs a BTP subaccount.

| SAP Build product | What it does in EQUALPATH | Status in this repo |
|---|---|---|
| **SAP Build Process Automation** | Runs the final human review (checkpoint 2) as an approval process. The reviewer decides in the SAP Build inbox, and an action sends the decision back to EQUALPATH, which resumes the paused LangGraph run. | Adapter implemented (`backend/app/providers/review_workflow.py`), plus the callback endpoint, action OpenAPI spec, trigger payload and destination. Goes live when the `SBPA_*` variables are set. Without them the local review queue is used, and the UI says so. |
| **SAP Build Apps** | Optional counsellor mobile app for the review queue and milestone-evidence reviews. It consumes the EQUALPATH REST API. | Deployment-ready: the API publishes OpenAPI at `/openapi.json`. Build steps below. |
| **SAP Build Work Zone** | Launchpad tile so counsellors and HR reviewers open EQUALPATH next to their other SAP apps. | Deployment-ready: `work-zone/tile.json` and the approuter in `/approuter`. |
| **SAP Build Code / SAP Business Application Studio** | Development environment. The repo opens in a BAS Full-Stack dev space and builds with the Cloud MTA Build Tool (`mbt build`). | Ready: `mta.yaml`, `xs-security.json`, `approuter/`. |

The SAP Learning catalog also recommends SAP Build learning assets. For example, Priya's *Enterprise application context* milestone links to **Develop and automate with SAP Build** and asks her to write test scenarios for an SAP Build Process Automation approval flow.

---

## 1. SAP Build Process Automation: "EQUALPATH Final Review" process

**Flow:** EQUALPATH `review_routing` node → *API trigger* → **Approval form** (counsellor / HR reviewer) → *Action* `submitReviewDecision` → EQUALPATH `/api/integrations/sap-build/review-decision` → LangGraph resumes → passport issued (or loops back for evidence, or ends on reject).

### Build steps (about 30 minutes in a trial or student subaccount)

1. **Subscribe** to SAP Build Process Automation and assign yourself `ProcessAutomationAdmin` and `ProcessAutomationDeveloper`. A starter tutorial is linked in the catalog: *Build Your First Business Process with SAP Build Process Automation*.
2. **Destination:** import `destinations/EQUALPATH_API.properties` in the BTP cockpit (Connectivity → Destinations). Set the URL to your EQUALPATH app and the secret header to the value of `SBPA_CALLBACK_SECRET`. In the SAP Build Control Tower, add the destination under *Backend Configuration → Destinations*.
3. **Actions project:** Lobby → Create → *Actions* → upload `process-automation/equalpath-actions-openapi.json` → add action **submitReviewDecision** → Release → Publish.
4. **Process project:** Lobby → Create → *Business Process* → name it `EQUALPATH Final Review`.
   - **Trigger:** *API trigger*. Process inputs, all of type string except `employerFlags` (number): `runId`, `candidateRef`, `roleTitle`, `proposedOutcomes`, `gapSummary`, `employerFlags`, `biasAuditResult`, `reviewUrl`.
   - **Approval form** "Final review":
     - Read-only fields bound to the inputs above. Show `proposedOutcomes`, `gapSummary`, `employerFlags` and `biasAuditResult`.
     - Dropdown `decision` with the values approve / reject / request_evidence.
     - Text area `reason` (required).
     - Recipients: the counsellor / HR reviewer group.
   - **Action step:** `submitReviewDecision` using destination `EQUALPATH_API`. Map `runId` ← input `runId`, `decision` ← form `decision`, `reason` ← form `reason`, `reviewer` ← the task *Processor* value, and `reviewerRole` = `counsellor`.
   - Release, then deploy. Copy the process **definition ID** (Monitor → Process and Workflow Definitions).
5. **Service key:** create an instance of `process-automation-service` (plan `standard`) and a service key.
6. **EQUALPATH env:**
   ```
   SBPA_API_URL=<endpoints.api from the service key>      # e.g. https://spa-api-gateway-bpi-us-prod.cfapps.us10.hana.ondemand.com
   SBPA_TOKEN_URL=<uaa.url>/oauth/token
   SBPA_CLIENT_ID=<uaa.clientid>
   SBPA_CLIENT_SECRET=<uaa.clientsecret>
   SBPA_DEFINITION_ID=<definition id from step 4>
   SBPA_CALLBACK_SECRET=<random string, same as in the destination>
   ```
7. Restart EQUALPATH. The **Architecture** screen now shows *SAP Build Process Automation: Connected*. Every review packet starts a process instance with `POST {SBPA_API_URL}/workflow/rest/v1/workflow-instances`. The Human Review screen shows *Routed via SAP Build Process Automation*.

**Data minimisation:** the process context holds only IDs, statuses and summaries (see `trigger-sample.json`). It never contains the candidate's name, contact details or accessibility notes.

**Test the callback without SAP Build:**
```bash
curl -X POST http://localhost:8000/api/integrations/sap-build/review-decision \
  -H "Content-Type: application/json" -H "X-EqualPath-Callback-Secret: $SBPA_CALLBACK_SECRET" \
  -d '{"runId":"<run id waiting at final review>","decision":"approve","reviewer":"A. Counsellor"}'
```

## 2. SAP Build Apps: counsellor review app (optional)

1. In SAP Build Apps, create a web or mobile app named `EQUALPATH Reviewer`.
2. Data → *REST API integration* → *BTP destination* `EQUALPATH_API` (set `AppgyverEnabled=true` on the destination).
3. Add resources:
   - `GET /api/reviews`: the list of open final reviews and evidence reviews.
   - `POST /api/evidence-submissions/{id}/decision` with body `{decision, reason}`.
   - `POST /api/runs/{runId}/final-review` with body `{decision, reason}`.
   - Sign in first with `POST /api/auth/login` (body `{"role":"counsellor","password":"..."}`) and send the returned token as `Authorization: Bearer <token>`. With XSUAA, forward the user token instead.
4. Build a list page from `GET /api/reviews` and a detail page with Accept / Reject buttons. Make the reason input required.

## 3. SAP Build Work Zone tile

Create a *URL* app in Work Zone Content Manager using `work-zone/tile.json`. Point it at the approuter URL so XSUAA single sign-on applies, then add it to a group and a role.

## 4. Open in SAP Business Application Studio (SAP Build Code)

```bash
git clone <repo> && cd equalpath
npm ci --prefix frontend && python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt
mbt build && cf deploy mta_archives/equalpath_1.0.0.mtar
```
