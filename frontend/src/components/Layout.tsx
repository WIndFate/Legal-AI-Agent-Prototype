import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import clsx from 'clsx';
import { SUPPORTED_LANGUAGES } from '../i18n';
import styles from '../styles/layout.module.css';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const homeHref = location.pathname === '/' ? '#top' : '/#top';

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    i18n.changeLanguage(e.target.value);
  };

  const navigateToAnchor = (targetId: 'top') => (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (location.pathname === '/') {
      event.preventDefault();
      const target = document.getElementById(targetId);
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (targetId === 'top') {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
      return;
    }

    event.preventDefault();
    navigate(`/#${targetId}`);
    window.setTimeout(() => {
      const target = document.getElementById(targetId);
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 120);
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="app">
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link to="/" className={styles.brand}>
            <span className={styles.brandMark} aria-hidden="true" />
            <span className={styles.brandCopy}>
              <span className={styles.brandName}>{t('app.title')}</span>
              <span className={styles.brandSubtitle}>{t('app.subtitle')}</span>
            </span>
          </Link>
          <nav className={styles.headerNav}>
            <a
              href={homeHref}
              onClick={navigateToAnchor('top')}
              className={clsx(styles.navLink, isActive('/') && styles.navLinkActive)}
            >
              {t('nav.home')}
            </a>
            <Link to="/examples" className={clsx(styles.navLink, isActive('/examples') && styles.navLinkActive)}>
              {t('nav.examples')}
            </Link>
            <Link to="/lookup" className={clsx(styles.navLink, isActive('/lookup') && styles.navLinkActive)}>
              {t('nav.lookup')}
            </Link>
          </nav>
          <label className={styles.languageShell}>
            <span className={styles.languageLabel}>{t('nav.language')}</span>
            <select
              className={styles.languageSelect}
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

      <div className={styles.disclaimerBanner}>
        {t('disclaimer.banner')}
      </div>

      <main className={styles.mainContent}>
        {children}
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerBrand}>
          <span className={clsx(styles.brandMark, styles.brandMarkSm)} aria-hidden="true" />
          <div>
            <p className={styles.footerBrandName}>{t('app.title')}</p>
            <p className={styles.footerTagline}>{t('app.subtitle')}</p>
          </div>
        </div>
        <nav className={styles.footerNav}>
          <a href={homeHref} onClick={navigateToAnchor('top')}>{t('nav.home')}</a>
          <Link to="/examples">{t('nav.examples')}</Link>
          <Link to="/lookup">{t('nav.lookup')}</Link>
          <Link to="/privacy">{t('footer.privacy')}</Link>
          <Link to="/terms">{t('footer.terms')}</Link>
        </nav>
        <p className={styles.footerDisclaimer}>
          {t('footer.disclaimer')}
        </p>
        <p className={styles.footerCopyright}>{t('footer.copyright')}</p>
      </footer>
    </div>
  );
}
