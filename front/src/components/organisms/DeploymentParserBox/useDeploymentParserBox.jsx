import { useState, useMemo } from 'react';

// Components
import DeploymentParserBox from './DeploymentParserBox';

function useDeploymentParserBox() {
  // 배포 결과 유형
  const [resultParserList, setResultParserList] = useState(null);
  const [deploymentParserError, setDeploymentParserError] = useState(false);
  const [deploymentParserList, setDeploymentParserList] = useState([
    {
      // 배포코드에서 체크포인트 폴더 경로 입력받을 Parser
      label: 'checkpointLoadDirPathParser',
      value: '',
      placeholder: 'label_path',
      optional: true,
    },
    {
      // 배포코드에서 특정 체크포인트를 지정한 경로를 입력받을 Parser
      label: 'checkpointLoadFilePathParser',
      value: '',
      placeholder: 'weight_path',
      optional: true,
    },
    {
      // 배포에 사용할 GPU 개수 입력받을 Parser
      label: 'deploymentNumOfGpuParser',
      value: '',
      placeholder: 'gpu',
      optional: true,
    },
  ]);

  // 파서 입력 이벤트 핸들러
  function parserInputHandler(e) {
    const { name, value } = e.target;

    const prevDeploymentParserList = [...deploymentParserList];
    const newDeploymentParserList = prevDeploymentParserList.map((i) => {
      const item = { ...i };
      if (name === item.label) {
        item.value = value;
        return item;
      }
      return item;
    });
    setDeploymentParserList(newDeploymentParserList);
    checkValidate(newDeploymentParserList);
  }

  /**
   * 선택사항(optional)이 아닌 필드에 값이 비어있으면 에러, 아니면 결과 생성
   *
   * @param {object} parserList 검사할 파서 리스트
   * @returns
   */
  function checkValidate(parserList) {
    for (let i = 0; i < parserList.length; i++) {
      if (!parserList[i].optional && parserList[i].value === '') {
        setDeploymentParserError(true);
        return;
      }
    }
    setDeploymentParserError(false);
    makeResultJson(parserList);
  }

  /**
   * 결과 포맷 만들기
   *
   * @param {object} deploymentParserList
   */
  function makeResultJson(parserList) {
    // deploymentParserList 가공
    const newDeploymentParserList = {};
    parserList.map(({ label, value }) => {
      newDeploymentParserList[label] = value;
      return { ...newDeploymentParserList };
    });
    setResultParserList(newDeploymentParserList);
  }

  function renderDeploymentParser() {
    return (
      <DeploymentParserBox
        parserList={deploymentParserList}
        parserInputHandler={parserInputHandler}
      />
    );
  }

  const result = useMemo(
    () => ({
      resultParserList,
      isValid: !deploymentParserError,
    }),
    [resultParserList, deploymentParserError],
  );

  return [result, renderDeploymentParser];
}

export default useDeploymentParserBox;
