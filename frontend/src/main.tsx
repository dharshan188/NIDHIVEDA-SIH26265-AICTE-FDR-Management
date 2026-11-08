import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MotionConfig } from 'framer-motion';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { installMotionPreference } from './lib/motion';
import { PrefsProvider } from './lib/prefs';
import { StoreProvider } from './store/Store';
import './styles/tokens.css';
import './styles.css';
import './styles/polish.css';
import './styles/nudge.css';

installMotionPreference();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <PrefsProvider>
        <StoreProvider>
          <MotionConfig reducedMotion="user">
            <App />
          </MotionConfig>
        </StoreProvider>
      </PrefsProvider>
    </BrowserRouter>
  </StrictMode>,
);
