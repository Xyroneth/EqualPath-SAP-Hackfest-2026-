/** Hand-drawn SVG illustrations. Colours come from CSS variables so they follow light / dark mode. */

export function HeroArt() {
  return (
    <svg viewBox="0 0 560 430" className="art hero-art" role="img" aria-label="A winding path from a candidate through learning steps to a ready workplace">
      <defs>
        <linearGradient id="hp" x1="0" x2="1">
          <stop offset="0" stopColor="var(--teal)" />
          <stop offset="1" stopColor="var(--blue)" />
        </linearGradient>
        <linearGradient id="hbg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--art-bg-a)" />
          <stop offset="1" stopColor="var(--art-bg-b)" />
        </linearGradient>
      </defs>
      <rect x="6" y="6" width="548" height="418" rx="34" fill="url(#hbg)" />
      <circle cx="95" cy="80" r="46" fill="var(--art-blob)" opacity=".55" className="float slow" />
      <circle cx="500" cy="330" r="34" fill="var(--art-blob)" opacity=".5" className="float" />
      <path pathLength="1" className="art-path-bg" d="M78 352 C176 326 150 226 262 232 S404 206 468 128" />
      <path pathLength="1" className="art-path" d="M78 352 C176 326 150 226 262 232 S404 206 468 128" stroke="url(#hp)" />
      {[[112, 338, 'done'], [190, 272, 'done'], [286, 232, 'now'], [388, 208, 'todo']].map(([x, y, s]: any, i) => (
        <g key={i} className={s === 'now' ? 'pulse-node' : ''}>
          <circle cx={x} cy={y} r="15" fill={s === 'done' ? 'var(--teal)' : 'var(--surface)'} stroke={s === 'now' ? 'var(--amber)' : s === 'done' ? 'var(--teal)' : 'var(--blue)'} strokeWidth="4" />
          {s === 'done' && <path d={`M${x - 6} ${y} l4 5 l8 -10`} stroke="#fff" strokeWidth="3.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />}
        </g>
      ))}
      <circle r="6" fill="var(--amber)"><animateMotion dur="6s" repeatCount="indefinite" path="M78 352 C176 326 150 226 262 232 S404 206 468 128" /></circle>
      {/* workplace */}
      <g transform="translate(452 40)">
        <rect x="0" y="34" width="86" height="72" rx="8" fill="var(--navy-fixed)" />
        <rect x="14" y="8" width="58" height="34" rx="6" fill="var(--blue)" />
        {[0, 1, 2].map((r) => [0, 1, 2].map((c) => <rect key={`${r}${c}`} x={12 + c * 24} y={46 + r * 18} width="14" height="10" rx="2" fill={(r + c) % 2 ? 'var(--amber)' : '#CFE3FA'} />))}
        <rect x="34" y="84" width="20" height="22" rx="3" fill="var(--teal)" />
        <path d="M43 8 V-14" stroke="var(--navy-fixed)" strokeWidth="3" />
        <path d="M43 -14 h22 l-5 7 l5 7 h-22z" fill="var(--amber)" />
      </g>
      <g transform="translate(408 36)">
        <g className="float">
          <circle cx="24" cy="24" r="24" fill="var(--green)" />
          <path d="M13 24 l8 9 l16 -18" stroke="#fff" strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      </g>
      {/* person */}
      <g transform="translate(24 268)">
        <ellipse cx="42" cy="118" rx="34" ry="6" fill="var(--navy-fixed)" opacity=".18" />
        <rect x="26" y="78" width="12" height="38" rx="5" fill="#2B3A55" />
        <rect x="46" y="78" width="12" height="38" rx="5" fill="#2B3A55" />
        <path d="M18 50 Q42 38 66 50 L70 88 Q42 96 14 88 Z" fill="var(--teal)" />
        <rect x="8" y="52" width="10" height="34" rx="5" fill="#E7B48D" transform="rotate(8 12 52)" />
        <rect x="66" y="52" width="10" height="34" rx="5" fill="#E7B48D" transform="rotate(-8 72 52)" />
        <rect x="37" y="34" width="10" height="14" rx="4" fill="#E7B48D" />
        <circle cx="42" cy="24" r="17" fill="#EFC09B" />
        <path d="M25 22 Q27 4 44 5 Q60 6 59 24 Q52 12 42 13 Q32 13 25 22Z" fill="#1F2937" />
        <circle cx="42" cy="0" r="8" fill="#1F2937" />
        <circle cx="36" cy="26" r="1.8" fill="#1F2937" /><circle cx="48" cy="26" r="1.8" fill="#1F2937" />
        <path d="M37 32 q5 4 10 0" stroke="#9A4B32" strokeWidth="2" fill="none" strokeLinecap="round" />
      </g>
      {/* floating skill chips */}
      {[['QA', 150, 168, 'var(--blue)', 'float'], ['Python', 262, 148, 'var(--teal)', 'float slow'], ['Excel', 356, 268, 'var(--green)', 'float'], ['SAP', 92, 246, 'var(--navy-fixed)', 'float slow']].map(([label, x, y, c, cls]: any) => (
        <g key={label} transform={`translate(${x} ${y})`}>
          <g className={cls}>
            <rect width={label.length * 9 + 26} height="28" rx="14" fill="var(--surface)" stroke={c} strokeWidth="2" />
            <text x={(label.length * 9 + 26) / 2} y="19" textAnchor="middle" fontSize="13" fontWeight="700" fill={c}>{label}</text>
          </g>
        </g>
      ))}
    </svg>
  );
}

export function EmptyArt({ kind = 'analysis' }: { kind?: 'analysis' | 'locked' | 'waiting' | 'evidence' }) {
  return (
    <svg viewBox="0 0 240 170" className="art empty-art" role="img" aria-hidden="true">
      <ellipse cx="120" cy="150" rx="80" ry="10" fill="var(--art-blob)" opacity=".5" />
      {kind === 'locked' && (
        <g>
          <path d="M120 18 L176 40 V86 C176 116 152 136 120 148 C88 136 64 116 64 86 V40 Z" fill="var(--blue)" opacity=".16" />
          <path d="M120 18 L176 40 V86 C176 116 152 136 120 148 C88 136 64 116 64 86 V40 Z" fill="none" stroke="var(--blue)" strokeWidth="5" strokeLinejoin="round" />
          <rect x="97" y="76" width="46" height="36" rx="8" fill="var(--navy-fixed)" />
          <path d="M106 76 v-10 a14 14 0 0 1 28 0 v10" fill="none" stroke="var(--navy-fixed)" strokeWidth="6" strokeLinecap="round" />
          <circle cx="120" cy="92" r="5" fill="var(--amber)" /><rect x="118" y="94" width="4" height="10" rx="2" fill="var(--amber)" />
        </g>
      )}
      {kind === 'analysis' && (
        <g>
          <rect x="52" y="34" width="84" height="104" rx="10" fill="var(--surface)" stroke="var(--line)" strokeWidth="3" transform="rotate(-8 94 86)" />
          <rect x="72" y="26" width="84" height="104" rx="10" fill="var(--surface)" stroke="var(--blue)" strokeWidth="3" />
          {[48, 62, 76, 90].map((y, i) => <rect key={y} x="86" y={y} width={i === 0 ? 40 : 56 - i * 6} height="6" rx="3" fill={i === 0 ? 'var(--teal)' : 'var(--line)'} />)}
          <circle cx="158" cy="106" r="24" fill="var(--blue-soft)" stroke="var(--navy-fixed)" strokeWidth="6" />
          <path d="M176 124 l22 22" stroke="var(--navy-fixed)" strokeWidth="9" strokeLinecap="round" />
          <path d="M148 106 l7 7 l13 -15" stroke="var(--green)" strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      )}
      {kind === 'waiting' && (
        <g>
          <path d="M84 24 h72 M84 146 h72" stroke="var(--navy-fixed)" strokeWidth="9" strokeLinecap="round" />
          <path d="M92 28 C92 66 120 76 120 86 C120 96 92 106 92 142 M148 28 C148 66 120 76 120 86 C120 96 148 106 148 142" fill="none" stroke="var(--blue)" strokeWidth="6" strokeLinecap="round" />
          <path d="M100 134 C108 116 120 112 120 112 C120 112 132 116 140 134Z" fill="var(--amber)" />
          <circle cx="120" cy="60" r="4" fill="var(--amber)" className="drip" />
        </g>
      )}
      {kind === 'evidence' && (
        <g>
          <rect x="66" y="30" width="108" height="98" rx="12" fill="var(--surface)" stroke="var(--blue)" strokeWidth="3" strokeDasharray="8 7" />
          <path d="M120 96 V60 M104 74 l16 -16 l16 16" stroke="var(--teal)" strokeWidth="7" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          <rect x="84" y="106" width="72" height="8" rx="4" fill="var(--line)" />
        </g>
      )}
    </svg>
  );
}

export function Avatar({ size = 64 }: { size?: number }) {
  return (
    <svg viewBox="0 0 96 96" width={size} height={size} className="avatar" role="img" aria-label="Priya">
      <circle cx="48" cy="48" r="48" fill="var(--teal-soft)" />
      <clipPath id="avc"><circle cx="48" cy="48" r="48" /></clipPath>
      <g clipPath="url(#avc)">
        <path d="M8 100 Q12 66 48 64 Q84 66 88 100Z" fill="var(--teal)" />
        <rect x="41" y="50" width="14" height="18" rx="6" fill="#E7B48D" />
        <circle cx="48" cy="40" r="19" fill="#EFC09B" />
        <path d="M28 38 Q29 16 49 16 Q68 17 68 39 Q60 24 48 25 Q36 25 28 38Z" fill="#1F2937" />
        <circle cx="48" cy="12" r="9" fill="#1F2937" />
        <circle cx="41" cy="42" r="2" fill="#1F2937" /><circle cx="55" cy="42" r="2" fill="#1F2937" />
        <path d="M42 50 q6 5 12 0" stroke="#9A4B32" strokeWidth="2.2" fill="none" strokeLinecap="round" />
        <circle cx="48" cy="35" r="1.6" fill="var(--red)" />
      </g>
    </svg>
  );
}

const FILE_STYLE: Record<string, [string, string]> = {
  pdf: ['#D93025', 'PDF'], xlsx: ['#188038', 'XLS'], docx: ['#1A73E8', 'DOC'], pptx: ['#E8710A', 'PPT'], csv: ['#0F9D8A', 'CSV'],
  text: ['#5B6B7F', 'TXT'], code: ['#7B4BC4', 'CODE'], image: ['#D6336C', 'IMG'],
};

export function FileIcon({ kind, size = 44 }: { kind: string; size?: number }) {
  const [color, label] = FILE_STYLE[kind] ?? FILE_STYLE.text;
  return (
    <svg viewBox="0 0 44 52" width={size} height={(size * 52) / 44} aria-hidden="true" className="file-icon">
      <path d="M4 4 a4 4 0 0 1 4 -4 h20 l12 12 v36 a4 4 0 0 1 -4 4 h-28 a4 4 0 0 1 -4 -4z" fill="var(--surface)" stroke={color} strokeWidth="2.5" />
      <path d="M28 0 v8 a4 4 0 0 0 4 4 h8" fill={color} opacity=".25" />
      <rect x="0" y="26" width="44" height="17" rx="4" fill={color} />
      <text x="22" y="39" textAnchor="middle" fontSize={label.length > 3 ? 9 : 10.5} fontWeight="800" fill="#fff" fontFamily="Arial, sans-serif">{label}</text>
    </svg>
  );
}

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      <rect width="64" height="64" rx="15" fill="#0A1F44" />
      <path d="M14 46 L30 20 L50 20" stroke="#2CC5C5" strokeWidth="6.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="50" cy="20" r="6.5" fill="#4DA3FF" />
      <path d="M20 47 h24" stroke="#F4F8FC" strokeWidth="5.5" strokeLinecap="round" />
    </svg>
  );
}
