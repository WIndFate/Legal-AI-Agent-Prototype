import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function NotFoundPage() {
  const { t } = useTranslation();
  const location = useLocation();

  return (
    <div className="page not-found-page">
      <div className="not-found-card">
        <p className="not-found-code">404</p>
        <h2 className="not-found-title">{t('not_found.title')}</h2>
        <p className="not-found-body">{t('not_found.body')}</p>
        <p className="not-found-path">{location.pathname}</p>
        <div className="not-found-actions">
          <Link to="/" className="btn-primary not-found-action">
            {t('not_found.home_action')}
          </Link>
          <Link to="/lookup" className="btn-share not-found-action">
            {t('not_found.lookup_action')}
          </Link>
        </div>
      </div>
    </div>
  );
}
