import { expect, test, type Page } from '@playwright/test';

const PASSWORDS = { counsellor: 'Counsel@2026', hr_reviewer: 'HRreview@2026', auditor: 'Audit@2026' };
const shots = process.env.EQUALPATH_SHOTS;
const snap = async (page: Page, name: string) => {
  if (shots) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(700);
    await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
  }
};

async function signIn(page: Page, role: keyof typeof PASSWORDS) {
  await page.getByTestId(`role-${role}`).click();
  await page.getByTestId('login-password').locator('input').fill(PASSWORDS[role]);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('rolebar')).toHaveAttribute('data-role', role);
}

/** Start the demo as Priya and run the agents up to the first pause (skills review). */
async function startAndAnalyse(page: Page) {
  await page.goto('/');
  await page.getByTestId('start-demo').click();
  await expect(page).toHaveURL(/\/profile/);
  await page.getByTestId('consent-process').click();
  await page.getByTestId('consent-share').click();
  await page.getByTestId('save-profile').click();
  await expect(page).toHaveURL(/\/evidence/);
  await page.getByTestId('run-orchestrator').click();
  await expect(page).toHaveURL(/\/skills/, { timeout: 45_000 }); // automatic jump, no button pressed
}

test('guided journey: profile -> evidence -> agents -> skills -> role -> pages -> counsellor decision -> passport', async ({ page, context }) => {
  await page.goto('/');
  await expect(page.getByTestId('provider-tag')).toContainText('AI:');
  await snap(page, '01-home');
  await page.getByTestId('start-demo').click();

  // ---- Profile: capitalised options, info button, consent required
  await expect(page).toHaveURL(/\/profile/);
  await expect(page.getByTestId('mode-remote')).toHaveText('Remote');
  await expect(page.getByTestId('mode-hybrid')).toHaveText('Hybrid');
  await expect(page.getByTestId('mode-onsite')).toHaveText('Onsite');
  await expect(page.getByTestId('gender-value')).toHaveText('Female');
  await page.getByRole('button', { name: 'More information' }).nth(1).click(); // accommodations (i)
  await expect(page.getByText('never a diagnosis')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByTestId('save-profile').click();
  await expect(page.getByText('Please allow processing of your profile to continue.')).toBeVisible();
  await page.getByTestId('consent-process').click();
  await page.getByTestId('consent-share').click();
  await page.getByTestId('consent-acc').click();
  await snap(page, '02-profile');
  await page.getByTestId('save-profile').click();

  // ---- Evidence: real files, open in new tabs, add more
  await expect(page).toHaveURL(/\/evidence/);
  await expect(page.getByTestId('doc-grid').locator('article')).toHaveCount(6);
  // (headless Chromium has no PDF viewer and downloads instead, so check the link the new tab is sent to)
  const [pdfTab, linkRes] = await Promise.all([context.waitForEvent('page'), page.waitForResponse(/view-link/), page.getByTestId('view-resume.pdf').click()]);
  const pdfRes = await page.request.get((await linkRes.json()).url);
  expect(pdfRes.headers()['content-type']).toBe('application/pdf');
  expect(pdfRes.headers()['content-disposition']).toContain('inline');
  expect((await pdfRes.body()).subarray(0, 5).toString()).toBe('%PDF-');
  await pdfTab.close();
  const [xlsTab] = await Promise.all([context.waitForEvent('page'), page.getByTestId('view-defect-tracker.xlsx').click()]);
  await xlsTab.waitForURL(/\/api\/view\//);
  await expect(xlsTab.getByText('DEF-1001')).toBeVisible(); // the Defects sheet opens first
  await xlsTab.getByText('Dashboard', { exact: true }).click();
  await expect(xlsTab.getByText('Open defects by severity')).toBeVisible();
  await expect(xlsTab.locator('svg.chart').first()).toBeVisible();
  await xlsTab.close();
  await page.getByTestId('file-input').setInputFiles({ name: 'api-notes.md', mimeType: 'text/markdown', buffer: Buffer.from('Wrote 12 API tests with Postman and checked every status code and JSON response for the orders service.') });
  await page.getByTestId('add-evidence').click();
  await expect(page.getByTestId('doc-grid').locator('article')).toHaveCount(7);
  await snap(page, '03-evidence');
  await page.getByTestId('run-orchestrator').click();

  // ---- Agents work, then the app moves on by itself
  await expect(page).toHaveURL(/\/working/);
  await snap(page, '04-working');
  await expect(page).toHaveURL(/\/skills/, { timeout: 45_000 });
  await expect(page.getByTestId('self-declared-note')).toContainText('Browser test automation');
  await expect(page.getByTestId('skill-test_automation.browser')).toContainText('Claimed');
  await expect(page.getByTestId('skill-api_testing')).toContainText('Backed by documents'); // from the file added above
  await expect(page.getByTestId('skill-software_testing.manual')).toContainText('Created and executed 42 regression test cases');
  await snap(page, '05-skills');
  await page.getByTestId('approve-profile').click();
  await expect(page).toHaveURL(/\/roles/, { timeout: 45_000 });
  await expect(page.getByTestId('role-qa-automation-associate')).toContainText('Best fit');
  await snap(page, '06-roles');
  await page.getByTestId('select-qa-automation-associate').click();
  await expect(page).toHaveURL(/\/gaps/, { timeout: 45_000 });

  // ---- Follow the "Next" buttons instead of hunting through the menu
  await expect(page.getByTestId('gap-enterprise_apps.sap_context')).toBeVisible();
  await snap(page, '07-gaps');
  await page.getByTestId('step-next').click();
  await expect(page).toHaveURL(/\/learning/);
  await expect(page.locator('a', { hasText: 'Open in SAP Learning' }).first()).toHaveAttribute('href', /learning\.sap\.com|developers\.sap\.com/);
  await snap(page, '08-learning');
  await page.getByTestId('step-next').click();
  await expect(page).toHaveURL(/\/employer/);
  await expect(page.getByTestId('cat-career_gap_requirement')).toHaveClass(/bad/);
  await expect(page.getByTestId('cat-unclear_work_conditions')).toHaveClass(/bad/);
  await expect(page.getByTestId('claim-career_breaks')).toContainText('Conflicting');
  await expect(page.getByTestId('employer-verdict')).toContainText('Not ready yet');
  await expect(page.getByTestId('ad-original').locator('.ad-mark.high').first()).toBeVisible(); // barriers highlighted in the ad itself
  await expect(page.getByTestId('employer-asks')).toContainText('top-tier institution');
  await page.getByTestId('tab-rewrite').click();
  await expect(page.getByTestId('ad-rewrite').locator('.ad-mark.new').first()).toBeVisible(); // changed lines marked
  await page.getByTestId('tab-improved').click();
  await expect(page.getByTestId('ad-improved')).toContainText('Career breaks');
  await page.getByTestId('tab-original').click();
  await snap(page, '09-employer');
  await page.getByTestId('step-next').click();
  await expect(page).toHaveURL(/\/fairness/);
  await expect(page.getByTestId('bias-result')).toContainText('Passed');
  await expect(page.getByTestId('twin-man')).toContainText('Rahul Verma');
  await expect(page.getByTestId('twin-man')).toContainText(/(\d+\.\d) → \1/); // same score before and after
  // Same check, other system: a deliberately biased filter is caught, with the rule that caused each difference
  await page.getByTestId('system-biased').click();
  await expect(page.getByTestId('bias-result')).toContainText('Bias found: 4 of 9');
  await expect(page.getByTestId('twin-age_older')).toContainText('Minus 10 points above age 35');
  await expect(page.getByTestId('twin-man')).toContainText('Same result');
  // Try your own twin: EQUALPATH never moves, the biased filter does
  await page.getByTestId('try-field-age').click();
  await page.getByTestId('try-value').locator('input').fill('52');
  await page.getByTestId('try-run').click();
  await expect(page.getByTestId('try-result-ours')).toContainText('Same result');
  await expect(page.getByTestId('try-result-ref')).toContainText('Different result (-10.0 points)');
  await snap(page, '10b-fairness-biased');
  await page.getByTestId('system-equalpath').click();
  await expect(page.getByTestId('bias-result')).toContainText('Passed');
  await snap(page, '10-fairness');
  await page.getByTestId('step-next').click();
  await expect(page).toHaveURL(/\/review/);
  await expect(page.getByTestId('handoff')).toBeVisible();
  await page.goto('/passport');
  await expect(page.getByTestId('empty-state')).toContainText('passport is issued only after a person approves');

  // ---- Human checkpoint 2: sign in as the Counsellor (wrong password first)
  await page.goto('/review');
  await snap(page, '11-handoff');
  await page.getByTestId('handoff-cta').click();
  await page.getByTestId('login-password').locator('input').fill('not-the-password');
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('login-error')).toContainText('Wrong password');
  await page.getByTestId('login-password').locator('input').fill(PASSWORDS.counsellor);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('rolebar')).toHaveAttribute('data-role', 'counsellor');
  await page.getByTestId('decision-edit').click();
  await page.getByTestId('edit-value').locator('input').fill('6');
  await page.getByTestId('edit-reason').locator('input').fill('Evening sessions are short; allow a buffer');
  await page.getByTestId('add-edit').click();
  await page.getByTestId('review-reason').locator('textarea').fill('Approved with adjusted effort for the SAP milestone');
  await snap(page, '12-review');
  await page.getByTestId('submit-review').click();
  await expect(page).toHaveURL(/\/passport/, { timeout: 45_000 });
  await expect(page.getByTestId('outcomes')).toContainText('Ready with Learning Milestone');
  await expect(page.getByTestId('outcomes')).toContainText('Employer Action Required');
  await expect(page.getByText('Evening sessions are short')).toBeVisible();
  await snap(page, '13-passport');

  // ---- HR Reviewer: no raw evidence, employer copy only
  await signIn(page, 'hr_reviewer');
  await page.goto('/evidence');
  await expect(page.getByTestId('empty-state')).toContainText('for someone else');
  await page.goto('/skills');
  await expect(page.getByTestId('empty-state')).toBeVisible();
  await page.goto('/passport');
  await expect(page.getByText('This is the employer copy')).toBeVisible();
  await page.goto('/review');
  await expect(page.getByTestId('tasks-panel')).toContainText('Your tasks as HR Reviewer');
  await expect(page.getByTestId('task-rewrite')).toHaveAttribute('data-status', 'todo');
  await snap(page, '14-hr-tasks');
  await page.getByTestId('task-rewrite').getByRole('button').click();
  await expect(page).toHaveURL(/\/employer/);
  await page.getByTestId('tab-rewrite').click();
  await page.getByRole('textbox', { name: 'Reason (required)' }).fill('Removes non-essential barriers');
  await page.getByTestId('approve-rewrite').click();
  await expect(page.getByText('Approved by HR').first()).toBeVisible();
  await page.getByTestId('res-career_breaks-fix_ad').click();
  await page.getByTestId('res-note-career_breaks').locator('textarea').fill('We will remove the uninterrupted-experience line this week.');
  await page.getByTestId('res-send-career_breaks').click();
  await expect(page.getByTestId('claim-resp-career_breaks')).toContainText('the job ad will be fixed');
  await snap(page, '15-hr-employer');
  await page.goto('/passport');
  await page.getByTestId('emp-invite').click();
  await page.getByTestId('emp-adj').first().click();
  await page.getByTestId('emp-reason').locator('textarea').fill('Strong, verified testing evidence. Happy to meet the interview needs.');
  await page.getByTestId('emp-send').click();
  await expect(page.getByTestId('employer-response')).toContainText('invited you to an interview');
  await page.goto('/review');
  await expect(page.getByTestId('task-candidate')).toHaveAttribute('data-status', 'done');

  // ---- Auditor: log and fairness only
  await signIn(page, 'auditor');
  await page.goto('/skills');
  await expect(page.getByTestId('empty-state')).toBeVisible();
  await page.goto('/activity');
  await expect(page.getByText('Log intact')).toBeVisible();
  await expect(page.getByText('Created and executed')).toHaveCount(0);
  await page.getByTestId('verify-log').click();
  await expect(page.getByTestId('task-verify')).toContainText('the chain is intact');
  await expect(page.getByTestId('access-log')).toContainText('resume.pdf'); // who opened the evidence
  await snap(page, '16-auditor');
  await page.getByTestId('task-fairness').getByRole('button').click();
  await expect(page).toHaveURL(/\/fairness/);
  await expect(page.getByTestId('twin-man')).toContainText('Hidden'); // Priya's real details stay hidden from the auditor
  await page.getByTestId('finding-no_concerns').click();
  await page.getByTestId('finding-note').locator('textarea').fill('All twins identical; the control test catches the biased filter.');
  await page.getByTestId('finding-submit').click();
  await expect(page.getByTestId('fairness-signoff')).toContainText('no concerns');
  await page.getByTestId('sign-out').click();
  await expect(page.getByTestId('rolebar')).toHaveAttribute('data-role', 'candidate');
  await page.goto('/passport');
  await expect(page.getByTestId('employer-response')).toContainText('invited you to an interview');

  await page.goto('/architecture');
  await expect(page.getByTestId('active-provider')).toContainText('AI provider');
  await snap(page, '17-architecture');
});

