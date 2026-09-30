import { Icon } from '@ui5/webcomponents-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Card, Chip, Cta, ErrorNote, InfoTip, Meter, NeedsAnalysis, Note, PageHead, StepFooter } from '../components/ui';
import { useVisit } from '../hooks';
import { useI18n } from '../i18n';
import { roleSummary, roleTitle } from '../lib/compose';
import { useApp } from '../state';

const COMPONENTS = ['capability_coverage', 'evidence_strength', 'work_condition_fit', 'entry_realism', 'gap_feasibility'];

export default function Roles() {
  const i18n = useI18n();
  const { t } = i18n;
  const nav = useNavigate();
  const { run, role, refresh } = useApp();
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const ranking = run?.values?.ranking;
  const chosen = run?.values?.selected_role_id;
  const waiting = run?.interrupt?.checkpoint === 'role_selection' && run?.run?.status !== 'running';
  useVisit('/roles', !!ranking);

  const choose = async (id: string) => {
    setBusy(id);
    setErr(null);
    try {
      await api.post(`/api/runs/${run.run.run_id}/role-selection`, { role_id: id });
      await refresh();
      nav('/working');
    } catch (e: any) {
      setErr(e.message);
      setBusy(null);
    }
  };
  const cond = (r: any, k: string) => (r.conditions[k]?.fit ? 'good' : 'bad');
  return (
    <>
      <PageHead step="roles" icon="target-group" title={t('roles.title')} sub={t('roles.sub')} actions={<InfoTip><b>{t('roles.info_title')}</b><p>{t('roles.info')}</p></InfoTip>} />
      <NeedsAnalysis ready={!!ranking}>
        {ranking && (
          <>
            {role !== 'candidate' && waiting && <Note tone="info">{t('roles.staff_wait')}</Note>}
            <ErrorNote error={err} />
            <div className="grid cols-3 stagger">
              {ranking.top_roles.map((r: any, i: number) => {
                const rec = r.role_id === ranking.recommended_role_id;
                return (
                  <article key={r.role_id} className={`role-card ${rec ? 'rec' : ''} ${chosen === r.role_id ? 'chosen' : ''}`} style={{ ['--i' as any]: i }} data-testid={`role-${r.role_id}`}>
                    {rec && <span className="ribbon"><Icon name="favorite" aria-hidden="true" /> {t('roles.best')}</span>}
                    <h3>{roleTitle(i18n, r.role_id, r.title)}</h3>
                    <p className="muted">{roleSummary(i18n, r.role_id, r.summary)}</p>
                    <div className="chip-row tight">
                      <Chip tone={cond(r, 'work_mode')} icon={cond(r, 'work_mode') === 'good' ? 'accept' : 'decline'}>{t('roles.mode')}</Chip>
                      <Chip tone={cond(r, 'location')} icon={cond(r, 'location') === 'good' ? 'accept' : 'decline'}>{t('roles.location')}</Chip>
                      <Chip tone={cond(r, 'language')} icon={cond(r, 'language') === 'good' ? 'accept' : 'decline'}>{t('roles.language')}</Chip>
                    </div>
                    <div className="meters">{COMPONENTS.map((c) => <Meter key={c} value={r.components[c]} label={t('roles.c_' + c)} />)}</div>
                    <p className="role-facts">{t('roles.facts', { v: r.gap_counts.verified, total: r.gap_counts.verified + r.gap_counts.developing + r.gap_counts.missing, hours: r.hours })}</p>
                    {waiting && role === 'candidate' && <Cta onClick={() => choose(r.role_id)} loading={busy === r.role_id} variant={rec ? 'primary' : 'ghost'} testId={`select-${r.role_id}`}>{t('roles.choose')}</Cta>}
                    {chosen === r.role_id && <Chip tone="good" icon="accept">{t('roles.chosen')}</Chip>}
                  </article>
                );
              })}
            </div>
            <details className="more-roles">
              <summary>{t('roles.others', { n: ranking.other_roles.length })}</summary>
              <ul>{ranking.other_roles.map((r: any) => <li key={r.role_id}><b>{roleTitle(i18n, r.role_id, r.title)}</b> — {t('roles.c_capability_coverage')} {Math.round(r.components.capability_coverage * 100)}% · {t('roles.c_work_condition_fit')} {Math.round(r.components.work_condition_fit * 100)}%</li>)}</ul>
            </details>
          </>
        )}
      </NeedsAnalysis>
      {ranking && !waiting && <StepFooter step="roles" />}
    </>
  );
}
