import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import ja from './locales/ja.json';
import en from './locales/en.json';
import zhCN from './locales/zh-CN.json';
import zhTW from './locales/zh-TW.json';
import ko from './locales/ko.json';
import vi from './locales/vi.json';
import ptBR from './locales/pt-BR.json';
import id from './locales/id.json';
import ne from './locales/ne.json';

export const SUPPORTED_LANGUAGES = [
  { code: 'ja', name: '日本語' },
  { code: 'en', name: 'English' },
  { code: 'zh-CN', name: '简体中文' },
  { code: 'zh-TW', name: '繁體中文' },
  { code: 'ko', name: '한국어' },
  { code: 'vi', name: 'Tiếng Việt' },
  { code: 'pt-BR', name: 'Português' },
  { code: 'id', name: 'Bahasa Indonesia' },
  { code: 'ne', name: 'नेपाली' },
] as const;

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      ja: { translation: ja },
      en: { translation: en },
      'zh-CN': { translation: zhCN },
      'zh-TW': { translation: zhTW },
      ko: { translation: ko },
      vi: { translation: vi },
      'pt-BR': { translation: ptBR },
      id: { translation: id },
      ne: { translation: ne },
    },
    fallbackLng: 'ja',
    supportedLngs: SUPPORTED_LANGUAGES.map(l => l.code),
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'language',
      caches: ['localStorage'],
    },
    interpolation: {
      escapeValue: false,
    },
  });

// Apply ?lang= from email links for this visit only — do not persist to
// localStorage so the user's manually chosen site language is not overwritten.
const _langParam = new URLSearchParams(window.location.search).get('lang');
if (_langParam && SUPPORTED_LANGUAGES.some(l => l.code === _langParam)) {
  const _prev = localStorage.getItem('language');
  i18n.changeLanguage(_langParam);
  // Restore localStorage to the value before changeLanguage wrote to it
  if (_prev !== null) {
    localStorage.setItem('language', _prev);
  } else {
    localStorage.removeItem('language');
  }
}

export default i18n;
