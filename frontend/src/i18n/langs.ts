export interface LangMeta {
  code: string;
  native: string;
  english: string;
}

/** English and Hindi. Add a language by adding a catalog in src/locales and an entry here. */
export const LANGS: LangMeta[] = [
  { code: 'en', native: 'English', english: 'English' },
  { code: 'hi', native: 'हिन्दी', english: 'Hindi' },
];

/** The Devanagari font is bundled (works offline) and loaded only when Hindi is chosen. */
export const loadHindiFont = () => Promise.all([import('@fontsource/noto-sans-devanagari/400.css'), import('@fontsource/noto-sans-devanagari/700.css')]);
