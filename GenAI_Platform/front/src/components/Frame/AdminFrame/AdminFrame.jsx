// Components
import Frame from '../Frame';
import AdminHeader from '@src/containers/HeaderContainer';
import SideNav from '../SideNav';

/**
 *
 * @param {JSX.Element} children 페이지 컨텐츠 컴포넌트
 * @returns
 *
 * @component
 * @example
 *
 * return (
 *  <AdminFrame>
 *    page content
 *  </AdminFrame>
 * )
 *
 *
 *
 * -
 */
function AdminFrame({ children }) {
  return (
    <Frame headerRender={<AdminHeader />} sideNavRender={<SideNav />}>
      {children}
    </Frame>
  );
}

export default AdminFrame;
