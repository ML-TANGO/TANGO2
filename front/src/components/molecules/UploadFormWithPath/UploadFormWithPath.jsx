// i18n
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './UploadFormWithPath.module.scss';
const cx = classNames.bind(style);

function UploadFormWithPath({ children, datasetName, path }) {
  const { t } = useTranslation();
  return path === '/' ? (
    <div className={cx('wrapper')}>
      {/* <p className={cx('form-type')}>
        {`/${datasetName || `{${t('datasetName.label')}}`}/`}
      </p>
      <p className={cx('form-desc')}>{t('topLevelPath.message')}</p> */}
      {children}
    </div>
  ) : (
    <div className={cx('wrapper')}>
      <p className={cx('form-type')}>{`/${datasetName}${path}`}</p>
      <p className={cx('form-desc')}>{t('path.message')}</p>
      {children}
    </div>
  );
}

export default UploadFormWithPath;
