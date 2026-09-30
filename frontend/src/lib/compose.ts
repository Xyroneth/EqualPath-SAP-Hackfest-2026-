/** Builds readable, translatable sentences from the structured data (codes + numbers) the agents return. */
import type { I18nApi } from './types';

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
export const capKey = (cap: string) => 'cap.' + cap.replace(/\./g, '_');

export const capName = (i: I18nApi, cap: string, fallback?: string) => i.tf(capKey(cap), fallback ?? cap.split('.').pop()!.replace(/_/g, ' '));
export const levelName = (i: I18nApi, l?: string) => (l ? i.tf('level.' + l, l) : '');
export const outcomeName = (i: I18nApi, name: string) => i.tf('outcome.' + slug(name), name);
export const roleTitle = (i: I18nApi, id: string, fallback: string) => i.tf(`rolecat.${id}.title`, fallback);
export const roleSummary = (i: I18nApi, id: string, fallback: string) => i.tf(`rolecat.${id}.summary`, fallback);
export const nodeName = (i: I18nApi, id: string, fallback: string) => i.tf('node.' + id, fallback);
export const statusName = (i: I18nApi, s: string) => i.tf('status.' + s, s.replace(/_/g, ' '));

export function gapReason(i: I18nApi, g: any): string {
  const p = g.reason_params ?? {};
  switch (g.reason_code) {
    case 'met': return i.t('reason.met', { need: levelName(i, p.need), have: levelName(i, p.have), status: statusName(i, p.status) });
    case 'unsupported': return i.t('reason.unsupported', { source: p.source });
    case 'lower': return i.t('reason.lower', { need: levelName(i, p.need), have: levelName(i, p.have) });
    case 'adjacent': return i.t('reason.adjacent', { list: (p.adjacent ?? []).join(', ') });
    case 'none': return i.t('reason.none');
    default: return g.reason;
  }
}

export function activityText(i: I18nApi, e: any): string {
  const o = e.outputs ?? {};
  const t = i.t;
  switch (e.node) {
    case 'intake': return t('act.intake', { documents: o.documents ?? 0, redactions: o.redactions ?? 0 });
    case 'skills_discovery': return t('act.skills_discovery', { skills: o.skills ?? 0, source_supported: o.source_supported ?? 0, self_declared: o.self_declared ?? 0 });
    case 'candidate_review': return t('act.candidate_review', { corrections: o.corrections ?? 0 });
    case 'market_intelligence': return t('act.market_intelligence', { ranked: o.ranked ?? 0, role: o.recommended_id ? roleTitle(i, o.recommended_id, o.recommended) : o.recommended });
    case 'role_selection': return t('act.role_selection', { role: o.role_id ? roleTitle(i, o.role_id, o.role_title) : o.role_title });
    case 'learning_pathway': return t('act.learning_pathway', { verified: o.verified ?? 0, developing: o.developing ?? 0, missing: o.missing ?? 0, milestones: o.milestones ?? 0, hours: o.hours ?? 0, weeks: o.weeks ?? 0 });
    case 'employer_readiness': return t('act.employer_readiness', { flags: o.flags ?? 0, high: o.high ?? 0, conflicts: o.conflicts ?? 0 });
    case 'inclusive_matching': return t('act.inclusive_matching', { verified: o.verified ?? 0, total: o.total ?? 0, actions: o.employer_actions ?? 0 });
    case 'bias_audit': return o.passed ? t('act.bias_audit_pass', { n: o.counterfactuals ?? 0 }) : t('act.bias_audit_fail', { changed: o.changed ?? 0 });
    case 'review_routing': return t('act.review_routing', { where: o.workflow ?? '' });
    case 'final_review': return t('act.final_review', { decision: i.tf('decision.' + o.decision, o.decision ?? ''), reason: o.reason ? ` - ${o.reason}` : '' });
    case 'await_evidence': return t('act.await_evidence');
    case 'passport': return t('act.passport');
    default: return e.summary ?? '';
  }
}

