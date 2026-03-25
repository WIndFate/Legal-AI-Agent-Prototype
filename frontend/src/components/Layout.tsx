import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { SUPPORTED_LANGUAGES } from '../i18n';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const homeHref = location.pathname === '/' ? '#top' : '/#top';
  const examplesHref = location.pathname === '/' ? '#examples' : '/#examples';

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    i18n.changeLanguage(e.target.value);
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <Link to="/" className="brand">
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-copy">
              <span className="brand-name">{t('app.title')}</span>
              <span className="brand-subtitle">{t('app.subtitle')}</span>
            </span>
          </Link>
          <nav className="header-nav">
            <a href={homeHref} className={`nav-link ${isActive('/') ? 'nav-link-active' : ''}`}>
              {t('nav.home')}
            </a>
            <a href={examplesHref} className="nav-link">
              {t('nav.examples')}
            </a>
          </nav>
          <label className="language-shell">
            <span className="language-label">{t('nav.language')}</span>
            <select
              className="language-select"
              value={i18n.language}
              onChange={handleLanguageChange}
              aria-label={t('nav.language')}
            >
              {SUPPORTED_LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <div className="disclaimer-banner">
        {t('disclaimer.banner')}
      </div>

      <main className="main-content">
        {children}
      </main>

      <footer className="footer">
        <div className="footer-brand">
          <span className="brand-mark brand-mark-sm" aria-hidden="true" />
          <div>
            <p className="footer-brand-name">{t('app.title')}</p>
            <p className="footer-tagline">{t('app.subtitle')}</p>
          </div>
        </div>
        <nav className="footer-nav">
          <a href={homeHref}>{t('nav.home')}</a>
          <a href={examplesHref}>{t('nav.examples')}</a>
          <Link to="/privacy">{t('footer.privacy')}</Link>
          <Link to="/terms">{t('footer.terms')}</Link>
        </nav>
        <p className="footer-disclaimer">
          {t('footer.disclaimer')}
        </p>
        <p className="footer-copyright">{t('footer.copyright')}</p>
      </footer>
    </div>
  );
}
