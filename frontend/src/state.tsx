import { setTheme } from '@ui5/webcomponents-base/dist/config/Theme.js';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError, api, setApiToken, setUnauthorizedHandler, store, type Role } from './api';
import { useI18n } from './i18n';
import { computeJourney, type Journey } from './lib/journey';

export type Theme = 'light' | 'dark';
export interface Toast {
  id: number;
  kind: 'info' | 'success' | 'warning' | 'error';
  text: string;
}

interface AppState {
  role: Role;
  unlocked: Role[];
  switchRole: (role: Role, password?: string) => Promise<void>;
  signOut: (role?: Role) => void;
  loginDialog: Role | null;
  askLogin: (role: Role | null) => void;
  theme: Theme;
  toggleTheme: () => void;
  system: any;
  profile: any;
  setProfile: (p: any) => void;
  consent: any;
  setConsent: (c: any) => void;
  candidateId: string | null;
  docs: any[];
  refreshDocs: () => Promise<void>;
  runId: string | null;
  run: any;
  refresh: () => Promise<void>;
  journey: Journey;
  visited: string[];
  markVisited: (route: string) => void;
  startDemo: () => Promise<void>;
  saveProfile: () => Promise<string>;
  startRun: () => Promise<string>;
  setActiveRun: (runId: string, candidateId: string) => void;
  resetDemo: () => void;
  toasts: Toast[];
  toast: (text: string, kind?: Toast['kind']) => void;
  dismissToast: (id: number) => void;
}

const Ctx = createContext<AppState | null>(null);
const DEFAULT_CONSENT = { process_profile: false, use_llm_with_redaction: true, share_with_employer: false, share_accommodations: false };

