// Components
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { shallowEqual, useDispatch, useSelector } from 'react-redux';

import ExternalFineTuningView from './ExternalFineTuningView';

import { ButtonV2, Checkbox, Radio, Switch } from '@tango/ui-react';

import {
  handleSetModelRangeState,
  handleSetModelState,
} from '@src/store/modules/llmModel';
import { openModal } from '@src/store/modules/modal';
// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { loadModalComponent } from '@src/modal';

import SimpleNav from '../SimpleNav';
import Advanced from './Advanced';
import DataList from './DataList';
import FineTuningGraph from './FineTuningGraph';
import InstanceSetting from './InstanceSetting';
import { fineTuningTypeOptions, rangeBarTitle } from './item';
import ModelRangeBar from './ModelRangeBar/ModelRangeBar';
import TopButtonList from './TopButtonList';
import useSSETime from './useSSEFinetuningTime';
import useSSEGraph from './useSSEGraph';
import useSSEStatus from './useSSEStatus';

import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
import style from './FineTuning.module.scss';

import GroupIcon from '@images/icon/00-ic-llm-group.svg';
import IconSmile from '@images/icon/ic-smile.png';

const cx = classNames.bind(style);

const Tlabel = {
  'Number of Epochs': 'numberOfEpochs',
  'Gradient Accumulation Steps': 'gradientAccumulationSteps',
  'Cutoff Length': 'cutoffLength',
  'Learning Rate': 'learningRate',
  'Warmup Steps': 'warmupSteps',
};

const TlabelMM = {
  'Epochs': 'numberOfEpochs',
  'Learning Rate': 'learningRate',
  'Batch Size': 'perDeviceTrainBatchSize',
  'Warmup Steps': 'warmupSteps',
  'Cutoff Length': 'cutoffLength',
  'Gradient Accumulation Steps': 'gradientAccumulationSteps',
};

const PROJECTOR_OPTIONS = [
  { value: 'mlp2x_gelu',        label: 'mlp2x_gelu — 2-layer MLP + GELU (LLaVA 1.5)' },
  { value: 'mlp3x_gelu',        label: 'mlp3x_gelu — 3-layer MLP + GELU' },
  { value: 'linear',            label: 'linear — Single linear projection (LLaVA 1.0)' },
  { value: 'llama3_2_vision',   label: 'llama3_2_vision — Llama 3.2 Vision cross-attention' },
  { value: 'resampler',         label: 'resampler — Perceiver Resampler (Flamingo / Qwen-VL)' },
  { value: 'qformer',           label: 'qformer — Q-Former (BLIP-2 / InstructBLIP)' },
  { value: 'clip_mlp_gelu',     label: 'clip_mlp_gelu — CLIP MLP + GELU' },
];

const stage1Fields = [
  { label: 'Epochs', valueTitle: 'numberOfEpochs', min: 1, max: 100, step: 1 },
  { label: 'Learning Rate', valueTitle: 'learningRate', min: 0.000001, max: 0.01, step: 0.000001 },
  { label: 'Batch Size', valueTitle: 'perDeviceTrainBatchSize', min: 1, max: 64, step: 1 },
  { label: 'Warmup Steps', valueTitle: 'warmupSteps', min: 0, max: 10000, step: 100 },
];

const stage2Fields = [
  { label: 'Epochs', valueTitle: 'numberOfEpochs', min: 1, max: 100, step: 1 },
  { label: 'Learning Rate', valueTitle: 'learningRate', min: 0.000001, max: 0.01, step: 0.000001 },
  { label: 'Batch Size', valueTitle: 'perDeviceTrainBatchSize', min: 1, max: 64, step: 1 },
  { label: 'Warmup Steps', valueTitle: 'warmupSteps', min: 0, max: 10000, step: 100 },
  { label: 'Cutoff Length', valueTitle: 'cutoffLength', min: 64, max: 4096, step: 64 },
  { label: 'Gradient Accumulation Steps', valueTitle: 'gradientAccumulationSteps', min: 1, max: 32, step: 1 },
];

