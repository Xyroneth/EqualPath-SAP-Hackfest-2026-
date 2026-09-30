import { Button, Icon } from '@ui5/webcomponents-react';
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyArt } from '../art/Art';
import { useI18n } from '../i18n';
import { nextRoute } from '../lib/journey';
import { ROLES, STEPS, STEP_ROUTE, canOpen, stepsFor, type Step } from '../lib/roles';
import { statusName } from '../lib/compose';
import { useApp } from '../state';

/** Big call-to-action button with a sliding arrow. */
export function Cta({ children, onClick, disabled, loading, variant = 'primary', icon, testId, type = 'button', back }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; loading?: boolean; variant?: 'primary' | 'ghost' | 'soft'; icon?: string; testId?: string; type?: 'button' | 'submit'; back?: boolean;
}) {
  return (
    <button type={type} className={`cta ${variant}`} onClick={onClick} disabled={disabled || loading} data-testid={testId} aria-busy={loading}>
      {back && <Icon name="arrow-left" className="cta-arrow back" />}
      {loading ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} /> : null}
      <span>{children}</span>
      {!back && <Icon name="arrow-right" className="cta-arrow" />}
    </button>
  );
}

const BADGE: Record<string, string> = {
  self_declared: 'warn', source_supported: 'good', assessed: 'good', externally_verified: 'good', verified: 'good', developing: 'warn', missing: 'bad',
  declared: 'neutral', document_verified: 'good', experience_validated: 'info', conflicting_evidence: 'bad', fit: 'good', conflict: 'bad', unconfirmed: 'warn',
  high: 'bad', medium: 'warn', low: 'neutral', completed: 'good', running: 'info', waiting_for_human: 'warn', pending: 'neutral', failed: 'bad', rejected: 'bad',
  pending_review: 'warn', accepted: 'good', not_started: 'neutral', started: 'info', evidence_submitted: 'warn', needs_more_evidence: 'bad', approved_by_hr: 'good',
  approved_by_hr_with_edits: 'good', rejected_by_hr: 'bad', pending_hr_approval: 'warn', request_more: 'warn', open: 'warn',
};
const BADGE_ICON: Record<string, string> = { good: 'accept', bad: 'decline', warn: 'alert', info: 'information', neutral: 'circle-task-2' };

export function Badge({ status, label }: { status: string; label?: string }) {
  const { t, tf } = useI18n();
  const tone = BADGE[status] ?? 'neutral';
  return (
    <span className={`badge ${tone}`} data-status={status}>
      <Icon name={BADGE_ICON[tone]} aria-hidden="true" />
      {label ?? tf('status.' + status, status.replace(/_/g, ' '))}
    </span>
  );
}
export const StatusText = ({ status }: { status: string }) => {
  const i18n = useI18n();
  return <>{statusName(i18n, status)}</>;
};

export function Chip({ children, tone = 'neutral', icon }: { children: ReactNode; tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'info' | 'accent'; icon?: string }) {
  return (
    <span className={`chip ${tone}`}>
      {icon && <Icon name={icon} aria-hidden="true" />}
      {children}
    </span>
  );
}

