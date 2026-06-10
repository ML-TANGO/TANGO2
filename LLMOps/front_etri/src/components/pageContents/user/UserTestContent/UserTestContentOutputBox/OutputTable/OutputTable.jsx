import { Fragment } from 'react';

import classNames from 'classnames/bind';
import style from './OutputTable.module.scss';
const cx = classNames.bind(style);

const OutputTable = ({ idx, output }) => {
  return (
    <div className={cx('result-table')}>
      <label className={cx('title')}>{Object.keys(output)[0]}</label>
      <table key={idx} className={cx('table')}>
        {output[Object.keys(output)].map((item, i) => {
          const columnKeys = Object.keys(item);
          return (
            <Fragment key={i}>
              {i === 0 && (
                <thead>
                  <tr>
                    {columnKeys.map((key, j) => (
                      <th key={j}>{key}</th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody>
                <tr>
                  {columnKeys.map((key, k) => (
                    <td key={k}>{JSON.stringify(item[key])}</td>
                  ))}
                </tr>
              </tbody>
            </Fragment>
          );
        })}
      </table>
    </div>
  );
};

export default OutputTable;
