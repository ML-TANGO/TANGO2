import { shallowEqual, useSelector } from 'react-redux';

import { calIsDeployLoading } from '../PlaygroundHeader/PlaygroundHeader';

import classNames from 'classnames/bind';
import style from './PlaygroundFrame.module.scss';

const cx = classNames.bind(style);

const PlaygroundFrame = ({ children, ...rest }) => {
  // ** [SSE] 배포 상태 **
  const { status: statusType } = useSelector(
    (state) => state.llmPlayground.status,
    shallowEqual,
  );

  const isDisabled = calIsDeployLoading(statusType);

  return (
    <div className={cx('frame', isDisabled && 'disabled')} {...rest}>
      {children}
    </div>
  );
};

export default PlaygroundFrame;