export function Card({ title, icon, aside, children, className = '', style }: { title?: ReactNode; icon?: string; aside?: ReactNode; children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <section className={`card ${className}`} style={style}>
      {(title || aside) && (
        <header className="card-head">
          {title && (
            <h3>
              {icon && <span className="card-icon"><Icon name={icon} aria-hidden="true" /></span>}
              {title}
            </h3>
          )}
          {aside && <div className="card-aside">{aside}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/** A small (i) button that reveals an explanation. Closed by default. */
export function InfoTip({ children, label }: { children: ReactNode; label?: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const off = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', off);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', off);
      document.removeEventListener('keydown', esc);
    };
  }, [open]);
  return (
    <span className="infotip" ref={ref}>
      <button type="button" className="info-btn" aria-expanded={open} aria-controls={id} aria-label={label ?? t('common.more_info')} onClick={() => setOpen((o) => !o)}>
        <Icon name="hint" aria-hidden="true" />
      </button>
      {open && (
        <div className="info-pop" id={id} role="region">
          {children}
        </div>
      )}
    </span>
  );
}

export function PageHead({ step, title, sub, actions, icon }: { step?: Step; title: ReactNode; sub?: ReactNode; actions?: ReactNode; icon?: string }) {
  const { t } = useI18n();
  const { role } = useApp();
  const list = stepsFor(role);
  const idx = step ? STEPS.indexOf(step) + 1 : 0;
  return (
    <header className="page-head">
      <div className="page-head-main">
        {step && list.includes(step) && (
          <div className="eyebrow">
            <span className="eyebrow-dot" />
            {t('common.step_of', { n: idx, total: STEPS.length })}
          </div>
        )}
        <h1>
          {icon && <span className="title-icon"><Icon name={icon} aria-hidden="true" /></span>}
          {title}
        </h1>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

/** Back / Next buttons so nobody has to hunt for the next page. Steps a role cannot open are skipped. */
export function StepFooter({ step, nextLabel, onNext, nextDisabled, hideNext }: { step: Step; nextLabel?: string; onNext?: () => void; nextDisabled?: boolean; hideNext?: boolean }) {
  const { t } = useI18n();
  const { role, journey } = useApp();
  const nav = useNavigate();
  const list = stepsFor(role);
  const i = list.indexOf(step);
  const prev = i > 0 ? list[i - 1] : null;
  const next = i >= 0 && i < list.length - 1 ? list[i + 1] : null;
  return (
    <footer className="step-footer">
      {prev ? <Cta variant="ghost" back onClick={() => nav(STEP_ROUTE[prev])}>{t('common.back')}</Cta> : <span />}
      {!hideNext && next && (
        <Cta onClick={onNext ?? (() => nav(STEP_ROUTE[next]))} disabled={nextDisabled ?? (role === 'candidate' && !journey.available[next] && next !== 'review')} testId="step-next">
          {nextLabel ?? t('common.next_step', { step: t('nav.' + next) })}
        </Cta>
      )}
    </footer>
  );
}

export function EmptyState({ kind = 'analysis', title, text, action }: { kind?: 'analysis' | 'locked' | 'waiting' | 'evidence'; title: ReactNode; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty" data-testid="empty-state">
      <EmptyArt kind={kind} />
      <h2>{title}</h2>
      {text && <p>{text}</p>}
      {action && <div className="empty-actions">{action}</div>}
    </div>
  );
}

/** Wrap a page that needs the analysis to have run. Shows a friendly explanation and ONE clear button instead of a dead end. */
export function NeedsAnalysis({ ready, children, waitingText }: { ready: boolean; children: ReactNode; waitingText?: string }) {
  const { t } = useI18n();
  const { candidateId, run, journey, role } = useApp();
  const nav = useNavigate();
  if (ready) return <>{children}</>;
  const running = run?.run?.status === 'running';
  const target = !candidateId ? '/profile' : !run ? '/evidence' : running ? '/working' : nextRoute(journey);
  const label = !candidateId ? t('gate.set_up') : !run ? t('gate.add_evidence') : running ? t('gate.see_progress') : t('gate.continue');
  return (
    <EmptyState
      kind={running ? 'waiting' : 'analysis'}
      title={running ? t('gate.running_title') : t('gate.title')}
      text={waitingText ?? (running ? t('gate.running_text') : role === 'candidate' ? t('gate.text') : t('gate.text_staff'))}
      action={role === 'candidate' || running ? <Cta onClick={() => nav(target)}>{label}</Cta> : <Cta onClick={() => nav('/')}>{t('gate.back_home')}</Cta>}
    />
  );
}

/** Page-level access check: shows who the page is for, with a button to switch. */
export function AccessGate({ route, children }: { route: string; children: ReactNode }) {
  const { t } = useI18n();
  const { role, askLogin, switchRole, unlocked } = useApp();
  if (canOpen(route, role)) return <>{children}</>;
  const allowed = ROLES.filter((r) => canOpen(route, r));
  const first = allowed[0];
  const go = async () => {
    if (first === 'candidate' || unlocked.includes(first)) await switchRole(first);
    else askLogin(first);
  };
  return (
    <EmptyState
      kind="locked"
      title={t('access.title')}
      text={t('access.text', { roles: allowed.map((r) => t('role.' + r)).join(' / ') })}
      action={<Cta onClick={go} testId="access-switch">{t('access.switch', { role: t('role.' + first) })}</Cta>}
    />
  );
}

export function Ring({ parts, size = 132, label }: { parts: { value: number; color: string }[]; size?: number; label?: ReactNode }) {
  const total = parts.reduce((a, b) => a + b.value, 0) || 1;
  const r = 46;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg viewBox="0 0 120 120" role="img" aria-hidden="true">
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--line)" strokeWidth="14" />
        {parts.map((p, i) => {
          const len = (p.value / total) * c;
          const el = <circle key={i} cx="60" cy="60" r={r} fill="none" stroke={p.color} strokeWidth="14" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset} transform="rotate(-90 60 60)" className="ring-seg" style={{ ['--i' as any]: i }} />;
          offset += len;
          return p.value ? el : null;
        })}
      </svg>
      <div className="ring-label">{label}</div>
    </div>
  );
}

export function Meter({ value, label, hint }: { value: number; label: string; hint?: string }) {
  return (
    <div className="meter" title={hint}>
      <div className="meter-row"><span>{label}</span><b>{Math.round(value * 100)}%</b></div>
      <div className="meter-track" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)} aria-label={label}>
        <div className="meter-fill" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}

