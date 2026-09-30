import { Button, Icon, Input, Option, Select, TextArea } from '@ui5/webcomponents-react';
import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileIcon } from '../art/Art';
import { api, openEvidence } from '../api';
import { Card, Chip, Cta, EmptyState, ErrorNote, Field, Note, PageHead, StepFooter } from '../components/ui';
import { useI18n } from '../i18n';
import { useApp } from '../state';

const TYPES = ['resume', 'work_sample', 'project', 'certificate'];
const FORMATS = ['PDF', 'Word', 'PowerPoint', 'Excel', 'CSV', 'TXT · MD', 'Code', 'PNG · JPG'];
const size = (b: number) => (b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export default function Evidence() {
  const { t, tf } = useI18n();
  const nav = useNavigate();
  const { role, candidateId, docs, refreshDocs, startRun, system, toast } = useApp();
  const [mode, setMode] = useState<'file' | 'text'>('file');
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [type, setType] = useState('work_sample');
  const [desc, setDesc] = useState('');
  const [text, setText] = useState('');
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const mine = role === 'candidate';

  if (!candidateId)
    return (
      <>
        <PageHead step="evidence" title={t('evidence.title')} />
        <EmptyState kind="evidence" title={t('evidence.no_profile')} text={t('evidence.no_profile_text')} action={<Cta onClick={() => nav('/profile')}>{t('gate.set_up')}</Cta>} />
      </>
    );

  const pick = (f: File | undefined | null) => {
    if (!f) return;
    setFile(f);
    setTitle((v) => v || f.name.replace(/\.[^.]+$/, ''));
    setErr(null);
  };
  const isImage = !!file && /\.(png|jpe?g)$/i.test(file.name);
  const add = async () => {
    setErr(null);
    setBusy(true);
    try {
      if (mode === 'file') {
        if (!file) throw new Error(t('evidence.err_nofile'));
        const form = new FormData();
        form.append('file', file);
        form.append('title', title || file.name);
        form.append('evidence_type', type);
        form.append('description', desc);
        await api.upload(`/api/candidates/${candidateId}/documents/upload`, form);
      } else {
        if (title.trim().length < 2 || text.trim().length < 20) throw new Error(t('evidence.err_text'));
        await api.post(`/api/candidates/${candidateId}/documents/text`, { title, evidence_type: type, text });
      }
      await refreshDocs();
      toast(t('evidence.added'), 'success');
      setFile(null); setTitle(''); setDesc(''); setText('');
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  const view = async (sid: string) => {
    try {
      if (!(await openEvidence(candidateId, sid))) toast(t('evidence.popup'), 'warning');
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };
  const remove = async (sid: string) => {
    await api.del(`/api/candidates/${candidateId}/documents/${encodeURIComponent(sid)}`);
    setConfirm(null);
    await refreshDocs();
  };
  const analyse = async () => {
    setStarting(true);
    setErr(null);
    try {
      await startRun();
      nav('/working');
    } catch (e: any) {
      setErr(e.message);
      setStarting(false);
    }
  };

  return (
    <>
      <PageHead step="evidence" icon="upload-to-cloud" title={t('evidence.title')} sub={mine ? t('evidence.sub') : t('evidence.sub_staff')} />
      {!mine && <Note tone="info" icon="shield">{t('evidence.staff_note')}</Note>}
      <div className={`evidence-layout ${mine ? '' : 'single'}`}>
        <div className="doc-grid stagger" data-testid="doc-grid">
          {docs.map((d, i) => (
            <article key={d.source_id} className="doc-card" style={{ ['--i' as any]: i }} data-testid={`doc-${d.source_id}`}>
              <FileIcon kind={d.kind} />
              <div className="doc-main">
                <h3 title={d.title}>{d.title}</h3>
                <div className="doc-meta">
                  <Chip tone="accent">{tf('etype.' + d.evidence_type, d.evidence_type)}</Chip>
                  <span>{d.filename}</span>
                  <span>{size(d.size)}</span>
                </div>
              </div>
              <div className="doc-actions">
                <Button icon="action" design="Emphasized" onClick={() => view(d.source_id)} data-testid={`view-${d.source_id}`}>{t('common.view')}</Button>
                {mine && (confirm === d.source_id ? (
                  <span className="confirm-row">
                    <Button design="Negative" onClick={() => remove(d.source_id)}>{t('common.yes_remove')}</Button>
                    <Button design="Transparent" onClick={() => setConfirm(null)}>{t('common.no')}</Button>
                  </span>
                ) : (
                  <Button icon="delete" design="Transparent" accessibleName={`${t('common.remove')} ${d.title}`} onClick={() => setConfirm(d.source_id)} />
                ))}
              </div>
            </article>
          ))}
          {docs.length === 0 && <EmptyState kind="evidence" title={t('evidence.none')} text={t('evidence.none_text')} />}
        </div>

        {mine && (
          <aside className="evidence-side">
            <Card title={t('evidence.add')} icon="add">
              <div className="seg" role="group">
                <button type="button" className={mode === 'file' ? 'on' : ''} onClick={() => setMode('file')} aria-pressed={mode === 'file'}>{t('evidence.upload')}</button>
                <button type="button" className={mode === 'text' ? 'on' : ''} onClick={() => setMode('text')} aria-pressed={mode === 'text'}>{t('evidence.paste')}</button>
              </div>
              {mode === 'file' ? (
                <div
                  className={`dropzone ${drag ? 'drag' : ''} ${file ? 'has-file' : ''}`}
                  onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
                  onDragLeave={() => setDrag(false)}
                  onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
                  onClick={() => input.current?.click()}
                  role="button" tabIndex={0} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
                  aria-label={t('evidence.drop')} data-testid="dropzone"
                >
                  <input ref={input} type="file" hidden accept={system?.accepted_files} onChange={(e) => pick(e.target.files?.[0])} data-testid="file-input" />
                  {file ? (
                    <><Icon name="attachment" aria-hidden="true" /><b>{file.name}</b><span>{size(file.size)}</span></>
                  ) : (
                    <><Icon name="upload-to-cloud" aria-hidden="true" /><b>{t('evidence.drop')}</b><span>{t('evidence.drop_sub', { mb: system?.max_upload_mb ?? 8 })}</span></>
                  )}
                </div>
              ) : (
                <Field label={t('evidence.text')}><TextArea rows={5} value={text} onInput={(e: any) => setText(e.target.value)} accessibleName={t('evidence.text')} data-testid="paste-text" /></Field>
              )}
              {mode === 'file' && <div className="format-chips">{FORMATS.map((f) => <span key={f}>{f}</span>)}</div>}
              <div className="form-grid">
                <Field label={t('evidence.name')}><Input value={title} onInput={(e: any) => setTitle(e.target.value)} accessibleName={t('evidence.name')} data-testid="evidence-title" /></Field>
                <Field label={t('evidence.kind')}>
                  <Select accessibleName={t('evidence.kind')} onChange={(e) => setType(e.detail.selectedOption.getAttribute('value')!)}>
                    {TYPES.map((k) => <Option key={k} value={k} selected={type === k}>{tf('etype.' + k, k)}</Option>)}
                  </Select>
                </Field>
                {isImage && <Field label={t('evidence.describe')} hint={t('evidence.describe_hint')}><TextArea rows={2} value={desc} onInput={(e: any) => setDesc(e.target.value)} accessibleName={t('evidence.describe')} /></Field>}
              </div>
              <ErrorNote error={err} />
              <Button design="Emphasized" icon="add" onClick={add} disabled={busy} data-testid="add-evidence">{t('evidence.add_btn')}</Button>
            </Card>
            <Card className="analyse-card">
              <div className="analyse-count"><b>{docs.length}</b><span>{t('evidence.ready', { n: docs.length })}</span></div>
              <Cta onClick={analyse} loading={starting} disabled={docs.length === 0} testId="run-orchestrator" icon="lightbulb">{t('evidence.analyse')}</Cta>
              <p className="muted small">{t('evidence.analyse_hint')}</p>
            </Card>
          </aside>
        )}
      </div>
      <StepFooter step="evidence" hideNext />
    </>
  );
}
