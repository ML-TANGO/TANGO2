// i18n
import { useTranslation } from 'react-i18next';

import PropTypes from 'prop-types';

import classNames from 'classnames/bind';
import styles from './CustomTable.module.scss';

const cx = classNames.bind(styles);

/**
 * @param {{
 *  title: string,
 *  data: Array<Object>,
 *  columns: Array<{ label: string, selector: string, headStyle?: Object, bodyStyle?: Object, cell?: Function, minWidth?: string, maxWidth?: string}>
 * }} props
 */
const CustomTable = ({ title, data = [], columns = [] }) => {
  const { t } = useTranslation();
  return (
    <div className={cx('table-wrapper')}>
      {title && <div className={cx('table-title')}>{title}</div>}
      <div className={cx('table-scrollable')}>
        <table className={cx('custom-table')}>
          <thead className={cx('table-head')}>
            <tr className={cx('table-row')}>
              {columns.map((column, index) => (
                <th
                  key={index}
                  className={cx('table-cell', 'table-head-cell')}
                  style={{
                    ...column.headStyle,
                    minWidth: column.minWidth || 'auto',
                    maxWidth: column.maxWidth || 'none',
                    width: column.width || 'auto',
                  }}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className={cx('table-body')}>
            {data.length === 0 ? (
              <tr className={cx('table-no-data')}>
                <td colSpan={columns.length}>
                  <span>{t('noData.message')}</span>
                </td>
              </tr>
            ) : (
              data.map((row, rowIndex) => (
                <tr key={rowIndex} className={cx('table-row')}>
                  {columns.map((column, colIndex) => (
                    <td
                      key={colIndex}
                      className={cx('table-cell')}
                      style={{
                        ...column.bodyStyle,
                        minWidth: column.minWidth || 'auto',
                        maxWidth: column.maxWidth || 'none',
                        width: column.width || 'auto',
                      }}
                    >
                      {column.cell ? column.cell(row) : row[column.selector]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

CustomTable.propTypes = {
  title: PropTypes.string,
  data: PropTypes.arrayOf(PropTypes.object).isRequired,
  columns: PropTypes.arrayOf(
    PropTypes.shape({
      label: PropTypes.string.isRequired,
      selector: PropTypes.string,
      headStyle: PropTypes.object,
      bodyStyle: PropTypes.object,
      cell: PropTypes.func,
      minWidth: PropTypes.string,
      maxWidth: PropTypes.string,
    }),
  ).isRequired,
};

export default CustomTable;
