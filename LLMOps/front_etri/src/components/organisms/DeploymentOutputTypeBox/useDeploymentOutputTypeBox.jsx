import { useState, useMemo, useEffect } from 'react';

// Components
import DeploymentOutputTypeBox from './DeploymentOutputTypeBox';

function useDeploymentOutputTypeBox(deploymentInputValueState) {
  const { category } = deploymentInputValueState.deploymentInputForm[0];
  const checkLLM = ['llm-multi', 'llm-single'].includes(category);

  useEffect(() => {
    if (!category) return;

    const newDeploymentOutputArr = [...deploymentOutputTypes];
    newDeploymentOutputArr.map((el) => {
      if (checkLLM && el.value === 'llm') {
        el.checked = true;
      } else {
        el.checked = false;
      }
      el.disabled = checkLLM;
    });

    setDeploymentOutputTypes(newDeploymentOutputArr);
    if (checkLLM) {
      makeResult(newDeploymentOutputArr);
    }
  }, [category]);

  // 배포 결과 유형
  const [outputTypeList, setOutputTypeList] = useState([]); // value만 있는 결과
  const [deploymentOutputTypes, setDeploymentOutputTypes] = useState([
    {
      label: 'Text',
      subtext: ['deploymentOutputTypes.text.message'],
      value: 'text',
      checked: false,
    },
    {
      label: 'Image',
      subtext: ['deploymentOutputTypes.image.message'],
      value: 'image',
      checked: false,
    },
    {
      label: 'Audio',
      subtext: ['deploymentOutputTypes.audio.message'],
      value: 'audio',
      checked: false,
    },
    {
      label: 'Video',
      subtext: ['deploymentOutputTypes.video.message'],
      value: 'video',
      checked: false,
    },
    /* {
      label: 'Bar Chart',
      subtext: ['deploymentOutputTypes.barchart.message'],
      value: 'barchart',
      checked: false,
    }, */
    {
      label: 'Column Chart',
      subtext: ['deploymentOutputTypes.columnchart.message'],
      value: 'columnchart',
      checked: false,
    },
    {
      label: 'Pie Chart',
      subtext: ['deploymentOutputTypes.piechart.message'],
      value: 'piechart',
      checked: false,
    },
    {
      label: 'Table',
      subtext: ['deploymentOutputTypes.table.message'],
      value: 'table',
      checked: false,
    },
    {
      label: '3D Object Model',
      subtext: ['deploymentOutputTypes.obj.message'],
      value: 'obj',
      checked: false,
    },
    {
      label: 'LLM',
      subtext: ['deploymentOutputTypes.llm.message'],
      value: 'llm',
      checked: false,
    },
    {
      label: 'other.label',
      subtext: ['deploymentOutputTypes.enterOther.message'],
      value: 'other',
      checked: false,
    },
  ]);
  const [otherDeploymentOutputTypes, setOtherDeploymentOutputTypes] =
    useState('');
  const [otherDeploymentOutputTypesError, setOtherDeploymentOutputTypesError] =
    useState('');

  function deploymentOutputTypesHandler(index) {
    const prevDeploymentOutputTypes = [...deploymentOutputTypes];
    let otherError = '';
    const newDeploymentOutputTypes = prevDeploymentOutputTypes.map(
      (v, i, arr) => {
        const value = { ...v };
        if (i === index) {
          value.checked = !v.checked;
          if (index === arr.length - 1) {
            // other
            if (value.checked) {
              otherError = null;
            }
          }
          return value;
        }
        return value;
      },
    );
    setDeploymentOutputTypes(newDeploymentOutputTypes);
    setOtherDeploymentOutputTypesError(otherError);
    makeResult(newDeploymentOutputTypes);
  }

  function textInputHandler(e) {
    const { value } = e.target;
    setOtherDeploymentOutputTypes(value);
    makeResult(deploymentOutputTypes);
    if (value === '') {
      setOtherDeploymentOutputTypesError('enterOther.empty.message');
    } else {
      setOtherDeploymentOutputTypesError('');
    }
  }

  function makeResult(deploymentOutputTypes) {
    let newDeploymentOutputTypes = [];
    deploymentOutputTypes.map(({ value, checked }) => {
      if (checked) {
        if (value === 'other') {
          newDeploymentOutputTypes.push(otherDeploymentOutputTypes);
        } else {
          newDeploymentOutputTypes.push(value);
        }
      }
      return newDeploymentOutputTypes;
    });
    setOutputTypeList(newDeploymentOutputTypes);
  }

  function renderDeploymentOutputType() {
    return (
      <DeploymentOutputTypeBox
        deploymentInputValueState={deploymentInputValueState}
        deploymentOutputTypes={deploymentOutputTypes}
        otherDeploymentOutputTypes={otherDeploymentOutputTypes}
        otherDeploymentOutputTypesError={otherDeploymentOutputTypesError}
        deploymentOutputTypesHandler={deploymentOutputTypesHandler}
        textInputHandler={textInputHandler}
      />
    );
  }

  const result = useMemo(
    () => ({
      outputTypeList,
      isValid:
        outputTypeList.length > 0 && otherDeploymentOutputTypesError === '',
    }),
    [outputTypeList, otherDeploymentOutputTypesError],
  );

  return [result, renderDeploymentOutputType];
}

export default useDeploymentOutputTypeBox;
