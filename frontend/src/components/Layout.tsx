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
  const languageBadge = getLanguageBadge(i18n.language);

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
  const navItems = [
    {
      key: 'home',
      label: t('nav.home'),
      href: homeHref,
      active: isActive('/'),
    },
    {
      key: 'examples',
      label: t('nav.examples'),
      to: '/examples',
      active: isActive('/examples'),
    },
    {
      key: 'lookup',
      label: t('nav.lookup'),
      to: '/lookup',
      active: isActive('/lookup'),
    },
  ];

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
            {navItems.map((item) =>
              item.to ? (
                <Link key={item.key} to={item.to} className={clsx(styles.navLink, item.active && styles.navLinkActive)}>
                  {item.label}
                </Link>
              ) : (
                <a
                  key={item.key}
                  href={item.href}
                  onClick={navigateToAnchor('top')}
                  className={clsx(styles.navLink, item.active && styles.navLinkActive)}
                >
                  {item.label}
                </a>
              ),
            )}
          </nav>
          <label className={styles.languageShell}>
            <span className={styles.languageLabel}>{t('nav.language')}</span>
            <span className={styles.languageCurrent} aria-hidden="true">{languageBadge}</span>
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

      <nav className={styles.mobileQuickNav}>
        <div className={styles.mobileQuickNavInner}>
          {navItems.map((item) =>
            item.to ? (
              <Link
                key={item.key}
                to={item.to}
                className={clsx(styles.mobileQuickNavLink, item.active && styles.mobileQuickNavLinkActive)}
              >
                {item.label}
              </Link>
            ) : (
              <a
                key={item.key}
                href={item.href}
                onClick={navigateToAnchor('top')}
                className={clsx(styles.mobileQuickNavLink, item.active && styles.mobileQuickNavLinkActive)}
              >
                {item.label}
              </a>
            ),
          )}
        </div>
      </nav>

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

function getLanguageBadge(code: string) {
  if (code === 'zh-CN') return 'CN';
  if (code === 'zh-TW') return 'TW';
  if (code === 'pt-BR') return 'PT';
  return code.slice(0, 2).toUpperCase();
}
