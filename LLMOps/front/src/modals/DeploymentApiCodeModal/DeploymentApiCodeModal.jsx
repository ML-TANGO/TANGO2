import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// Components
import DeploymentApiCodeModalContent from '@src/components/modalContents/DeploymentApiCodeModalContent/DeploymentApiCodeModalContent';
// Custom Hooks
import useDeploymentInputValueBox from '@src/components/organisms/DeploymentInputValueBox/useDeploymentInputValueBox';
import useDeploymentOutputTypeBox from '@src/components/organisms/DeploymentOutputTypeBox/useDeploymentOutputTypeBox';
import useDeploymentParserBox from '@src/components/organisms/DeploymentParserBox/useDeploymentParserBox';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';
// Utils
import { errorToastMessage } from '@src/utils';

/**
 * 배포 API 코드 생성 모달 컴포넌트
 * 모달의 상태 관리 및 이벤트 정의
 * src/containers/ModalContainer/ModalContainer.jsx에서 사용
 * @param {{
 *  type: 'CREATE_DEPLOYMENT_API',
 *  data: any,
 * }} props
 * @returns
 */
function DeploymentApiCodeModal({ type, data: modalData }) {
  const { t } = useTranslation();

  // Custom Hooks
  const [apiFileNameState, setApiFileNameState] = useState({
    value: '',
    error: null,
  });
  const [deploymentInputValueState, deploymentInputValueRender] =
    useDeploymentInputValueBox();
  const [deploymentOutputTypeState, deploymentOutputTypeRender] =
    useDeploymentOutputTypeBox(deploymentInputValueState);
  const [deploymentParserState, deploymentParserRender] =
    useDeploymentParserBox();

  const [deployFooterMessage, setDeployFooterMessage] = useState('');

  const validateCategoryPair = (categories) => {
    const hasCanvasImage = categories.includes('canvas-image');
    const hasCanvasCoordinate = categories.includes('canvas-coordinate');
    return hasCanvasImage === hasCanvasCoordinate;
  };

  const validateDeploymentForm = (form) => {
    for (const { category, api_key, value_type } of form) {
      if (!category) return `${t('categorySelect.error.message')}`;
      if (!api_key) return `${t('apiKeySelect.error.message')}`;
      if (!value_type) return `${t('dataTypeSelect.error.message')}`;
    }
    return null;
  };

  useEffect(() => {
    if (!apiFileNameState.value) {
      setDeployFooterMessage(`${t('apiFileName.error.message')}`);
      return;
    }

    const categories = deploymentInputValueState.deploymentInputForm.map(
      (v) => v.category,
    );

    if (!validateCategoryPair(categories)) {
      setDeployFooterMessage(`${t('canvasSelect.error.message')}`);
      return;
    }

    const formErrorMessage = validateDeploymentForm(
      deploymentInputValueState.deploymentInputForm,
    );

    if (formErrorMessage) {
      setDeployFooterMessage(formErrorMessage);
      return;
    }

    if (!deploymentOutputTypeState.outputTypeList.length) {
      setDeployFooterMessage(`${t('deploymentServiceSelect.error.message')}`);
      return;
    }

    setDeployFooterMessage('');
  }, [apiFileNameState, deploymentInputValueState, deploymentOutputTypeState]);

  // event Handler
  const apiFileNameHandler = (e) => {
    const { value } = e.target;
    if (value === '') {
      setApiFileNameState({ value, error: t('fileName.empty.message') });
    } else {
      setApiFileNameState({ value, error: '' });
    }
  };

  /**
   * API 가이드 코드 다운로드
   *
   * @param {string} script 파일 내용
   * @param {string} fileName 파일 이름
   */
  const downloadFile = (script, fileName) => {
    const blob = new Blob([script], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  // 모든 인풋 유효성 검증 여부 (true 일 경우 저장 버튼 활성화)
  const isValidate =
    apiFileNameState.error === '' &&
    deploymentInputValueState.isValid &&
    deploymentOutputTypeState.isValid &&
    deploymentParserState.isValid;

  const onSubmit = async (callback) => {
    const json = {
      api_file_name: apiFileNameState.value,
      deployment_input_data_form_list:
        deploymentInputValueState.deploymentInputForm,
      deployment_output_types: deploymentOutputTypeState.outputTypeList,
    };

    if (deploymentParserState.resultParserList) {
      if (
        deploymentParserState.resultParserList.checkpointLoadFilePathParser !==
        ''
      ) {
        json.checkpoint_load_file_path_parser =
          deploymentParserState.resultParserList.checkpointLoadFilePathParser;
      }

      if (
        deploymentParserState.resultParserList.checkpointLoadDirPathParser !==
        ''
      ) {
        json.checkpoint_load_dir_path_parser =
          deploymentParserState.resultParserList.checkpointLoadDirPathParser;
      }

      if (
        deploymentParserState.resultParserList.deploymentNumOfGpuParser !== ''
      ) {
        json.deployment_num_of_gpu_parser =
          deploymentParserState.resultParserList.deploymentNumOfGpuParser;
      }
    }

    const response = await callApi({
      url: 'deployments/create_deployment_api',
      method: 'post',
      body: { custom_deployment_json: JSON.stringify(json) },
    });
    const { result, message, status, error } = response;
    if (status === STATUS_SUCCESS) {
      downloadFile(result.custom_api_script, result.api_file_name);
      callback();
    } else if (status === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error('Fail');
    }
  };

  return (
    <DeploymentApiCodeModalContent
      title={t('createDeploymentApiCode.label')}
      onSubmit={onSubmit}
      isValidate={isValidate}
      type={type}
      modalData={modalData}
      apiFileNameState={apiFileNameState}
      apiFileNameHandler={apiFileNameHandler}
      deploymentInputValueRender={deploymentInputValueRender}
      deploymentOutputTypeRender={deploymentOutputTypeRender}
      deploymentParserRender={deploymentParserRender}
      deployFooterMessage={deployFooterMessage}
    />
  );
}
export default DeploymentApiCodeModal;
