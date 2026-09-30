import { Button, Dialog, Icon, Input, Option, Select } from '@ui5/webcomponents-react';
import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ApiError, type Role } from '../api';
import { Logo } from '../art/Art';
import { useI18n } from '../i18n';
import { nextHint } from '../lib/journey';
import { MORE_ITEMS, ROLES, ROLE_ICON, STEP_ICON, STEP_ROUTE, STEPS, canOpen, stepsFor } from '../lib/roles';
import { useApp } from '../state';
import { Cta } from './ui';

export function TopBar({ onMenu }: { onMenu: () => void }) {
  const { t, lang, setLang, langs } = useI18n();
  const { theme, toggleTheme, system } = useApp();
  const nav = useNavigate();
  const kind = system?.provider?.kind as string | undefined;
  return (
    <header className="topbar" role="banner">
      <button type="button" className="icon-btn menu-btn" aria-label={t('top.menu')} onClick={onMenu}><Icon name="menu2" /></button>
      <div className="brand" onClick={() => nav('/')} role="link" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && nav('/')}>
        <Logo />
        <div>
          <strong>EQUALPATH</strong>
          <span>{t('app.tagline')}</span>
        </div>
      </div>
      <div className="topbar-right">
        {kind && (
          <span className={`ai-chip ${kind}`} title={system.provider.detail} data-testid="provider-tag">
            <Icon name={kind === 'demo' ? 'lightbulb' : 'ai'} aria-hidden="true" />
            {t(kind === 'sap_ai_core' ? 'top.ai_sap' : kind === 'openai' ? 'top.ai_openai' : 'top.ai_demo')}
          </span>
        )}
        <label className="lang-select">
          <Icon name="globe" aria-hidden="true" />
          <span className="sr-only">{t('top.language')}</span>
          <Select accessibleName={t('top.language')} data-testid="lang-select" onChange={(e) => setLang(e.detail.selectedOption.getAttribute('value')!)}>
            {langs.map((l) => (
              <Option key={l.code} value={l.code} selected={l.code === lang}>
                {l.native}
              </Option>
            ))}
          </Select>
        </label>
        <button type="button" className="icon-btn" onClick={toggleTheme} aria-label={theme === 'dark' ? t('top.light') : t('top.dark')} title={theme === 'dark' ? t('top.light') : t('top.dark')} data-testid="theme-toggle">
          <Icon name={theme === 'dark' ? 'light-mode' : 'dark-mode'} />
        </button>
      </div>
    </header>
  );
}

/** The most visible control on the page: it is coloured by the role you are acting as, and staff roles show a lock until signed in. */
export function RoleBar() {
  const { t } = useI18n();
  const { role, unlocked, switchRole, askLogin, signOut, toast } = useApp();
  const pick = async (r: Role) => {
    if (r === role) return;
    if (r === 'candidate' || unlocked.includes(r)) {
      await switchRole(r);
      toast(t('role.now_as', { role: t('role.' + r) }), 'success');
    } else askLogin(r);
  };
  return (
    <div className={`rolebar r-${role}`} data-role={role} data-testid="rolebar">
      <div className="rolebar-inner">
        <span className="rolebar-label"><Icon name="group" aria-hidden="true" /> {t('role.viewing_as')}</span>
        <div className="role-pills" role="group" aria-label={t('role.viewing_as')}>
          {ROLES.map((r) => {
            const locked = r !== 'candidate' && !unlocked.includes(r);
            return (
              <button key={r} type="button" className={`role-pill r-${r} ${r === role ? 'active' : ''}`} aria-pressed={r === role} onClick={() => pick(r)} data-testid={`role-${r}`}>
                <Icon name={ROLE_ICON[r]} aria-hidden="true" />
                <span>{t('role.' + r)}</span>
                {r !== 'candidate' && <Icon name={locked ? 'locked' : 'unlocked'} className="lock" aria-label={locked ? t('role.locked') : t('role.unlocked')} />}
              </button>
            );
          })}
        </div>
        <span className="rolebar-hint">{t('role.hint_' + role)}</span>
        {role !== 'candidate' && (
          <button type="button" className="signout" onClick={() => { signOut(); toast(t('role.signed_out'), 'info'); }} data-testid="sign-out">
            <Icon name="log" aria-hidden="true" /> {t('role.sign_out')}
          </button>
        )}
      </div>
    </div>
  );
}

