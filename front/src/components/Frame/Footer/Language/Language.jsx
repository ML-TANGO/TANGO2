import { useState, useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';

// i18n
import i18next from 'i18next';
import { withTranslation } from 'react-i18next';

// CSS module
import style from './Language.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const IS_CUSTOM = import.meta.env.VITE_REACT_APP_MODE === 'CUSTOM';

const Language = () => {
  const options = { ko: '한국어', en: 'English' };
  const selected = i18next.language;
  const [isOptionOpen, setIsOptionOpen] = useState(false);

  const language = useRef(null);
  const handleClick = useCallback(
    (e) => {
      if (
        language.current &&
        !ReactDOM.findDOMNode(language.current).contains(e.target)
      ) {
        setIsOptionOpen(false);
      }
    },
    [setIsOptionOpen],
  );
  useEffect(() => {
    document.addEventListener('click', handleClick, false);
    return () => {
      document.removeEventListener('click', handleClick, false);
    };
  }, [handleClick]);

  // 언어 변경
  const changeLanguage = (lng) => {
    window.localStorage.setItem('language', lng);
    i18next.changeLanguage(lng);
  };
  return (
    <div
      className={cx('language-setting', IS_CUSTOM && 'custom')}
      ref={language}
      onClick={() => {
        setIsOptionOpen(!isOptionOpen);
      }}
    >
      <img
        src='/images/icon/public.svg'
        alt='language'
        className={cx('language-icon')}
      />
      <span className={cx('language-selected')}>
        {options[i18next.language]}
      </span>
      <img
        src='/images/icon/arrow-down.svg'
        alt='▼'
        className={cx('arrow-icon', isOptionOpen && 'open')}
      />
      {isOptionOpen && (
        <ul className={cx('options')}>
          <li
            className={cx('option_li', selected === 'ko' && 'selected')}
            onClick={() => changeLanguage('ko')}
          >
            {options.ko}
          </li>
          <li
            className={cx('option_li', selected === 'en' && 'selected')}
            onClick={() => changeLanguage('en')}
          >
            {options.en}
          </li>
        </ul>
      )}
    </div>
  );
};

export default withTranslation()(Language);
