import classNames from 'classnames/bind';
import style from './OutputCom.module.scss';

const cx = classNames.bind(style);

function OutputCom({ data }) {
  return (
    <div className={cx('container')}>
      <pre className={cx('item')}>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}

export default OutputCom;
