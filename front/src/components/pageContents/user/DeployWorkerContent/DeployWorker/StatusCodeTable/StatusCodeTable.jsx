// i18n
import { useTranslation } from 'react-i18next';

// Components
import { Tooltip } from '@jonathan/ui-react';

// CSS Module
import classNames from 'classnames/bind';
import style from './StatusCodeTable.module.scss';
const cx = classNames.bind(style);

function StatusCodeTable({ data }) {
  const {
    200: status2xx,
    300: status3xx,
    400: status4xx,
    500: status5xx,
    rest: statusEtc,
  } = data;
  const { t } = useTranslation();
  return (
    <div className={cx('status-code-count')}>
      <label>
        <span>{t('statusCodeCount.label')}</span>
        <Tooltip
          title={t('statusCodeCount.tooltip.title')}
          contents={
            <>
              <ul className={cx('list-tooltip')}>
                <li>{t('statusCodeCount.tooltip.message2')}</li>
                <li>{t('statusCodeCount.tooltip.message3')}</li>
                <li>{t('statusCodeCount.tooltip.message4')}</li>
                <li>{t('statusCodeCount.tooltip.message5')}</li>
              </ul>
              <div style={{ marginTop: '8px', fontSize: '12px' }}>
                {t('statusCodeCount.tooltip.message1')}
              </div>
            </>
          }
          contentsAlign={{ horizontal: 'left' }}
          iconCustomStyle={{ width: '20px' }}
          contentsCustomStyle={{ width: '360px' }}
        />
      </label>
      <div className={cx('table-area')}>
        <div className={cx('table')}>
          <div className={cx('header')}>
            <label>2xx</label>
            <label>3xx</label>
            <label>4xx</label>
            <label>5xx</label>
            <label>etc.</label>
          </div>
          <div className={cx('body')}>
            <ol>
              {status2xx &&
                Object.keys(status2xx).map((key, idx) => {
                  return (
                    <li key={idx}>
                      {key}: {status2xx[key]}
                    </li>
                  );
                })}
            </ol>
            <ol>
              {status3xx &&
                Object.keys(status3xx).map((key, idx) => {
                  return (
                    <li key={idx}>
                      {key}: {status3xx[key]}
                    </li>
                  );
                })}
            </ol>
            <ol>
              {status4xx &&
                Object.keys(status4xx).map((key, idx) => {
                  return (
                    <li key={idx}>
                      {key}: {status4xx[key]}
                    </li>
                  );
                })}
            </ol>
            <ol>
              {status5xx &&
                Object.keys(status5xx).map((key, idx) => {
                  return (
                    <li key={idx}>
                      {key}: {status5xx[key]}
                    </li>
                  );
                })}
            </ol>
            <ol>
              {statusEtc &&
                Object.keys(statusEtc).map((key, idx) => {
                  return (
                    <li key={idx}>
                      {key}: {statusEtc[key]}
                    </li>
                  );
                })}
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}

export default StatusCodeTable;
