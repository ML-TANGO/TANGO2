import { PureComponent } from 'react';
import { connect } from 'react-redux';

// Components
import JobLogModal from '@src/components/Modal/JobLogModal';
import { toast } from '@src/components/Toast';

// Action
import { closeModal } from '@src/store/modules/modal';

// Network
import { callApi, network, STATUS_SUCCESS } from '@src/network';

import initLog from './initLog.json';

class JobLogModalContainer extends PureComponent {
  _isMounted = false;

  _isApiCall = false;

  state = {
    validate: true, // Create(Confirm) 버튼 활성/비활성 여부 상태 값
    logData: '',
    totalLength: null,
    jobId: null,
    jobName: '',
    jobData: [],
    jobStatus: '',
    trainingType: '',
    metricsData: {},
    metricsInfo: {},
    parameterSettings: [],
    isInitGraph: false,
    guideLodResult: '',
  };

  async componentDidMount() {
    this._isMounted = true;
    const {
      data: { jobId, jobName, jobData, trainingType },
    } = this.props;

    this.setState(
      {
        trainingType,
        jobName,
        jobData,
        jobId,
      },
      () => {
        // this.getJobLog();
      },
    );
  }

  componentWillUnmount() {
    this._isMounted = false;
  }
  /** ================================================================================
   * API START
   ================================================================================ */

  // 로그 다운로드
  downloadLog = async (index) => {
    const { jobName, jobId } = this.state;

    try {
      const { data, status } = await network.callApiWithPromise({
        url: `projects/training-log-download?training_id=${jobId}`,
        method: 'GET',
      });

      if (status === 0) {
        toast.error(data.message);
        return;
      }

      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `[Job]${jobName}-${index}.log`;
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error);
      console.log('[JOB LOG DOWNLOAD ERROR] : ', error);
    }
  };

  getJobLog = async () => {
    // if (this._isApiCall) return false;
    this._isApiCall = true;
    const {
      data: { jobId },
    } = this.props;

    const response = await callApi({
      url: `projects/training-log?training_id=${jobId}`,
      method: 'get',
    });

    const logResponse = await callApi({
      url: `projects/training-log-guide?training_type=training`,
      method: 'get',
    });

    const { status, result, message, length: totalLength } = response;
    const { result: guideLodResult, status: logStatus } = logResponse;

    if (logStatus === STATUS_SUCCESS) {
      this.setState({ guideLodResult });
    }

    if (!this._isMounted) return false;

    if (status === STATUS_SUCCESS) {
      const {
        log: logData,
        metrics_data: metricsData,
        metrics_info: metricsInfo,
        parameter_settings: parameterSettings,
        status: jobStatus,
      } = result;

      const keys = Object.keys(metricsData);
      if (keys.length !== 0 && metricsData[keys[0]].length < 2) {
        this.setState(
          {
            logData,
            totalLength,
            jobStatus,
          },
          () => {
            if (jobStatus === 'running') {
              setTimeout(() => {
                this._isApiCall = false;
                this.getJobLog();
              }, 1000);
            }
          },
        );
        return response;
      }
      if (this.checkGraphData(metricsData)) {
        this.setState(
          {
            logData,
            totalLength,
            jobId,
            metricsData,
            metricsInfo,
            parameterSettings,
            jobStatus,
          },
          () => {
            if (jobStatus === 'running') {
              setTimeout(() => {
                this._isApiCall = false;
                this.getJobLog();
              }, 1000);
            }
          },
        );
      } else {
        this.initGraph(() => {
          this.setState(
            {
              logData,
              totalLength,
              jobId,
              metricsData,
              metricsInfo,
              parameterSettings,
              jobStatus,
            },
            () => {
              if (jobStatus === 'running') {
                setTimeout(() => {
                  this._isApiCall = false;
                  this.getJobLog();
                }, 1000);
              }
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
    const { state, props, onSubmit, downloadLog, getJobLog } = this;
    return (
      <JobLogModal
        {...state}
        {...props}
        onSubmit={onSubmit}
        downloadLog={downloadLog}
        getJobLog={getJobLog}
      />
    );
  }
}

export default connect(null, { closeModal })(JobLogModalContainer);
