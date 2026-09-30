import { Icon } from '@ui5/webcomponents-react';
import type { ReactNode } from 'react';

/** How one line of the ad should be highlighted (a barrier, or a line the rewrite changed). */
export interface LineMark {
  tone: 'high' | 'medium' | 'low' | 'new';
  tags: string[];
}

type Block =
  | { kind: 'section'; label: string; text: string; raw: string }
  | { kind: 'heading'; text: string; raw: string }
  | { kind: 'bullets'; items: { text: string; raw: string }[] }
  | { kind: 'para'; text: string; raw: string };

/** Job ads are stored as plain text ("Label: text" sections and "- " bullets); this turns them into a readable posting. */
export function parseAd(text: string): { title: string; employer: string; blocks: Block[] } {
  const lines = text.split('\n');
  const first = (lines.shift() ?? '').trim();
  const cut = first.lastIndexOf(' - ');
  const title = cut > 0 ? first.slice(0, cut) : first;
  const employer = cut > 0 ? first.slice(cut + 3) : '';
  const blocks: Block[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith('- ')) {
      const last = blocks[blocks.length - 1];
      const item = { text: line.slice(2), raw: line.slice(2) };
      if (last?.kind === 'bullets') last.items.push(item);
      else blocks.push({ kind: 'bullets', items: [item] });
      continue;
    }
    if (line.endsWith(':') && line.length < 60) {
      blocks.push({ kind: 'heading', text: line.slice(0, -1), raw: line });
      continue;
    }
    const m = line.match(/^([A-Z][A-Za-z ,'()-]{2,40}):\s+(.+)$/);
    if (m && m[1].split(' ').length <= 6) blocks.push({ kind: 'section', label: m[1], text: m[2], raw: line });
    else blocks.push({ kind: 'para', text: line, raw: line });
  }
  return { title, employer, blocks };
}

function Marked({ raw, mark, children }: { raw: string; mark: (raw: string) => LineMark | null; children: ReactNode }) {
  const m = mark(raw);
  if (!m) return <>{children}</>;
  return (
    <span className={`ad-mark ${m.tone}`}>
      {children}
      {m.tags.length > 0 && (
        <span className="ad-tags">
          {m.tags.map((t) => (
            <span key={t} className="ad-tag"><Icon name={m.tone === 'new' ? 'edit' : 'alert'} aria-hidden="true" />{t}</span>
          ))}
        </span>
      )}
    </span>
  );
}

export function JobAd({ text, facts, mark = () => null, footer, testId }: {
  text: string;
  facts?: { icon: string; text: string }[];
  mark?: (raw: string) => LineMark | null;
  footer?: ReactNode;
  testId?: string;
}) {
  const ad = parseAd(text);
  return (
    <article className="ad" data-testid={testId}>
      <header className="ad-head">
        <span className="ad-logo" aria-hidden="true">{(ad.employer || ad.title).slice(0, 1)}</span>
        <div>
          <h3>{ad.title}</h3>
          {ad.employer && <span className="ad-employer">{ad.employer}</span>}
        </div>
      </header>
      {facts && facts.length > 0 && (
        <div className="ad-facts">
          {facts.map((f) => <span key={f.text} className="ad-fact"><Icon name={f.icon} aria-hidden="true" />{f.text}</span>)}
        </div>
      )}
      <div className="ad-body">
        {ad.blocks.map((b, i) => {
          if (b.kind === 'heading') return <h4 key={i}>{b.text}</h4>;
          if (b.kind === 'bullets') {
            return (
              <ul key={i}>
                {b.items.map((it) => <li key={it.raw}><Marked raw={it.raw} mark={mark}>{it.text}</Marked></li>)}
              </ul>
            );
          }
          if (b.kind === 'section') {
            return (
              <div key={i} className="ad-section">
                <h4>{b.label}</h4>
                <p><Marked raw={b.raw} mark={mark}>{b.text}</Marked></p>
              </div>
            );
          }
          return <p key={i}><Marked raw={b.raw} mark={mark}>{b.text}</Marked></p>;
        })}
      </div>
      {footer}
    </article>
  );
}
