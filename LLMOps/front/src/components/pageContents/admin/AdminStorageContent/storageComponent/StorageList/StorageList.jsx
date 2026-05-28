import { useTranslation } from 'react-i18next';

// Components
//import ListLoading from './ListLoading';

// CSS Module
import classNames from 'classnames/bind';
import style from './StorageList.module.scss';

const cx = classNames.bind(style);

/**
 * 노드 페이지에서 사용되는 비율 목록 컴포넌트
 * @param {{
 *  title: string,
 *  listData: [ { name: string, used: number, total: number } ],
 * }} props
 */
function StorageList({ listData, columns = [], isColumnShow = true }) {
  const { t } = useTranslation();

  return (
    <div className={cx('node-rate-list')}>
      <table className={cx('table')}>
        {isColumnShow && (
          <thead className={cx('thead')}>
            <tr className={cx('tr')}>
              {columns.map(({ label, headStyle }, key) => (
                <td key={key} className={cx('td')} style={headStyle}>
                  {label}
                </td>
              ))}
            </tr>
          </thead>
        )}

        <tbody className={cx('tbody')}>
          {listData &&
            listData.length > 0 &&
            listData.map((d, i) => {
              return (
                <tr key={i} className={cx('tr')}>
                  {columns.map(({ bodyStyle, selector, cell }, key) => {
                    if (!d) {
                      return (
                        <td
                          key={key}
                          className={cx('td')}
                          style={bodyStyle}
                        ></td>
                      );
                    }

                    return (
                      <div key={key} className={cx('td')} style={bodyStyle}>
                        {cell ? cell(d) : d[selector]}
                      </div>
                    );
                  })}
                </tr>
              );
            })}
          {listData && listData.length === 0 && (
            <div className={cx('no-data')}>
              <span>{t('noData.message')}</span>
            </div>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default StorageList;
