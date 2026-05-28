import { useTranslation } from 'react-i18next';

import classNames from 'classnames/bind';
import style from './Tab.module.scss';

const cx = classNames.bind(style);

const Tab = ({
  tabValue,
  handleTab,
  leftText = 'basicResourceManagement.label',
  rightText = 'resourceManagementByProject.label',
}) => {
  const { t } = useTranslation();
  return (
    <div className={cx('tabs-cont')}>
      <div
        className={cx('tab', tabValue === 0 && 'activeColor')}
        onClick={() => handleTab(0)}
      >
        {t(leftText)}
      </div>
      <div
        className={cx('tab', tabValue === 1 && 'activeColor')}
        onClick={() => handleTab(1)}
      >
        {t(rightText)}
      </div>
    </div>
  );
};

export default Tab;