export function LoginDialog() {
  const { t } = useI18n();
  const { loginDialog, askLogin, switchRole, toast } = useApp();
  const [pw, setPw] = useState('');
  const [show, setShow] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (loginDialog) {
      setPw('');
      setErr(null);
      setShow(false);
    }
  }, [loginDialog]);
  const submit = async () => {
    if (!loginDialog || !pw) return setErr(t('login.enter'));
    setBusy(true);
    setErr(null);
    try {
      await switchRole(loginDialog, pw);
      toast(t('role.now_as', { role: t('role.' + loginDialog) }), 'success');
      askLogin(null);
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 401) setErr(t('login.wrong'));
      else if (e instanceof ApiError && e.status === 429) setErr(t('login.locked', { seconds: (e.message.match(/\d+/) ?? ['60'])[0] }));
      else setErr(t('login.error'));
    } finally {
      setBusy(false);
    }
  };
  const r = loginDialog ?? 'counsellor';
  return (
    <Dialog open={!!loginDialog} headerText={t('login.title', { role: t('role.' + r) })} onClose={() => askLogin(null)} className={`login-dialog r-${r}`} accessibleName={t('login.title', { role: t('role.' + r) })}
      footer={<div className="dialog-footer"><Button design="Transparent" onClick={() => askLogin(null)}>{t('common.cancel')}</Button><Button design="Emphasized" onClick={submit} disabled={busy} data-testid="login-submit">{t('login.submit')}</Button></div>}>
      <form className="login-form" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <div className={`login-hero r-${r}`}><Icon name={ROLE_ICON[r]} /><div><b>{t('role.' + r)}</b><span>{t('role.desc_' + r)}</span></div></div>
        <label className="field">
          <span className="field-label">{t('login.password')}</span>
          <div className="pw-row">
            <Input type={show ? 'Text' : 'Password'} value={pw} onInput={(e: any) => setPw(e.target.value)} valueState={err ? 'Negative' : 'None'} accessibleName={t('login.password')} data-testid="login-password" />
            <button type="button" className="icon-btn" aria-label={show ? t('login.hide') : t('login.show')} onClick={() => setShow((s) => !s)}><Icon name={show ? 'hide' : 'show'} /></button>
          </div>
        </label>
        {err && <div className="note bad" role="alert" data-testid="login-error"><Icon name="alert" /><span>{err}</span></div>}
        <p className="field-hint">{t('login.hint')}</p>
        <button type="submit" className="sr-only">{t('login.submit')}</button>
      </form>
    </Dialog>
  );
}

const NEXT_TITLES: Record<string, string> = {
  candidate_review: 'next.skills', role_selection: 'next.roles', evidence_request: 'next.evidence_request', final_review: 'next.decide',
};

