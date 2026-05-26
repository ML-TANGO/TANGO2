// Atoms
import { Button } from '@jonathan/ui-react';

// CSS module
import classNames from 'classnames/bind';
import style from './IntegrationLoginFailPageContent.module.scss';
const cx = classNames.bind(style);

const IntegrationLoginFailPageContent = ({ redirectPortal }) => {
  return (
    <div className={cx('container')}>
      <div className={cx('logo')}></div>
      <div className={cx('message-box')}>
        <h2 className={cx('title')}>로그인 실패</h2>
        <p className={cx('content')}>
          로그인에 실패하였습니다.
          <br />
          잠시 후 다시 시도해주세요.
        </p>
        <Button type='primary' onClick={redirectPortal}>
          포탈 서비스로 돌아가기
        </Button>
      </div>
    </div>
  );
};

export default IntegrationLoginFailPageContent;
