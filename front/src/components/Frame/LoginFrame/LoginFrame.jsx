// CSS Module
import PromptCommitList from '@src/components/pageContents/llm/PromptContent/PromptContent/PromptCommitList';

import classNames from 'classnames/bind';
import style from './LoginFrame.module.scss';

const cx = classNames.bind(style);

/**
 * 로그인 화면 프레임 컴포넌트
 * @param {{
 *  headerRender: JSX.Element,
 *  leftContentRender: JSX.Element,
 *  rightContentRender: JSX.Element,
 *  footerRender: JSX.Element,
 * }}
 * @component
 *
 * const Header = () => <div>header</div>;
 * const LeftContent = () => <div>left content</div>;
 * const RightContent = () => <div>right content</div>;
 * const Footer = () => <div>footer</div>;
 *
 * return (
 *  <LoginFrame
 *    headerRender={<Header />}
 *    leftContentRender={<LeftContent />}
 *    rightContentRender={<RightContent />}
 *    footerRender={<Footer />}
 *  />
 * );
 *
 */
function LoginFrame({
  headerRender,
  leftContentRender,
  rightContentRender,
  footerRender,
}) {
  return (
    <div className={cx('login-page')}>
      <div className={cx('header')}>{headerRender}</div>
      <div className={cx('login-inner-box')}>
        <div className={cx('left-box')}>{leftContentRender}</div>
        <div className={cx('right-box')}>{rightContentRender}</div>
      </div>
      {footerRender}
    </div>
  );
}

export default LoginFrame;
