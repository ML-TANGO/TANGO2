import { useEffect, useState } from 'react';

// i18n
// import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './ProgressStatusItem.module.scss';
const cx = classNames.bind(style);

ProgressStatusItem.defaultProps = {
  title: '-',
  rate: '-',
  data: undefined,
};

function ProgressStatusItem({ data, countHandler }) {
  // const { t } = useTranslation();
  const [title, setTitle] = useState('');
  const [rate, setRate] = useState('');
  useEffect(() => {
    if (!data) {
      countHandler();
      return;
    }
    if (data.setCallback) {
      data.setCallback((result) => {
        if (result) {
          const { title, rate } = result;
          setTitle(title);
          setRate(rate);
        } else {
          countHandler();
        }
      });
    }
    if (data.setDoneFunc) {
      data.setDoneFunc(countHandler);
    }
  }, [data, countHandler]);

  return (
    <li className={cx('progress-item')}>
      <div className={cx('progress-info')}>
        <span className={cx('rate')}>{rate}%</span>
        <span className={cx('name')}>
          {/* {t('decompression.label')} */}
          {title}
        </span>
      </div>
      <div className={cx('progress')}>
        <div className={cx('bar')} style={{ width: `${rate}%` }}></div>
      </div>
    </li>
  );
}

export default ProgressStatusItem;
