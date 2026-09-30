import { Button, Dialog, Icon, Input, Option, Select, TextArea } from '@ui5/webcomponents-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Card, Chip, Cta, EmptyState, ErrorNote, Field, InfoTip, Note, PageHead, StepFooter, Toggle } from '../components/ui';
import { useI18n } from '../i18n';
import { useApp } from '../state';

const MODES = ['remote', 'hybrid', 'onsite'];
const GENDERS = ['prefer_not_to_say', 'female', 'male', 'non_binary', 'other'];
const BREAK_REASONS = ['caregiving', 'health', 'study', 'relocation', 'other'];
const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

export default function Profile() {
  const { t, tf } = useI18n();
  const nav = useNavigate();
  const { profile, setProfile, consent, setConsent, saveProfile, candidateId, resetDemo, toast, startOwn, startSample, isSample } = useApp();
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [langText, setLangText] = useState<string | null>(null);
  useEffect(() => setLangText(null), [candidateId, isSample, !profile]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!profile)
    return (
      <>
        <PageHead step="profile" title={t('profile.title')} />
        <EmptyState kind="evidence" title={t('profile.empty_title')} text={t('profile.empty_text')}
          action={<div className="row wrap center"><Cta onClick={() => startOwn()} testId="start-own">{t('home.start')}</Cta><Cta variant="ghost" onClick={() => startSample()}>{t('home.start_sample')}</Cta></div>} />
      </>
    );
  const wc = profile.work_conditions;
  const acc = profile.accommodations ?? { shareable_work_accommodations: [], private_note: '' };
  const set = (patch: any) => { setErr(null); setProfile({ ...profile, ...patch }); };
  const setWC = (patch: any) => set({ work_conditions: { ...wc, ...patch } });
  const toggleMode = (m: string) => setWC({ work_modes: wc.work_modes.includes(m) ? wc.work_modes.filter((x: string) => x !== m) : [...wc.work_modes, m] });

  const save = async () => {
    setErr(null);
    if (!consent.process_profile) return setErr(t('profile.err_consent'));
    if ((profile.display_name ?? '').trim().length < 2 || (profile.location_city ?? '').trim().length < 2) return setErr(t('profile.err_required'));
    if (!(profile.languages ?? []).length) return setErr(t('profile.err_languages'));
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
  const setBreak = (patch: any) => set({ career_break: { months: 0, reason: null, wording: '', ...(profile.career_break ?? {}), ...patch } });
  const num = (v: string) => (v === '' ? null : Number(v));
  return (
    <>
      <PageHead step="profile" icon="shield" title={t('profile.title')} sub={t('profile.sub')} />
      <Note tone="info" icon={isSample ? 'hint' : 'edit'} testId="profile-mode">{isSample ? t('profile.mode_sample') : t('profile.mode_own')}</Note>
      <div className="grid cols-2 stagger">
        <Card title={t('profile.about')} icon="person-placeholder">
          <div className="form-grid">
            <Field label={t('profile.name') + ' *'}><Input value={profile.display_name ?? ''} onInput={(e: any) => set({ display_name: e.target.value })} accessibleName={t('profile.name')} data-testid="profile-name" /></Field>
            <Field label={t('profile.city') + ' *'}><Input value={profile.location_city ?? ''} onInput={(e: any) => set({ location_city: e.target.value, location_wording: '', work_conditions: { ...wc, commute_city: e.target.value } })} accessibleName={t('profile.city')} data-testid="profile-city" /></Field>
            <Field label={t('profile.state')}><Input value={profile.location_state ?? ''} onInput={(e: any) => set({ location_state: e.target.value, location_wording: '' })} accessibleName={t('profile.state')} data-testid="profile-state" /></Field>
            <Field label={t('profile.languages') + ' *'} hint={t('profile.languages_hint')}>
              <Input value={langText ?? (profile.languages ?? []).join(', ')} onInput={(e: any) => { setLangText(e.target.value); set({ languages: e.target.value.split(',').map((x: string) => x.trim()).filter(Boolean) }); }} accessibleName={t('profile.languages')} data-testid="profile-languages" />
            </Field>
            <Field label={t('profile.experience')} hint={t('profile.experience_hint')}>
              <Input type="Number" value={String(profile.relevant_experience_years ?? 0)} onInput={(e: any) => set({ relevant_experience_years: Math.max(0, Number(e.target.value) || 0) })} accessibleName={t('profile.experience')} data-testid="profile-experience" />
            </Field>
            <Field label={t('profile.goal')}><Input value={profile.goal ?? ''} placeholder={t('profile.goal_ph')} onInput={(e: any) => set({ goal: e.target.value })} accessibleName={t('profile.goal')} data-testid="profile-goal" /></Field>
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
          <p className="muted small">{t('profile.fairness_optional')}</p>
          <div className="form-grid five">
            <Field label={t('profile.age')}><Input type="Number" value={profile.age == null ? '' : String(profile.age)} onInput={(e: any) => set({ age: num(e.target.value) })} accessibleName={t('profile.age')} data-testid="profile-age" /></Field>
            <Field label={t('profile.gender')}>
              <Select accessibleName={t('profile.gender')} onChange={(e) => set({ gender: e.detail.selectedOption.getAttribute('value') === 'prefer_not_to_say' ? null : e.detail.selectedOption.getAttribute('value') })} data-testid="profile-gender">
                {GENDERS.map((g) => <Option key={g} value={g} selected={(profile.gender ?? 'prefer_not_to_say') === g}>{tf('gender.' + g, cap(g))}</Option>)}
              </Select>
            </Field>
            <Field label={t('profile.break_years')}><Input type="Number" value={String(breakYears)} onInput={(e: any) => { const months = Math.max(0, Math.round((Number(e.target.value) || 0) * 12)); setBreak({ months, reason: months ? (profile.career_break?.reason ?? 'caregiving') : null }); }} accessibleName={t('profile.break_years')} data-testid="profile-break-years" /></Field>
            <Field label={t('profile.break_reason')}>
              <Select accessibleName={t('profile.break_reason')} disabled={!breakYears} onChange={(e) => setBreak({ reason: e.detail.selectedOption.getAttribute('value') })} data-testid="profile-break-reason">
                {BREAK_REASONS.map((r) => <Option key={r} value={r} selected={(profile.career_break?.reason ?? 'caregiving') === r}>{tf('breakreason.' + r, cap(r))}</Option>)}
              </Select>
            </Field>
            <Field label={t('profile.college')}><Input value={profile.college ?? ''} onInput={(e: any) => set({ college: e.target.value })} accessibleName={t('profile.college')} data-testid="profile-college" /></Field>
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
