// CSS Module
import classNames from 'classnames/bind';
import style from './CompanyLogo.module.scss';

const cx = classNames.bind(style);

function CompanyLogo() {
  return (
    <div className={cx('powered-by')}>
      <span className={cx('text')}>Powered by</span>
      <a href='https://www.acryl.ai' rel='noopener noreferrer' target='_blank'>
        <img
          className={cx('logo')}
          alt='Powered by ACRYL'
          src='/images/logo/ACRYL_CI-white-text-color-logo.png'
        />
      </a>
    </div>
  );
}

export default CompanyLogo;
