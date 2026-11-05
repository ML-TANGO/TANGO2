import { PureComponent } from 'react';
// i18n
import { withTranslation } from 'react-i18next';
import { connect } from 'react-redux';
import { withRouter } from 'react-router-dom';

// Components
import UserServiceContent from '@src/components/pageContents/user/UserServiceContent';

import { startPath } from '@src/store/modules/breadCrumb';
import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { closeModal, openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

class UserServicePage extends PureComponent {
  _isMounted = false;

  _isApiCall = false;

  state = {
    originData: [],
    cardData: [],
    serviceType: { label: 'all.label', value: 'all' },
    deploymentType: { label: 'allModelType.label', value: 'all' },
    status: { label: 'allStatus.label', value: 'all' }, // { label: 'serviceActive', value: 'active' }
    loading: false,
    serverError: false,
    workspaceId: null,
  };

  async componentDidMount() {
    this.props.startPath([
      {
        component: {
          name: 'Simulation',
          t: this.props.t,
        },
      },
    ]);
    this._isMounted = true;
    const {
      location: { pathname },
    } = this.props;
    const wid = pathname.split('/')[3];
    this.setState({ workspaceId: wid, loading: true });
    await this.getServicesData(true);
  }

  componentWillUnmount() {
    this._isMounted = false;
  }

  /**
   * API 호출 GET
   * 서비스 데이터 가져오기
   */
  getServicesData = async (isFirst) => {
    if (this._isApiCall) return false;
    this._isApiCall = true;

    let wid = this.state.workspaceId;
    if (!wid) {
      const {
        location: { pathname },
      } = this.props;
      wid = pathname.split('/')[3];
    }

    const response = await callApi({
      url: `services?workspace_id=${wid}`,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (!this._isMounted) return response;
    if (status === STATUS_SUCCESS) {
      this.setState(
        {
          originData: result.list,
          cardData: result.list,
          loading: false,
          serverError: false,
        },
        () => {
          setTimeout(() => {
            this._isApiCall = false;
            this.getServicesData(false);
          }, 1000);
        },
      );
      // sorting 된 데이터 내에서 다시 필터/검색 실행 (첫 조회시 제외)
      if (!isFirst) {
        this.onSearch(this.state.keyword);
      }
    } else {
      errorToastMessage(error, message);
      this.setState({
        loading: false,
        serverError: true,
      });
    }
    return response;
  };

  /**
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */
  selectInputHandler = (name, value) => {
    const newState = {
      [name]: value,
    };

    this.setState(newState, async () => {
      this.onSearch();
    });
  };

  /**
   * 필터
   */
  onSearch = (keyword) => {
    const { originData, serviceType, deploymentType, status } = this.state;

    let cardData = originData;

    if (serviceType.value !== 'all') {
      cardData = cardData.filter(
        (item) => item.service_type === serviceType.value,
      );
    }

    if (deploymentType.value !== 'all') {
      cardData = cardData.filter((item) => item.type === deploymentType.value);
    }

    if (status.value !== 'all') {
      cardData = cardData.filter((item) => item.status.status === status.value);
    }

    this.setState({
      cardData,
    });
  };

  /**
   * 서비스 목록으로 이동
   *
   * @param {object} service 서비스 데이터
   */
  openTest = (service) => {
    const {
      location: { pathname },
      trackingEvent,
    } = this.props;
    this.props.history.push({
      pathname: `${pathname}/${service.id}/test`,
      state: {
        id: service.id,
        name: service.name,
        loc: ['Home', service.name, 'Test'],
      },
    });
    trackingEvent({
      category: 'User Service Page',
      action: 'Move to Test Page',
    });
  };

  /**
   * 배포 화면으로 이동
   */
  moveToDeploymentPage = () => {
    const {
      location: { pathname },
      trackingEvent,
    } = this.props;
    const pathName = `${pathname}`.replace('services', 'deployments');
    this.props.history.push({
      pathname: pathName,
    });
    trackingEvent({
      category: 'User Service Page',
      action: 'Move to Deployment Page',
    });
  };

  render() {
    const { state, openTest, moveToDeploymentPage, selectInputHandler } = this;

    return (
      <>
        <UserServiceContent
          {...state}
          openTest={openTest}
          selectInputHandler={selectInputHandler}
          moveToDeploymentPage={moveToDeploymentPage}
        />
      </>
    );
  }
}

export default connect(null, { openModal, closeModal, openConfirm, startPath })(
  withRouter(withTranslation()(UserServicePage)),
);
