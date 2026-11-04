import { PureComponent } from 'react';
import { withRouter } from 'react-router-dom';
import { connect } from 'react-redux';

// Actions
import { logoutRequest } from '@src/store/modules/auth';
import { closeNav, openNav } from '@src/store/modules/nav';

// Components
import Header from '@src/components/Frame/Header';

const SERVICE_LOGO_SYMBOL =
  import.meta.env.VITE_REACT_APP_SERVICE_LOGO_SYMBOL ||
  '/images/logo/dashboard-loc-logo.svg';

class HeaderContainer extends PureComponent {
  constructor(props) {
    super(props);
    this.state = {
      popupOpen: false,
    };
  }

  onLogout = () => {
    this.props.logoutRequest();
  };

  contextPopupHandler = () => {
    this.setState({
      popupOpen: !this.state.popupOpen,
    });
  };

  // Events
  navHandler = () => {
    const { isExpand } = this.props.nav;
    if (isExpand) this.props.closeNav();
    else this.props.openNav();
  };

  render() {
    const { state, props, onLogout, contextPopupHandler, navHandler } = this;
    const {
      auth: { userName },
      nav,
    } = props;

    const {
      location: { pathname },
      type,
    } = props;

    const { isExpand } = nav;

    let title = '';
    const loc = [
      {
        label: <img src={SERVICE_LOGO_SYMBOL} alt='dashboard' />,
        path: '/admin/dashboard',
      },
    ];
    const pathArr = pathname.split('/');
    const firstDepth = pathArr[2];
    if (firstDepth === 'dashboard') {
      title = 'dashboard';
    } else if (firstDepth === 'workspaces') {
      title = 'Workspaces';
      loc.push({ label: title, path: '/admin/workspaces' });
    } else if (firstDepth === 'trainings') {
      title = 'Trainings';
      loc.push({ label: title, path: '/admin/trainings' });
    } else if (firstDepth === 'deployments') {
      title = 'Deployments';
      loc.push({ label: title, path: '/admin/deployments' });
    } else if (firstDepth === 'builtin_models') {
      title = 'Built-in Models';
      loc.push({ label: title, path: '/admin/builtin_models' });
    } else if (firstDepth === 'datasets') {
      title = 'Datasets';
      loc.push({ label: title, path: '/admin/datasets' });
    } else if (firstDepth === 'docker_images') {
      title = 'Docker Images';
      loc.push({ label: title, path: '/admin/docker_images' });
    } else if (firstDepth === 'nodes') {
      title = 'Nodes';
      loc.push({ label: title, path: '/admin/nodes' });
    } else if (firstDepth === 'records') {
      title = 'Records';
      loc.push({ label: title, path: '/admin/recordes' });
    } else if (firstDepth === 'users') {
      title = 'Users';
      loc.push({ label: title, path: '/admin/users' });
    }
    return (
      <Header
        {...state}
        title={title}
        loc={loc}
        authType='ADMIN'
        userName={userName}
        type={type}
        isExpand={isExpand}
        onLogout={onLogout}
        navHandler={navHandler}
        contextPopupHandler={contextPopupHandler}
      />
    );
  }
}

export default connect(({ auth, nav }) => ({ auth, nav }), {
  logoutRequest,
  closeNav,
  openNav,
})(withRouter(HeaderContainer));
