// i18n
import { useTranslation } from 'react-i18next';

import CustomNavLink from '../CustomNavLink';

// CSS Module
import classNames from 'classnames/bind';
import style from './AdminNav.module.scss';

const cx = classNames.bind(style);

const adminNavList = [
  { name: 'Workspaces', path: '/admin/workspaces', icon: 'workspace' },
  // { name: 'Trainings', path: '/admin/trainings', icon: 'training' },
  // { name: 'Deployments', path: '/admin/deployments', icon: 'deployment' },
  // { name: 'Built-in Models', path: '/admin/builtin_models', icon: 'built-in' },
  // { name: 'Docker Images', path: '/admin/docker_images', icon: 'dockerimage' },
  { name: 'Datasets', path: '/admin/datasets', icon: 'dataset' },
  { name: 'Nodes', path: '/admin/nodes', icon: 'node' },
  { name: 'Storage', path: '/admin/storages', icon: 'storage' },
  // { name: 'Network', path: '/admin/networks', icon: 'network' },
  // { name: 'Benchmarking', path: '/admin/benchmarking', icon: 'benchmarking' },
  { name: 'Records', path: '/admin/records', icon: 'record' },
  { name: 'Users', path: '/admin/users', icon: 'user' },
  // { name: 'Billing', path: '/admin/billing/basic', icon: 'billing' },
];

/**
 * 관리자 로그인 시 제공되는 사이드 네비게이션
 * @param {boolean} isExpand 사이드 네비게이션 확정 여부 true: 확장 false: 축소
 * @returns {JSX.Element}
 * @component
 * @example
 *
 * const isExpand = false;
 *
 * return (
 *  <AdminNav isExpand={isExpand} />
 * )
 * -
 */
function AdminNav({ isExpand }) {
  const { t } = useTranslation();
  const MODE = import.meta.env.VITE_REACT_APP_MODE;
  // 커스텀 서비스 매뉴얼 유무
  const IS_MANUAL = import.meta.env.VITE_REACT_APP_IS_MANUAL === 'true';
  // 매뉴얼 숨김 유무
  const IS_HIDE_MANUAL =
    import.meta.env.VITE_REACT_APP_IS_HIDE_MANUAL === 'true';

  const onServiceManual = (service) => {
    const link = document.createElement('a');
    if (service === 'Flightbase') {
      if (MODE === 'INTEGRATION') {
        link.href = `${
          import.meta.env.VITE_REACT_APP_INTEGRATION_API_HOST
        }manual/Flightbase_User_Guide.pdf`;
      } else {
        link.href = '/manual/Flightbase_Guide.pdf'; // 서버에 파일이름은 항상 동일하게 올리고
      }
      link.download = 'Flightbase_사용자_매뉴얼_v1.5.1.pdf'; // 다운로드 받을 때 업데이트 날짜 들어가게 하기
      link.target = '_blank';
    } else if (service === 'DNA+DRONE') {
      link.href = '/manual/DNA_AIP_manual.pdf';
      link.download = 'DNA_AIP_manual.pdf';
      link.target = '_blank';
    }
    link.click();
    link.remove();
  };

  return (
    <>
      <div className={cx('admin-nav', isExpand ? 'expand' : 'hide')}>
        <ul className={cx('nav')}>
          {adminNavList.map(({ path, name, icon, exact }, idx) => (
            <li key={idx}>
              <CustomNavLink
                pathname={path}
                name={t(name)}
                iconPath={`/images/nav/icon-lnb-${icon}-gray.svg`}
                activeIconPath={`/images/nav/icon-lnb-${icon}-blue.svg`}
                exact={exact}
                isExpand={isExpand}
                realName={name}
              />
            </li>
          ))}
        </ul>
      </div>

      {(MODE !== 'CUSTOM' || IS_MANUAL) && !IS_HIDE_MANUAL && (
        <div className={cx('manual-box')}>
          <button
            className={cx('manual-download-btn')}
            onClick={() => onServiceManual('Flightbase')}
          >
            Service Manual
            <img
              className={cx('icon')}
              src='/images/icon/00-ic-data-download-blue.svg'
              alt='download'
            />
          </button>
        </div>
      )}
    </>
  );
}

export default AdminNav;
