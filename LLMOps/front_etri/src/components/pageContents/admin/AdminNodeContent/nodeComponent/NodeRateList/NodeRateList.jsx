import { memo } from 'react';
import { useTranslation } from 'react-i18next';

// Components
import ListLoading from './ListLoading';

// CSS Module
import classNames from 'classnames/bind';
import style from './NodeRateList.module.scss';

const cx = classNames.bind(style);

/**
 * 노드 페이지에서 사용되는 비율 목록 컴포넌트
 * @param {{
 *  title: string,
 *  listData: [ { name: string, used: number, total: number } ],
 * }} props
 */
const NodeRateList = memo(({ title, listData, columns = [] }) => {
  const { t } = useTranslation();

  return (
    <div className={cx('node-rate-list')}>
      <div className={cx('title')}>{title}</div>
      <div className={cx('table')}>
        {/* <div className={cx('thead')}>
          <div className={cx('tr')}>
            {columns.map(({ label, headStyle }, key) => (
              <div key={key} className={cx('td')} style={headStyle}>
                {label}
              </div>
            ))}
          </div>
        </div> */}
        <div className={cx('tbody')}>
          {listData === null && <ListLoading />}
          {listData &&
            listData.length > 0 &&
            listData.map((d, i) => {
              return (
                <div key={i} className={cx('tr')}>
                  {columns.map(({ bodyStyle, selector, cell }, key) => (
                    <div key={key} className={cx('td')} style={bodyStyle}>
                      <span className={cx('name')}>{d.name}</span>
                      {cell ? cell(d) : d[selector]}
                    </div>
                  ))}
                </div>
              );
            })}
          {listData && listData.length === 0 && (
            <div className={cx('no-data')}>
              <span>{t('noData.message')}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

export default NodeRateList;