export function Quote({ text, source, onSource }: { text: string; source: string; onSource?: () => void }) {
  const { t } = useI18n();
  return (
    <figure className="quote">
      <blockquote>“{text}”</blockquote>
      <figcaption>
        {onSource ? <button type="button" className="link-btn" onClick={onSource}>{t('common.source')}: {source} <Icon name="action" aria-hidden="true" /></button> : <>{t('common.source')}: {source}</>}
      </figcaption>
    </figure>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <div className="note bad" role="alert">
      <Icon name="alert" aria-hidden="true" />
      <span>{error}</span>
    </div>
  );
}

export function Note({ tone = 'info', icon, children, testId }: { tone?: 'info' | 'good' | 'warn' | 'bad'; icon?: string; children: ReactNode; testId?: string }) {
  return (
    <div className={`note ${tone}`} data-testid={testId}>
      <Icon name={icon ?? (tone === 'good' ? 'message-success' : tone === 'bad' ? 'alert' : tone === 'warn' ? 'alert' : 'information')} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function Toasts() {
  const { toasts, dismissToast } = useApp();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((x) => (
        <div key={x.id} className={`toast ${x.kind}`}>
          <Icon name={x.kind === 'success' ? 'message-success' : x.kind === 'error' ? 'alert' : x.kind === 'warning' ? 'alert' : 'information'} aria-hidden="true" />
          <span>{x.text}</span>
          <button type="button" aria-label="Close" onClick={() => dismissToast(x.id)}><Icon name="decline" /></button>
        </div>
      ))}
    </div>
  );
}

export function Field({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function Toggle({ label, desc, checked, onChange, disabled, testId }: { label: string; desc?: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; testId?: string }) {
  return (
    <div className={`toggle-row ${disabled ? 'disabled' : ''}`}>
      <div>
        <div className="toggle-label">{label}</div>
        {desc && <div className="toggle-desc">{desc}</div>}
      </div>
      <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} className={`switch ${checked ? 'on' : ''}`} data-testid={testId} onClick={() => onChange(!checked)}>
        <span className="knob" />
      </button>
    </div>
  );
}

export { Button };
