import { useHistory, useLocation } from 'react-router-dom';

import usePreloadComponent from '@src/hooks/usePreloadComponent';

import BillingNav from './BillingNav';

// CSS module
import classNames from 'classnames/bind';
import style from './CustomNavLink.module.scss';

const cx = classNames.bind(style);

const modules = import.meta.glob('@src/pages/*.jsx');
const modulesArr = Object.entries(modules);

const TO_PATH_FROM_SRCPATH = {
  '/admin/workspaces': 'AdminWorkspacePage.jsx',
  '/admin/trainings': 'AdminTrainingPage.jsx',
  '/admin/deployments': 'AdminDeploymentPage.jsx',
  '/admin/docker_images': 'AdminDockerImagePage.jsx',
  '/admin/datasets': 'AdminDatasetPage.jsx',
  '/admin/nodes': 'AdminNodePage.jsx',
  '/admin/storages': 'AdminStoragePage.jsx',
  '/admin/records': 'AdminRecordPage.jsx',
  '/admin/users': 'AdminUserPage.jsx',
};

const handleMouseEnterPreload = (path, lazyLoad) => {
  const preloadPath = TO_PATH_FROM_SRCPATH[path];
  const findPath = modulesArr.find((info) => info[0].includes(preloadPath));

  if (findPath) {
    const LazyLoadPage = lazyLoad(findPath[1]);
    LazyLoadPage.preload();
  }
};

/**
 *
 * @param {string} pathname 페이지 경로
 * @param {string} name 링크에 보여줄 경로 이름
 * @param {string} iconPath 페이지 경로
 * @param {string} activeIconPath 페이지 경로
 * @param {Boolean} exact 네비게이션 경로 정확하게 일치하는거를 찾을지 여부
 * @param {Boolean} disabled 네비게이션 활성화 여부
 * @param {Boolean} isExpand 네비게이션 펼침 여부
 *
 * @component
 * @example
 *
 * const pathname = '/user/dashboard';
 * const name = 'Dashboard';
 * const iconPath = '/path/path';
 * const activeIconPath = '/path/path';
 *
 * return (
 *  <CustomLink
 *    pathname={pathname}
 *    name={name}
 *    iconPath={iconPath}
 *    activeIconPath={activeIconPath}
 *  />
 * );
 *
 *
 * -
 */
function CustomNavLink({
  pathname,
  name,
  iconPath,
  activeIconPath,
  exact,
  disabled,
  isExpand,
  testId,
  realName,
}) {
  const { lazyLoad } = usePreloadComponent();
  const location = useLocation();
  const history = useHistory();

  const { pathname: currentPathname } = location;

  const tmpCurrentPathname = currentPathname.split('/').slice(0, 5).join('/');
  const tmpPathname = pathname.split('/').slice(0, 5).join('/');
  const isBillingPage = currentPathname.includes('/billing');

  const moveToPage = (e) => {
    if (
      !e.target.closest('span') ||
      e.target.closest('span').className !== cx('bookmark-btn')
    ) {
      history.push({
        pathname,
      });
    }
  };

  return (
    <div className={cx('menu-container')}>
      <button
        className={cx(
          'menu-item',
          exact
            ? tmpCurrentPathname === tmpPathname && 'active'
            : tmpCurrentPathname.indexOf(tmpPathname) !== -1 && 'active',
          disabled ? 'disabled' : '',
          isBillingPage && 'billing-item',
        )}
        onClick={moveToPage}
        data-testid={testId}
        onMouseOver={() => handleMouseEnterPreload(tmpPathname, lazyLoad)}
      >
        <img
          src={
            exact
              ? tmpCurrentPathname === tmpPathname
                ? activeIconPath
                : iconPath
              : tmpCurrentPathname.indexOf(tmpPathname) !== -1
              ? activeIconPath
              : iconPath
          }
          alt='nav icon'
          className={cx('icon')}
        />
        <span className={cx('name', isExpand && 'show')} title={name}>
          {name}
        </span>
      </button>
      {realName === 'Billing' && isBillingPage && (
        <BillingNav isExpand={isExpand} />
      )}
    </div>
  );
}

export default CustomNavLink;