export function outcomeText(i: I18nApi, o: any): string {
  const p = o.params ?? {};
  switch (o.code) {
    case 'learning': return i.t('outcome.text.learning', { n: p.n, names: (p.capabilities ?? []).map((c: string) => capName(i, c)).join(', '), hours: p.hours, weeks: p.weeks });
    case 'employer': return i.t('outcome.text.employer', { n: p.n, high: p.high, cats: (p.categories ?? []).map((c: string) => i.tf('cat.' + c, c)).join('; ') });
    case 'ready': return i.t('outcome.text.ready');
    case 'bias_flag': return i.t('outcome.text.bias_flag');
    case 'override': return i.t('outcome.text.override', { reason: p.reason ?? '' });
    default: return o.explanation;
  }
}

export function actionText(i: I18nApi, a: any): string {
  const p = a.params ?? {};
  switch (a.code) {
    case 'milestone': return i.t('action.milestone', { gap: capName(i, p.capability, p.gap), hours: p.hours });
    case 'review_evidence': return i.t('action.review_evidence');
    case 'jd_rewrite': return i.t(p.status === 'pending_hr_approval' ? 'action.jd_pending' : 'action.jd_done', { status: statusName(i, p.status) });
    case 'fix_flag': return i.t('action.fix_flag', { label: i.tf('cat.' + p.category, p.category), text: p.text ? ` "${p.text}"` : '' });
    case 'resolve_conflict': return i.t('action.resolve_conflict', { claim: i.tf('claim.' + p.claim + '.q', p.claim) });
    case 'employer_response': return i.t('action.employer_response');
    case 'reviewer_action': return p.text;
    default: return a.action;
  }
}

export function actorName(i: I18nApi, s: string): string {
  const map: Record<string, string> = { Candidate: 'candidate', Employer: 'employer', 'Employer HR': 'employer', 'HR reviewer': 'hr_reviewer', Counsellor: 'counsellor', 'Counsellor (reviewer recommendation)': 'counsellor',
    'Candidate, with counsellor review': 'candidate_counsellor', 'Counsellor / HR reviewer': 'reviewers', 'Employer (interview)': 'employer', Reviewer: 'reviewers' };
  return map[s] ? i.t('who.' + map[s]) : s;
}
export const sideName = (i: I18nApi, s: string) => i.tf('side.' + slug(s), s);

export function claimNote(i: I18nApi, n: any): string {
  switch (n.code) {
    case 'contradicted_by': return i.t('note.contradicted', { sources: (n.sources ?? []).map((s: string) => (s === 'job_description' ? i.t('note.the_jd') : i.t('note.a_policy'))).join(', ') });
    case 'feedback_contradicts': return i.t('note.fb_contradicts', { n: n.n });
    case 'feedback_supports': return i.t('note.fb_supports', { n: n.n });
    case 'not_offered': return i.t('note.not_offered');
    case 'feedback_excluded': return i.t('note.fb_excluded', { n: n.n });
    case 'not_in_jd': return i.t('note.not_in_jd');
    default: return '';
  }
}

export function conditionNote(i: I18nApi, c: any): string {
  const n = c.note ?? {};
  switch (n.code) {
    case 'employer_says': return i.t('cond.employer_says', { answer: n.answer, level: statusName(i, n.level) });
    case 'not_stated': return i.t('cond.not_stated');
    case 'stated': return c.status === 'conflict' ? i.t('cond.conflict') : i.t('cond.stated');
    case 'none_shared': return i.t('cond.none_shared');
    default: return c.detail ?? '';
  }
}

export const flagWhy = (i: I18nApi, f: any) => i.tf(`flagwhy.${f.category}.${f.aspect ?? 'text'}`, f.explanation ?? '');

/** Milestone wording: translated when it came from the built-in template and was not edited by a reviewer. */
export function milestoneText(i: I18nApi, m: any, field: 'task' | 'why'): string {
  const original = field === 'task' ? m.practice_task : m.why_it_matters;
  const key = `ms.${m.capability.replace(/\./g, '_')}.${field}`;
  return m.generated_by === 'deterministic template' && !m.text_edited && i.has(key) ? i.t(key) : original;
}
export function milestoneEvidence(i: I18nApi, m: any): string[] {
  const key = `ms.${m.capability.replace(/\./g, '_')}.evidence`;
  return m.generated_by === 'deterministic template' && !m.text_edited && i.has(key) ? i.t(key).split('|') : m.required_evidence;
}
