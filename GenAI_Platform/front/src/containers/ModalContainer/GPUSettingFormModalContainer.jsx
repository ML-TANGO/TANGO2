import { PureComponent } from 'react';

// Components
import GPUSettingFormModal from '@src/components/Modal/GPUSettingFormModal';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';

class GPUSettingFormModalContainer extends PureComponent {
  state = {
    validate: false,
    totalGpu: 0,
    trainingGpu: '', // Training GPU
    prevTrainingGpu: 0, // Training GPU
    trainingGpuError: null, // Training GPU input 에러 텍스트
    deploymentGpu: '',
    prevDeploymentGpu: 0, // Service GPU
    deploymentGpuError: null, // Service GPU input 에러 텍스트
  };

  componentDidMount() {
    this.getWorkspaceGPUInfo();
  }

  // 워크스페이스 GPU 정보 조회
  getWorkspaceGPUInfo = async () => {
    const { workspaceId } = this.props.data;
    const response = await callApi({
      url: `workspaces/${workspaceId}/gpu`,
      method: 'get',
    });
    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      const {
        training_gpu: trainingGpu,
        deployment_gpu: deploymentGpu,
        total_gpu: totalGpu,
      } = result;
      this.setState({
        trainingGpu,
        deploymentGpu,
        prevTrainingGpu: trainingGpu,
        prevDeploymentGpu: deploymentGpu,
        totalGpu,
      });
    } else {
      errorToastMessage(error, message);
    }
  };

  // 인풋 이벤트 핸들러
  inputHandler = (e) => {
    const { totalGpu, prevTrainingGpu, prevDeploymentGpu } = this.state;
    const { name, value } = e;
    const newState = {
      [name]: value,
      [`${name}Error`]: null,
    };
    if (name === 'trainingGpu' && value !== '') {
      if (totalGpu < Number(value)) {
        newState.trainingGpu = totalGpu;
        newState.deploymentGpu = 0;
      } else {
        newState.trainingGpu = value;
        newState.deploymentGpu = totalGpu - Number(value);
      }
    } else if (name === 'deploymentGpu') {
      if (totalGpu < Number(value)) {
        newState.deploymentGpu = totalGpu;
        newState.trainingGpu = 0;
      } else {
        newState.deploymentGpu = value;
        newState.trainingGpu = totalGpu - Number(value);
      }
    }
    if (
      Number(newState.trainingGpu) !== prevTrainingGpu ||
      Number(newState.deploymentGpu) !== prevDeploymentGpu
    ) {
      newState.validate = true;
    } else {
      newState.validate = false;
    }
    this.setState(newState);
  };

  // 워크스페이스 GPU 수정
  onSubmit = async (callback) => {
    const { workspaceId } = this.props.data;
    const url = `workspaces/${workspaceId}/gpu`;
    const { trainingGpu, deploymentGpu } = this.state;

    const body = {
      training_gpu: trainingGpu,
      deployment_gpu: deploymentGpu,
    };
    const response = await callApi({
      url,
      method: 'PUT',
      body,
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      if (callback) callback();
      defaultSuccessToastMessage('update');
      return true;
    }
    errorToastMessage(error, message);
    return false;
  };

  render() {
    const { props, state, inputHandler, onSubmit } = this;
    return (
      <GPUSettingFormModal
        {...props}
        {...state}
        inputHandler={inputHandler}
        onSubmit={onSubmit}
      />
    );
  }
}

export default GPUSettingFormModalContainer;
