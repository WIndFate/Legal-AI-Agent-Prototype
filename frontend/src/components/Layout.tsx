import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { SUPPORTED_LANGUAGES } from '../i18n';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { t, i18n } = useTranslation();

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    i18n.changeLanguage(e.target.value);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <Link to="/" className="logo">
            <h1>{t('app.title')}</h1>
          </Link>
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
        </div>
      </header>

      <div className="disclaimer-banner">
        {t('disclaimer.banner')}
      </div>

      <main className="main-content">
        {children}
      </main>

      <footer className="footer">
        <p className="footer-disclaimer">
          本サービスは法律相談ではありません。具体的な法的判断は弁護士にご相談ください
        </p>
        <div className="footer-links">
          <span>{t('footer.privacy')}</span>
          <span>{t('footer.terms')}</span>
        </div>
      </footer>
    </div>
  );
}