const FineTuning = memo(function FineTuning({ navList, data, ...rest }) {
  const { userName } = useSelector((state) => state.auth, shallowEqual);

  const { t } = useTranslation();
  const { workspaceId, modelId } = data;

  const { range, originRange } = useSelector(
    (state) => state.llmModel,
    shallowEqual,
  );

  const hasFetchedInitially = useRef(false);
  // Router Hooks
  const dispatch = useDispatch();

  const [infoData, setInfoData] = useState(null);
  const [fineTuningData, setFineTuningData] = useState(null);
  const [fineTuningType, setFineTuningType] = useState(1);
  const [graphData, setGraphData] = useState(null);
  const [progressData, setProgressData] = useState(null);
  const [commitId, setCommitId] = useState(null);
  const [accelator, setAccelator] = useState(false); // 0 1 Accelator 기능
  const [accelatorDirty, setAccelatorDirty] = useState(false);
  const [userChangedFineTuningType, setUserChangedFineTuningType] =
    useState(false);
  const [btnDisable, setBtnDisable] = useState({
    system: false,
    commitLoad: false,
    commit: false,
    run: true,
  });
  const [fineStatus, setFineStatus] = useState(null);
  const [rangeCheckValue, setRangeCheckValue] = useState({
    bit: false,
    lora: true,
  });

  const [stage1, setStage1] = useState({
    numberOfEpochs: 3,
    learningRate: 0.00003,
    perDeviceTrainBatchSize: 8,
    warmupSteps: 150,
  });
  const [stage1Origin, setStage1Origin] = useState({
    numberOfEpochs: 3,
    learningRate: 0.00003,
    perDeviceTrainBatchSize: 8,
    warmupSteps: 150,
  });

  const [stage2, setStage2] = useState({
    numberOfEpochs: 5,
    learningRate: 0.00005,
    perDeviceTrainBatchSize: 4,
    warmupSteps: 100,
    cutoffLength: 1024,
    gradientAccumulationSteps: 2,
  });
  const [stage2Origin, setStage2Origin] = useState({
    numberOfEpochs: 5,
    learningRate: 0.00005,
    perDeviceTrainBatchSize: 4,
    warmupSteps: 100,
    cutoffLength: 1024,
    gradientAccumulationSteps: 2,
  });

  const [stage2CheckValue, setStage2CheckValue] = useState({
    bit: false,
    lora: true,
  });

  const [stage1ProjectorType, setStage1ProjectorType] = useState('mlp2x_gelu');

  const [stage1Enabled, setStage1Enabled] = useState(true);
  const [stage2Enabled, setStage2Enabled] = useState(true);

  const isMultimodal = useMemo(() => {
    return infoData?.load_type === 'multimodal';
  }, [infoData]);

  const handleRangeBar = useCallback(
    (e, label) => {
      const changeType = Tlabel[label];

      dispatch(
        handleSetModelRangeState({
          type: changeType,
          modelValue: +e.target.value,
        }),
      );
    },
    [dispatch],
  );

  const handleRefreshRangeBar = useCallback(
    (label) => {
      const changeType = Tlabel[label];
      const refreshValue = originRange[changeType];

      dispatch(
        handleSetModelRangeState({
          type: changeType,
          modelValue: refreshValue,
        }),
      );
    },
    [dispatch, originRange],
  );

  const handleStage1RangeBar = useCallback((e, label) => {
    const key = TlabelMM[label];
    setStage1((prev) => ({
      ...prev,
      [key]: +e.target.value,
    }));
  }, []);

  const handleStage1Refresh = useCallback((label) => {
    const key = TlabelMM[label];
    setStage1((prev) => ({
      ...prev,
      [key]: stage1Origin[key],
    }));
  }, [stage1Origin]);

  const handleStage2RangeBar = useCallback((e, label) => {
    const key = TlabelMM[label];
    setStage2((prev) => ({
      ...prev,
      [key]: +e.target.value,
    }));
  }, []);

  const handleStage2Refresh = useCallback((label) => {
    const key = TlabelMM[label];
    setStage2((prev) => ({
      ...prev,
      [key]: stage2Origin[key],
    }));
  }, [stage2Origin]);

  // get commit id
  const getCommitId = (loadId) => {
    setCommitId(loadId);
  };

  const filteredRest = useMemo(() => {
    const { tReady, dispatch, ...remainingProps } = rest;
    return remainingProps;
  }, [rest]);

  // Training upload data modal
  const onClickUpload = () => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_DATA_UPLOAD',
        modalData: {
          workspaceId,
          modelId,
          git: fineTuningData?.huggingface_git,
          refresh: () => getFineTuningData(),
        },
      }),
    );
  };
  // Run Commit
  const onClickCommitLoad = () => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_COMMIT_LOAD',
        modalData: {
          workspaceId,
          modelId,
          // git: fineTuningData?.huggingface_git,
          getCommitId,
          refresh: () => getFineTuningData(),
        },
      }),
    );
  };

  //  Commit
  const onClickCommit = ({ stop }) => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_COMMIT',
        modalData: {
          workspaceId,
          modelId,
          stop,
          refresh: () => getFineTuningData(),
        },
      }),
    );
  };

  const runFineTuning = async ({ instanceId, instanceCount, gpuCount }) => {
    const isMM = infoData?.load_type === 'multimodal';

    const fine_tuning_config = {
      fine_tuning_type: fineTuningType === 1 ? 'basic' : 'advanced', // basic, advanced
      used_tango_accelerator: accelator ? 1 : 0,
    };

    if (fineTuningType === 1) {
      if (isMM) {
        if (stage1Enabled) {
          fine_tuning_config.stage1_config = {
            num_train_epochs: stage1.numberOfEpochs,
            learning_rate: stage1.learningRate,
            per_device_train_batch_size: stage1.perDeviceTrainBatchSize,
            warmup_steps: stage1.warmupSteps,
            projector_type: stage1ProjectorType,
          };
        }
        if (stage2Enabled) {
          fine_tuning_config.stage2_config = {
            num_train_epochs: stage2.numberOfEpochs,
            learning_rate: stage2.learningRate,
            per_device_train_batch_size: stage2.perDeviceTrainBatchSize,
            warmup_steps: stage2.warmupSteps,
            cutoff_length: stage2.cutoffLength,
            gradient_accumulation_steps: stage2.gradientAccumulationSteps,
            load_in_8bit: stage2CheckValue.bit ? 1 : 0,
            used_lora: stage2CheckValue.lora ? 1 : 0,
          };
        }
      } else {
        fine_tuning_config.cutoff_length = range.cutoffLength;
        fine_tuning_config.gradient_accumulation_steps = range.gradientAccumulationSteps;
        fine_tuning_config.learning_rate = range.learningRate;
        fine_tuning_config.load_in_8bit = rangeCheckValue.bit ? 1 : 0;
        fine_tuning_config.num_train_epochs = range.numberOfEpochs;
        fine_tuning_config.used_lora = rangeCheckValue.lora ? 1 : 0;
        fine_tuning_config.warmup_steps = range.warmupSteps;
      }
    } else {
      const configFile = fineTuningData?.model_config_file_list[0] ?? {
        file_name: '',
      };
      fine_tuning_config.config_file_name = configFile.file_name;
    }

    const body = {
      model_id: parseInt(modelId, 10),
      model_dataset_id: fineTuningData?.model_datasets[0]?.id ?? 0,
      instance_id: instanceId,
      instance_count: instanceCount,
      gpu_count: gpuCount,
      fine_tuning_config,
    };

    if (commitId) {
      // 커밋불러오기로한 아이디값 가져오기
      body.commit_id = commitId;
    }

    const response = await callApi({
      url: `models/fine-tuning/run`,
      method: 'post',
      body,
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setAccelatorDirty(false);
      return true;
    } else {
      errorToastMessage(error, message);
    }
  };

  // Run  Modal
  const onClickRun = () => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_SETTING',
        modalData: {
          workspaceId,
          modelId,
          // git: fineTuningData?.huggingface_git,
          onSubmit: ({ instanceId, instanceCount, gpuCount }) => {
            return runFineTuning({ instanceId, instanceCount, gpuCount });
          },
          refresh: () => getFineTuningData(),
        },
      }),
    );
  };

  const onClickSystemLog = () => {
    dispatch(
      openModal({
        modalType: 'FINETUNING_SYSTEM_LOG',
        modalData: {
          workspaceId,
          modelId,
          modelName: fineTuningData?.model_name,
        },
      }),
    );
  };

  // Configuration file upload modal
  const onClickConfigUpload = () => {
    dispatch(
      openModal({
        modalType: 'CONFIGURATION_DATA_UPLOAD',
        modalData: {
          workspaceId,
          modelId,
          refresh: () => getFineTuningData(),
        },
      }),
    );
  };

  // get fine tuning
  const getFineTuningData = useCallback(
    async (fineTuningStatus) => {
      //* 처음에만 get 해서 redux;

      const summaryResponse = await callApi({
        url: `models/fine-tuning/summary?model_id=${modelId}`,
        method: 'get',
      });
      let currentInfoData = null;
      if (summaryResponse.status === STATUS_SUCCESS) {
        setInfoData(summaryResponse.result);
        currentInfoData = summaryResponse.result;
      }

      const response = await callApi({
        url: `models/fine-tuning?model_id=${modelId}`,
        method: 'get',
      });

      const { status, result, message, error } = response;
      if (status === STATUS_SUCCESS) {
        setFineTuningData(result);

        // 외부 학습 모델은 fine_tuning_config 가 null (partner manifest 기반).
        // 아래 internal LLM hyperparameter dispatch 는 skip 하고
        // ExternalFineTuningView 로 render 분기.
        if (result?.training_type === 'external') {
          return;
        }

        const isMM = currentInfoData?.load_type === 'multimodal';

        if (isMM) {
          const s1 = result?.stage1_config;
          const s2 = result?.stage2_config;

          const getStage1Data = {
            numberOfEpochs: s1?.num_train_epochs ?? 3,
            learningRate: s1?.learning_rate ?? 0.00003,
            perDeviceTrainBatchSize: s1?.per_device_train_batch_size ?? 8,
            warmupSteps: s1?.warmup_steps ?? 150,
          };

          const getStage2Data = {
            numberOfEpochs: s2?.num_train_epochs ?? 5,
            learningRate: s2?.learning_rate ?? 0.00005,
            perDeviceTrainBatchSize: s2?.per_device_train_batch_size ?? 4,
            warmupSteps: s2?.warmup_steps ?? 100,
            cutoffLength: s2?.cutoff_length ?? 1024,
            gradientAccumulationSteps: s2?.gradient_accumulation_steps ?? 2,
          };

          setStage1(getStage1Data);
          setStage1Origin(getStage1Data);
          setStage2(getStage2Data);
          setStage2Origin(getStage2Data);
          setStage2CheckValue({
            bit: s2?.load_in_8bit ?? 0,
            lora: s2?.used_lora ?? 1,
          });
        } else {
          const config = result?.fine_tuning_config;

          const getRangeData = {
            numberOfEpochs: config?.num_train_epochs ?? 3,
            gradientAccumulationSteps: config?.gradient_accumulation_steps ?? 1,
            cutoffLength: config?.cutoff_length ?? 512,
            learningRate: config?.learning_rate ?? 0.00005,
            warmupSteps: config?.warmup_steps ?? 100,
          };

          if (!accelatorDirty) {
            setAccelator(config?.used_tango_accelerator ?? 0);
          }

          dispatch(
            handleSetModelState({
              type: 'range',
              range: getRangeData,
            }),
          );

          dispatch(
            handleSetModelState({
              type: 'originRange',
              originRange: getRangeData,
            }),
          );

          setRangeCheckValue({
            bit: config?.load_in_8bit ?? 0,
            lora: config?.used_lora ?? 0,
          });
        }

        if (!userChangedFineTuningType) {
          const config = result?.fine_tuning_config;
          setFineTuningType(config?.fine_tuning_type === 'basic' ? 1 : 2);
        }
      } else {
        errorToastMessage(error, message);
      }
    },
    [accelatorDirty, dispatch, modelId, userChangedFineTuningType],
  );

  // training delete
  const onDeleteTrainingData = async (selectedId) => {
    const response = await callApi({
      url: `models/option/model-dataset?model_dataset_id=${selectedId}`,
      method: 'delete',
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('delete');
      getFineTuningData();
    } else {
      errorToastMessage(error, message);
    }
  };

  const handleRangeCheckbox = (type) => {
    setRangeCheckValue((prev) => ({
      ...prev,
      [type]: !prev[type],
    }));
  };

  const changeAccelerator = () => {
    setAccelator((prev) => !prev);
    setAccelatorDirty(true);
  };

  // config delete
  const onDeleteConfigData = async (selectedId) => {
    const response = await callApi({
      url: `models/option/model-configuration?model_config_id=${selectedId}`,
      method: 'delete',
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('delete');
      getFineTuningData();
    } else {
      errorToastMessage(error, message);
    }
  };

  // SSE Status
  useSSEStatus(modelId, userName, setFineStatus);

  // fineTuning status
  const fineTuningStatus = useMemo(
    () => fineStatus?.fine_tuning_status?.status,
    [fineStatus],
  );

  // fineTuning status === running
  const runningStatus = useMemo(
    () => fineTuningStatus === 'running',
    [fineTuningStatus],
  );

  useSSEGraph(modelId, userName, fineTuningStatus, setGraphData);
  useSSETime(modelId, userName, setProgressData, fineTuningStatus);

  // * A-LLM MODELBASE 용 모델이름과 커밋버전
  const modelName = fineTuningData?.commit_model_name || '';
  const [allmName, allmCommit] = modelName.split('/') || ['', '']; // '/' 기준으로 분리- 앞 모델, 뒤 커밋

  // 실행 버튼 활성화 비활성화 체크
  const runValidate = useCallback(() => {
    const isMM = infoData?.load_type === 'multimodal';
    const hasActiveStage = !isMM || fineTuningType !== 1 || stage1Enabled || stage2Enabled;

    const conditions = [
      fineTuningData?.model_datasets?.length > 0, // 학습 데이터 선택 여부
      !(
        fineTuningType === 2 &&
        fineTuningData?.model_config_file_list?.length === 0
      ), // config 선택 여부
      hasActiveStage, // Multimodal basic 일 때, 적어도 하나의 stage가 켜져 있어야 함
    ];

    setBtnDisable((prev) => ({
      ...prev,
      run: !conditions.every(Boolean),
    }));
  }, [
    fineTuningData?.model_config_file_list,
    fineTuningData?.model_datasets?.length,
    fineTuningType,
    infoData?.load_type,
    stage1Enabled,
    stage2Enabled,
  ]);

  useEffect(() => {
    runValidate();
  }, [runValidate]);

  useEffect(() => {
    loadModalComponent('FINETUNING_DATA_UPLOAD');
    loadModalComponent('CONFIGURATION_DATA_UPLOAD');
    loadModalComponent('FINETUNING_SETTING');
    loadModalComponent('FINETUNING_COMMIT_LOAD');
    loadModalComponent('FINETUNING_COMMIT');
    loadModalComponent('FINETUNING_SYSTEM_LOG');
  }, []);

  useEffect(() => {
    const fetchFineTuningData = async () => {
      await getFineTuningData(fineTuningStatus);
    };

    if (!hasFetchedInitially.current) {
      fetchFineTuningData(); // 초기 호출
      hasFetchedInitially.current = true;
    }

    if (fineTuningStatus === 'running') {
      fetchFineTuningData(); // 상태 변경 시 호출
    }
  }, [fineTuningStatus, getFineTuningData]);

  // 외부 학습 모델 (training_type='external') 은 FineTuning 탭 안에서
  // 같은 SimpleNav + box{left, right} 레이아웃을 유지한 채 내용만 교체한다.
  // (별도 탭으로 분리하지 않음 — internal 과 동일한 운영 UX.)
  const isExternalModel = fineTuningData?.training_type === 'external';

  if (isExternalModel) {
    return (
      <ExternalFineTuningView
        navList={navList}
        fineTuningData={fineTuningData}
        workspaceId={workspaceId}
        modelId={modelId}
        refresh={() => getFineTuningData()}
        filteredRest={filteredRest}
      />
    );
  }

  return (
    <div id='info-tab' className={cx('info-tab')}>
      <SimpleNav
        navList={navList}
        t={t}
        {...filteredRest}
        topButtonList={
          <TopButtonList
            t={t}
            modelId={modelId}
            // status={fineTuningStatus}
            fineStatus={fineStatus}
            btnDisable={btnDisable}
            onClickSystemLog={onClickSystemLog}
            onClickRun={onClickRun}
            onClickCommitLoad={onClickCommitLoad}
            onClickCommit={onClickCommit}
          />
        }
        titleName={fineTuningData?.model_name}
        subTitle={fineTuningData?.latest_commit_info?.name}
      />
      <div className={cx('box')}>
        <div className={cx('left', runningStatus && 'disabled')}>
          <div className={cx('left-top')}>
            <div className={cx('model-box')}>
              <div className={cx('title')}>{t('model.label')}</div>
              <div className={cx('name')}>
                {!fineTuningData && '-'}
                {fineTuningData &&
                  (fineTuningData?.commit_model_name ? (
                    <div className={cx('model-box')}>
                      <img src={GroupIcon} alt='icon' />
                      <span className={cx('model')}>GenAI Platform</span>
                      <span>{allmName}</span>
                    </div>
                  ) : (
                    <div className={cx('model-box')}>
                      <img src={IconSmile} alt='icon' />
                      <span className={cx('model')}>Hugging Face</span>
                      <span>{fineTuningData?.huggingface_mode_id}</span>
                    </div>
                  ))}
              </div>
              {fineTuningData && fineTuningData?.commit_model_name && (
                <div className={cx('commit')}>
                  <div className={cx('title')}>{`${t('commit.label')} ${t(
                    'version.label',
                  )}`}</div>
                  <div className={cx('name')}>{allmCommit}</div>
                </div>
              )}
            </div>
            <div className={cx('training-data-box')}>
              <div className={cx('title')}>{t('trainingData.label')}</div>
              {fineTuningData?.model_datasets?.length > 0 ? (
                <DataList
                  list={fineTuningData?.model_datasets}
                  // selectedList={selectedTraining}
                  disable={!!runningStatus}
                  onClickDelete={onDeleteTrainingData}
                  t={t}
                />
              ) : (
                <ButtonV2
                  type='outline'
                  size='l'
                  label={t('trainingDataSelect.label')}
                  // disabled={disabled}
                  onClick={onClickUpload}
                  style={{ width: '100%' }}
                />
              )}
            </div>
            <div className={cx('type-box')}>
              <div className={cx('title')}>{t('fineTuningType.label')}</div>

              <Radio
                options={fineTuningTypeOptions.map((data, i) => ({
                  ...data,
                  labelStyle: {
                    fontSize: '14px',
                    fontFamily: 'SpoqaM',
                    textWrap: 'nowrap',
                  },
                  // disabled: data.disabled,
                }))}
                name='fineTuningType'
                selectedValue={fineTuningType}
                isReadonly={runningStatus}
                onChange={(e) => {
                  if (!runningStatus) {
                    setUserChangedFineTuningType(true);
                    setFineTuningType(+e.target.value);
                  }
                }}
              />
              <div className={cx('border')}></div>
              {fineTuningType === 1 && (
                isMultimodal ? (
                  <div className={cx('stage-container')}>
                    {/* Stage 1: Projector Training */}
                    <div className={cx('stage-card', !stage1Enabled && 'stage-card-disabled')}>
                      <div className={cx('stage-header')}>
                        <Checkbox
                          checked={stage1Enabled}
                          onChange={() => {
                            if (!runningStatus) {
                              setStage1Enabled((prev) => !prev);
                            }
                          }}
                          disabled={runningStatus}
                        />
                        <span className={cx('stage-badge')}>1</span>
                        <span className={cx('stage-title')}>Stage 1: Projector Training</span>
                      </div>
                      <div className={cx('stage-desc')}>
                        Train the projection layer connecting vision encoder and LLM
                      </div>
                      <div className={cx('projector-select-row')}>
                        <label className={cx('projector-label')}>Projector Architecture</label>
                        <select
                          className={cx('projector-select')}
                          value={stage1ProjectorType}
                          disabled={runningStatus || !stage1Enabled}
                          onChange={(e) => setStage1ProjectorType(e.target.value)}
                        >
                          {PROJECTOR_OPTIONS.map(({ value, label }) => (
                            <option key={value} value={value}>{label}</option>
                          ))}
                        </select>
                      </div>
                      <div className={cx('flex-16')}>
                        {stage1Fields.map(({ label, valueTitle, min, max, step }) => (
                          <ModelRangeBar
                            key={`stage1-${valueTitle}`}
                            label={label}
                            value={stage1[valueTitle]}
                            min={min}
                            max={max}
                            step={step}
                            disabled={runningStatus || !stage1Enabled}
                            onChange={handleStage1RangeBar}
                            handleRefresh={handleStage1Refresh}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Arrow / Divider */}
                    <div className={cx('stage-divider')}>
                      <span className={cx('arrow')}>↓</span>
                    </div>

                    {/* Stage 2: LLM Training (LoRA) */}
                    <div className={cx('stage-card', !stage2Enabled && 'stage-card-disabled')}>
                      <div className={cx('stage-header')}>
                        <Checkbox
                          checked={stage2Enabled}
                          onChange={() => {
                            if (!runningStatus) {
                              setStage2Enabled((prev) => !prev);
                            }
                          }}
                          disabled={runningStatus}
                        />
                        <span className={cx('stage-badge')}>2</span>
                        <span className={cx('stage-title')}>Stage 2: LLM Fine-tuning (LoRA)</span>
                      </div>
                      <div className={cx('stage-desc')}>
                        Fine-tune the LLM with LoRA adapters
                      </div>
                      <div className={cx('flex-16')}>
                        {stage2Fields.map(({ label, valueTitle, min, max, step }) => (
                          <ModelRangeBar
                            key={`stage2-${valueTitle}`}
                            label={label}
                            value={stage2[valueTitle]}
                            min={min}
                            max={max}
                            step={step}
                            disabled={runningStatus || !stage2Enabled}
                            onChange={handleStage2RangeBar}
                            handleRefresh={handleStage2Refresh}
                          />
                        ))}
                        <div
                          className={cx(
                            'range-checkbox',
                            (runningStatus || !stage2Enabled) && 'disabled',
                          )}
                          style={{ margin: '12px 0 6px 0' }}
                        >
                          Load in 8bit
                          <Checkbox
                            checked={stage2CheckValue.bit}
                            onChange={() => {
                              if (!runningStatus && stage2Enabled) {
                                setStage2CheckValue((prev) => ({
                                  ...prev,
                                  bit: !prev.bit,
                                }));
                              }
                            }}
                            disabled={runningStatus || !stage2Enabled}
                          />
                        </div>
                        <div
                          className={cx(
                            'range-checkbox',
                            (runningStatus || !stage2Enabled) && 'disabled',
                          )}
                        >
                          Use LoRA
                          <Checkbox
                            checked={stage2CheckValue.lora}
                            onChange={() => {
                              if (!runningStatus && stage2Enabled) {
                                setStage2CheckValue((prev) => ({
                                  ...prev,
                                  lora: !prev.lora,
                                }));
                              }
                            }}
                            disabled={runningStatus || !stage2Enabled}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className={cx('flex-16')}>
                    {rangeBarTitle.map(
                      ({ label, valueTitle, min, max, step }) => {
                        return (
                          <ModelRangeBar
                            key={`single-${valueTitle}`}
                            label={label}
                            value={range[valueTitle]}
                            min={min}
                            max={max}
                            step={step}
                            disabled={runningStatus}
                            onChange={handleRangeBar}
                            handleRefresh={handleRefreshRangeBar}
                          />
                        );
                      },
                    )}
                    <div
                      className={cx(
                        'range-checkbox',
                        runningStatus && 'disabled',
                      )}
                      style={{ margin: '24px 0 14px 0' }}
                    >
                      Load in 8bit
                      <Checkbox
                        checked={rangeCheckValue.bit}
                        onChange={() => {
                          if (!runningStatus) {
                            handleRangeCheckbox('bit');
                          }
                        }}
                        disabled={runningStatus}
                      />
                    </div>
                    <div
                      className={cx(
                        'range-checkbox',
                        runningStatus && 'disabled',
                      )}
                    >
                      Use LoRA
                      <Checkbox
                        checked={rangeCheckValue.lora}
                        onChange={() => {
                          if (!runningStatus) {
                            handleRangeCheckbox('lora');
                          }
                        }}
                        disabled={runningStatus}
                      />
                    </div>
                  </div>
                )
              )}
              {fineTuningType === 2 && (
                <>
                  <Advanced
                    onClick={onClickConfigUpload}
                    list={fineTuningData?.model_config_file_list ?? []}
                    disabled={
                      fineTuningStatus !== 'stop' && fineTuningStatus !== 'done'
                    }
                    onClickDelete={onDeleteConfigData}
                    git={fineTuningData?.huggingface_git}
                    t={t}
                  />
                </>
              )}
            </div>
          </div>
          {runningStatus && (
            <InstanceSetting
              infoData={
                fineTuningData?.resource_info
                  ? fineTuningData?.resource_info
                  : {}
              }
            />
          )}
        </div>
        <div className={cx('right')}>
          <FineTuningGraph
            fineTuningType={fineTuningType}
            data={graphData}
            fineStatus={fineStatus}
            fineTuningData={fineTuningData}
            progressData={progressData}
          />
        </div>
      </div>
    </div>
  );
});

export default FineTuning;