function initialTheme(): Theme {
  const saved = store.get('theme');
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function readTokens(): Partial<Record<Role, string>> {
  try {
    return JSON.parse(store.get('tokens', true) || '{}');
  } catch {
    return {};
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [tokens, setTokens] = useState<Partial<Record<Role, string>>>(readTokens);
  const [role, setRoleState] = useState<Role>(() => {
    const r = store.get('role', true) as Role | null;
    return r && (r === 'candidate' || readTokens()[r]) ? r : 'candidate';
  });
  const [loginDialog, askLogin] = useState<Role | null>(null);
  const [theme, setThemeState] = useState<Theme>(initialTheme);
  const [system, setSystem] = useState<any>(null);
  const [profile, setProfile] = useState<any>(null);
  const [consent, setConsent] = useState<any>(DEFAULT_CONSENT);
  const [candidateId, setCandidateId] = useState<string | null>(store.get('candidateId'));
  const [docs, setDocs] = useState<any[]>([]);
  const [runId, setRunId] = useState<string | null>(store.get('runId'));
  const [run, setRun] = useState<any>(null);
  const [visited, setVisited] = useState<string[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timer = useRef<number | undefined>(undefined);
  const toastId = useRef(1);

  // ---- API token follows the active role (set synchronously so children fetch with the right identity)
  setApiToken(role === 'candidate' ? null : tokens[role] ?? null);

  const dismissToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const toast = useCallback((text: string, kind: Toast['kind'] = 'info') => {
    const id = toastId.current++;
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    window.setTimeout(() => dismissToast(id), 4500);
  }, [dismissToast]);

  // ---- theme (light / dark), also applied to the SAP UI5 components
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    // Deferred: the SAP UI5 ThemeProvider (a parent) applies its default theme after this effect on first render.
    const id = window.setTimeout(() => setTheme(theme === 'dark' ? 'sap_horizon_dark' : 'sap_horizon'), 0);
    store.set('theme', theme);
    return () => window.clearTimeout(id);
  }, [theme]);
  const toggleTheme = () => setThemeState((t) => (t === 'dark' ? 'light' : 'dark'));

  // ---- sign in / out
  const setRole = (r: Role) => {
    setRoleState(r);
    store.set('role', r, true);
  };
  const switchRole = useCallback(async (r: Role, password?: string) => {
    if (r === 'candidate') {
      setApiToken(null);
      setRole('candidate');
      return;
    }
    if (!password && tokens[r]) {
      setApiToken(tokens[r] ?? null);
      setRole(r);
      return;
    }
    const s = await api.post('/api/auth/login', { role: r, password: password ?? '' });
    setApiToken(s.token);
    const next = { ...tokens, [r]: s.token };
    setTokens(next);
    store.set('tokens', JSON.stringify(next), true);
    setRole(r);
  }, [tokens]);
  const signOut = useCallback((r?: Role) => {
    const target = r ?? role;
    const next = { ...tokens };
    delete next[target];
    setTokens(next);
    store.set('tokens', JSON.stringify(next), true);
    if (target === role) setRole('candidate');
  }, [tokens, role]);
  useEffect(() => {
    setUnauthorizedHandler(() => {
      signOut();
      toast(t('toast.expired'), 'warning');
    });
  }, [signOut, toast, t]);

  useEffect(() => {
    api.get('/api/system/status').then(setSystem).catch(() => setSystem(null));
  }, []);

  // ---- candidate profile / documents
  const refreshDocs = useCallback(async () => {
    if (!candidateId || (role !== 'candidate' && role !== 'counsellor')) return setDocs([]);
    try {
      setDocs((await api.get(`/api/candidates/${candidateId}/documents`)).documents);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setCandidateId(null);
        store.set('candidateId', null);
      }
      setDocs([]);
    }
  }, [candidateId, role]);
  useEffect(() => {
    refreshDocs();
  }, [refreshDocs]);

  useEffect(() => {
    if (!candidateId || role !== 'candidate' || profile) return;
    api.get(`/api/candidates/${candidateId}`).then((c) => {
      setProfile(c.profile);
      setConsent(c.consent);
    }).catch(() => undefined);
  }, [candidateId, role, profile]);

  // ---- run polling
  const refresh = useCallback(async () => {
    if (!runId) return;
    try {
      setRun(await api.get(`/api/runs/${runId}`));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setRunId(null);
        setRun(null);
        store.set('runId', null);
      }
    }
  }, [runId]);
  useEffect(() => {
    window.clearTimeout(timer.current);
    if (!runId) return;
    let alive = true;
    const tick = async () => {
      await refresh();
      if (alive) timer.current = window.setTimeout(tick, run?.run?.status === 'running' ? 500 : 2500);
    };
    tick();
    return () => {
      alive = false;
      window.clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, role, run?.run?.status]);

  useEffect(() => {
    try {
      setVisited(runId ? JSON.parse(store.get(`visited.${runId}`) || '[]') : []);
    } catch {
      setVisited([]);
    }
  }, [runId]);
  const markVisited = useCallback((route: string) => {
    setVisited((v) => {
      if (v.includes(route)) return v;
      const next = [...v, route];
      if (runId) store.set(`visited.${runId}`, JSON.stringify(next));
      return next;
    });
  }, [runId]);

  // ---- demo flow actions (all as the open Candidate role)
  const startDemo = async () => {
    const persona = await api.get('/api/demo/persona');
    setProfile(persona.profile);
    setConsent(DEFAULT_CONSENT);
    setCandidateId(null);
    setRunId(null);
    setRun(null);
    setDocs([]);
    store.set('candidateId', null);
    store.set('runId', null);
  };
  const saveProfile = async () => {
    if (candidateId) {
      await api.put(`/api/candidates/${candidateId}`, { profile, consent });
      return candidateId;
    }
    const { candidate_id } = await api.post('/api/candidates', { profile, consent, seed_persona: 'priya' });
    setCandidateId(candidate_id);
    store.set('candidateId', candidate_id);
    return candidate_id;
  };
  const startRun = async () => {
    if (!candidateId) throw new Error('No candidate');
    const { run_id } = await api.post('/api/runs', { candidate_id: candidateId });
    setRunId(run_id);
    store.set('runId', run_id);
    setRun(null);
    return run_id;
  };
  const setActiveRun = (rid: string, cid: string) => {
    setRunId(rid);
    setCandidateId(cid);
    store.set('runId', rid);
    store.set('candidateId', cid);
    setRun(null);
  };
  const resetDemo = () => {
    setRunId(null);
    setCandidateId(null);
    setRun(null);
    setProfile(null);
    setDocs([]);
    setConsent(DEFAULT_CONSENT);
    store.set('runId', null);
    store.set('candidateId', null);
  };

  const journey = useMemo(() => computeJourney(candidateId, run, visited), [candidateId, run, visited]);
  const unlocked = (Object.keys(tokens) as Role[]).filter((r) => tokens[r]);

  return (
    <Ctx.Provider value={{ role, unlocked, switchRole, signOut, loginDialog, askLogin, theme, toggleTheme, system, profile, setProfile, consent, setConsent, candidateId, docs, refreshDocs,
      runId, run, refresh, journey, visited, markVisited, startDemo, saveProfile, startRun, setActiveRun, resetDemo, toasts, toast, dismissToast }}>
      {children}
    </Ctx.Provider>
  );
}

export function useApp() {
  const c = useContext(Ctx);
  if (!c) throw new Error('useApp outside provider');
  return c;
}
