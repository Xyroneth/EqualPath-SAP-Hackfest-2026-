import { Button, Dialog, Icon, Input, TextArea } from '@ui5/webcomponents-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Card, Chip, Cta, EmptyState, ErrorNote, Field, InfoTip, Note, PageHead, StepFooter, Toggle } from '../components/ui';
import { useI18n } from '../i18n';
import { useApp } from '../state';

const MODES = ['remote', 'hybrid', 'onsite'];
const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

export default function Profile() {
  const { t, tf } = useI18n();
  const nav = useNavigate();
  const { profile, setProfile, consent, setConsent, saveProfile, candidateId, resetDemo, toast } = useApp();
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (!profile)
    return (
      <>
        <PageHead step="profile" title={t('profile.title')} />
        <EmptyState kind="evidence" title={t('profile.empty_title')} text={t('profile.empty_text')} action={<Cta onClick={() => nav('/')}>{t('profile.empty_cta')}</Cta>} />
      </>
    );
  const wc = profile.work_conditions;
  const acc = profile.accommodations ?? { shareable_work_accommodations: [], private_note: '' };
  const set = (patch: any) => setProfile({ ...profile, ...patch });
  const setWC = (patch: any) => set({ work_conditions: { ...wc, ...patch } });
  const toggleMode = (m: string) => setWC({ work_modes: wc.work_modes.includes(m) ? wc.work_modes.filter((x: string) => x !== m) : [...wc.work_modes, m] });

  const save = async () => {
    setErr(null);
    if (!consent.process_profile) return setErr(t('profile.err_consent'));
    if (!profile.display_name?.trim() || !profile.location_city?.trim()) return setErr(t('profile.err_required'));
    if (!wc.work_modes.length) return setErr(t('profile.err_modes'));
    setBusy(true);
    try {
      await saveProfile();
      nav('/evidence');
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  const exportData = async () => {
    try {
      await api.saveAs(`/api/candidates/${candidateId}/export`, `equalpath-${candidateId}.json`);
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };
  const deleteData = async () => {
    await api.del(`/api/candidates/${candidateId}`);
    setConfirmDelete(false);
    resetDemo();
    toast(t('profile.deleted'), 'success');
    nav('/');
  };
  const breakYears = Math.round((profile.career_break?.months ?? 0) / 12);
  return (
    <>
      <PageHead step="profile" icon="shield" title={t('profile.title')} sub={t('profile.sub')} />
      <div className="grid cols-2 stagger">
        <Card title={t('profile.about')} icon="person-placeholder">
          <div className="form-grid">
            <Field label={t('profile.name')}><Input value={profile.display_name} onInput={(e: any) => set({ display_name: e.target.value })} accessibleName={t('profile.name')} /></Field>
            <Field label={t('profile.city')}><Input value={profile.location_city} onInput={(e: any) => set({ location_city: e.target.value, work_conditions: { ...wc, commute_city: e.target.value } })} accessibleName={t('profile.city')} /></Field>
            <Field label={t('profile.languages')} hint={t('profile.languages_hint')}>
              <Input value={(profile.languages ?? []).join(', ')} onInput={(e: any) => set({ languages: e.target.value.split(',').map((x: string) => x.trim()).filter(Boolean) })} accessibleName={t('profile.languages')} />
            </Field>
            <Field label={t('profile.goal')}><Input value={profile.goal} onInput={(e: any) => set({ goal: e.target.value })} accessibleName={t('profile.goal')} /></Field>
          </div>
        </Card>

        <Card title={t('profile.work')} icon="calendar">
          <Field label={t('profile.modes')}>
            <div className="mode-chips" role="group" aria-label={t('profile.modes')}>
              {MODES.map((m) => (
                <button key={m} type="button" className={`mode-chip ${wc.work_modes.includes(m) ? 'on' : ''}`} aria-pressed={wc.work_modes.includes(m)} onClick={() => toggleMode(m)} data-testid={`mode-${m}`}>
                  {wc.work_modes.includes(m) && <Icon name="accept" aria-hidden="true" />}{tf('mode.' + m, cap(m))}
                </button>
              ))}
            </div>
          </Field>
          <Toggle label={t('profile.relocate')} checked={!!wc.can_relocate} onChange={(v) => setWC({ can_relocate: v })} />
          <div className="form-grid">
            <Field label={t('profile.hours')}><Input type="Number" value={String(wc.weekly_learning_hours)} onInput={(e: any) => setWC({ weekly_learning_hours: Number(e.target.value) || 1 })} accessibleName={t('profile.hours')} /></Field>
            <Field label={t('profile.schedule')}><TextArea rows={2} value={wc.schedule_needs} onInput={(e: any) => setWC({ schedule_needs: e.target.value })} accessibleName={t('profile.schedule')} /></Field>
          </div>
        </Card>

        <Card title={<>{t('profile.permissions')}<InfoTip>{t('profile.permissions_info')}</InfoTip></>} icon="key">
          <Toggle label={t('profile.c_process')} desc={t('profile.c_process_d')} checked={consent.process_profile} onChange={(v) => setConsent({ ...consent, process_profile: v })} testId="consent-process" />
          <Toggle label={t('profile.c_ai')} desc={t('profile.c_ai_d')} checked={consent.use_llm_with_redaction} onChange={(v) => setConsent({ ...consent, use_llm_with_redaction: v })} />
          <Toggle label={t('profile.c_share')} desc={t('profile.c_share_d')} checked={consent.share_with_employer} onChange={(v) => setConsent({ ...consent, share_with_employer: v })} testId="consent-share" />
          <Toggle label={t('profile.c_acc')} desc={t('profile.c_acc_d')} checked={consent.share_accommodations} onChange={(v) => setConsent({ ...consent, share_accommodations: v })} testId="consent-acc" />
        </Card>

        <Card title={<>{t('profile.access')}<InfoTip label={t('common.more_info')}><b>{t('profile.access_info_title')}</b><p>{t('profile.access_info')}</p></InfoTip></>} icon="accessibility">
          <Field label={t('profile.acc_share')} hint={t('profile.acc_share_hint')}>
            <TextArea rows={3} value={(acc.shareable_work_accommodations ?? []).join('\n')} accessibleName={t('profile.acc_share')}
              onInput={(e: any) => set({ accommodations: { ...acc, shareable_work_accommodations: e.target.value.split('\n').filter((l: string) => l.trim()) } })} />
          </Field>
          <Field label={<span className="with-icon"><Icon name="locked" aria-hidden="true" /> {t('profile.acc_private')}</span>} hint={t('profile.acc_private_hint')}>
            <TextArea rows={2} value={acc.private_note ?? ''} accessibleName={t('profile.acc_private')} onInput={(e: any) => set({ accommodations: { ...acc, private_note: e.target.value } })} />
          </Field>
        </Card>

        <Card title={<>{t('profile.fairness')}<InfoTip>{t('profile.fairness_info')}</InfoTip></>} icon="compare" className="span-2">
          <div className="fact-row">
            <div className="fact"><span>{t('profile.age')}</span><b>{profile.age}</b></div>
            <div className="fact"><span>{t('profile.gender')}</span><b data-testid="gender-value">{tf('gender.' + profile.gender, cap(profile.gender ?? ''))}</b></div>
            <div className="fact"><span>{t('profile.break')}</span><b>{t('profile.break_value', { years: breakYears, reason: tf('breakreason.' + profile.career_break?.reason, cap(profile.career_break?.reason ?? '')) })}</b></div>
          </div>
        </Card>
      </div>

      <ErrorNote error={err} />
      <div className="actions-row">
        <Cta onClick={save} loading={busy} testId="save-profile">{t('profile.save')}</Cta>
        {!consent.process_profile && <Chip tone="warn" icon="alert">{t('profile.consent_needed')}</Chip>}
      </div>

      {candidateId && (
        <Card title={t('profile.data')} icon="user-settings" className="data-card">
          <p className="muted">{t('profile.data_text')}</p>
          <div className="row">
            <Button icon="download" design="Transparent" onClick={exportData}>{t('profile.export')}</Button>
            <Button icon="delete" design="Negative" onClick={() => setConfirmDelete(true)} data-testid="delete-data">{t('profile.delete')}</Button>
          </div>
        </Card>
      )}
      <Dialog open={confirmDelete} headerText={t('profile.delete')} onClose={() => setConfirmDelete(false)}
        footer={<div className="dialog-footer"><Button design="Transparent" onClick={() => setConfirmDelete(false)}>{t('common.cancel')}</Button><Button design="Negative" onClick={deleteData} data-testid="confirm-delete">{t('profile.delete_yes')}</Button></div>}>
        <p>{t('profile.delete_confirm')}</p>
      </Dialog>
      <StepFooter step="profile" hideNext />
    </>
  );
}
