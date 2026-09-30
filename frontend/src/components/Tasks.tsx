import { Button, Icon } from '@ui5/webcomponents-react';
import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useI18n } from '../i18n';
import { useApp } from '../state';
import { Chip } from './ui';

type Status = 'todo' | 'done' | 'locked' | 'none';

function TaskRow({ n, status, title, text, action, testId }: { n: number; status: Status; title: ReactNode; text: ReactNode; action?: ReactNode; testId: string }) {
  const { t } = useI18n();
  return (
    <li className={`task ${status}`} data-testid={testId} data-status={status}>
      <span className="task-n">{status === 'done' ? <Icon name="accept" aria-hidden="true" /> : status === 'locked' ? <Icon name="locked" aria-hidden="true" /> : n}</span>
      <div className="task-body">
        <div className="task-top"><b>{title}</b><Chip tone={status === 'done' ? 'good' : status === 'todo' ? 'warn' : 'neutral'}>{t('tasks.s_' + status)}</Chip></div>
        <p>{text}</p>
      </div>
      {action && <div className="task-act">{action}</div>}
    </li>
  );
}

function Panel({ role, title, sub, done, total, children }: { role: string; title: string; sub: string; done: number; total: number; children: ReactNode }) {
  const { t } = useI18n();
  return (
    <section className={`tasks-panel r-${role}`} data-testid="tasks-panel">
      <header>
        <div><h2>{title}</h2><p>{sub}</p></div>
        <div className="tasks-progress" aria-label={t('tasks.done_n', { done, total })}>
          <svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="15.5" className="trk" /><circle cx="18" cy="18" r="15.5" className="val" style={{ strokeDasharray: `${(done / Math.max(total, 1)) * 97.4} 97.4` }} /></svg>
          <span>{t('tasks.done_n', { done, total })}</span>
        </div>
      </header>
      <ol className="task-list">{children}</ol>
    </section>
  );
}

/** HR Reviewer = the employer side: fix the ad, answer what does not add up, then respond to the candidate. */
export function HrTasks() {
  const { t } = useI18n();
  const nav = useNavigate();
  const { runId, run } = useApp();
  const [s, setS] = useState<any>(null);
  const passport = !!run?.values?.passport;
  useEffect(() => {
    if (!runId || !run?.values?.employer_scan) return setS(null);
    api.get(`/api/runs/${runId}/employer-tasks`).then(setS).catch(() => setS(null));
  }, [runId, !!run?.values?.employer_scan, passport]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!s) return null;
  const by = Object.fromEntries(s.tasks.map((x: any) => [x.id, x]));
  const counted = s.tasks.filter((x: any) => x.status !== 'none');
  return (
    <Panel role="hr_reviewer" title={t('tasks.hr_title')} sub={t('tasks.hr_sub')} done={counted.filter((x: any) => x.status === 'done').length} total={counted.length}>
      <TaskRow n={1} testId="task-rewrite" status={by.rewrite.status} title={t('tasks.hr_rewrite')} text={by.rewrite.status === 'none' ? t('tasks.hr_rewrite_none') : t('tasks.hr_rewrite_d')}
        action={by.rewrite.status !== 'none' && <Button design={by.rewrite.status === 'todo' ? 'Emphasized' : 'Transparent'} icon="document" onClick={() => nav('/employer#rewrite')}>{t('tasks.open_rewrite')}</Button>} />
      <TaskRow n={2} testId="task-claims" status={by.claims.status} title={t('tasks.hr_claims')}
        text={by.claims.status === 'none' ? t('tasks.hr_claims_none') : t('tasks.hr_claims_d', { n: by.claims.open, total: by.claims.total })}
        action={by.claims.status !== 'none' && <Button design={by.claims.status === 'todo' ? 'Emphasized' : 'Transparent'} icon="hint" onClick={() => nav('/employer#claims')}>{t('tasks.open_claims')}</Button>} />
      <TaskRow n={3} testId="task-candidate" status={by.candidate.status} title={t('tasks.hr_candidate')}
        text={by.candidate.status === 'locked' ? t('tasks.locked_' + by.candidate.blocked_by) : t('tasks.hr_candidate_d')}
        action={by.candidate.status !== 'locked' && <Button design={by.candidate.status === 'todo' ? 'Emphasized' : 'Transparent'} icon="document" onClick={() => nav('/passport')} data-testid="task-candidate-open">{t('tasks.open_passport')}</Button>} />
    </Panel>
  );
}

