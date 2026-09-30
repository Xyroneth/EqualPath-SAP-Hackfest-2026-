import { Button, Icon, Input, TextArea } from '@ui5/webcomponents-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { JobAd, type LineMark } from '../components/JobAd';
import { Badge, Card, Chip, EmptyState, ErrorNote, Field, InfoTip, NeedsAnalysis, Note, PageHead, StepFooter } from '../components/ui';
import { useVisit } from '../hooks';
import { useI18n } from '../i18n';
import { claimNote, flagWhy } from '../lib/compose';
import { useApp } from '../state';

const CATS = ['degree_requirement', 'career_gap_requirement', 'age_requirement', 'gender_or_family_requirement', 'physical_requirement', 'exclusionary_or_vague_wording',
  'unclear_work_conditions', 'missing_accessible_interview_info', 'missing_accommodation_process', 'missing_return_to_work_support'];
const SEV: Record<string, number> = { high: 3, medium: 2, low: 1 };
const norm = (s: string) => s.trim().replace(/^-\s*/, '').trim();

export default function Employer() {
  const i18n = useI18n();
  const { t, tf } = i18n;
  const { run, runId, role, toast } = useApp();
  const [improved, setImproved] = useState<any>(null);
  const [emp, setEmp] = useState<any>(null);
  const [tab, setTab] = useState<'original' | 'rewrite' | 'improved'>('original');
  const [edited, setEdited] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [answers, setAnswers] = useState<Record<string, { resolution: string; note: string }>>({});
  const [err, setErr] = useState<string | null>(null);
  const scan = run?.values?.employer_scan;
  const isHr = role === 'hr_reviewer';
  useVisit('/employer', !!scan);

  const loadEmp = () => runId && api.get(`/api/runs/${runId}/employer-tasks`).then(setEmp).catch(() => setEmp(null));
  useEffect(() => {
    setImproved(null);
    if (scan?.improved_job_id) api.get(`/api/jobs`).then((j) => {
      const job = j.jobs.find((x: any) => x.job_id === scan.improved_job_id);
      if (job) setImproved(job);
    }).catch(() => undefined);
  }, [scan?.improved_job_id]);
  useEffect(() => {
    loadEmp();
  }, [runId, scan?.job_id, role]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (window.location.hash === '#claims') document.getElementById('claims')?.scrollIntoView({ behavior: 'smooth' });
    if (window.location.hash === '#rewrite') setTab('rewrite');
  }, [scan?.job_id]);

  const rewrite = emp?.rewrite;
  const canApprove = isHr && rewrite?.status === 'pending_hr_approval';
  const catName = (c: string) => tf('cat.' + c, c);

  const decide = async (decision: string) => {
    setErr(null);
    if (reason.trim().length < 5) return setErr(t('employer.err_reason'));
    try {
      await api.post(`/api/runs/${runId}/jd-rewrite/decision`, { decision, reason, edited_text: decision === 'edit' ? edited : undefined });
      setReason('');
      setEdited(null);
      await loadEmp();
      toast(t('employer.saved'), 'success');
    } catch (e: any) {
      setErr(e.message);
    }
  };
  const answer = async (claimId: string) => {
    setErr(null);
    const a = answers[claimId];
    if (!a?.resolution || (a.note ?? '').trim().length < 5) return setErr(t('employer.err_answer'));
    try {
      await api.post(`/api/runs/${runId}/claims/${claimId}/response`, a);
      await loadEmp();
      toast(t('employer.saved'), 'success');
    } catch (e: any) {
      setErr(e.message);
    }
  };

  // ---- highlighting
  const flagMark = (raw: string): LineMark | null => {
    const fs = (scan?.flags ?? []).filter((f: any) => f.kind === 'text' && norm(raw) === norm(f.text));
    if (!fs.length) return null;
    const top = fs.reduce((a: any, b: any) => (SEV[b.severity] > SEV[a.severity] ? b : a));
    return { tone: top.severity, tags: fs.map((f: any) => catName(f.category)) };
  };
  const originalLines = useMemo(() => new Set((scan?.job_text ?? '').split('\n').map(norm).filter(Boolean)), [scan?.job_text]);
  const rewriteMark = (raw: string): LineMark | null => {
    if (originalLines.has(norm(raw))) return null;
    const ch = (rewrite?.changes ?? scan?.suggested_rewrite?.changes ?? []).find((c: any) => c.after && norm(c.after) === norm(raw));
    if (!ch) return /^Apply\b/.test(norm(raw)) || norm(raw).startsWith('What you need') ? null : { tone: 'new', tags: [t('employer.ch_edited')] };
    return { tone: 'new', tags: [t('employer.ch_' + ch.kind) + ': ' + ch.categories.map(catName).join(', ')] };
  };

  if (scan && !scan.job_text) {
    return (
      <>
        <PageHead step="employer" icon="building" title={t('employer.title')} sub={t('employer.sub_none')} />
        <EmptyState kind="analysis" title={t('common.old_run')} text={t('common.old_run_text')} />
      </>
    );
  }
  if (!scan) {
    return (
      <>
        <PageHead step="employer" icon="building" title={t('employer.title')} sub={t('employer.sub_none')} />
        <NeedsAnalysis ready={false}>{null}</NeedsAnalysis>
      </>
    );
  }

  const flags: any[] = scan.flags ?? [];
  const high = flags.filter((f) => f.severity === 'high').length;
  const missing = flags.filter((f) => f.kind === 'missing');
  const flaggedCats = new Set(flags.map((f) => f.category));
  const total = scan.categories_total ?? CATS.length;
  const passedChecks = CATS.filter((c) => !flaggedCats.has(c)).length;
  const facts = scan.facts ?? {};
  // "At a glance" chips are read from the ad text itself, so each tab shows what that version actually says.
  const factChips = (text: string) => {
    const modes = ['hybrid', 'remote', 'onsite'].filter((m) => new RegExp(m === 'onsite' ? 'on-?site' : `\\b${m}\\b`, 'i').test(text));
    const hours = text.match(/\d{1,2}[:.]\d{2}\s*(?:to|-)\s*\d{1,2}[:.]\d{2}(?:\s*IST)?/)?.[0];
    return [
      { icon: 'map', text: scan.employer_city ?? '' },
      { icon: 'home', text: modes.length ? modes.map((m) => tf('mode.' + m, m)).join(' / ') : t('employer.fact_mode_none') },
      { icon: 'time-entry-request', text: hours ?? t('employer.fact_hours_none') },
    ].filter((f) => f.text);
  };
  const rwStatus = rewrite?.status ?? scan.suggested_rewrite?.status;
  const rwKey = rwStatus?.startsWith('approved') ? 'approved' : rwStatus?.startsWith('rejected') ? 'rejected' : rwStatus === 'not_needed' ? 'not_needed' : 'pending';
  const removed = (rewrite?.changes ?? scan.suggested_rewrite?.changes ?? []).filter((c: any) => c.kind === 'removed');

  return (
    <>
      <PageHead step="employer" icon="building" title={t('employer.title')} sub={t('employer.sub2', { employer: scan.employer_short ?? scan.employer, role: scan.job_title })}
        actions={<InfoTip><b>{t('employer.info_title')}</b><p>{t('employer.info')}</p></InfoTip>} />

      {/* ---- verdict + numbers */}
      <section className={`emp-hero ${flags.length ? 'bad' : 'good'}`} data-testid="employer-verdict">
        <div className="emp-id">
          <span className="ad-logo big" aria-hidden="true">{(scan.employer_short ?? scan.employer).slice(0, 1)}</span>
          <div>
            <span className="emp-name">{scan.employer}</span>
            <span className="muted small">{scan.employer_industry} · {scan.employer_city} · {scan.job_title}</span>
            <h2>{flags.length ? t('employer.verdict_bad', { n: flags.length }) : t('employer.verdict_good')}</h2>
            <p>{flags.length ? t('employer.verdict_bad_text', { high }) : t('employer.verdict_good_text')}</p>
            <Chip tone="warn">{t('employer.simulated')}</Chip>
          </div>
        </div>
        <div className="emp-stats">
          <div className={`stat ${flags.length ? 'bad' : 'good'}`}><b>{flags.length}</b><span>{t('employer.stat_barriers')}</span><small>{t('employer.stat_serious', { n: high })}</small></div>
          <div className="stat"><b>{passedChecks}/{total}</b><span>{t('employer.stat_checks')}</span></div>
          <div className={`stat ${scan.conflict_count ? 'warn' : 'good'}`}><b>{scan.claims.length}</b><span>{t('employer.stat_claims')}</span><small>{t('employer.stat_conflicts', { n: scan.conflict_count ?? 0 })}</small></div>
          <div className={`stat ${rwKey === 'approved' ? 'good' : rwKey === 'rejected' ? 'bad' : 'warn'}`}><b><Icon name={rwKey === 'approved' ? 'accept' : rwKey === 'rejected' ? 'decline' : 'pending'} /></b><span>{t('employer.stat_rewrite')}</span><small>{t('employer.rw_' + rwKey)}</small></div>
        </div>
      </section>

      {/* ---- the ad */}
      <Card title={t('employer.ad_title')} icon="document" className="ad-card">
        <div className="seg ad-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === 'original'} className={tab === 'original' ? 'on' : ''} onClick={() => setTab('original')} data-testid="tab-original">
            {t('employer.t_original')} <span className="tab-count bad">{flags.length}</span>
          </button>
          <button type="button" role="tab" aria-selected={tab === 'rewrite'} className={tab === 'rewrite' ? 'on' : ''} onClick={() => setTab('rewrite')} disabled={!rewrite && !scan.suggested_rewrite?.text} data-testid="tab-rewrite">
            {t('employer.t_rewrite')} <span className={`tab-count ${rwKey === 'approved' ? 'good' : 'warn'}`}>{t('employer.rw_short_' + rwKey)}</span>
          </button>
          <button type="button" role="tab" aria-selected={tab === 'improved'} className={tab === 'improved' ? 'on' : ''} onClick={() => setTab('improved')} disabled={!improved} data-testid="tab-improved">
            {t('employer.t_improved')} <span className="tab-count good">0</span>
          </button>
        </div>

        {tab === 'original' && (
          <>
            <p className="muted small ad-hint"><Icon name="hint" aria-hidden="true" /> {t('employer.original_hint')}</p>
            <JobAd text={scan.job_text} facts={factChips(scan.job_text)} mark={flagMark} testId="ad-original"
              footer={missing.length > 0 && (
                <div className="ad-missing">
                  <h4><Icon name="alert" aria-hidden="true" /> {t('employer.missing_title')}</h4>
                  <ul>{missing.map((f) => <li key={f.flag_id} className={f.severity}><b>{catName(f.category)}</b><span>{flagWhy(i18n, f)}</span></li>)}</ul>
                </div>
              )} />
          </>
        )}

        {tab === 'rewrite' && (
          <>
            <p className="muted small ad-hint"><Icon name="edit" aria-hidden="true" /> {t('employer.rewrite_hint')}</p>
            {canApprove ? (
              <TextArea rows={18} value={edited ?? rewrite.suggested} onInput={(e: any) => setEdited(e.target.value)} accessibleName={t('employer.t_rewrite')} />
            ) : (
              <JobAd text={rewrite?.suggested ?? scan.suggested_rewrite?.text ?? ''} facts={factChips(rewrite?.suggested ?? scan.suggested_rewrite?.text ?? '')} mark={rewriteMark} testId="ad-rewrite"
                footer={removed.length > 0 && (
                  <div className="ad-removed">
                    <h4><Icon name="delete" aria-hidden="true" /> {t('employer.removed_title')}</h4>
                    <ul>{removed.map((c: any) => <li key={c.before}><s>{c.before}</s><span className="ad-tag"><Icon name="alert" aria-hidden="true" />{c.categories.map(catName).join(', ')}</span></li>)}</ul>
                  </div>
                )} />
            )}
            {canApprove && (
              <div className="approve-box">
                <Field label={t('employer.reason')}><Input value={reason} onInput={(e: any) => setReason(e.target.value)} accessibleName={t('employer.reason')} /></Field>
                <div className="row wrap">
                  <Button design="Positive" icon="accept" onClick={() => decide(edited ? 'edit' : 'approve')} data-testid="approve-rewrite">{edited ? t('employer.approve_edits') : t('employer.approve')}</Button>
                  <Button design="Negative" icon="decline" onClick={() => decide('reject')}>{t('employer.reject')}</Button>
                </div>
              </div>
            )}
            {!canApprove && rwKey === 'pending' && <Note tone="warn" icon="employee-approvals">{t('employer.needs_hr')}</Note>}
            {rwKey === 'approved' && <Note tone="good">{t('employer.rescan_ok')}</Note>}
            {rewrite?.history?.length > 0 && <p className="muted small">{t('employer.rw_by', { who: rewrite.history[rewrite.history.length - 1].actor, reason: rewrite.history[rewrite.history.length - 1].reason })}</p>}
          </>
        )}

        {tab === 'improved' && improved && (
          <>
            <Note tone="good" icon="accept">{t('employer.improved_hint', { employer: scan.employer_short ?? scan.employer, n: total })}</Note>
            <JobAd text={improved.text} facts={factChips(improved.text)} testId="ad-improved" />
          </>
        )}
        <ErrorNote error={tab !== 'original' ? err : null} />
      </Card>

      {/* ---- what the employer asks for + checks */}
      <div className="grid cols-2 emp-grid">
        <Card title={t('employer.asks_title')} icon="task">
          <p className="muted small">{t('employer.asks_sub')}</p>
          <ul className="asks" data-testid="employer-asks">
            {(facts.requirements ?? []).map((r: string, i: number) => {
              const cats: string[] = facts.requirement_flags?.[i] ?? [];
              return (
                <li key={r} className={cats.length ? 'bad' : 'good'}>
                  <Icon name={cats.length ? 'alert' : 'accept'} aria-hidden="true" />
                  <span>{r}</span>
                  <em>{cats.length ? cats.map(catName).join(', ') : t('employer.asks_ok')}</em>
                </li>
              );
            })}
          </ul>
        </Card>
        <Card title={t('employer.checked_n', { n: total })} icon="inspection">
          <ul className="checks">
            {CATS.map((c) => {
              const n = flags.filter((f) => f.category === c).length;
              return (
                <li key={c} className={n ? 'bad' : 'good'} data-testid={`cat-${c}`}>
                  <Icon name={n ? 'alert' : 'accept'} aria-hidden="true" /> {catName(c)}{n > 1 && <Chip tone="bad">{n}</Chip>}
                </li>
              );
            })}
          </ul>
        </Card>
      </div>

      {/* ---- findings */}
      <Card title={t('employer.flags')} icon="alert">
        <div className="flag-list">
          {flags.map((f) => (
            <div key={f.flag_id} className={`flag-item sev-${f.severity}`}>
              <div className="flag-top"><Badge status={f.severity} /><b>{catName(f.category)}</b></div>
              {f.text ? <p className="flag-quote">“{f.text}”</p> : <p className="flag-quote muted">{t('employer.not_in_ad')}</p>}
              <p className="small">{flagWhy(i18n, f)}</p>
              <span className="flag-fix"><Icon name={f.fix === 'remove' ? 'delete' : f.fix === 'add' ? 'add' : 'edit'} aria-hidden="true" /> {t('employer.fix_' + (f.fix ?? 'rewrite'))}</span>
            </div>
          ))}
          {flags.length === 0 && <p className="good-text">{t('employer.no_flags')}</p>}
        </div>
      </Card>

      {/* ---- claims */}
      <Card title={t('employer.claims')} icon="hint" aside={<InfoTip>{t('employer.claims_info')}</InfoTip>}>
        <span id="claims" className="anchor" />
        <p className="muted small">{t('employer.claims_sub')}</p>
        <div className="claim-grid">
          {scan.claims.map((c: any) => {
            const resp = emp?.claim_responses?.[c.claim_id];
            const a = answers[c.claim_id] ?? { resolution: '', note: '' };
            return (
              <div key={c.claim_id} className={`claim lvl-${c.evidence_level}`} data-testid={`claim-${c.claim_id}`}>
                <div className="claim-top"><b>{t('claim.' + c.claim_id + '.q')}</b><Badge status={c.evidence_level} /></div>
                <blockquote className="claim-answer"><Icon name="employee" aria-hidden="true" /> “{c.answer}”</blockquote>
                <div className="chip-row tight">
                  {(c.sources ?? []).map((s: any) => (
                    <Chip key={s.source_id} tone={s.effect === 'supports' ? 'good' : 'bad'} icon={s.effect === 'supports' ? 'accept' : 'decline'}>
                      {s.kind === 'job_ad' ? t('employer.src_job_ad') : t('employer.src_policy')} {t('employer.ev_' + s.effect)}
                    </Chip>
                  ))}
                  {c.consented_feedback?.supports > 0 && <Chip tone="info" icon="group">{t('employer.fb_agree', { n: c.consented_feedback.supports })}</Chip>}
                  {c.consented_feedback?.contradicts > 0 && <Chip tone="warn" icon="group">{t('employer.fb_disagree', { n: c.consented_feedback.contradicts })}</Chip>}
                </div>
                {c.note_codes?.filter((n: any) => !['feedback_supports', 'feedback_contradicts'].includes(n.code)).map((n: any, i: number) => <p key={i} className="muted small">{claimNote(i18n, n)}</p>)}
                {c.requires_human_review && (
                  resp ? (
                    <div className="claim-resp" data-testid={`claim-resp-${c.claim_id}`}>
                      <b><Icon name="accept" aria-hidden="true" /> {t('employer.responded', { what: t('employer.res_' + resp.resolution) })}</b>
                      <span className="small">“{resp.note}”</span>
                    </div>
                  ) : isHr ? (
                    <div className="claim-form">
                      <Chip tone="warn" icon="employee-approvals">{t('employer.needs_review')}</Chip>
                      <div className="res-choice" role="radiogroup" aria-label={t('employer.respond_title')}>
                        {['fix_ad', 'update_statement'].map((r) => (
                          <button key={r} type="button" role="radio" aria-checked={a.resolution === r} className={a.resolution === r ? 'on' : ''}
                            onClick={() => setAnswers({ ...answers, [c.claim_id]: { ...a, resolution: r } })} data-testid={`res-${c.claim_id}-${r}`}>{t('employer.res_opt_' + r)}</button>
                        ))}
                      </div>
                      <TextArea rows={2} placeholder={t('employer.respond_note')} value={a.note} onInput={(e: any) => setAnswers({ ...answers, [c.claim_id]: { ...a, note: e.target.value } })} accessibleName={t('employer.respond_note')} data-testid={`res-note-${c.claim_id}`} />
                      <Button design="Emphasized" onClick={() => answer(c.claim_id)} data-testid={`res-send-${c.claim_id}`}>{t('employer.respond_send')}</Button>
                    </div>
                  ) : (
                    <Chip tone="warn" icon="employee-approvals">{t('employer.wait_hr')}</Chip>
                  )
                )}
              </div>
            );
          })}
        </div>
        <ErrorNote error={tab === 'original' ? err : null} />
      </Card>
      <Note tone="info" icon="hint">{t('employer.disclaimer')}</Note>
      <StepFooter step="employer" />
    </>
  );
}
