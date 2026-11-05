import { useState, useCallback, useEffect } from 'react';

// Components
import ServerResourceSettingForm from '@src/components/modalContents/NodeFormModalContent/ServerResourceSettingForm';

// Atoms
import CheckboxList from '@src/components/molecules/CheckboxList';

/**
 * 노드 생성, 수정 모달에서 서버 모드 설정 폼의 로직과 컴포넌트를 함께 분리한 커스텀 훅
 * @param {number} maxCpuResource 서버에서 뜨는 pod 또는 gpu가 최대로 사용할 수 있는 CPU core 정보
 * @param {number} numGpuResource CPU 사용량 할당 참고용 GPU 개수
 * @param {number} maxRamResource 서버에서 pod 또는 gpu가 최대로 사용할 수 있는 Ram 정보
 *
 * @returns {[
 *  {
 *    selectedMode: [ { label: string, checked: boolean } ],
 *    isValid: boolean,
 *    gpuModeCpuRsc: number,
 *    cpuModeCpuRsc: number,
 *    gpuModeRam: number,
 *    cpuModeRam: number,
 *    temporarySizeLimit: number,
 *  },
 *  ({
 *    is_cpu_server: number,
 *   is_gpu_server: number,
 *    cpu_cores_limit_per_gpu: number,
 *    cpu_cores_limit_per_pod: number,
 *    ram_limit_per_gpu: number,
 *    ram_limit_per_pod: number,
 *    ephemeral_storage_limit: number,
 *  }) => {},
 *  () => JSX.Element,
 *  () => JSX.Element
 * ]}
 * 리턴 값(배열)의 첫번째 인덱스 값은 선택된  값을 가진 객체를 리턴한다.
 * 두번째 인덱스 값은 함수이며 노드 수정 모달에서 생성 시 작성한 노드 모드 값 및 리소스 할당 값을 셋팅하는 함수이다.
 * 세번째 인덱스 값은 서버 모드 설정을 위한 컴포넌트를 화면에 렌더링하는 함수이다.
 * 네번째 인덱스 값은 네트워크 인터페이스 설정을 위한 컴포넌트를 화면에 렌더링하는 함수이다.
 *
 *
 */
