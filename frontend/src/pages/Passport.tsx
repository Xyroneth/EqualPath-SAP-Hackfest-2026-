import { Button, CheckBox, Icon, TextArea } from '@ui5/webcomponents-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, openEvidence } from '../api';
import { Badge, Card, Chip, Cta, EmptyState, ErrorNote, NeedsAnalysis, Note, PageHead, Quote, StepFooter } from '../components/ui';
import { useVisit } from '../hooks';
import { useI18n } from '../i18n';
import { actionText, actorName, capName, conditionNote, flagWhy, gapReason, levelName, milestoneEvidence, milestoneText, outcomeName, outcomeText, sideName, claimNote } from '../lib/compose';
import { useApp } from '../state';

const SECTIONS = ['capability', 'gaps', 'conditions', 'employer', 'fairness', 'human', 'next'];
const EMP_DECISIONS = [['invite', 'calendar', 'good'], ['talent_pool', 'save', 'info'], ['decline', 'decline', 'bad']] as const;

/** The employer's answer to the candidate: the HR Reviewer records it here, and the candidate sees it on her passport. */
function EmployerResponse({ runId, isHr, employer }: { runId: string; isHr: boolean; employer: string }) {
  const { t } = useI18n();
  const { toast } = useApp();
  const [s, setS] = useState<any>(null);
  const [d, setD] = useState<string>('');
  const [reason, setReason] = useState('');
  const [adj, setAdj] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = () => api.get(`/api/runs/${runId}/employer-tasks`).then(setS).catch(() => setS(null));
  useEffect(() => {
    load();
  }, [runId, isHr]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!s) return null;
  const send = async () => {
    setErr(null);
    if (!d || reason.trim().length < 5) return setErr(t('emp_resp.err'));
    try {
      await api.post(`/api/runs/${runId}/employer-decision`, { decision: d, reason, adjustments: d === 'invite' ? adj : [] });
      await load();
      toast(t('emp_resp.sent'), 'success');
    } catch (e: any) {
      setErr(e.message);
    }
  };
  const dec = s.decision;
  if (dec) {
    return (
      <section className={`emp-resp ${dec.decision}`} data-testid="employer-response">
        <span className="emp-resp-ico"><Icon name={dec.decision === 'invite' ? 'calendar' : dec.decision === 'decline' ? 'decline' : 'save'} aria-hidden="true" /></span>
        <div>
          <span className="muted small">{isHr ? t('emp_resp.hr_title') : t('emp_resp.title')}</span>
          <h3>{t('emp_resp.cand_' + dec.decision, { employer })}</h3>
          <p>“{dec.reason}”</p>
          {dec.adjustments?.length > 0 && <><b className="small">{t('emp_resp.agreed')}</b><ul>{dec.adjustments.map((a: string) => <li key={a}>{a}</li>)}</ul></>}
          <small className="muted">{dec.actor} · {(dec.at ?? '').slice(0, 16).replace('T', ' ')} UTC</small>
        </div>
      </section>
    );
  }
  if (!isHr) return <Note tone="info" icon="pending">{t('emp_resp.none_yet', { employer })}</Note>;
  if (!s.can_decide) return <Note tone="warn" icon="locked">{t('tasks.locked_' + (s.tasks.find((x: any) => x.id === 'candidate')?.blocked_by ?? 'passport'))}</Note>;
  return (
    <Card title={t('emp_resp.hr_title')} icon="business-card" className="emp-resp-form">
      <p className="muted small">{t('emp_resp.hr_sub')}</p>
      <div className="decision-grid three" role="radiogroup" aria-label={t('emp_resp.hr_title')}>
        {EMP_DECISIONS.map(([k, icon, tone]) => (
          <button key={k} type="button" role="radio" aria-checked={d === k} className={`decision ${tone} ${d === k ? 'on' : ''}`} onClick={() => setD(k)} data-testid={`emp-${k}`}>
            <Icon name={icon} aria-hidden="true" /><b>{t('emp_resp.d_' + k)}</b><span>{t('emp_resp.d_' + k + '_d')}</span>
          </button>
        ))}
      </div>
      {d === 'invite' && (
        <div className="adj-box">
          <b className="small">{t('emp_resp.adjustments')}</b>
          {s.shared_accommodations.length ? s.shared_accommodations.map((a: string) => (
            <CheckBox key={a} text={a} checked={adj.includes(a)} onChange={() => setAdj(adj.includes(a) ? adj.filter((x) => x !== a) : [...adj, a])} data-testid="emp-adj" />
          )) : <p className="muted small">{t('emp_resp.no_adjustments')}</p>}
        </div>
      )}
      <TextArea rows={2} value={reason} placeholder={t('emp_resp.reason')} onInput={(e: any) => setReason(e.target.value)} accessibleName={t('emp_resp.reason')} data-testid="emp-reason" />
      <ErrorNote error={err} />
      <Cta onClick={send} testId="emp-send" icon="paper-plane">{t('emp_resp.send')}</Cta>
    </Card>
  );
}

