// CSS module
import classNames from 'classnames/bind';
import style from './StorageSettingModalHeader.module.scss';
const cx = classNames.bind(style);

function StorageSettingModalHeader(headerPorps) {
  const { t } = headerPorps;
  return (
    <>
      <h2 className={cx('title')}>{t('storageSetting.label')}</h2>
    </>
  );
}

export default StorageSettingModalHeader;
