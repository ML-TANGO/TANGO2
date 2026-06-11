// UseHistory
import { useHistory } from 'react-router-dom';

// Atoms
import { Button } from '@tango/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './NotFoundPageContent.module.scss';
const cx = classNames.bind(style);

const MODE = import.meta.env.VITE_REACT_APP_MODE?.toLowerCase();

const NotFoundPageContent = () => {
  const history = useHistory();
  function goHome() {
    history.push({ pathname: '/' });
  }

  return (
    <div className={cx('container')}>
      <div className={cx('logo', MODE)}></div>
      <div className={cx('message-box')}>
        <h2 className={cx('title')}>404</h2>
        <p className={cx('content')}>
          존재하지 않는 주소를 입력하셨거나,
          <br />
          요청하신 페이지의 주소가 변경, 삭제되어 찾을 수 없습니다.
          <br />
          입력하신 주소가 정확한지 다시 한 번 확인해주세요.
        </p>
        <Button type='primary' onClick={() => goHome()}>
          홈으로 이동하기
        </Button>
      </div>
    </div>
  );
};

export default NotFoundPageContent;