/** Auditor = oversight: prove the log is intact, sign off the fairness check, see who opened evidence, keep a report. */
export function AuditorTasks({ events, onVerified }: { events: any[]; onVerified: () => void }) {
  const { t } = useI18n();
  const nav = useNavigate();
  const { runId, run } = useApp();
  const [check, setCheck] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<any>(null);
  const [downloaded, setDownloaded] = useState(false);
  const [sawAccess, setSawAccess] = useState(false);
  useEffect(() => {
    if (runId && run?.values?.bias_audit) api.get(`/api/runs/${runId}/fairness-review`).then((r) => setReview(r.review)).catch(() => setReview(null));
  }, [runId, !!run?.values?.bias_audit]); // eslint-disable-line react-hooks/exhaustive-deps
  const verified = check ?? (events.some((e) => e.event_type === 'audit_verified') ? { valid: true, fromLog: true } : null);
  const verify = async () => {
    setBusy(true);
    try {
      setCheck(await api.post('/api/audit/verify', {}));
      onVerified();
    } finally {
      setBusy(false);
    }
  };
  const download = () => {
    const rows = [['time_utc', 'type', 'who', 'what', 'run', 'fingerprint']].concat(
      events.map((e) => [e.ts, e.event_type, e.actor, e.summary, e.run_id ?? '', e.hash]),
    );
    const csv = rows.map((r) => r.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: `equalpath-audit-report-${new Date().toISOString().slice(0, 10)}.csv` });
    a.click();
    URL.revokeObjectURL(url);
    setDownloaded(true);
  };
  const tasks: Status[] = [verified ? 'done' : 'todo', !run?.values?.bias_audit ? 'locked' : review ? 'done' : 'todo', sawAccess ? 'done' : 'todo', downloaded ? 'done' : 'todo'];
  return (
    <Panel role="auditor" title={t('tasks.au_title')} sub={t('tasks.au_sub')} done={tasks.filter((x) => x === 'done').length} total={tasks.length}>
      <TaskRow n={1} testId="task-verify" status={tasks[0]} title={t('tasks.au_verify')}
        text={check ? (check.valid ? t('tasks.verified', { n: check.events, hash: String(check.head ?? '').slice(0, 12) }) : t('tasks.verified_bad', { id: check.broken_at })) : t('tasks.au_verify_d')}
        action={<Button design={verified ? 'Transparent' : 'Emphasized'} icon="shield" onClick={verify} disabled={busy} data-testid="verify-log">{t('tasks.verify_btn')}</Button>} />
      <TaskRow n={2} testId="task-fairness" status={tasks[1]} title={t('tasks.au_fair')}
        text={review ? t('tasks.au_fair_done', { finding: t('fair.audited_' + review.finding) }) : !run?.values?.bias_audit ? t('tasks.no_run_text') : t('tasks.au_fair_d')}
        action={run?.values?.bias_audit && <Button design={review ? 'Transparent' : 'Emphasized'} icon="compare" onClick={() => nav('/fairness#signoff')}>{t('tasks.open_fairness')}</Button>} />
      <TaskRow n={3} testId="task-access" status={tasks[2]} title={t('tasks.au_access')} text={t('tasks.au_access_d')}
        action={<Button design="Transparent" icon="show" onClick={() => { setSawAccess(true); document.getElementById('access-log')?.scrollIntoView({ behavior: 'smooth' }); }}>{t('tasks.see_list')}</Button>} />
      <TaskRow n={4} testId="task-report" status={tasks[3]} title={t('tasks.au_report')} text={t('tasks.au_report_d')}
        action={<Button design="Transparent" icon="download" onClick={download} data-testid="download-report">{t('tasks.download')}</Button>} />
    </Panel>
  );
}
