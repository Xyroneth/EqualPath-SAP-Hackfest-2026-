import '@ui5/webcomponents-react/dist/Assets.js';
import '@ui5/webcomponents-icons/dist/AllIcons.js';
import { ThemeProvider } from '@ui5/webcomponents-react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { I18nProvider } from './i18n';
import { AppProvider } from './state';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <ThemeProvider>
        <BrowserRouter>
          <AppProvider>
            <App />
          </AppProvider>
        </BrowserRouter>
      </ThemeProvider>
    </I18nProvider>
  </StrictMode>,
);
