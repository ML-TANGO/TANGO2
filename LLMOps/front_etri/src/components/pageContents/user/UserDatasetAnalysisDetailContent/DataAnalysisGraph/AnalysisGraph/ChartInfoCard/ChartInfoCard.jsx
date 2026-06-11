import { useTranslation } from 'react-i18next';

import { Checkbox } from '@tango/ui-react';

import classNames from 'classnames/bind';
import style from './ChartInfoCard.module.scss';

const cx = classNames.bind(style);

const ChartInfoCard = ({
  type,
  data,

  checkboxHandler,
  checkedId,
  showInfoHandler,
}) => {
  const { t } = useTranslation();

  return (
    <div className={cx('chart-item')}>
      <div className={cx('title')}>
        <Checkbox
          checked={checkedId.includes(data?.id)}
          onChange={() => {
            checkboxHandler(data?.id);
          }}
          customStyle={{
            padding: '0 0 0 16px',
            fontSize: '14px',
          }}
          // disabled={false}
        />
        <div className={cx('graph-name')}>{data?.name ?? '-'}</div>
      </div>
      {/* <div className={cx('chart-container')}>
        
      </div> */}
      <div
        className={cx('info-container')}
        onClick={() => showInfoHandler(data?.id)}
      >
        <div className={cx('item')}>
          <span className={cx('label')}>{t('description.label')}</span>
          <span className={cx('value', data?.description ?? 'no-desc')}>
            {data?.description ?? t('no.desc')}
          </span>
        </div>
        <div className={cx('item')}>
          <span className={cx('label')}>{t('dataset.label')}</span>
          <span className={cx('value')}>
            <img src={'/images/icon/data-black.svg'} alt='icon' />
            {data?.dataset ?? '-'}
          </span>
        </div>
        <div className={cx('item')}>
          <span className={cx('label')}>{t('data.label')}</span>
          <span className={cx('value')}>
            <img src={'/images/icon/file-black.svg'} alt='icon' />
            {data?.data ?? '-'}
          </span>
        </div>
        <div className={cx('item')}>
          <span className={cx('label')}>{t('visualizationField.label')}</span>
          <span className={cx('value')}>{data?.column ?? '-'}</span>
        </div>
      </div>
      {/* <div className={cx('epoch')}>
        <img src='/images/icon/info-icon.svg' alt='icon' />1 Epoch = {epoch}{' '}
        steps
      </div> */}
    </div>
  );
};

export default ChartInfoCard;