const useServerResourceSettingInput = (
  maxCpuResource,
  numGpuResource,
  maxRamResource,
  deviceInfo,
  cpuServerInitialValue,
  modalType,
  addNodeMinNum,
) => {
  // Component State\

  const [modeOptions, setModeOptions] = useState([
    { label: 'GPU Server', value: 'gpu', checked: true },
    { label: 'CPU Server', value: 'cpu', checked: false },
  ]);
  const [gpuModeCpuRsc, setGpuModeCpuRsc] = useState('');
  const [gpuModeCpuRscError, setGpuModeCpuRscError] = useState();
  const [cpuModeCpuRsc, setCpuModeCpuRsc] = useState('');
  const [cpuModeCpuRscError, setCpuModeCpuRscError] = useState();
  const [gpuModeRam, setGpuModeRam] = useState('');
  const [gpuModeRamError, setGpuModeRamError] = useState();
  const [cpuModeRam, setCpuModeRam] = useState('');
  const [cpuModeRamError, setCpuModeRamError] = useState();
  const [rscOverDistributingGPUServer, setRscOverDistributingGPUServer] =
    useState([
      { label: 'Cores', value: 'cpu', checked: false },
      { label: 'RAM', value: 'ram', checked: false },
    ]);

  const [rscOverDistributingCPUServer, setRscOverDistributingCPUServer] =
    useState([
      { label: 'Cores', value: 'cpu', percent: 0, noLimit: false },
      { label: 'RAM', value: 'ram', percent: 0, noLimit: false },
    ]);
  // const [CPUOverDistributingGPUServer, setCPUOverDistributingGPUServer] = useState(false); // GPU 서버 CPU 100이상 사용 가능 여부
  // const [RAMOverDistributingGPUServer, setRAMOverDistributingGPUServer] = useState(false); // GPU 서버 RAM 100이상 사용 가능 여부
  // const [CPUOverDistributingCPUServer, setCPUOverDistributingCPUServer] = useState(false); // CPU 서버 CPU 100이상 사용 가능 여부
  // const [RAMOverDistributingCPUServer, setRAMOverDistributingCPUServer] = useState(false); // CPU 서버 RAM 100이상 사용 가능 여부
  const [temporarySizeLimit, setTemporarySizeLimit] = useState(10);
  const [temporarySizeLimitError, setTemporarySizeLimitError] = useState('');

  // Events
  const checkboxHandler = (e, idx, name) => {
    if (name === 'modeOptions') {
      const tmpModelOptions = [...modeOptions];
      tmpModelOptions[idx].checked = !tmpModelOptions[idx].checked;
      setModeOptions(tmpModelOptions);
    } else if (name === 'rscOverDistributingGPUServer') {
      const tmpModelOptions = [...rscOverDistributingGPUServer];
      tmpModelOptions[idx].checked = !tmpModelOptions[idx].checked;
      setRscOverDistributingGPUServer(tmpModelOptions);
    }
  };
  const cpuServerSliderHandler = useCallback(
    (name, percent, limit = false) => {
      const newCpuServer = [];
      const coresItem = rscOverDistributingCPUServer.filter(
        (el) => el?.label === 'Cores',
      );
      const ramItem = rscOverDistributingCPUServer.filter(
        (el) => el?.label === 'RAM',
      );

      const coresPercent = coresItem[0]?.percent;
      const ramPercent = ramItem[0]?.percent;

      const coresNoLimit = coresItem[0]?.noLimit;
      const ramNoLimit = ramItem[0]?.noLimit;

      rscOverDistributingCPUServer?.forEach((el) => {
        if (el?.label === 'RAM' && name === 'ram') {
          newCpuServer.push({
            label: 'Cores',
            value: 'cpu',
            percent: coresPercent,
            noLimit: coresNoLimit,
          });
          newCpuServer.push({
            label: 'RAM',
            value: 'ram',
            percent,
            noLimit: limit,
          });
        } else if (el?.label === 'Cores' && name === 'core') {
          newCpuServer.push({
            label: 'RAM',
            value: 'ram',
            percent: ramPercent, // 여기서의 el은 RAM의 el...
            noLimit: ramNoLimit,
          });
          newCpuServer.push({
            label: 'Cores',
            value: 'cpu',
            percent,
            noLimit: limit,
          });
        }
      });
      if (name) {
        setRscOverDistributingCPUServer(newCpuServer);
      }
    },
    [rscOverDistributingCPUServer],
  );

  useEffect(() => {
    const initialValue = [
      {
        label: 'Cores',
        value: 'cpu',
        percent: cpuServerInitialValue.cores,
        noLimit: false,
      },
      {
        label: 'RAM',
        value: 'ram',
        percent: cpuServerInitialValue.ram,
        noLimit: false,
      },
    ];
    setRscOverDistributingCPUServer(initialValue);
  }, [cpuServerInitialValue]);

  const validate = (name, value) => {
    if (name === 'gpuModeCpuRsc') {
      if (value === '') setGpuModeCpuRscError('Empty');
      else setGpuModeCpuRscError('');
    } else if (name === 'cpuModeCpuRsc') {
      if (value === '') setCpuModeCpuRscError('Empty');
      else setCpuModeCpuRscError('');
    } else if (name === 'gpuModeRam') {
      if (value === '') setGpuModeRamError('Empty');
      else setGpuModeRamError('');
    } else if (name === 'cpuModeRam') {
      if (value === '') setCpuModeRamError('Empty');
      else setCpuModeRamError('');
    } else if (name === 'temporarySizeLimit') {
      if (value === '') setTemporarySizeLimitError('Empty');
      else setTemporarySizeLimitError('');
    }
  };

  const inputHandler = (e) => {
    const { name, value } = e;
    if (name === 'gpuModeCpuRsc') {
      if (Number(value) <= maxCpuResource || value === '')
        setGpuModeCpuRsc(value);
      else if (Number(value) > maxCpuResource) setGpuModeCpuRsc(maxCpuResource);
    } else if (name === 'cpuModeCpuRsc') {
      if (Number(value) <= maxCpuResource || value === '')
        setCpuModeCpuRsc(value);
      else if (Number(value) > maxCpuResource) setCpuModeCpuRsc(maxCpuResource);
    } else if (name === 'gpuModeRam') {
      if (Number(value) <= maxRamResource || value === '')
        setGpuModeRam(parseInt(value, 10));
      else if (Number(value) > maxRamResource)
        setGpuModeRam(parseInt(maxRamResource, 10));
    } else if (name === 'cpuModeRam') {
      if (Number(value) <= maxRamResource || value === '')
        setCpuModeRam(parseInt(value, 10));
      else if (Number(value) > maxRamResource)
        setCpuModeRam(parseInt(maxRamResource, 10));
    } else if (name === 'temporarySizeLimit') {
      setTemporarySizeLimit(value);
    }
    validate(name, value);
  };

  const validCheck = () => {
    // 서버 모드 하나 이상 체크 했는지 확인
    const isValidServerMode =
      modeOptions.filter(({ checked }) => checked).length > 0;
    // CPU 및 RAM 리소스 입력 확인
    let isValidResourceForm = true;
    for (let i = 0; i < modeOptions.length; i += 1) {
      const { value, checked } = modeOptions[i];
      if (checked && value === 'gpu') {
        if (gpuModeCpuRscError !== '' || gpuModeRamError !== '') {
          isValidResourceForm = false;
          break;
        }
      } else if (checked && value === 'cpu') {
        if (cpuModeCpuRscError !== '' || cpuModeRamError !== '') {
          isValidResourceForm = false;
          break;
        }
      }
    }
    // 임시 용량 크기 제한 입력 값 확인
    const isValidTemporarySizeLimit = temporarySizeLimitError === '';
    return (
      isValidServerMode && isValidResourceForm && isValidTemporarySizeLimit
    );
  };

  const setServerResourceInputState = (nodeData) => {
    const {
      is_cpu_server: isCpuServer,
      is_gpu_server: isGpuServer,
      cpu_cores_limit_per_gpu: cpuCoresLimitPerGpu,
      cpu_cores_limit_per_pod: cpuCoresLimitPerPod,
      ram_limit_per_gpu: ramLimitPerGpu,
      ram_limit_per_pod: ramLimitPerPod,
      ephemeral_storage_limit: ephemeralStorageLimit,
      cpu_cores_lock_per_gpu: cpuCoresLockPerGpu,
      ram_lock_per_gpu: ramLockPerGpu,
    } = nodeData;
    setModeOptions([
      { label: 'GPU Server', value: 'gpu', checked: isGpuServer === 1 },
      { label: 'CPU Server', value: 'cpu', checked: isCpuServer === 1 },
    ]);

    setRscOverDistributingGPUServer([
      { label: 'Cores', value: 'cpu', checked: cpuCoresLockPerGpu === 1 },
      { label: 'RAM', value: 'ram', checked: ramLockPerGpu === 1 },
    ]);

    if (cpuCoresLimitPerGpu !== null) {
      setGpuModeCpuRsc(cpuCoresLimitPerGpu);
      setGpuModeCpuRscError('');
    }
    if (cpuCoresLimitPerPod !== null) {
      setCpuModeCpuRsc(cpuCoresLimitPerPod);
      setCpuModeCpuRscError('');
    }
    if (ramLimitPerGpu !== null) {
      setGpuModeRam(ramLimitPerGpu);
      setGpuModeRamError('');
    }
    if (ramLimitPerPod !== null) {
      setCpuModeRam(ramLimitPerPod);
      setCpuModeRamError('');
    }
    if (ephemeralStorageLimit !== null) {
      setTemporarySizeLimit(ephemeralStorageLimit);
      setTemporarySizeLimitError('');
    }
  };

  // Render
  const renderServerModeInput = () => {
    if (
      maxCpuResource === null ||
      maxCpuResource === undefined ||
      numGpuResource === null ||
      numGpuResource === undefined ||
      maxRamResource === null ||
      maxRamResource === undefined
    )
      return null;

    return (
      <CheckboxList
        label='serverMode.label'
        options={modeOptions}
        onChange={(e, i) => {
          checkboxHandler(e, i, 'modeOptions');
        }}
        horizontal
      />
    );
  };

  const renderServerResourceSettingInput = () => {
    if (
      maxCpuResource === null ||
      maxCpuResource === undefined ||
      numGpuResource === null ||
      numGpuResource === undefined ||
      maxRamResource === null ||
      maxRamResource === undefined
    )
      return null;

    return (
      <ServerResourceSettingForm
        modeOptions={modeOptions}
        gpuModeCpuRsc={gpuModeCpuRsc}
        cpuModeCpuRsc={cpuModeCpuRsc}
        gpuModeRam={gpuModeRam}
        cpuModeRam={cpuModeRam}
        gpuModeCpuRscError={gpuModeCpuRscError}
        cpuModeCpuRscError={cpuModeCpuRscError}
        gpuModeRamError={gpuModeRamError}
        cpuModeRamError={cpuModeRamError}
        maxCpuResource={maxCpuResource}
        numGpuResource={numGpuResource}
        maxRamResource={maxRamResource}
        temporarySizeLimit={temporarySizeLimit}
        temporarySizeLimitError={temporarySizeLimitError}
        rscOverDistributingGPUServer={rscOverDistributingGPUServer}
        rscOverDistributingCPUServer={rscOverDistributingCPUServer}
        checkboxHandler={checkboxHandler}
        inputHandler={inputHandler}
        deviceInfo={deviceInfo}
        cpuServerSliderHandler={cpuServerSliderHandler}
        cpuServerInitialValue={cpuServerInitialValue}
        modalType={modalType}
        addNodeMinNum={addNodeMinNum}
      />
    );
  };

  const selectedMode = modeOptions.filter(({ checked }) => checked);
  const selectedRscOverdistributingGPUServer =
    rscOverDistributingGPUServer.filter(({ checked }) => checked);
  const selectedRscOverdistributingCPUServer =
    rscOverDistributingCPUServer.filter(({ checked }) => checked);

  const result = {
    selectedMode,
    isValid: validCheck(),
    gpuModeCpuRsc,
    cpuModeCpuRsc,
    gpuModeRam,
    cpuModeRam,
    temporarySizeLimit,
    selectedRscOverdistributingGPUServer,
    selectedRscOverdistributingCPUServer,
    rscOverDistributingCPUServer,
  };

  return [
    result,
    setServerResourceInputState,
    renderServerModeInput,
    renderServerResourceSettingInput,
    rscOverDistributingCPUServer,
  ];
};

export default useServerResourceSettingInput;
