import { useEffect, useState, type ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { LoginDialog, NextBar, RoleBar, SideNav, TopBar } from './components/chrome';
import { AccessGate, Toasts } from './components/ui';
import { useI18n } from './i18n';
import Activity from './pages/Activity';
import Architecture from './pages/Architecture';
import Employer from './pages/Employer';
import Evidence from './pages/Evidence';
import Fairness from './pages/Fairness';
import Gaps from './pages/Gaps';
import Landing from './pages/Landing';
import Learning from './pages/Learning';
import Passport from './pages/Passport';
import Practice from './pages/Practice';
import Profile from './pages/Profile';
import Review from './pages/Review';
import Roles from './pages/Roles';
import Skills from './pages/Skills';
import Working from './pages/Working';

const guard = (route: string, el: ReactNode) => <Route path={route} element={<AccessGate route={route}>{el}</AccessGate>} />;

export default function App() {
  const { t } = useI18n();
  const loc = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => {
    setNavOpen(false);
    document.getElementById('main')?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [loc.pathname]);
  return (
    <div className="app">
      <a className="skip-link" href="#main">{t('app.skip')}</a>
      <div className="chrome">
        <TopBar onMenu={() => setNavOpen((o) => !o)} />
        <RoleBar />
      </div>
      <div className="body">
        <SideNav open={navOpen} onClose={() => setNavOpen(false)} />
        <main id="main" tabIndex={-1}>
          <NextBar />
          <div key={loc.pathname} className="page page-enter">
            <Routes>
              {guard('/', <Landing />)}
              {guard('/profile', <Profile />)}
              {guard('/evidence', <Evidence />)}
              {guard('/working', <Working />)}
              {guard('/skills', <Skills />)}
              {guard('/roles', <Roles />)}
              {guard('/gaps', <Gaps />)}
              {guard('/learning', <Learning />)}
              {guard('/employer', <Employer />)}
              {guard('/fairness', <Fairness />)}
              {guard('/review', <Review />)}
              {guard('/passport', <Passport />)}
              {guard('/activity', <Activity />)}
              {guard('/architecture', <Architecture />)}
              {guard('/practice', <Practice />)}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
          <footer className="foot">{t('app.footer')}</footer>
        </main>
      </div>
      <LoginDialog />
      <Toasts />
    </div>
  );
}
