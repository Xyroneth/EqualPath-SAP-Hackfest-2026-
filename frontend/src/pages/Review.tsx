import { Button, Icon, Input, Option, Select, TextArea } from '@ui5/webcomponents-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { HrTasks } from '../components/Tasks';
import { Badge, Card, Chip, Cta, EmptyState, ErrorNote, Field, NeedsAnalysis, Note, PageHead, StepFooter } from '../components/ui';
import { useVisit } from '../hooks';
import { useI18n } from '../i18n';
import { capName, outcomeName } from '../lib/compose';
import { useApp } from '../state';

const DECISIONS = [
  ['approve', 'accept', 'good'],
  ['edit', 'edit', 'info'],
  ['request_evidence', 'inbox', 'warn'],
  ['reject', 'decline', 'bad'],
] as const;

export default function Review() {
  const i18n = useI18n();
  const { t, tf } = i18n;
  const nav = useNavigate();
  const { run, runId, role, refresh, setActiveRun, askLogin, switchRole, unlocked, toast } = useApp();
  const [queue, setQueue] = useState<any>(null);
  const [decision, setDecision] = useState('approve');
  const [reason, setReason] = useState('');
  const [edits, setEdits] = useState<any[]>([]);
  const [showEdit, setShowEdit] = useState(false);
  const [edit, setEdit] = useState({ milestone: '', field: 'estimated_hours', value: '', reason: '' });
  const [nextAction, setNextAction] = useState('');
  const [evReason, setEvReason] = useState<Record<string, string>>({});
  const [evNote, setEvNote] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [audited, setAudited] = useState<any>(null);
  const staff = role === 'counsellor' || role === 'hr_reviewer';
  const v = run?.values ?? {};
  const it = run?.interrupt;
  const running = run?.run?.status === 'running';
  const atFinal = it?.checkpoint === 'final_review' && !running;
  const atEvidence = it?.checkpoint === 'evidence_request' && !running;
  const milestones = v.pathway?.milestones ?? [];
  useVisit('/review', !!v.final_review);

  const load = () => staff && api.get('/api/reviews').then(setQueue).catch(() => undefined);
  useEffect(() => {
    load();
    const id = window.setInterval(load, 4000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, runId]);
  useEffect(() => {
    if (staff && runId && v.bias_audit) api.get(`/api/runs/${runId}/fairness-review`).then((r) => setAudited(r.review)).catch(() => setAudited(null));
  }, [staff, runId, !!v.bias_audit]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (milestones.length && !edit.milestone) setEdit((e) => ({ ...e, milestone: milestones[milestones.length - 1].milestone_id }));
  }, [milestones.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const addEdit = () => {
    if (!edit.value || edit.reason.trim().length < 5) return setErr(t('review.err_edit'));
    setEdits([...edits, { target: `milestone:${edit.milestone}.${edit.field}`, new_value: edit.field === 'estimated_hours' ? Number(edit.value) : edit.value, reason: edit.reason, label: `${capName(i18n, milestones.find((m: any) => m.milestone_id === edit.milestone)?.capability ?? '', edit.milestone)} · ${t('review.f_' + edit.field)}` }]);
    setEdit({ ...edit, value: '', reason: '' });
    setErr(null);
  };
  const submit = async () => {
    setErr(null);
    const all = edits.map(({ label, ...e }) => e);
    if (nextAction.trim()) all.push({ target: 'recommendation.next_action', new_value: nextAction, reason: reason || 'Reviewer recommendation' });
    const d = all.length && decision === 'approve' ? 'edit' : decision;
    if (d !== 'approve' && reason.trim().length < 5) return setErr(t('review.err_reason'));
    setBusy(true);
    try {
      await api.post(`/api/runs/${runId}/final-review`, { decision: d, reason: reason || null, edits: all });
      await refresh();
      nav('/working');
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };
  const decideEvidence = async (id: string, d: string) => {
    setErr(null);
    if ((evReason[id] ?? '').trim().length < 5) return setErr(t('review.err_reason'));
    try {
      await api.post(`/api/evidence-submissions/${id}/decision`, { decision: d, reason: evReason[id] });
      await load();
      await refresh();
      toast(t('review.saved'), 'success');
    } catch (e: any) {
      setErr(e.message);
    }
  };
  const respond = async () => {
    try {
      await api.post(`/api/runs/${runId}/evidence-response`, { note: evNote });
      await refresh();
      nav('/working');
    } catch (e: any) {
      setErr(e.message);
    }
  };
  const goStaff = async () => {
    if (unlocked.includes('counsellor')) {
      await switchRole('counsellor');
      toast(t('role.now_as', { role: t('role.counsellor') }), 'success');
    } else askLogin('counsellor');
  };

  // ------------------------------------------------------------------ Candidate view
  if (role === 'candidate') {
    return (
      <>
        <PageHead step="review" icon="approvals" title={t('review.title')} sub={t('review.sub_candidate')} />
        <NeedsAnalysis ready={!!run && !!v.review_task}>
          {atEvidence && (
            <Card title={t('review.requested')} icon="inbox">
              <Note tone="warn">{it.request}</Note>
              <Field label={t('review.your_answer')}><TextArea rows={3} value={evNote} onInput={(e: any) => setEvNote(e.target.value)} accessibleName={t('review.your_answer')} /></Field>
              <p className="muted small">{t('review.add_more')} <a href="/evidence">{t('nav.evidence')}</a></p>
              <ErrorNote error={err} />
              <Cta onClick={respond} disabled={evNote.trim().length < 3}>{t('review.send')}</Cta>
            </Card>
          )}
          {!atEvidence && !v.final_review && (
            <div className="handoff" data-testid="handoff">
              <ol className="handoff-steps">
                <li className="done"><span><Icon name="accept" /></span>{t('review.h1')}</li>
                <li className="now"><span><Icon name="employee-approvals" /></span>{t('review.h2')}</li>
                <li><span><Icon name="document" /></span>{t('review.h3')}</li>
              </ol>
              <EmptyState kind="waiting" title={t('review.waiting_title')} text={t('review.waiting_text')} action={<Cta onClick={goStaff} testId="handoff-cta" icon="employee-approvals">{t('role.switch_to', { role: t('role.counsellor') })}</Cta>} />
            </div>
          )}
          {v.final_review && (
            <Card title={t('review.done_title')} icon="message-success">
              <p>{t('review.done_text', { decision: tf('decision.' + v.final_review.decision, v.final_review.decision), who: v.final_review.actor })}</p>
              {v.final_review.reason && <p className="muted">“{v.final_review.reason}”</p>}
              {v.passport && <Cta onClick={() => nav('/passport')}>{t('next.done_cta')}</Cta>}
            </Card>
          )}
        </NeedsAnalysis>
        <StepFooter step="review" hideNext={!v.passport} />
      </>
    );
  }

  // ------------------------------------------------------------------ Staff view
  const waitingCases: any[] = queue?.final_reviews ?? [];
  const es = v.employer_scan;
  return (
    <>
      <PageHead step="review" icon="approvals" title={role === 'hr_reviewer' ? t('review.title_hr') : t('review.title')} sub={role === 'hr_reviewer' ? t('review.sub_hr') : t('review.sub_staff')} />
      {role === 'hr_reviewer' && (run ? <HrTasks /> : <EmptyState kind="waiting" title={t('tasks.no_run')} text={t('tasks.no_run_text')} />)}
      {role === 'hr_reviewer' && atFinal && <Note tone="info" icon="employee-approvals">{t('review.hr_waits')}</Note>}
      {role === 'counsellor' && waitingCases.length > 0 && (
        <Card title={t('review.queue', { n: waitingCases.length })} icon="inbox" className="queue-card">
          {waitingCases.map((c) => (
            <div key={c.task_id} className={`queue-row ${c.run_id === runId ? 'active' : ''}`} data-testid={`case-${c.run_id}`}>
              <div><b>{c.role_title}</b><span className="muted small"> · {c.proposed_outcomes.map((o: string) => outcomeName(i18n, o)).join(' + ')}</span></div>
              {c.run_id === runId ? <Chip tone="good" icon="accept">{t('review.open_now')}</Chip> : <Button design="Emphasized" onClick={() => setActiveRun(c.run_id, c.candidate_id)}>{t('review.open')}</Button>}
            </div>
          ))}
        </Card>
      )}
      {role === 'hr_reviewer' ? null : atFinal ? (
        <div className="review-grid">
          <Card title={t('review.packet')} icon="task">
            <div className="packet">
              <div className="chip-row">{it.task.proposed_outcomes.map((o: string) => <Chip key={o} tone="accent">{outcomeName(i18n, o)}</Chip>)}</div>
              <dl className="facts">
                <dt>{t('review.p_gaps')}</dt><dd>{t('review.p_gaps_v', { v: v.pathway?.counts.verified, d: v.pathway?.counts.developing, m: v.pathway?.counts.missing })}</dd>
                <dt>{t('review.p_plan')}</dt><dd>{t('review.p_plan_v', { hours: v.pathway?.total_hours, weeks: v.pathway?.estimated_weeks })}</dd>
                <dt>{t('review.p_employer')}</dt><dd>{es ? t('review.p_employer_v', { flags: es.flags?.length ?? 0, conflicts: es.conflicts_requiring_review?.length ?? 0 }) : '—'}</dd>
                <dt>{t('review.p_fair')}</dt><dd>{v.bias_audit?.passed ? t('fair.passed') : t('fair.failed')}</dd>
                <dt>{t('review.p_auditor')}</dt><dd data-testid="packet-auditor">{audited ? <><Badge status={audited.finding === 'concern' ? 'failed' : 'completed'} label={t('fair.audited_' + audited.finding)} /> <span className="small muted">“{audited.note}”</span></> : t('review.p_auditor_none')}</dd>
                {v.candidate_review && <><dt>{t('review.p_cand')}</dt><dd>{t('review.p_cand_v', { n: v.candidate_review.corrections.length })}</dd></>}
                <dt>{t('review.p_route')}</dt><dd>{it.task.workflow?.provider}</dd>
              </dl>
              <div className="row">
                <Button design="Transparent" icon="lightbulb" onClick={() => nav('/skills')}>{t('nav.skills')}</Button>
                <Button design="Transparent" icon="map-2" onClick={() => nav('/gaps')}>{t('nav.gaps')}</Button>
                <Button design="Transparent" icon="building" onClick={() => nav('/employer')}>{t('nav.employer')}</Button>
              </div>
            </div>
          </Card>
          <Card title={t('review.decide')} icon="approvals" className="decide-card">
            <div className="decision-grid" role="radiogroup" aria-label={t('review.decide')}>
              {DECISIONS.map(([k, icon, tone]) => (
                <button key={k} type="button" role="radio" aria-checked={decision === k} className={`decision ${tone} ${decision === k ? 'on' : ''}`} onClick={() => { setDecision(k); if (k === 'edit') setShowEdit(true); }} data-testid={`decision-${k}`}>
                  <Icon name={icon} aria-hidden="true" />
                  <b>{t('review.d_' + k)}</b>
                  <span>{t('review.d_' + k + '_d')}</span>
                </button>
              ))}
            </div>
            <Field label={t('review.reason') + (decision === 'approve' ? ` (${t('common.optional')})` : ' *')}><TextArea rows={2} value={reason} onInput={(e: any) => setReason(e.target.value)} accessibleName={t('review.reason')} data-testid="review-reason" /></Field>
            <details open={showEdit} onToggle={(e) => setShowEdit((e.target as HTMLDetailsElement).open)} className="edit-box">
              <summary>{t('review.change')}</summary>
              <div className="form-grid">
                <Field label={t('review.what')}>
                  <Select accessibleName={t('review.what')} onChange={(e) => setEdit({ ...edit, milestone: e.detail.selectedOption.getAttribute('value')! })}>
                    {milestones.map((m: any) => <Option key={m.milestone_id} value={m.milestone_id} selected={edit.milestone === m.milestone_id}>{capName(i18n, m.capability, m.gap)}</Option>)}
                  </Select>
                </Field>
                <Field label={t('review.field')}>
                  <Select accessibleName={t('review.field')} onChange={(e) => setEdit({ ...edit, field: e.detail.selectedOption.getAttribute('value')! })}>
                    {['estimated_hours', 'practice_task', 'importance'].map((f) => <Option key={f} value={f} selected={edit.field === f}>{t('review.f_' + f)}</Option>)}
                  </Select>
                </Field>
                <Field label={t('review.new_value')}><Input value={edit.value} onInput={(e: any) => setEdit({ ...edit, value: e.target.value })} accessibleName={t('review.new_value')} data-testid="edit-value" /></Field>
                <Field label={t('review.edit_reason')}><Input value={edit.reason} onInput={(e: any) => setEdit({ ...edit, reason: e.target.value })} accessibleName={t('review.edit_reason')} data-testid="edit-reason" /></Field>
              </div>
              <Button icon="add" onClick={addEdit} data-testid="add-edit">{t('review.add_edit')}</Button>
              {edits.map((e, i) => <p key={i} className="small edit-line"><Icon name="edit" aria-hidden="true" /> {e.label}: <b>{String(e.new_value)}</b> — {e.reason}</p>)}
              <Field label={t('review.next_action')}><Input value={nextAction} onInput={(e: any) => setNextAction(e.target.value)} accessibleName={t('review.next_action')} /></Field>
            </details>
            <ErrorNote error={err} />
            <Cta onClick={submit} loading={busy} testId="submit-review">{t('review.submit')}</Cta>
          </Card>
        </div>
      ) : (
        !waitingCases.length && !(queue?.evidence_reviews?.length) && (
          <EmptyState kind="waiting" title={run && v.final_review ? t('review.done_title') : t('review.nothing')} text={run && v.final_review ? t('review.done_text', { decision: tf('decision.' + v.final_review.decision, v.final_review.decision), who: v.final_review.actor }) : t('review.nothing_text')}
            action={v.passport ? <Cta onClick={() => nav('/passport')}>{t('next.done_cta')}</Cta> : undefined} />
        )
      )}
      {role === 'counsellor' && (queue?.evidence_reviews?.length ?? 0) > 0 && (
        <Card title={t('review.evidence_q', { n: queue.evidence_reviews.length })} icon="attachment">
          {queue.evidence_reviews.map((s: any) => (
            <div key={s.submission_id} className="evreview" data-testid={`evreview-${s.submission_id}`}>
              <div className="chip-row tight"><b>{capName(i18n, s.capability, s.gap)}</b><Chip>{t('learn.k_' + s.evidence_kind)}</Chip></div>
              <p className="muted small">{s.title}</p>
              <pre className="doc">{s.content}</pre>
              <p className="small">{t('review.rule')}: {t('review.rule_text')}</p>
              <div className="row wrap">
                <Input placeholder={t('review.reason')} value={evReason[s.submission_id] ?? ''} onInput={(e: any) => setEvReason({ ...evReason, [s.submission_id]: e.target.value })} accessibleName={t('review.reason')} data-testid="ev-reason" />
                <Button design="Positive" onClick={() => decideEvidence(s.submission_id, 'accept')} data-testid="ev-accept">{t('review.accept')}</Button>
                <Button onClick={() => decideEvidence(s.submission_id, 'request_more')}>{t('review.more')}</Button>
                <Button design="Negative" onClick={() => decideEvidence(s.submission_id, 'reject')}>{t('review.reject')}</Button>
              </div>
            </div>
          ))}
          <ErrorNote error={err} />
        </Card>
      )}
      {role === 'counsellor' && (queue?.jd_rewrites?.length ?? 0) > 0 && (
        <Card title={t('review.jd_q', { n: queue.jd_rewrites.length })} icon="document">
          {queue.jd_rewrites.map((r: any) => <div key={r.run_id} className="queue-row"><span>{r.job_id}</span><Button design="Transparent" onClick={() => { if (r.run_id !== runId) toast(t('review.open_case_first'), 'info'); nav('/employer'); }}>{t('review.open_employer')}</Button></div>)}
        </Card>
      )}
      <StepFooter step="review" hideNext={!v.passport} />
    </>
  );
}
