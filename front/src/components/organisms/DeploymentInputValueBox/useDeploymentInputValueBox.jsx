import { useMemo, useState } from 'react';

// Components
import DeploymentInputValueBox from './DeploymentInputValueBox';

function useDeploymentInputValueBox() {
  const [deploymentInputForm, setDeploymentInputForm] = useState([
    {
      method: 'POST',
      location: '',
      apiKey: '',
      valueType: '',
      category: '',
      categoryDesc: '',
      talkType: 'llm-multi',
    },
  ]);
  const [deploymentInputFormError, setDeploymentInputFormError] =
    useState(null);
  const defaultDeploymentInputForm = {
    method: 'POST',
    location: '',
    apiKey: '',
    valueType: '',
    category: '',
    categoryDesc: '',
    talkType: '',
  };

  // 배포 테스트 입력 폼 추가
  function addDeploymentInputForm() {
    const newDeploymentInputForm = [...deploymentInputForm];
    newDeploymentInputForm.push({ ...defaultDeploymentInputForm });
    setDeploymentInputForm(newDeploymentInputForm);
    setDeploymentInputFormError(
      deploymentInputFormError === '' ? null : deploymentInputFormError,
    );
  }

  // 배포 테스트 입력 폼 삭제
  function removeDeploymentInputForm(idx) {
    let newDeploymentInputForm = [...deploymentInputForm];
    newDeploymentInputForm = [
      ...newDeploymentInputForm.slice(0, idx),
      ...newDeploymentInputForm.slice(idx + 1, newDeploymentInputForm.length),
    ];

    // location 재설정
    for (let i = 0; i < newDeploymentInputForm.length; i++) {
      setLocationByCategory(
        i,
        newDeploymentInputForm[i].category,
        newDeploymentInputForm,
      );
    }

    setDeploymentInputForm(newDeploymentInputForm);
    checkValidate(newDeploymentInputForm);
  }

  /**
   * 카테고리 선택에 따라 Location 선택 변경
   * - 카테고리 image / canvas-image / audio / video / csv: location file
   * - 카테고리 text
   *   - 추가를 통해 text, image 등 다른 카테고리와 같이 받는 경우 : location form
   *   - 단일로 받는 경우 : location body
   * - 카테고리 canvas-coordinate: location form
   *
   * @param {number} idx input 인덱스
   * @param {string} category input 카테고리 값
   * @param {objecet} inputForm
   *
   */
  function setLocationByCategory(idx, category, inputForm) {
    const newInputForm = [...inputForm];

    switch (category) {
      case 'llm':
      case 'text':
        newInputForm[idx].location = 'body';
        break;
      case 'image':
      case 'audio':
      case 'video':
      case 'csv':
      case 'canvas-image':
        newInputForm[idx].location = 'file';
        break;
      case 'canvas-coordinate':
        newInputForm[idx].location = 'form';
        break;
      default:
        newInputForm[idx].location = 'body';
    }
    if (newInputForm.length > 1) {
      for (let i = 0; i < newInputForm.length; i++) {
        if (newInputForm[i].category === 'text') {
          newInputForm[i].location = 'form';
        }
      }
    }
  }

  // 배포 테스트 입력 폼 이벤트 핸들러
  function deploymentInputFormHandler(e, idx) {
    const { name, value } = e.target;
    const newDeploymentInputForm = [...deploymentInputForm];
    const inputData = newDeploymentInputForm[idx];

    if (name.indexOf('category') !== -1 && value === 'llm') {
      inputData.apiKey = 'llm';
      inputData.valueType = 'str';
    }

    if (name.indexOf('method') !== -1) {
      inputData.method = value;
    } else if (name.indexOf('location') !== -1) {
      inputData.location = value;
    } else if (name.indexOf('categoryDesc') !== -1) {
      inputData.categoryDesc = value;
    } else if (name.indexOf('category') !== -1) {
      inputData.category = value;
      setLocationByCategory(idx, value, newDeploymentInputForm);
    } else if (name.indexOf('talkType') !== -1) {
      inputData.talkType = value;
    } else {
      inputData[name] = value;
    }
    setDeploymentInputForm(newDeploymentInputForm);
    checkValidate(newDeploymentInputForm);
  }

  function checkValidate(inputForm) {
    let validateCount = 0;
    let error = null;

    // 배포 서비스 테스트 입력값 형식 확인
    if (inputForm.length < 1) {
      validateCount += 1;
    } else {
      let canvasImageCount = 0;
      let canvasCoordinateCount = 0;
      for (let i = 0; i < inputForm.length; i += 1) {
        const { apiKey, valueType, category, location } = inputForm[i];
        if (
          apiKey === '' ||
          valueType === '' ||
          category === '' ||
          location === ''
        ) {
          validateCount += 1;
          error = 'enterRequired.message';
        }
        if (category === 'canvas-image') {
          canvasImageCount += 1;
        } else if (category === 'canvas-coordinate') {
          canvasCoordinateCount += 1;
        }
      }
      // canvas-image, canvas-coordinate 쌍 있는지 체크하기
      if (canvasImageCount !== canvasCoordinateCount) {
        validateCount += 1;
        error = 'canvasCategory.message';
      }
    }

    if (validateCount === 0) {
      setDeploymentInputFormError('');
    } else {
      setDeploymentInputFormError(error);
    }
  }

  const llmOption = (category, talkType) => {
    if (category !== 'llm') return category;
    return talkType;
  };

  function makeResultJson(deploymentInputForm) {
    const inputForm = deploymentInputForm.map(
      ({
        method: m,
        location,
        apiKey,
        valueType,
        category,
        categoryDesc,
        talkType,
      }) => {
        return {
          method: m,
          location,
          api_key: apiKey,
          value_type: valueType,
          category: llmOption(category, talkType),
          category_description: categoryDesc,
        };
      },
    );
    return inputForm;
  }

  function renderDeploymentInputValue() {
    return (
      <DeploymentInputValueBox
        deploymentInputForm={deploymentInputForm}
        deploymentInputFormError={deploymentInputFormError}
        addInputForm={addDeploymentInputForm}
        removeInputForm={removeDeploymentInputForm}
        inputHandler={deploymentInputFormHandler}
      />
    );
  }

  const result = useMemo(
    () => ({
      deploymentInputForm: makeResultJson(deploymentInputForm),
      isValid: deploymentInputFormError === '',
    }),
    [deploymentInputForm, deploymentInputFormError],
  );

  return [result, renderDeploymentInputValue];
}

export default useDeploymentInputValueBox;
