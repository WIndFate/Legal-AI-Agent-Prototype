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
      order: ['querystring', 'localStorage', 'navigator', 'htmlTag'],
      lookupQuerystring: 'lang',
      lookupLocalStorage: 'language',
      caches: ['localStorage'],
    },
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
