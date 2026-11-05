import React from 'react';
import { useHistory, useLocation } from 'react-router-dom';

import classNames from 'classnames/bind';
import style from './BillingNav.module.scss';

const cx = classNames.bind(style);

const billingType = [
  {
    icon: '/images/nav/icon-lnb-billing-default.svg',
    activeIcon: '/images/nav/icon-lnb-billing-active.svg',
    name: ['기본 요금 관리'],
    path: '/admin/billing/basic',
  },
  {
    icon: '/images/nav/icon-lnb-billing-default.svg',
    activeIcon: '/images/nav/icon-lnb-billing-active.svg',
    name: ['인스턴스', '과금 정책 관리'],
    path: '/admin/billing/instance',
  },
  {
    icon: '/images/nav/icon-lnb-billing-default.svg',
    activeIcon: '/images/nav/icon-lnb-billing-active.svg',
    name: ['스토리지', '과금 정책 관리'],
    path: '/admin/billing/storage',
  },
  {
    icon: '/images/nav/icon-lnb-billing-monitoring-default.svg',
    activeIcon: '/images/nav/icon-lnb-billing-monitoring-active.svg',
    name: ['과금 모니터링'],
    path: '/admin/billing/monitoring',
  },
];

const BillingNav = ({ isExpand }) => {
  const location = useLocation();
  const history = useHistory();
  const { pathname: currentPathname } = location;

  return (
    <div className={cx('billing-container')}>
      <div className={cx('billing')}>
        {billingType.map(({ icon, name, path, activeIcon }) => (
          <div
            className={cx('type', path === currentPathname && 'current-path')}
            onClick={() => history.push(path)}
            key={path}
          >
            <img
              src={path === currentPathname ? activeIcon : icon}
              alt='billing'
            />
            {isExpand && (
              <div
                className={cx(
                  'billing-text',
                  path === currentPathname && 'current-path',
                )}
              >
                {name.map((v) => (
                  <span key={v}>{v}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default BillingNav;
