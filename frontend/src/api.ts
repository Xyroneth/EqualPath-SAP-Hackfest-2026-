export type Role = 'candidate' | 'counsellor' | 'hr_reviewer' | 'auditor';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;
export const setApiToken = (t: string | null) => {
  token = t;
};
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn;
};

async function request<T = any>(method: string, path: string, body?: unknown | FormData): Promise<T> {
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  const headers: Record<string, string> = {};
  if (!isForm) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body) });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: any) => d.msg).join('; ') : JSON.stringify(j.detail ?? j);
    } catch {
      /* keep the status text */
    }
    if (res.status === 401 && token && !path.startsWith('/api/auth/')) onUnauthorized?.();
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

export const api = {
  get: <T = any>(p: string) => request<T>('GET', p),
  post: <T = any>(p: string, b?: unknown) => request<T>('POST', p, b ?? {}),
  put: <T = any>(p: string, b?: unknown) => request<T>('PUT', p, b ?? {}),
  del: <T = any>(p: string) => request<T>('DELETE', p),
  upload: <T = any>(p: string, form: FormData) => request<T>('POST', p, form),
  /** Download a text/JSON/HTML response through the authorised API and save it as a file. */
  async saveAs(path: string, filename: string, type = 'application/json') {
    const res = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) throw new ApiError(res.status, res.statusText);
    download(filename, await res.text(), type);
  },
};

export function download(filename: string, content: string, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Open a piece of evidence in a NEW browser tab. The tab is opened first (so pop-up blockers allow it), then pointed at a short-lived link. */
export async function openEvidence(candidateId: string, sourceId: string): Promise<boolean> {
  const win = window.open('about:blank', '_blank');
  if (win) {
    win.opener = null;
    win.document.write('<title>EQUALPATH</title><body style="font-family:sans-serif;color:#526071;padding:40px">Opening…</body>');
  }
  try {
    const { url } = await api.post(`/api/candidates/${candidateId}/documents/${encodeURIComponent(sourceId)}/view-link`);
    if (win) win.location.href = url;
    else window.location.href = url;
    return !!win;
  } catch (e) {
    win?.close();
    throw e;
  }
}

export const store = {
  get(key: string, session = false): string | null {
    try {
      return (session ? sessionStorage : localStorage).getItem(`equalpath.${key}`);
    } catch {
      return null;
    }
  },
  set(key: string, value: string | null, session = false) {
    try {
      const s = session ? sessionStorage : localStorage;
      if (value === null) s.removeItem(`equalpath.${key}`);
      else s.setItem(`equalpath.${key}`, value);
    } catch {
      /* storage unavailable: state lives in memory only */
    }
  },
};
