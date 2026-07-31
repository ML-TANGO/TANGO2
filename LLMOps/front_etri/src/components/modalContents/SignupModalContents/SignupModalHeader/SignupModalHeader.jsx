import tangoIcon from '@images/logo/ICO_Tango.svg';

import closeIcon from './ic-close.svg';

// CSS module
import classNames from 'classnames/bind';
import style from '../SignupModalContent.module.scss';

const cx = classNames.bind(style);

const SignupModalHeader = ({ t, handleCloseModal }) => {
  return (
    <div className={cx('header')}>
      <img
        className={cx('close-button')}
        onClick={handleCloseModal}
        src={closeIcon}
        alt='close'
      />
      <img src={tangoIcon} alt='logo' className={cx('img')} />
      <div className={cx('title')}>Request to Join</div>
      <div className={cx('sub-title')}>
        {t('signup.title1.label')}
        <br />
        {t('signup.title2.label')}
      </div>
    </div>
  );
};

export default SignupModalHeader;
