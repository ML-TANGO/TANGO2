import CustomSkeleton from '@src/components/atoms/CustomSkeleton';

import classNames from 'classnames/bind';
import style from './SkeletonCard.module.scss';

const cx = classNames.bind(style);

const SkeletonCard = () => {
  return (
    <li className={cx('card')}>
      <div className={cx('status-box')}>
        <CustomSkeleton width={120} height={18} mb={4} />
        <CustomSkeleton width={80} height={24} mb={6} />
        <CustomSkeleton width={200} height={19} />
      </div>
      <div className={cx('content-info-box')}>
        <CustomSkeleton width={180} height={27} mb={12} />
        <div className={cx('right-box')}>
          <div className={cx('info-item')}>
            <CustomSkeleton width={100} height={19} mb={4} />
            <CustomSkeleton width={80} height={23} />
          </div>
          <div className={cx('info-item')}>
            <CustomSkeleton width={120} height={19} mb={4} />
            <CustomSkeleton width={90} height={16} mb={8} />
            <CustomSkeleton width={160} height={16} mb={8} />
            <CustomSkeleton width={80} height={16} mb={8} />
            <CustomSkeleton width={100} height={16} mb={8} />
          </div>
        </div>
      </div>
    </li>
  );
};

export default SkeletonCard;
