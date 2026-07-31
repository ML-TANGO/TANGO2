import { useDispatch, useSelector } from 'react-redux';

import i18next from 'i18next';

// Actions
import { langSettingPopup } from '@src/store/modules/headerOptions';

// Components
import Popup from '../Popup';
import ContextPopupBtn from '../ContextPopupBtn';

// CSS Module
import classNames from 'classnames/bind';
import style from './LangSetting.module.scss';

const cx = classNames.bind(style);

function LangSetting() {
  const dispatch = useDispatch();
  const selected = i18next.language;
  const {
    headerOptions: { langSettingPopup: isOpen },
  } = useSelector((state) => ({
    headerOptions: state.headerOptions,
  }));

  const popupHandler = () => {
    dispatch(langSettingPopup());
  };

  // 언어 변경
  const changeLanguage = (lng) => {
    window.localStorage.setItem('language', lng);
    popupHandler();
    i18next.changeLanguage(lng);
  };
  return (
    <div className={cx('lang-setting')}>
      {isOpen && (
        <Popup popupHandler={popupHandler} position='right'>
          <ul className={cx('options')}>
            <li
              className={cx('option_li', selected === 'ko' && 'selected')}
              onClick={() => changeLanguage('ko')}
            >
              <img
                className={cx('flag')}
                src='/images/icon/Korea.svg'
                alt='Korea'
              />
              <span>한국어</span>
            </li>
            <li
              className={cx('option_li', selected === 'en' && 'selected')}
              onClick={() => changeLanguage('en')}
            >
              <img
                className={cx('flag')}
                src='/images/icon/USA.svg'
                alt='USA'
              />
              <span>ENGLISH</span>
            </li>
          </ul>
        </Popup>
      )}
      <ContextPopupBtn
        isOpen={isOpen}
        customStyle={{ padding: '6px' }}
        popupHandler={popupHandler}
        disableArrow
      >
        <img src='/images/icon/lang.svg' alt='lang icon' />
      </ContextPopupBtn>
    </div>
  );
}

export default LangSetting;
