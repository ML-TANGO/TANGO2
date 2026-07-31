import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './DatasetFileUploadModalHeader.module.scss';

const cx = classNames.bind(style);

function DatasetFileUploadModalHeader() {
  const { t } = useTranslation();

  return <h2 className={cx('title')}>{t('uploadData.label')}</h2>;
}
export default DatasetFileUploadModalHeader;
