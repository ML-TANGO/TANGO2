import { PureComponent } from 'react';
import { connect } from 'react-redux';

// Components
import HpsLogModal from '@src/components/Modal/HpsLogModal';
import { toast } from '@src/components/Toast';

// Action
import { closeModal } from '@src/store/modules/modal';

// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';

// log json
import initLog from './initLog.json';

let timer;
class HpsLogModalContainer extends PureComponent {
  _isMounted = false;

  _isApiCall = false;

  state = {
    validate: true, // Create(Confirm) 버튼 활성/비활성 여부 상태 값
    logTable: [],
    selectedLogId: null,
    logData: null,
    totalLength: null,
    hpsId: null,
    hpsName: '',
    hpsData: [],
    trainingType: '',
    metricsData: {},
    metricsInfo: {},
    parameterSettings: [],
    selectedHps: null,
    hpsStatus: null,
    maxJobIndex: null,
    maxJobInfo: null,
    realTimeLog: false,
    isInitGraph: false,
    loading: false,
    noGraphData: false,
    grapthData: '',
  };

  async componentDidMount() {
    this._isMounted = true;
    const {
      data: { hpsId, hpsName, hpsData, trainingType },
    } = this.props;

    // selectedHps 값은 테이블에서 아이템을 클릭 시(selectHPS 함수) 할당됨
    // 할당전에는 Log 정보를 가져오는 api는 호출하지 않음
    timer = setInterval(() => {
      const { realTimeLog, selectedHps } = this.state;
      if (realTimeLog) this.getHpsLog(selectedHps.id);
    }, 2000);

    this.setState(
      {
        trainingType,
        hpsName,
        hpsData,
        hpsId,
      },
      async () => {
        await this.getHpsResult();
        await this.getHpsLog();
      },
    );
  }

  componentWillUnmount() {
    this._isMounted = false;
    clearInterval(timer);
  }
  /** ================================================================================
   * API START
   ================================================================================ */

  // 로그 다운로드
  handleHpsLogDownload = async (index) => {
    const { hpsName, hpsId, selectedLogId } = this.state;

    try {
      const { data, status } = await network.callApiWithPromise({
        url: `projects/hps-log-download?hps_id=${hpsId}`,
        method: 'GET',
      });

      if (status === 0) {
        toast.error(data.message);
        return;
      }

      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `[HPS]${hpsName}-${index}_No.${selectedLogId}.log`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error);
      console.log('[ERROR HPS LOG DOWNLOAD] : ', error);
    }
  };

  getHpsResult = async () => {
    if (this.state.logTable.length === 0) {
      this.setState({ loading: true });
    }

    if (this._isApiCall) return false;
    this._isApiCall = true;
    const { hpsId } = this.state;
    const response = await callApi({
      url: `projects/hyperparam_search_result?hps_id=${hpsId}`,
      method: 'GET',
    });
    const { status, result, message } = response;

    if (!this._isMounted) return false;

    if (status === STATUS_SUCCESS) {
      if (result && result.log_table !== undefined) {
        const {
          log_table: logTable,
          parameter_settings: parameterSettings,
          status: hpsStatus,
          max_index: maxJobIndex,
          max_item: maxJobInfo,
        } = result;
        this.setState(
          {
            logTable,
            parameterSettings,
            hpsStatus,
            maxJobIndex,
            maxJobInfo,
          },
          () => {
            // HPS 상태가 학습중 일 때만 재귀호출로 Log 정보 업데이트
            if (hpsStatus === 'running') {
              setTimeout(() => {
                this._isApiCall = false;
                this.getHpsResult();
              }, 1000);
            }
          },
        );
      } else {
        toast.error('There are no results yet.');
      }
    } else {
      this._isApiCall = false;
      toast.error(message);
    }
    this.setState({ loading: false });
    return response;
  };

  getHpsLog = async (id, scrollToTarget) => {
    const { hpsId } = this.state;
    const response = await callApi({
      url: `projects/hyperparam_search_log?hps_id=${hpsId}${
        id ? `&table_item_id=${id}` : ''
      }`,
      method: 'get',
    });

    const { status, result, message, length: totalLength } = response;

    if (!this._isMounted) return false;

    if (status === STATUS_SUCCESS) {
      const {
        log: logData,
        metrics_data: metricsData,
        metrics_info: metricsInfo,
      } = result;
      const keys = Object.keys(metricsData);
      this.setState({ grapthData: keys });
      if (keys.length !== 0 && metricsData[keys[0]].length < 2) {
        this.setState(
          {
            logData,
            totalLength,
            hpsId,
            selectedLogId: id,
          },
          () => {
            if (scrollToTarget && id) scrollToTarget();
          },
        );
        return response;
      }

      if (this.checkGraphData(metricsData)) {
        this.setState(
          {
            logData,
            totalLength,
            hpsId,
            metricsData,
            metricsInfo,
            selectedLogId: id,
          },
          () => {
            if (scrollToTarget && id) scrollToTarget();
          },
        );
      } else {
        this.initGraph(() => {
          this.setState(
            {
              logData,
              totalLength,
              hpsId,
              metricsData,
              metricsInfo,
              selectedLogId: id,
            },
            () => {
              if (scrollToTarget && id) scrollToTarget();
            },
          );
        });
      }
    } else {
      this._isApiCall = false;
      toast.error(message);
    }
    return response;
  };

  /** ================================================================================
   * API END
   ================================================================================ */

  /** ================================================================================
   * Event Handler START
   ================================================================================ */

  // submit 버튼 클릭 이벤트
  onSubmit = async () => {
    const { type } = this.props;
    this.props.closeModal(type);

    return true;
  };

  selectHPS = (selectedHps, scrollToTarget) => {
    const { logTable, hpsStatus, grapthData } = this.state;

    if (grapthData.length === 0) {
      this.setState({ noGraphData: true });
    }
    if (
      logTable[logTable.length - 1].id === selectedHps.id &&
      hpsStatus === 'running'
    ) {
      this.setState(
        { selectedHps, realTimeLog: true, isInitGraph: false },
        () => {
          this.getHpsLog(selectedHps.id, scrollToTarget);
        },
      );
    } else {
      this.setState(
        { selectedHps, realTimeLog: false, isInitGraph: false },
        () => {
          this.getHpsLog(selectedHps.id, scrollToTarget);
        },
      );
    }
  };

  /** ================================================================================
   * Event Handler END
   ================================================================================ */

  checkGraphData = (metricsData) => {
    const metricsDataKeys = Object.keys(metricsData);
    for (let i = 0; i < metricsDataKeys.length; i += 1) {
      const key = metricsDataKeys[i];
      const paramArr = metricsData[key];
      const paramSet = new Set(paramArr);
      if (paramSet.size === 1 && paramArr.length > 1) return false;
    }
    return true;
  };

  initGraph = (callback) => {
    const { isInitGraph } = this.state;
    if (isInitGraph) {
      if (callback) callback();
      return;
    }
    const { result } = initLog;
    const { metrics_data: metricsData, metrics_info: metricsInfo } = result;
    this.setState(
      {
        metricsData,
        metricsInfo,
        isInitGraph: true,
      },
      () => {
        if (callback) callback();
      },
    );
  };

  render() {
    const { state, props, onSubmit, selectHPS, handleHpsLogDownload } = this;

    return (
      <HpsLogModal
        {...state}
        {...props}
        onSubmit={onSubmit}
        selectHPS={selectHPS}
        downloadLog={handleHpsLogDownload}
      />
    );
  }
}

export default connect(null, { closeModal })(HpsLogModalContainer);