export default function Passport() {
  const i18n = useI18n();
  const { t, tf } = i18n;
  const nav = useNavigate();
  const { run, runId, role, candidateId, toast } = useApp();
  const [p, setP] = useState<any>(null);
  const [audience, setAudience] = useState<'candidate' | 'employer'>('candidate');
  const [err, setErr] = useState<string | null>(null);
  const done = !!run?.values?.passport;
  const isHr = role === 'hr_reviewer';
  useVisit('/passport', !!p);

  useEffect(() => {
    if (!runId || !done) return setP(null);
    api.get(`/api/runs/${runId}/passport?audience=${isHr ? 'employer' : audience}`).then((x) => { setP(x); setErr(null); }).catch((e) => { setP(null); setErr(e.message); });
  }, [runId, done, audience, isHr, run?.values?.pathway?.counts?.verified, role]);

  const open = (sid: string) => candidateId && openEvidence(candidateId, sid).then((ok) => !ok && toast(t('evidence.popup'), 'warning')).catch((e) => toast(e.message, 'error'));
  const dl = (kind: 'html' | 'json') => kind === 'html'
    ? api.saveAs(`/api/runs/${runId}/passport.html?audience=${isHr ? 'employer' : audience}`, `passport-${runId}.html`, 'text/html')
    : api.saveAs(`/api/runs/${runId}/passport?audience=${isHr ? 'employer' : audience}`, `passport-${runId}.json`);

  return (
    <>
      <PageHead step="passport" icon="document" title={t('passport.title')} sub={p ? t('passport.sub', { id: p.passport_id, role: p.target_role }) : t('passport.sub_none')}
        actions={p && (
          <div className="page-actions no-print">
            {!isHr && (
              <div className="seg" role="group" aria-label={t('passport.audience')}>
                <button type="button" className={audience === 'candidate' ? 'on' : ''} onClick={() => setAudience('candidate')}>{t('passport.a_candidate')}</button>
                <button type="button" className={audience === 'employer' ? 'on' : ''} onClick={() => setAudience('employer')} data-testid="audience-employer">{t('passport.a_employer')}</button>
              </div>
            )}
            <Button icon="print" onClick={() => window.print()}>{t('passport.print')}</Button>
            <Button icon="download" onClick={() => dl('html')} data-testid="download-html">HTML</Button>
            <Button icon="download" onClick={() => dl('json')}>JSON</Button>
          </div>
        )} />
      <NeedsAnalysis ready={done || !!p} waitingText={t('passport.blocked')}>
        {!p && !err && <p className="muted">…</p>}
        <ErrorNote error={p ? null : err && !done ? err : null} />
        {p && (
          <>
            <nav className="section-pills no-print" aria-label={t('passport.sections')}>
              {SECTIONS.map((s, i) => <a key={s} href={`#sec-${s}`}>{i + 1}. {t('passport.s_' + s)}</a>)}
            </nav>
            <div className="outcomes" data-testid="outcomes">
              {p.outcomes.map((o: any, i: number) => (
                <div key={o.outcome} className={`outcome ${o.outcome.split(' ')[0].toLowerCase()}`} style={{ ['--i' as any]: i }}>
                  <span className="outcome-side">{sideName(i18n, o.side)} · {actorName(i18n, o.responsible)}</span>
                  <strong>{outcomeName(i18n, o.outcome)}</strong>
                  <p>{outcomeText(i18n, o)}</p>
                </div>
              ))}
            </div>
            <Note tone="info" icon="hint">{t('passport.disclaimer')}</Note>
            {p.audience === 'employer' && <Note tone="warn" icon="shield">{t('passport.employer_note')}</Note>}
            {runId && <EmployerResponse runId={runId} isHr={isHr} employer={p.sections.employer_readiness.employer ?? ''} />}

            <Card title={`1. ${t('passport.s_capability')}`} icon="lightbulb" className="pp-card" style={{}}>
              <span id="sec-capability" className="anchor" />
              {p.sections.capability_evidence.withheld ? <p className="muted">{t('passport.withheld')}</p> : (
                <div className="grid cols-2">
                  {p.sections.capability_evidence.items.map((c: any) => (
                    <div key={c.normalized_skill} className="pp-skill">
                      <div className="row between"><b>{capName(i18n, c.normalized_skill, c.skill_name)}</b><Badge status={c.verification_status} /></div>
                      <span className="small muted">{levelName(i18n, c.proficiency)} · {tf('etype.' + c.evidence_type, c.evidence_type)}</span>
                      <Quote text={c.evidence_quote} source={c.source_id} onSource={p.audience !== 'employer' && /\.[a-z0-9]{2,4}$/i.test(c.source_id) ? () => open(c.source_id) : undefined} />
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card title={`2. ${t('passport.s_gaps')}`} icon="map-2" className="pp-card">
              <span id="sec-gaps" className="anchor" />
              {p.sections.role_gap_map.withheld ? <p className="muted">{t('passport.withheld')}</p> : (
                <>
                  <div className="scroll-x"><table className="tbl">
                    <thead><tr><th>{t('passport.capability')}</th><th>{t('passport.required')}</th><th>{t('passport.status')}</th><th>{t('passport.why')}</th></tr></thead>
                    <tbody>{p.sections.role_gap_map.gaps.map((g: any) => <tr key={g.capability}><td>{capName(i18n, g.capability, g.capability_name)}</td><td>{levelName(i18n, g.required_level)}</td><td><Badge status={g.status} /></td><td className="small">{gapReason(i18n, g)}</td></tr>)}</tbody>
                  </table></div>
                  <h4>{t('passport.plan', { hours: p.sections.role_gap_map.total_hours, weeks: p.sections.role_gap_map.estimated_weeks })}</h4>
                  <div className="scroll-x"><table className="tbl">
                    <thead><tr><th>{t('passport.step')}</th><th>{t('learn.learn')}</th><th>{t('passport.hours')}</th><th>{t('learn.proof')}</th><th>{t('passport.status')}</th></tr></thead>
                    <tbody>{p.sections.role_gap_map.milestones.map((m: any) => (
                      <tr key={m.milestone_id}><td>{capName(i18n, m.capability, m.gap)}</td>
                        <td><a href={m.learning_asset_url} target="_blank" rel="noreferrer">{m.learning_asset_title}</a><br /><span className="small muted">{m.learning_asset_provider}</span></td>
                        <td>{m.estimated_hours}</td><td className="small">{milestoneEvidence(i18n, m).join(' · ')}</td><td><Badge status={m.progress} /></td></tr>
                    ))}</tbody>
                  </table></div>
                </>
              )}
            </Card>

            <Card title={`3. ${t('passport.s_conditions')}`} icon="calendar" className="pp-card">
              <span id="sec-conditions" className="anchor" />
              {p.sections.work_condition_fit.withheld ? <p className="muted">{t('passport.withheld')}</p> : (
                <div className="scroll-x"><table className="tbl">
                  <thead><tr><th>{t('passport.condition')}</th><th>{t('passport.candidate')}</th><th>{t('passport.status')}</th><th>{t('passport.note')}</th><th>{t('passport.responsible')}</th></tr></thead>
                  <tbody>{p.sections.work_condition_fit.conditions.map((c: any) => (
                    <tr key={c.key}><td>{t('cond.k_' + c.key)}</td>
                      <td>{c.key === 'work_mode' ? (c.candidate_list ?? []).map((m: string) => tf('mode.' + m, m)).join(', ') : c.candidate === 'Not shared by candidate' ? t('passport.not_shared') : c.candidate || t('cond.none_shared')}</td>
                      <td><Badge status={c.status} /></td><td className="small">{conditionNote(i18n, c)}</td><td>{c.responsible ? actorName(i18n, c.responsible) : '—'}</td></tr>
                  ))}</tbody>
                </table></div>
              )}
            </Card>

            <Card title={`4. ${t('passport.s_employer')}`} icon="building" className="pp-card">
              <span id="sec-employer" className="anchor" />
              <p>{t('employer.sub', { flags: p.sections.employer_readiness.flags.length, high: p.sections.employer_readiness.flags.filter((f: any) => f.severity === 'high').length, conflicts: p.sections.employer_readiness.claims.filter((c: any) => c.requires_human_review).length })} · {t('passport.rewrite')}: <b>{t('employer.rw_' + (p.sections.employer_readiness.rewrite_status?.startsWith('approved') ? 'approved' : p.sections.employer_readiness.rewrite_status?.startsWith('rejected') ? 'rejected' : 'pending'))}</b></p>
              <div className="flag-list">{p.sections.employer_readiness.flags.map((f: any, i: number) => (
                <div key={i} className="flag-item"><div className="flag-top"><Badge status={f.severity} /><b>{t('cat.' + (f.category ?? ''))}</b></div>{f.text && <p className="flag-quote">“{f.text}”</p>}<p className="muted small">{flagWhy(i18n, f)}</p></div>
              ))}</div>
              <div className="claim-grid">{p.sections.employer_readiness.claims.map((c: any) => (
                <div key={c.claim_id} className="claim"><div className="claim-top"><b>{t('claim.' + c.claim_id + '.q')}</b><Badge status={c.evidence_level} /></div><p className="claim-answer">“{c.answer}”</p>{c.note_codes?.map((n: any, i: number) => <p key={i} className="muted small">{claimNote(i18n, n)}</p>)}</div>
              ))}</div>
              <p className="muted small">{t('employer.disclaimer')}</p>
            </Card>

            <Card title={`5. ${t('passport.s_fairness')}`} icon="compare" className="pp-card">
              <span id="sec-fairness" className="anchor" />
              <Chip tone={p.sections.bias_audit.passed ? 'good' : 'bad'} icon={p.sections.bias_audit.passed ? 'accept' : 'alert'}>{p.sections.bias_audit.passed ? t('fair.passed_text', { n: p.sections.bias_audit.counterfactuals_run }) : t('fair.failed')}</Chip>
              {p.sections.bias_audit.reference_flagged != null && <p className="small">{t('passport.fair_control', { n: p.sections.bias_audit.reference_flagged })}</p>}
              {p.sections.bias_audit.auditor_review
                ? <p className="small"><Badge status={p.sections.bias_audit.auditor_review.finding === 'concern' ? 'failed' : 'completed'} label={t('fair.audited_' + p.sections.bias_audit.auditor_review.finding)} /> “{p.sections.bias_audit.auditor_review.note}”</p>
                : <p className="small muted">{t('fair.signoff_none')}</p>}
              <ul>{['single_person', 'llm_not_rerun', 'group_monitoring'].map((k) => <li key={k} className="small">{t('fairlim.' + k)}</li>)}</ul>
            </Card>

            <Card title={`6. ${t('passport.s_human')}`} icon="approvals" className="pp-card">
              <span id="sec-human" className="anchor" />
              <p><b>{tf('decision.' + p.sections.human_review.decision, p.sections.human_review.decision)}</b> — {p.sections.human_review.reviewer} ({p.sections.human_review.reviewer_role}) · {(p.sections.human_review.at ?? '').slice(0, 16).replace('T', ' ')} UTC</p>
              {p.sections.human_review.reason && <p className="muted">{t('review.reason')}: “{p.sections.human_review.reason}”</p>}
              {p.sections.human_review.edits.map((e: any, i: number) => <p key={i} className="small edit-line"><Icon name="edit" aria-hidden="true" /> {e.target.replace('milestone:', '')}: {String(e.old)} → <b>{String(e.new)}</b> — {e.reason}</p>)}
              {p.sections.human_review.candidate_review && <p className="small muted">{t('passport.cand_approved', { n: p.sections.human_review.candidate_review.corrections.length })}</p>}
            </Card>

            <Card title={`7. ${t('passport.s_next')}`} icon="task" className="pp-card">
              <span id="sec-next" className="anchor" />
              <div className="scroll-x"><table className="tbl">
                <thead><tr><th>{t('passport.action')}</th><th>{t('passport.responsible')}</th><th>{t('passport.status')}</th></tr></thead>
                <tbody>{p.sections.next_actions.items.map((a: any, i: number) => <tr key={i}><td>{actionText(i18n, a)}</td><td>{actorName(i18n, a.responsible)}</td><td><Badge status={a.status} /></td></tr>)}</tbody>
              </table></div>
            </Card>
          </>
        )}
      </NeedsAnalysis>
      {p && role !== 'hr_reviewer' && <StepFooter step="passport" hideNext />}
    </>
  );
}
