export interface I18nApi {
  t: (key: string, params?: Record<string, string | number>) => string;
  tf: (key: string, fallback: string, params?: Record<string, string | number>) => string;
  has: (key: string) => boolean;
}
