import { Fragment } from 'react';
import { Badge, Card, Note, PageHead } from '../components/ui';
import { useI18n } from '../i18n';
import { slug } from '../lib/compose';
import { useApp } from '../state';

const STATE_TONE: Record<string, string> = { connected: 'completed', in_use: 'completed', running_on_btp: 'completed', curated_catalog: 'started', adapter_ready: 'pending', deployment_ready: 'pending' };

function Diagram() {
  const box = (x: number, y: number, w: number, h: number, title: string, sub: string, cls: string) => (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={10} className={`d-box ${cls}`} />
      <text x={x + w / 2} y={y + 24} textAnchor="middle" className="d-title">{title}</text>
      <text x={x + w / 2} y={y + 42} textAnchor="middle" className="d-sub">{sub}</text>
    </g>
  );
  const arrow = (x1: number, y1: number, x2: number, y2: number) => <line x1={x1} y1={y1} x2={x2} y2={y2} className="d-arrow" markerEnd="url(#ah)" />;
  return (
    <svg viewBox="0 0 980 440" className="diagram" role="img" aria-label="EQUALPATH architecture">
      <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" className="d-head" /></marker></defs>
      {box(20, 20, 250, 60, 'React + SAP UI5 Web Components', '15 screens · English + Hindi · dark mode', 'ui')}
      {box(20, 110, 250, 60, 'SAP Build Apps / Work Zone', 'counsellor app · launchpad tile', 'ready')}
      {box(330, 20, 320, 60, 'FastAPI + Pydantic', 'sign-in · roles · PII redaction · audit', 'core')}
      {box(330, 110, 320, 200, '', '', 'core')}
      <text x={490} y={134} textAnchor="middle" className="d-title">LangGraph Career Orchestrator</text>
      {['Skills Discovery → [Human 1] → Market Intelligence', '→ role choice → Learning Pathway ∥ Employer Readiness', '→ Inclusive Matching → Bias Audit → review routing', '→ [Human 2] → Mutual Readiness Passport'].map((l, i) => <text key={l} x={490} y={162 + i * 22} textAnchor="middle" className="d-sub">{l}</text>)}
      <text x={490} y={264} textAnchor="middle" className="d-sub">checkpoints · retries · interrupts</text>
      {box(710, 20, 250, 60, 'IdentityProvider', 'password sign-in | XSUAA', 'sap')}
      {box(710, 100, 250, 60, 'LLMProvider', 'SAP AI Core | OpenAI | demo', 'sap')}
      {box(710, 180, 250, 60, 'SAP Build Process Automation', 'final review approval', 'sap')}
      {box(710, 260, 250, 60, 'CandidateRepository', 'SQLite | SAP HANA Cloud', 'sap')}
      {box(710, 340, 250, 60, 'LearningCatalogProvider', 'curated SAP Learning catalog', 'sap')}
      {box(330, 350, 320, 60, 'Immutable audit log', 'append-only · SHA-256 hash chain', 'core')}
      {arrow(270, 50, 330, 50)}{arrow(270, 140, 330, 160)}{arrow(490, 80, 490, 110)}{arrow(650, 50, 710, 50)}{arrow(650, 135, 710, 130)}{arrow(650, 185, 710, 210)}{arrow(650, 235, 710, 290)}{arrow(650, 285, 710, 370)}{arrow(490, 310, 490, 350)}
    </svg>
  );
}

export default function Architecture() {
  const { t, tf } = useI18n();
  const { system } = useApp();
  return (
    <>
      <PageHead icon="overview-chart" title={t('arch.title')} sub={t('arch.sub')} />
      {system && (
        <Note tone={system.provider.live ? 'good' : 'warn'} icon="ai" testId="active-provider">
          <b>{t('arch.provider')}:</b> {t(system.provider.kind === 'sap_ai_core' ? 'top.ai_sap' : system.provider.kind === 'openai' ? 'top.ai_openai' : 'top.ai_demo')} ({system.provider.model}). {t(system.provider.live ? 'arch.live' : 'arch.not_live')}
        </Note>
      )}
      <Card title={t('arch.diagram')} icon="overview-chart"><Diagram /></Card>
      <Card title={t('arch.sap')} icon="org-chart">
        <div className="scroll-x">
          <table className="tbl">
            <thead><tr><th>SAP</th><th>{t('arch.role')}</th><th>{t('arch.state')}</th></tr></thead>
            <tbody>
              {system?.sap_services.map((s: any) => (
                <tr key={s.service} data-testid={`sap-${s.service}`}>
                  <td><b>{s.service}</b></td>
                  <td>{tf('svc.' + slug(s.service), s.use)}</td>
                  <td><Badge status={STATE_TONE[s.state] ?? 'pending'} label={t('arch.s_' + s.state)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="grid cols-2">
        <Card title={t('arch.roadmap')} icon="calendar">
          <ul>
            <li>SAP SuccessFactors</li><li>SAP Talent Intelligence Hub</li><li>SAP Joule</li><li>SAP Business Data Cloud</li>
          </ul>
          <p className="muted small">{t('arch.roadmap_text')}</p>
        </Card>
        <Card title={t('arch.labels')} icon="tag">
          <dl className="facts">
            {system && ['persona', 'roles', 'jobs', 'employer', 'monitoring'].map((k) => <Fragment key={k}><dt>{t('label.' + k)}</dt><dd>{t('labelv.' + k)}</dd></Fragment>)}
            <dt>{t('arch.storage')}</dt><dd>{system?.repository.kind}</dd>
            <dt>{t('arch.identity')}</dt><dd>{system?.identity}</dd>
          </dl>
          <p className="small"><a href="/docs" target="_blank" rel="noreferrer">{t('arch.api')} (/docs)</a></p>
        </Card>
      </div>
    </>
  );
}
