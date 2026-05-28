import { useState, useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';
// i18n
import { withTranslation } from 'react-i18next';
// CSS module
import style from './FamilySite.module.scss';
import classNames from 'classnames/bind';
const cx = classNames.bind(style);

const FamilySite = ({ t }) => {
  const [isOptionOpen, setIsOptionOpen] = useState(false);
  const family = useRef(null);
  const handleClick = useCallback(
    (e) => {
      if (
        family.current &&
        !ReactDOM.findDOMNode(family.current).contains(e.target)
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
  // Family Site 열기
  const moveFamilySite = (siteName) => {
    if (siteName === 'acryl') {
      window.open('https://www.acryl.ai/', '_blank');
    } else if (siteName === 'jonathan') {
      window.open('https://jonathan.acryl.ai/', '_blank');
    } else if (siteName === 'hugbot') {
      window.open('https://hugbot.acryl.ai/', '_blank');
    }
  };
  return (
    <div
      className={cx('family-site')}
      ref={family}
      onClick={() => {
        setIsOptionOpen(!isOptionOpen);
      }}
    >
      <span>{t('familySite.label')}</span>
      <img src='/images/icon/plus.svg' alt='+' />
      {isOptionOpen && (
        <ul className={cx('options')}>
          <li
            className={cx('option_li')}
            onClick={() => moveFamilySite('acryl')}
          >
            {t('acrylHomepage.label')}
          </li>
          <li
            className={cx('option_li')}
            onClick={() => moveFamilySite('jonathan')}
          >
            {t('jonathanHomepage.label')}
          </li>
          <li
            className={cx('option_li')}
            onClick={() => moveFamilySite('hugbot')}
          >
            {t('hugbotHomepage.label')}
          </li>
        </ul>
      )}
    </div>
  );
};
export default withTranslation()(FamilySite);
