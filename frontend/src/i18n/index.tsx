import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { store } from '../api';
import en from '../locales/en.json';
import { LANGS, loadHindiFont, type LangMeta } from './langs';

type Catalog = Record<string, string>;
const loaders = import.meta.glob('../locales/*.json') as Record<string, () => Promise<{ default: Catalog }>>;
const cache: Record<string, Catalog> = { en: en as Catalog };

export type TFn = (key: string, params?: Record<string, string | number>) => string;

interface I18n {
  lang: string;
  meta: LangMeta;
  setLang: (code: string) => void;
  t: TFn;
  /** Translate, or return the fallback text if the key is unknown (used for server-provided names). */
  tf: (key: string, fallback: string, params?: Record<string, string | number>) => string;
  has: (key: string) => boolean;
  langs: LangMeta[];
}

const Ctx = createContext<I18n | null>(null);

function interpolate(s: string, params?: Record<string, string | number>) {
  return params ? s.replace(/\{(\w+)\}/g, (_, k) => (k in params ? String(params[k]) : `{${k}}`)) : s;
}

function initialLang(): string {
  const saved = store.get('lang');
  if (saved && LANGS.some((l) => l.code === saved)) return saved;
  const nav = (navigator.language || 'en').toLowerCase().split('-')[0];
  return LANGS.some((l) => l.code === nav) ? nav : 'en';
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState(initialLang);
  const [, force] = useState(0);
  const meta = LANGS.find((l) => l.code === lang) ?? LANGS[0];

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!cache[lang]) {
        const load = loaders[`../locales/${lang}.json`];
        if (load) cache[lang] = (await load()).default;
      }
      if (lang === 'hi') await loadHindiFont().catch(() => undefined);
      if (!alive) return;
      const root = document.documentElement;
      root.lang = lang;
      root.style.setProperty('--font-script', lang === 'hi' ? '"Noto Sans Devanagari"' : 'sans-serif');
      force((n) => n + 1);
    })();
    return () => {
      alive = false;
    };
  }, [lang, meta]);

  const setLang = useCallback((code: string) => {
    store.set('lang', code);
    setLangState(code);
  }, []);

  const value = useMemo<I18n>(() => {
    const cur = cache[lang] ?? cache.en;
    const lookup = (key: string) => cur[key] ?? cache.en[key];
    return {
      lang,
      meta,
      setLang,
      langs: LANGS,
      has: (key) => lookup(key) !== undefined,
      t: (key, params) => interpolate(lookup(key) ?? key, params),
      tf: (key, fallback, params) => interpolate(lookup(key) ?? fallback, params),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, meta, setLang, cache[lang]]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n() {
  const c = useContext(Ctx);
  if (!c) throw new Error('useI18n outside provider');
  return c;
}
export const useT = () => useI18n().t;