export function NextBar() {
  const { t } = useI18n();
  const { role, candidateId, run, journey, askLogin, switchRole, unlocked } = useApp();
  const nav = useNavigate();
  const loc = useLocation();
  if (role === 'auditor' || ['/', '/working', '/architecture', '/practice'].includes(loc.pathname)) return null;
  const h = nextHint(role, candidateId, run, journey);
  const it = run?.interrupt?.checkpoint;
  const step = STEPS.find((s) => STEP_ROUTE[s] === h.route);
  let title = '', sub = '', cta = '', tone = 'info', go: (() => void) | null = () => nav(h.route);
  switch (h.kind) {
    case 'start': title = t('next.start'); sub = t('next.start_sub'); cta = t('next.start_cta'); break;
    case 'evidence': title = t('next.evidence'); sub = t('next.evidence_sub'); cta = t('next.evidence_cta'); break;
    case 'agents': title = t('next.agents'); sub = t('next.agents_sub'); cta = t('next.agents_cta'); tone = 'work'; break;
    case 'your_turn': title = t(NEXT_TITLES[it] ?? 'next.your_turn'); sub = t('next.your_turn_sub'); cta = t('next.open'); tone = 'turn'; break;
    case 'wait_candidate':
      title = t('next.wait_candidate'); sub = t('next.wait_candidate_sub'); cta = t('role.switch_to', { role: t('role.candidate') }); tone = 'wait';
      go = async () => { await switchRole('candidate'); nav(h.route); };
      break;
    case 'wait_reviewer':
      title = t('next.wait_reviewer'); sub = t('next.wait_reviewer_sub'); cta = t('role.switch_to', { role: t('role.counsellor') }); tone = 'wait';
      go = async () => { if (unlocked.includes('counsellor')) { await switchRole('counsellor'); nav('/review'); } else askLogin('counsellor'); };
      break;
    case 'done': title = t('next.done'); sub = t('next.done_sub'); cta = t('next.done_cta'); tone = 'done'; break;
    default: title = step ? t('next.view', { step: t('nav.' + step) }) : t('next.continue'); sub = t('next.view_sub'); cta = t('common.continue'); break;
  }
  if (loc.pathname === h.route) return null;
  if (h.kind === 'view' && STEPS.some((s2) => STEP_ROUTE[s2] === loc.pathname)) return null;
  return (
    <div className={`nextbar ${tone}`} data-testid="next-bar" data-kind={h.kind}>
      <span className="nb-icon"><Icon name={tone === 'done' ? 'message-success' : tone === 'wait' ? 'history' : tone === 'work' ? 'process' : 'navigation-right-arrow'} aria-hidden="true" /></span>
      <div className="nb-text">
        <b>{title}</b>
        <span>{sub}</span>
      </div>
      {go && <Cta onClick={go} testId="next-bar-cta">{cta}</Cta>}
    </div>
  );
}

export function SideNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { role, journey, candidateId, resetDemo, toast } = useApp();
  const nav = useNavigate();
  const steps = stepsFor(role);
  const showState = role === 'candidate' || role === 'counsellor';
  const more = MORE_ITEMS.filter((m) => canOpen(m.route, role));
  return (
    <>
      {open && <div className="scrim" onClick={onClose} />}
      <nav className={`sidenav ${open ? 'open' : ''}`} aria-label={t('nav.aria')}>
        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} onClick={onClose}>
          <span className="nav-ico"><Icon name="home" aria-hidden="true" /></span><span>{t('nav.home')}</span>
        </NavLink>
        {steps.length > 0 && <div className="nav-group">{t('nav.journey')}</div>}
        <ol className="steps">
          {steps.map((s, i) => {
            const st = showState ? journey.state[s] : 'todo';
            return (
              <li key={s}>
                <NavLink to={STEP_ROUTE[s]} onClick={onClose} className={({ isActive }) => `step-link ${st} ${isActive ? 'active' : ''}`} data-testid={`nav-${s}`}>
                  <span className="step-num">{st === 'done' ? <Icon name="accept" aria-hidden="true" /> : showState && role === 'candidate' ? i + 1 : <Icon name={STEP_ICON[s]} aria-hidden="true" />}</span>
                  <span className="step-name">{role === 'hr_reviewer' && s === 'review' ? t('review.title_hr') : t('nav.' + s)}</span>
                </NavLink>
              </li>
            );
          })}
        </ol>
        {more.length > 0 && <div className="nav-group">{t('nav.more')}</div>}
        {more.map((m) => (
          <NavLink key={m.route} to={m.route} onClick={onClose} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} data-testid={`nav-${m.route.slice(1)}`}>
            <span className="nav-ico"><Icon name={m.icon} aria-hidden="true" /></span><span>{t(m.key)}</span>
          </NavLink>
        ))}
        {role === 'candidate' && candidateId && (
          <button type="button" className="nav-restart" onClick={() => { resetDemo(); toast(t('nav.restarted'), 'info'); nav('/'); onClose(); }}>
            <Icon name="refresh" aria-hidden="true" /> {t('nav.restart')}
          </button>
        )}
      </nav>
    </>
  );
}