test('staff roles cannot be entered without their own password', async ({ page }) => {
  await page.goto('/');
  for (const role of ['counsellor', 'hr_reviewer', 'auditor'] as const) {
    await page.getByTestId(`role-${role}`).click();
    await page.getByTestId('login-password').locator('input').fill(PASSWORDS.counsellor); // only right for the Counsellor
    await page.getByTestId('login-submit').click();
    if (role === 'counsellor') await expect(page.getByTestId('rolebar')).toHaveAttribute('data-role', 'counsellor');
    else await expect(page.getByTestId('login-error')).toBeVisible();
    await page.keyboard.press('Escape');
  }
});

test('candidate cannot open staff pages; direct pages explain themselves instead of a dead end', async ({ page }) => {
  await page.goto('/skills');
  await expect(page.getByTestId('empty-state')).toContainText('Nothing to show yet');
  await page.getByTestId('empty-state').getByRole('button').click();
  await expect(page).toHaveURL(/\/profile/);
  await page.goto('/activity');
  await expect(page.getByText('No activity yet')).toBeVisible();
});

test('dark mode and language switching', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('theme-toggle').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByTestId('theme-toggle').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByTestId('lang-select').click();
  await page.getByRole('option', { name: /हिन्दी/ }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'hi');
  await expect(page.getByTestId('start-demo')).not.toContainText("Start Priya's demo");
});

test('after the demo, everything from the run is reachable from the menu too', async ({ page }) => {
  await startAndAnalyse(page);
  await page.getByTestId('nav-evidence').click();
  await expect(page).toHaveURL(/\/evidence/);
  await page.getByTestId('nav-passport').click();
  await expect(page.getByTestId('empty-state')).toBeVisible();
});
