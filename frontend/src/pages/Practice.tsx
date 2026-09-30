import { useState } from 'react';
import { Card, Chip, PageHead } from '../components/ui';

/** Practice target for the browser-automation and API-testing milestones. Text stays in English on purpose (stable for test scripts). */
export default function Practice() {
  const [user, setUser] = useState('');
  const [pw, setPw] = useState('');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [form, setForm] = useState({ email: '', qty: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const login = (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(user === 'tester' && pw === 'Practice@123' ? { ok: true, text: 'Welcome, tester!' } : { ok: false, text: 'Invalid username or password' });
  };
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) errs.email = 'Enter a valid e-mail address';
    const q = Number(form.qty);
    if (!Number.isInteger(q) || q < 1 || q > 100) errs.qty = 'Quantity must be a whole number from 1 to 100';
    setErrors(errs);
    setSaved(Object.keys(errs).length === 0);
  };
  return (
    <>
      <PageHead icon="lab" title="Practice application" sub="A safe target for the browser-automation and API-testing steps. Username: tester · Password: Practice@123 · API: GET/POST /api/practice/orders" />
      <Chip tone="warn">Practice sandbox, not a real system</Chip>
      <div className="grid cols-2">
        <Card title="Login">
          <form onSubmit={login} className="plain-form" id="login-form">
            <label htmlFor="username">Username</label>
            <input id="username" name="username" value={user} onChange={(e) => setUser(e.target.value)} />
            <label htmlFor="password">Password</label>
            <input id="password" name="password" type="password" value={pw} onChange={(e) => setPw(e.target.value)} />
            <button id="login-button" type="submit" className="cta primary">Log in</button>
            {msg && <p id="login-message" role="status" className={msg.ok ? 'good-text' : 'bad-text'}>{msg.text}</p>}
          </form>
        </Card>
        <Card title="Order form validation">
          <form onSubmit={save} className="plain-form" id="order-form" noValidate>
            <label htmlFor="email">E-mail</label>
            <input id="email" name="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} aria-describedby="email-error" />
            {errors.email && <p id="email-error" className="bad-text">{errors.email}</p>}
            <label htmlFor="qty">Quantity</label>
            <input id="qty" name="qty" value={form.qty} onChange={(e) => setForm({ ...form, qty: e.target.value })} aria-describedby="qty-error" />
            {errors.qty && <p id="qty-error" className="bad-text">{errors.qty}</p>}
            <button id="save-button" type="submit" className="cta primary">Save</button>
            {saved && <p id="save-message" role="status" className="good-text">Order saved</p>}
          </form>
        </Card>
      </div>
    </>
  );
}
