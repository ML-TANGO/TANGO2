import { Loading } from '@tango/ui-react';

import classNames from 'classnames/bind';
import style from './FBLoading.module.scss';

const cx = classNames.bind(style);

const FBLoading = () => {
  return (
    <div className={cx('loading-cont')}>
      <Loading />
    </div>
  );
};

export default FBLoading;
