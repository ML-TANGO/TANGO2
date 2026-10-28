import { shallowEqual, useSelector } from 'react-redux';

import { calIsDeployLoading } from '../PlaygroundHeader/PlaygroundHeader';

import classNames from 'classnames/bind';
import style from './PlaygroundFrame.module.scss';

const cx = classNames.bind(style);

const PlaygroundFrame = ({ children, disabled, ...rest }) => {
  // ** [SSE] 배포 상태 **
  const { status: statusType } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );

  // 명시값이 없으면 기존 단일 화면의 Redux 상태 계산을 그대로 사용한다.
  // controlled 카드는 역할별 배포 상태를 주입해 다른 화면의 Redux 상태가 섞이지 않게 한다.
  const isDisabled = disabled ?? calIsDeployLoading(statusType);

  return (
    <div className={cx('frame', isDisabled && 'disabled')} {...rest}>
      {children}
    </div>
  );
};

export default PlaygroundFrame;
