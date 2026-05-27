import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

// CSS Module
import classNames from 'classnames/bind';
import style from './AdminNodeRateList.module.scss';

const cx = classNames.bind(style);

/**
 * 노드 페이지에서 사용되는 비율 목록 컴포넌트
 * @param {{
 *  title: string,
 *  listData: [ { name: string, used: number, total: number } ],
 * }} props
 */
const NodeRateList = ({
  listData,
  columns = [],
  handleRowClick = null,
  ...rest
}) => {
  const { t } = useTranslation();
  const scrollContRef = useRef(null);
  const headerRef = useRef(null);

  const handleBodyScroll = () => {
    if (headerRef.current && scrollContRef.current) {
      headerRef.current.scrollLeft = scrollContRef.current.scrollLeft;
    }
  };

  useEffect(() => {
    if (scrollContRef.current) {
      scrollContRef.current.addEventListener('scroll', handleBodyScroll);
    }

    return () => {
      if (scrollContRef.current) {
        // eslint-disable-next-line react-hooks/exhaustive-deps
        scrollContRef.current.removeEventListener('scroll', handleBodyScroll);
      }
    };
  }, []);

  return (
    <div className={cx('table')} {...rest}>
      <div className={cx('scroll-cont')} ref={scrollContRef}>
        <div className={cx('thead')} ref={headerRef}>
          <div className={cx('tr')}>
            {columns.map(({ label, headStyle }, key) => (
              <div key={key} className={cx('td')} style={headStyle}>
                {label}
              </div>
            ))}
          </div>
        </div>
        <div className={cx('tbody')}>
          {listData &&
            listData.length > 0 &&
            listData.map((d, idx) => {
              return (
                <div
                  key={idx}
                  className={cx('tr', handleRowClick && 'click')}
                  onClick={() => {
                    if (handleRowClick) {
                      handleRowClick(idx);
                    }
                  }}
                >
                  {columns.map(({ bodyStyle, selector, cell }, key) => (
                    <div key={key} className={cx('td')} style={bodyStyle}>
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
};

export default NodeRateList;
