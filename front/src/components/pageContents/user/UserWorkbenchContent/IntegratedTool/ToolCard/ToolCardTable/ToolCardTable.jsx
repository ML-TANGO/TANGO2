import classNames from 'classnames/bind';
import style from './ToolCardTable.module.scss';

const cx = classNames.bind(style);

const ToolCardTable = ({ executreList, t }) => {
  return (
    <div className={cx('content')}>
      <div className={cx('tab-menu')}>
        <div className={cx('menu-item', 'selected')}>
          {t('runEnvironment.label')}
        </div>
      </div>
      <div className={cx('inner-box')}>
        <ul className={cx('list')}>
          {executreList.map((info, idx) => {
            return (
              <li className={cx('item')} key={idx}>
                <div
                  className={cx('label', info.label === 'Master Pod' && 'bold')}
                >
                  {info.label}
                </div>
                <div className={cx('value')}>{info.value}</div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
};

export default ToolCardTable;
