import { Icon } from '@ui5/webcomponents-react';
import { useEffect, useState } from 'react';
import { api } from '../api';
import { AuditorTasks } from '../components/Tasks';
import { Badge, Card, Chip, EmptyState, InfoTip, PageHead } from '../components/ui';
import { useI18n } from '../i18n';
import { activityText, nodeName } from '../lib/compose';
import { useApp } from '../state';

export default function Activity() {
  const i18n = useI18n();
  const { t, tf } = i18n;
  const { run, runId, role } = useApp();
  const [audit, setAudit] = useState<any>(null);
  const [tick, setTick] = useState(0);
  const len = run?.timeline?.length ?? 0;
  useEffect(() => {
    const q = role === 'auditor' ? '' : runId ? `?run_id=${runId}` : null;
    if (q === null) return setAudit(null);
    api.get('/api/audit' + q).then(setAudit).catch(() => setAudit(null));
  }, [runId, len, run?.run?.status, role, tick]);
  const access = (audit?.events ?? []).filter((e: any) => e.event_type === 'evidence_viewed');
  const details = role === 'candidate' || role === 'counsellor';
  return (
    <>
      <PageHead icon="process" title={t('activity.title')} sub={role === 'auditor' ? t('activity.sub_auditor') : t('activity.sub')} actions={<InfoTip><b>{t('activity.info_title')}</b><p>{t('activity.info')}</p></InfoTip>} />
      {role === 'auditor' && <AuditorTasks events={audit?.events ?? []} onVerified={() => setTick((n) => n + 1)} />}
      {role === 'auditor' && audit && (
        <Card title={t('activity.access_title', { n: access.length })} icon="show">
          <span id="access-log" className="anchor" />
          <p className="muted small">{t('activity.access_sub')}</p>
          {access.length ? (
            <div className="scroll-x">
              <table className="tbl" data-testid="access-log">
                <thead><tr><th>{t('activity.time')}</th><th>{t('activity.actor')}</th><th>{t('activity.access_doc')}</th></tr></thead>
                <tbody>{access.slice().reverse().map((e: any) => (
                  <tr key={e.event_id}><td className="mono nowrap">{e.ts.slice(0, 19).replace('T', ' ')}</td><td>{e.actor}</td><td className="mono">{e.details?.source_id ?? '—'}</td></tr>
                ))}</tbody>
              </table>
            </div>
          ) : <p className="muted">{t('activity.access_none')}</p>}
        </Card>
      )}
      {run && (
        <Card title={t('activity.agents')} icon="group">
          <div className="pipeline">
            {run.nodes.map((n: any) => (
              <div key={n.node} className={`pnode ${n.status} k-${n.kind}`}>
                <span className="pnode-name">{nodeName(i18n, n.node, n.agent)}</span>
                <Badge status={n.status} />
              </div>
            ))}
          </div>
          <ol className="timeline">
            {run.timeline.map((e: any) => (
              <li key={e.audit_event_id} className={`tl k-${e.kind}`}>
                <div className="tl-head"><b>{nodeName(i18n, e.node, e.agent)}</b><span className="muted small mono">{e.duration_ms} ms{e.method ? ` · ${e.method}` : ''}</span></div>
                <p>{activityText(i18n, e)}</p>
                {details && <details><summary>{t('activity.details')}</summary><pre className="doc">{JSON.stringify({ inputs: e.inputs, outputs: e.outputs }, null, 2)}</pre></details>}
              </li>
            ))}
          </ol>
        </Card>
      )}
      {audit ? (
        <Card title={t('activity.audit', { n: audit.events.length })} icon="log" aside={<Badge status={audit.chain.valid ? 'completed' : 'failed'} label={audit.chain.valid ? t('activity.chain_ok') : t('activity.chain_bad')} />}>
          <p className="muted small">{t('activity.audit_text')}</p>
          <div className="scroll-x tall">
            <table className="tbl">
              <thead><tr><th>{t('activity.time')}</th><th>{t('activity.type')}</th><th>{t('activity.actor')}</th><th>{t('activity.summary')}</th></tr></thead>
              <tbody>{audit.events.slice().reverse().map((e: any) => (
                <tr key={e.event_id}><td className="mono nowrap">{e.ts.slice(0, 19).replace('T', ' ')}</td><td><Chip>{tf('audit.' + e.event_type, e.event_type)}</Chip></td><td>{e.actor}</td><td>{e.summary}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      ) : !run && <EmptyState kind="analysis" title={t('activity.none')} text={t('activity.none_text')} />}
    </>
  );
}
