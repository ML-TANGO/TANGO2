import { useCallback } from 'react';
import { Button } from '@tango/ui-react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { logoutRequest } from '@src/store/modules/auth';

import FlightbaseIcon from '@images/logo/ICO_Tango.svg';
import Error500FontEn from '@images/logo/500Font.svg';
import Error500FontKo from '@images/logo/500FontKO.svg';

import classNames from 'classnames/bind';
import style from './ErrorContent.module.scss';
const cx = classNames.bind(style);

const ErrorContent = () => {
  const { i18n } = useTranslation();
  const { language: lan } = i18n;
  const dispatch = useDispatch();

  const handleBack = useCallback(() => {
    dispatch(logoutRequest());
    window.location.href = '/';
  }, [dispatch]);

  return (
    <div className={cx('page-container')}>
      <div className={cx('error-container')}>
        <div className={cx('left-side')}>
          <div className={cx('img')}>
            <img src={FlightbaseIcon} alt='Token Expired' />
          </div>
        </div>
        <div className={cx('right-side')}>
          <div className={cx('code')}>
            <img
              src={lan === 'en' ? Error500FontEn : Error500FontKo}
              alt='tokenError'
            />
          </div>

          <div className={cx('btn')}>
            <Button
              onClick={() => handleBack()}
              customStyle={{
                fontFamily: 'MarkerFont',
                fontWeight: '500',
              }}
            >
              <div className={cx('desc')}>
                {lan === 'en' ? 'Bring me back' : '돌아가기'}
              </div>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ErrorContent;
