import { Icon } from '@ui5/webcomponents-react';
import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cta, ErrorNote, Note } from '../components/ui';
import { useI18n } from '../i18n';
import { activityText, nodeName } from '../lib/compose';
import { useApp } from '../state';

const DEST: Record<string, Record<string, string>> = {
  candidate: { candidate_review: '/skills', role_selection: '/roles', final_review: '/gaps', evidence_request: '/review', completed: '/passport', rejected: '/review' },
  counsellor: { candidate_review: '/skills', role_selection: '/roles', final_review: '/review', evidence_request: '/review', completed: '/passport', rejected: '/review' },
  hr_reviewer: { final_review: '/review', completed: '/passport', rejected: '/review' },
  auditor: {},
};

/** Live view of the agents. It moves on by itself as soon as a human is needed or the work is finished. */
export default function Working() {
  const i18n = useI18n();
  const { t } = i18n;
  const nav = useNavigate();
  const { run, role, runId } = useApp();
  const entered = useRef(Date.now());

  useEffect(() => {
    if (!run) return;
    const status = run.run.status;
    if (status === 'running' || status === 'failed') return;
    const key = status === 'completed' ? 'completed' : status === 'rejected' ? 'rejected' : run.interrupt?.checkpoint;
    const dest = DEST[role]?.[key] ?? (role === 'auditor' ? '/activity' : '/review');
    const wait = Math.max(500, 1500 - (Date.now() - entered.current));
    const id = window.setTimeout(() => nav(dest, { replace: true }), wait);
    return () => window.clearTimeout(id);
  }, [run, role, nav]);

  if (!runId)
    return (
      <div className="empty"><h2>{t('work.none')}</h2><Cta onClick={() => nav('/evidence')}>{t('gate.add_evidence')}</Cta></div>
    );
  const nodes: any[] = run?.nodes ?? [];
  const done = nodes.filter((n) => n.status === 'completed').length;
  const total = nodes.length || 12;
  const timeline: Record<string, any> = Object.fromEntries((run?.timeline ?? []).map((e: any) => [e.node, e]));
  const failed = run?.run?.status === 'failed';
  return (
    <div className="working" data-testid="working">
      <div className="working-head">
        <span className={`work-orb ${failed ? 'bad' : ''}`}><Icon name={failed ? 'alert' : 'process'} aria-hidden="true" /></span>
        <h1>{failed ? t('work.failed') : done >= total ? t('work.done') : t('work.title')}</h1>
        <p className="sub">{failed ? run.run.error : t('work.sub')}</p>
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label={t('work.title')}>
          <div className="progress-fill" style={{ width: `${Math.round((done / total) * 100)}%` }} />
        </div>
        <span className="progress-count">{t('work.count', { done, total })}</span>
      </div>
      <ol className="agent-list">
        {nodes.map((n, i) => {
          const entry = timeline[n.node];
          return (
            <li key={n.node} className={`agent ${n.status} ${n.kind}`} style={{ ['--i' as any]: i }} data-testid={`node-${n.node}`}>
              <span className="agent-dot">
                {n.status === 'completed' ? <Icon name="accept" aria-hidden="true" /> : n.status === 'running' ? <span className="spinner" aria-hidden="true" /> : n.kind === 'human' ? <Icon name="employee-approvals" aria-hidden="true" /> : <span className="dot-empty" />}
              </span>
              <div>
                <b>{nodeName(i18n, n.node, n.agent)}</b>
                {entry && <span>{activityText(i18n, entry)}</span>}
                {!entry && n.status === 'waiting_for_human' && <span>{t('work.waiting_human')}</span>}
              </div>
            </li>
          );
        })}
      </ol>
      {failed ? <ErrorNote error={run.run.error} /> : <Note tone="info">{t('work.note')}</Note>}
    </div>
  );
}
