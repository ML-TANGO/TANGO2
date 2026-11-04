import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './HpsParamSetting.module.scss'; // 기존 scss 재사용 (HpsLogModal.module.scss)

const cx = classNames.bind(style);

function HpsParamSetting() {
  const { t } = useTranslation();
  return (
    <div className={cx('param-box')}>
      <div className={cx('item')}>
        <span className={cx('param')}>batch_size_per_gpu</span>
        <span className={cx('setting-value')}>
          <span>{t('min.label')}</span>
          <span>16</span>
        </span>
        <span className={cx('setting-value')}>
          <span>{t('max.label')}</span>
          <span>16</span>
        </span>
        <span className={cx('setting-value')}>
          <span>{t('searchCount.label')}</span>
          <span>20</span>
        </span>
      </div>
      <div className={cx('item')}>
        <span className={cx('param')}>epochs</span>
        <span className={cx('setting-value')}>
          <span>{t('min.label')}</span>
          <span>16</span>
        </span>
        <span className={cx('setting-value')}>
          <span>{t('max.label')}</span>
          <span>16</span>
        </span>
        <span className={cx('setting-value')}>
          <span>{t('searchCount.label')}</span>
          <span>20</span>
        </span>
      </div>
      <div className={cx('item')}>
        <span className={cx('param')}>lr</span>
        <span className={cx('setting-value')}>
          <span>{t('min.label')}</span>
          <span>16</span>
        </span>
        <span className={cx('setting-value')}>
          <span>{t('max.label')}</span>
          <span>16</span>
        </span>
        <span className={cx('setting-value')}>
          <span>{t('searchCount.label')}</span>
          <span>20</span>
        </span>
      </div>
    </div>
  );
}

export default HpsParamSetting;
