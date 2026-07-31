// CSS module
import classNames from 'classnames/bind';
import style from './OtherWsItem.module.scss';
const cx = classNames.bind(style);

function OtherWsItem({ count, t }) {
  return (
    <div className={cx('other-ws-item')}>
      {t ? t('taskInAnotherWorkspace.label') : 'Task in another workspace'} (
      {count})
    </div>
  );
}

export default OtherWsItem;
