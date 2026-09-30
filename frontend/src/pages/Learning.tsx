import { Button, Dialog, Icon, Input, Option, Select, TextArea } from '@ui5/webcomponents-react';
import { useState } from 'react';
import { api } from '../api';
import { Badge, Chip, ErrorNote, Field, InfoTip, NeedsAnalysis, Note, PageHead, StepFooter } from '../components/ui';
import { useVisit } from '../hooks';
import { useI18n } from '../i18n';
import { capName, milestoneEvidence, milestoneText } from '../lib/compose';
import { useApp } from '../state';

export default function Learning() {
  const i18n = useI18n();
  const { t } = i18n;
  const { run, role, refresh, toast } = useApp();
  const [dlg, setDlg] = useState<any>(null);
  const [form, setForm] = useState({ evidence_kind: 'reflection', title: '', content: '' });
  const [err, setErr] = useState<string | null>(null);
  const pw = run?.values?.pathway;
  const mine = role === 'candidate';
  useVisit('/learning', !!pw);

  const start = async (m: any) => {
    setErr(null);
    try {
      await api.post(`/api/runs/${run.run.run_id}/milestones/${m.milestone_id}/start`, {});
      toast(t('learn.started_toast'), 'success');
      await refresh();
    } catch (e: any) {
      setErr(e.message);
    }
  };
  const submit = async () => {
    setErr(null);
    if (form.content.trim().length < 10) return setErr(t('learn.err_content'));
    try {
      await api.post(`/api/runs/${run.run.run_id}/milestones/${dlg.milestone_id}/evidence`, form);
      toast(t('learn.sent_toast'), 'success');
      setDlg(null);
      setForm({ evidence_kind: 'reflection', title: '', content: '' });
      await refresh();
    } catch (e: any) {
      setErr(e.message);
    }
  };
  return (
    <>
      <PageHead step="learning" icon="education" title={t('learn.title')}
        sub={pw ? t('learn.sub', { n: pw.milestones.length, hours: pw.total_hours, weeks: pw.estimated_weeks, weekly: pw.weekly_hours }) : t('learn.sub_none')}
        actions={<InfoTip><b>{t('learn.info_title')}</b><p>{t('learn.info')}</p></InfoTip>} />
      <NeedsAnalysis ready={!!pw}>
        {pw && (
          <>
            {!mine && <Note tone="info">{t('learn.staff_note')}</Note>}
            <ErrorNote error={err} />
            <ol className="milestones stagger">
              {pw.milestones.map((m: any, i: number) => {
                const sap = m.learning_asset_provider.startsWith('SAP');
                const ev = milestoneEvidence(i18n, m);
                return (
                  <li key={m.milestone_id} className="milestone" style={{ ['--i' as any]: i }} data-testid={`milestone-${m.milestone_id}`}>
                    <span className="ms-num">{i + 1}</span>
                    <div className="ms-body">
                      <header>
                        <h3>{capName(i18n, m.capability, m.gap)}</h3>
                        <div className="chip-row tight"><Badge status={m.status} /><Chip icon="history">{t('learn.hours', { n: m.estimated_hours })}</Chip><Badge status={m.progress} /></div>
                      </header>
                      <p className="ms-why">{milestoneText(i18n, m, 'why')}</p>
                      <div className="ms-steps">
                        <div className="ms-step">
                          <span className="ms-step-n">1</span>
                          <div>
                            <b>{t('learn.learn')}</b>
                            <span>{m.learning_asset_title} <small className="muted">· {sap ? 'SAP Learning' : t('learn.external')}</small></span>
                          </div>
                          <a className={`link-cta ${sap ? 'sap' : ''}`} href={m.learning_asset_url} target="_blank" rel="noopener noreferrer" data-testid={`open-${m.milestone_id}`}>
                            {sap ? t('learn.open_sap') : t('learn.open')} <Icon name="action" aria-hidden="true" />
                          </a>
                        </div>
                        <div className="ms-step"><span className="ms-step-n">2</span><div><b>{t('learn.practice')}</b><span>{milestoneText(i18n, m, 'task')}</span></div></div>
                        <div className="ms-step"><span className="ms-step-n">3</span><div><b>{t('learn.proof')}</b><span className="chips-inline">{ev.map((x) => <em key={x}>{x}</em>)}</span></div></div>
                      </div>
                      {m.submissions?.map((s: any) => <p key={s.submission_id} className="small">{s.title} <Badge status={s.status === 'pending_review' ? 'pending_review' : s.status} /></p>)}
                      {mine && (
                        <div className="row">
                          <Button onClick={() => start(m)} disabled={m.progress !== 'not_started'} data-testid={`start-${m.milestone_id}`}>{t('learn.mark_started')}</Button>
                          <Button design="Emphasized" onClick={() => { setDlg(m); setForm({ ...form, title: capName(i18n, m.capability, m.gap) }); }} disabled={m.progress === 'accepted'} data-testid={`submit-${m.milestone_id}`}>{t('learn.submit')}</Button>
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
            <p className="muted small">{t('learn.practice_link')} <a href="/practice" target="_blank" rel="noreferrer">/practice</a></p>
          </>
        )}
      </NeedsAnalysis>
      <Dialog open={!!dlg} headerText={t('learn.submit')} onClose={() => setDlg(null)}
        footer={<div className="dialog-footer"><Button design="Transparent" onClick={() => setDlg(null)}>{t('common.cancel')}</Button><Button design="Emphasized" onClick={submit} data-testid="send-evidence">{t('learn.send')}</Button></div>}>
        <div className="dialog-form">
          <p className="muted small">{dlg && milestoneEvidence(i18n, dlg).join(' · ')}</p>
          <Field label={t('learn.kind')}>
            <Select accessibleName={t('learn.kind')} onChange={(e) => setForm({ ...form, evidence_kind: e.detail.selectedOption.getAttribute('value')! })}>
              {['project', 'screenshot', 'assessment_result', 'reflection'].map((k) => <Option key={k} value={k} selected={form.evidence_kind === k}>{t('learn.k_' + k)}</Option>)}
            </Select>
          </Field>
          <Field label={t('evidence.name')}><Input value={form.title} onInput={(e: any) => setForm({ ...form, title: e.target.value })} accessibleName={t('evidence.name')} /></Field>
          <Field label={t('learn.content')}><TextArea rows={5} value={form.content} onInput={(e: any) => setForm({ ...form, content: e.target.value })} accessibleName={t('learn.content')} data-testid="evidence-content" /></Field>
          <ErrorNote error={err} />
        </div>
      </Dialog>
      {pw && <StepFooter step="learning" />}
    </>
  );
}
