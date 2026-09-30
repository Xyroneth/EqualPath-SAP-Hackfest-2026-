import { Icon } from '@ui5/webcomponents-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar, HeroArt } from '../art/Art';
import { Chip, Cta, ErrorNote } from '../components/ui';
import { useI18n } from '../i18n';
import { homeFor } from '../lib/roles';
import { useApp } from '../state';

export default function Landing() {
  const { t } = useI18n();
  const nav = useNavigate();
  const { role, switchRole, startOwn, startSample, candidateId, run } = useApp();
  const [busy, setBusy] = useState<'own' | 'sample' | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const start = async (kind: 'own' | 'sample') => {
    setBusy(kind);
    setErr(null);
    try {
      await switchRole('candidate');
      await (kind === 'own' ? startOwn() : startSample());
      nav('/profile');
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  };
  const steps = [
    ['upload-to-cloud', 'home.s1'],
    ['map-2', 'home.s2'],
    ['document', 'home.s3'],
  ];
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-copy">
          <span className="pill-label"><Icon name="favorite-list" aria-hidden="true" /> {t('home.badge')}</span>
          <h1>{t('home.title')}</h1>
          <p className="hero-sub">{t('home.sub')}</p>
          <div className="hero-actions">
            {role === 'candidate' ? (
              <>
                <Cta onClick={() => start('own')} loading={busy === 'own'} disabled={!!busy} testId="start-own">{t('home.start')}</Cta>
                {candidateId && <Cta variant="ghost" onClick={() => nav(run ? '/working' : '/evidence')}>{t('home.continue')}</Cta>}
              </>
            ) : (
              <Cta onClick={() => nav(homeFor(role))} testId="open-workspace">{t('home.open_workspace')}</Cta>
            )}
          </div>
          <ErrorNote error={err} />
          <ul className="hero-points">
            <li><Icon name="accept" aria-hidden="true" /> {t('home.p1')}</li>
            <li><Icon name="accept" aria-hidden="true" /> {t('home.p2')}</li>
            <li><Icon name="accept" aria-hidden="true" /> {t('home.p3')}</li>
          </ul>
        </div>
        <div className="hero-art"><HeroArt /></div>
      </section>

      <section className="how" aria-labelledby="how-h">
        <h2 id="how-h">{t('home.how')}</h2>
        <div className="how-grid stagger">
          {steps.map(([icon, key], i) => (
            <div className="how-card" key={key} style={{ ['--i' as any]: i }}>
              <span className="how-num">{i + 1}</span>
              <span className="how-icon"><Icon name={icon} aria-hidden="true" /></span>
              <h3>{t(key)}</h3>
              <p>{t(key + '_d')}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="persona-strip sample-strip card" aria-labelledby="sample-h">
        <Avatar size={72} />
        <div className="persona-text">
          <em id="sample-h">{t('home.sample_title')}</em>
          <b>Priya Sharma · 31</b>
          <span>{t('home.persona')}</span>
        </div>
        <Chip tone="warn" icon="hint">{t('home.fictional')}</Chip>
        {role === 'candidate' && <Cta variant="soft" onClick={() => start('sample')} loading={busy === 'sample'} disabled={!!busy} testId="start-demo">{t('home.start_sample')}</Cta>}
      </section>
    </div>
  );
}
