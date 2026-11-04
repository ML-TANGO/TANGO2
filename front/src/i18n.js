import i18n from 'i18next';
import Backend from 'i18next-xhr-backend';
import Cache from 'i18next-localstorage-cache';
import { initReactI18next } from 'react-i18next';

const allowedLanguages = ['ko', 'en'];

let lng = 'ko';

// 처음에 브라우저 설정 언어 가져오기
const browserLanguage =
  navigator.language || navigator.userLanguage || navigator.systemLanguage;
if (browserLanguage !== null) {
  if (browserLanguage.toLowerCase().substring(0, 2) === 'ko') {
    lng = 'ko';
  } else {
    lng = 'en';
  }
}

// 언어 설정을 이미 한 경우
const storageLanguage = localStorage.getItem('language');
if (storageLanguage && allowedLanguages.indexOf(storageLanguage) > -1) {
  lng = storageLanguage;
}

if (import.meta.hot) {
  import.meta.hot.on('locales-update', () => {
    i18n.reloadResources().then(() => {
      i18n.changeLanguage(i18n.language);
    });
  });
}

i18n
  .use(Backend)
  .use(initReactI18next)
  .use(Cache)
  .init({
    lng,
    backend: {
      /* translation file path */
      loadPath: '/assets/i18n/{{ns}}/{{lng}}.json',
    },
    fallbackLng: 'en',
    debug: false,
    /* can have multiple namespace, in case you want to divide a huge translation into smaller pieces and load them on demand */
    ns: ['translations'],
    defaultNS: 'translations',
    keySeparator: false,
    interpolation: {
      escapeValue: false,
      formatSeparator: ',',
    },
    react: {
      useSuspense: false,
    },
  });

export default i18n;
