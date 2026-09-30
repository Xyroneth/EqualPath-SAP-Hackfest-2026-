import { Icon, Input } from '@ui5/webcomponents-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, openEvidence } from '../api';
import { Badge, Card, Chip, Cta, ErrorNote, Field, InfoTip, NeedsAnalysis, Note, PageHead, Quote, StepFooter, Toggle } from '../components/ui';
import { useVisit } from '../hooks';
import { useI18n } from '../i18n';
import { capName, levelName } from '../lib/compose';
import { useApp } from '../state';

const LEVELS = ['awareness', 'basic', 'intermediate', 'advanced'];

export default function Skills() {
  const i18n = useI18n();
  const { t } = i18n;
  const nav = useNavigate();
  const { run, role, refresh, candidateId, toast } = useApp();
  const [dec, setDec] = useState<Record<string, any>>({});
  const [added, setAdded] = useState<any[]>([]);
  const [draft, setDraft] = useState({ name: '', what: '' });
  const [sharing, setSharing] = useState<Record<string, boolean> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const v = run?.values ?? {};
  const discovery = v.discovery;
  const waiting = run?.interrupt?.checkpoint === 'candidate_review' && run?.run?.status !== 'running';
  const mine = role === 'candidate';
  const skills: any[] = v.candidate_review ? v.skills : discovery?.skills ?? [];
  const share = sharing ?? run?.interrupt?.sharing ?? {};
  useVisit('/skills', !!discovery);

  const selfDeclared = skills.filter((s) => s.verification_status === 'self_declared' && s.candidate_action !== 'removed');
  const setD = (k: string, patch: any) => setDec((d) => ({ ...d, [k]: { action: 'edit', ...(d[k] ?? {}), ...patch } }));
  const open = (sid: string) => candidateId && openEvidence(candidateId, sid).then((ok) => !ok && toast(t('evidence.popup'), 'warning')).catch((e) => toast(e.message, 'error'));

  const approve = async () => {
    setErr(null);
    const list = Object.entries(dec).filter(([, d]) => d.action !== 'accept').map(([normalized_skill, d]) => ({ normalized_skill, action: d.action, skill_name: d.skill_name, proficiency: d.proficiency, reason: d.reason }));
    const missing = list.find((d) => !d.reason?.trim());
    if (missing) return setErr(t('skills.err_reason'));
    setBusy(true);
    try {
      await api.post(`/api/runs/${run.run.run_id}/candidate-review`, { decisions: list, added_skills: added.map((a) => ({ skill_name: a.name, evidence_quote: a.what, normalized_skill: 'other.' + a.name.toLowerCase().replace(/[^a-z0-9]+/g, '_') })), sharing: sharing ?? undefined, approve: true });
      await refresh();
      nav('/working');
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };

  return (
    <>
      <PageHead step="skills" icon="lightbulb" title={t('skills.title')} sub={t('skills.sub')} />
      <NeedsAnalysis ready={!!discovery}>
        {discovery && (
          <>
            <div className="chip-row">
              <Chip tone="accent" icon="lightbulb">{t('skills.count', { n: skills.length })}</Chip>
              <Chip tone="good" icon="accept">{t('skills.backed', { n: skills.length - selfDeclared.length })}</Chip>
              <Chip tone="warn" icon="alert">{t('skills.claimed', { n: selfDeclared.length })}</Chip>
              <InfoTip><b>{t('skills.info_title')}</b><p>{t('skills.info')}</p></InfoTip>
            </div>
            {selfDeclared.length > 0 && (
              <Note tone="warn" testId="self-declared-note">
                <b>{selfDeclared.map((s) => capName(i18n, s.normalized_skill, s.skill_name)).join(', ')}</b> — {t('skills.claimed_note')}
              </Note>
            )}
            {v.candidate_review && <Note tone="good">{t('skills.approved', { n: v.candidate_review.corrections.length })}</Note>}
            {!mine && waiting && <Note tone="info">{t('skills.staff_wait')}</Note>}
            <div className="skill-grid stagger">
              {skills.map((s, i) => {
                const d = dec[s.normalized_skill];
                const action = d?.action ?? 'accept';
                const gone = s.candidate_action === 'removed' || action === 'remove';
                const fileSource = /\.[a-z0-9]{2,4}$/i.test(s.source_id);
                return (
                  <article key={s.normalized_skill} className={`skill ${s.verification_status} ${gone ? 'gone' : ''}`} style={{ ['--i' as any]: i }} data-testid={`skill-${s.normalized_skill}`}>
                    <header>
                      <h3>{capName(i18n, s.normalized_skill, s.skill_name)}</h3>
                      <Badge status={s.verification_status} />
                    </header>
                    <div className="chip-row tight">
                      <Chip icon="bar-chart">{levelName(i18n, s.proficiency)}</Chip>
                      <span className="conf" title={t('skills.conf_hint')}>{t('skills.conf', { n: Math.round(s.confidence * 100) })}</span>
                    </div>
                    <Quote text={s.evidence_quote} source={s.source_id} onSource={fileSource && candidateId ? () => open(s.source_id) : undefined} />
                    {s.verification_status === 'self_declared' && <p className="hint-warn"><Icon name="alert" aria-hidden="true" /> {t('skills.only_claimed')}</p>}
                    {waiting && mine && (
                      <div className="skill-actions">
                        <div className="seg small" role="group">
                          {(['accept', 'edit', 'remove'] as const).map((a) => (
                            <button key={a} type="button" className={action === a ? 'on' : ''} aria-pressed={action === a} onClick={() => setDec((x) => ({ ...x, [s.normalized_skill]: { ...(x[s.normalized_skill] ?? {}), action: a } }))} data-testid={`${a}-${s.normalized_skill}`}>
                              {t('skills.' + a)}
                            </button>
                          ))}
                        </div>
                        {action === 'edit' && (
                          <div className="level-chips" role="group" aria-label={t('skills.level')}>
                            {LEVELS.map((l) => <button key={l} type="button" className={(d?.proficiency ?? s.proficiency) === l ? 'on' : ''} onClick={() => setD(s.normalized_skill, { proficiency: l })}>{levelName(i18n, l)}</button>)}
                          </div>
                        )}
                        {action !== 'accept' && <Input placeholder={t('skills.reason')} value={d?.reason ?? ''} onInput={(e: any) => setD(s.normalized_skill, { action, reason: e.target.value })} accessibleName={t('skills.reason')} data-testid={`reason-${s.normalized_skill}`} />}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>

            {waiting && mine && (
              <>
                <div className="grid cols-2">
                  <Card title={t('skills.add')} icon="add">
                    <div className="form-grid">
                      <Field label={t('skills.add_name')}><Input value={draft.name} onInput={(e: any) => setDraft({ ...draft, name: e.target.value })} accessibleName={t('skills.add_name')} /></Field>
                      <Field label={t('skills.add_what')}><Input value={draft.what} onInput={(e: any) => setDraft({ ...draft, what: e.target.value })} accessibleName={t('skills.add_what')} /></Field>
                    </div>
                    <button type="button" className="link-btn" onClick={() => { if (draft.name.length > 1 && draft.what.length > 7) { setAdded([...added, draft]); setDraft({ name: '', what: '' }); } else setErr(t('skills.err_add')); }}>+ {t('skills.add_btn')}</button>
                    {added.map((a) => <div key={a.name} className="chip-row tight"><Chip icon="add">{a.name}</Chip><Badge status="self_declared" /></div>)}
                  </Card>
                  <Card title={t('skills.share')} icon="shield">
                    <Toggle label={t('profile.c_share')} checked={!!share.share_with_employer} onChange={(x) => setSharing({ ...share, share_with_employer: x })} />
                    <Toggle label={t('profile.c_acc')} checked={!!share.share_accommodations} onChange={(x) => setSharing({ ...share, share_accommodations: x })} />
                  </Card>
                </div>
                <ErrorNote error={err} />
                <div className="actions-row">
                  <Cta onClick={approve} loading={busy} testId="approve-profile">{t('skills.approve')}</Cta>
                  <span className="muted small">{t('skills.approve_hint')}</span>
                </div>
              </>
            )}
          </>
        )}
      </NeedsAnalysis>
      {discovery && !waiting && <StepFooter step="skills" />}
    </>
  );
}
