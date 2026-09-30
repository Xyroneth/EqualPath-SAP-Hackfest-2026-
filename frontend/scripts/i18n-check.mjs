// Usage: node scripts/i18n-check.mjs [--list]
// Verifies that every text key used in the code exists in en.json, and that every locale has exactly the same keys + placeholders.
import fs from 'node:fs';
import path from 'node:path';

const src = path.resolve('src');
const localesDir = path.join(src, 'locales');
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]));
const files = walk(src).filter((f) => /\.(tsx?|ts)$/.test(f));

const used = new Map();
const add = (k, f) => used.set(k, (used.get(k) ?? new Set()).add(path.relative(src, f)));
const dynamic = new Set();
for (const f of files) {
  const code = fs.readFileSync(f, 'utf8');
  for (const m of code.matchAll(/\b(?:t|tf|has)\(\s*(['"`])([^'"`]+?)\1(?!\s*\+)/g)) {
    if (m[2].includes('${')) dynamic.add(m[2]);
    else if (/^[a-z_]+(\.[A-Za-z0-9_]+)+$/.test(m[2])) add(m[2], f);
  }
  for (const m of code.matchAll(/\b(?:t|tf)\(\s*'([a-z_]+\.)'\s*\+/g)) dynamic.add(m[1] + '*');
  for (const m of code.matchAll(/\b(?:t|tf)\(\s*`([^`]+)`/g)) if (m[1].includes('${')) dynamic.add(m[1]);
}
const en = JSON.parse(fs.readFileSync(path.join(localesDir, 'en.json'), 'utf8'));
let bad = 0;
if (process.argv.includes('--list')) {
  console.log([...used.keys()].sort().join('\n'));
  console.log('\n# dynamic key patterns:\n' + [...dynamic].sort().join('\n'));
  process.exit(0);
}
const missing = [...used.keys()].filter((k) => !(k in en));
if (missing.length) { bad++; console.log(`MISSING in en.json (${missing.length}):\n  ` + missing.join('\n  ')); }
const unused = Object.keys(en).filter((k) => !used.has(k));
console.log(`en.json: ${Object.keys(en).length} keys; ${used.size} static keys used in code; ${unused.length} only referenced dynamically or unused`);
const ph = (s) => (s.match(/\{\w+\}/g) ?? []).sort().join(',');
for (const f of fs.readdirSync(localesDir).filter((x) => x.endsWith('.json') && x !== 'en.json').sort()) {
  const cat = JSON.parse(fs.readFileSync(path.join(localesDir, f), 'utf8'));
  const miss = Object.keys(en).filter((k) => !(k in cat));
  const extra = Object.keys(cat).filter((k) => !(k in en));
  const badPh = Object.keys(en).filter((k) => k in cat && ph(en[k]) !== ph(cat[k]));
  const empty = Object.keys(cat).filter((k) => !String(cat[k]).trim());
  const problems = miss.length + extra.length + badPh.length + empty.length;
  if (problems) bad++;
  console.log(`${f.padEnd(10)} ${problems ? 'PROBLEMS' : 'ok'}  keys=${Object.keys(cat).length}` + (problems ? `  missing=${miss.length} extra=${extra.length} placeholderMismatch=${badPh.length} empty=${empty.length}` : ''));
  if (miss.length) console.log('   missing:', miss.slice(0, 8).join(', '));
  if (badPh.length) console.log('   placeholders:', badPh.slice(0, 8).join(', '));
}
process.exit(bad ? 1 : 0);
