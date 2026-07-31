// i18n

// Atom
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import {
  InputNumber,
  Radio as TangoRadio,
  Selectbox,
} from '@tango/ui-react';

// Type
import { TRAINING_TOOL_TYPE } from '@src/types';

import Dropdown from '@src/components/atoms/Dropdown';
// Components
import Radio from '@src/components/atoms/input/Radio';
import ModalFrame from '@src/components/Modal/ModalFrame';
import NewStyleModalFrame from '@src/components/Modal/NewStyleModalFrame';
import GpuNodeSelectBox from '@src/components/molecules/GpuNodeSelectBox';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

// CSS module
import classNames from 'classnames/bind';
import style from './ToolGpuAllocateModalContent.module.scss';

const cx = classNames.bind(style);

const ToolGpuAllocateModalContent = ({
  type,
  modalData,
  validate,
  message,
  messageType,
  inputValue,
  onChangeInputValue,
  handleGpuClusterOption,
  gpuClusterSelectedOption,
  maxValue,
  onSubmit,
  dockerImageList,
  selectedImage,
  selectImageHandler,
  gpuClusterList,
  handleSelectedGpuCluster,
  gpuClusterType,
  handleGpuClusterType,
  selectedGpuClusterType,
  podGpuGcd,
  gpuUsingError,
  instanceType,
  instanceInfo,
  datasetList,
  selectedDataset,
  handleDataset,
  footerMessage,
}) => {
  const { t } = useTranslation();
  const { submit, cancel, toolType, toolName } = modalData;
  const newSubmit = {
    text: submit.text,
    func: async () => {
      const res = await onSubmit(submit.func);
      return res;
    },
  };

  const gpuClusterOption = [
    {
      label: 'autoSetting',
      value: 1,
      desc: t('autoSetting.desc'),
      descStatus: true,
    },
    {
      label: 'manualSetting',
      value: 0,
      desc: t('manualSetting.desc'),
      descStatus: false,
    },
  ];

  const Message = ({ message }) => {
    // 줄 바꿈 문자를 <br> 태그로 변환
    const formattedMessage = message.replace(/\n/g, '<br>');

    return (
      <div
        className='message'
        dangerouslySetInnerHTML={{ __html: formattedMessage }}
      />
    );
  };
  const title = useMemo(() => {
    return (
      <div className={cx('title')}>
        <span className={cx('instance')}>
          {instanceType === 'GPU'
            ? t('gpuAllocation.label')
            : t('cpuAllocation.label')}
        </span>
        <img
          className={cx('tool-icon')}
          src={`/images/icon/ic-${TRAINING_TOOL_TYPE[toolType]?.type}.svg`}
          alt={`${TRAINING_TOOL_TYPE[toolType]?.type} icon`}
        />
        <span className={cx('tool-label')}>
          {toolName ? toolName : TRAINING_TOOL_TYPE[toolType]?.label}
        </span>
      </div>
    );
  }, [instanceType, t, toolName, toolType]);

  return (
    <NewStyleModalFrame
      title={title}
      type={type}
      isResize={true}
      isMinimize={true}
      validate={validate}
      submit={newSubmit}
      cancel={cancel}
      footerMessage={footerMessage}
    >
      <div className={cx('contents')}>
        <div className={cx('first-row')}>
          <div className={cx('row', 'row-content')}>
            <InputBoxWithLabel
              labelText={t('dockerImage.label')}
              labelSize='large'
              disableErrorMsg
              style={{ marginBottom: '32px' }}
            >
              <Dropdown
                size='medium'
                placeholder={t('dockerImage.placeholder')}
                list={dockerImageList}
                value={selectedImage}
                handleOptionClick={(v) => {
                  selectImageHandler(v);
                }}
                style={{ height: '36px' }}
              />
            </InputBoxWithLabel>
          </div>
        </div>
        <div className={cx('row', instanceType === 'GPU' && 'grid')}>
          <InputBoxWithLabel
            labelText={t('dataset.label')}
            labelSize='large'
            disableErrorMsg
            style={{ marginBottom: '16px' }}
          >
            <Dropdown
              size='medium'
              placeholder={t('graphDataset.message')}
              list={datasetList}
              value={selectedDataset}
              handleOptionClick={handleDataset}
              style={{ height: '36px' }}
            />
          </InputBoxWithLabel>
          {instanceType === 'GPU' && (
            <div className={cx('row', 'row-content')}>
              <InputBoxWithLabel
                labelText={t('gpuAllocationNumber.label')}
                labelSize='large'
                disableErrorMsg
                labelDescText={`${
                  instanceInfo.resource_name.length < 18
                    ? instanceInfo.resource_name
                    : instanceInfo.resource_name.slice(0, 15) + '...'
                }`}
                labelDescStyle={{
                  color: 'rgba(116, 116, 116, 1)',
                  marginLeft: '8px',
                  fontSize: '14px',
                  fontFamily: 'SpoqaM',
                }}
              >
                <InputNumber
                  name='workspaceInput'
                  placeholder={`${t('currentAvailableCount')} : ${maxValue}`}
                  min={0}
                  max={maxValue}
                  value={inputValue}
                  onChange={(e) => {
                    let inputValue = e.value;
                    if (e.value > maxValue) {
                      inputValue = maxValue;
                    }
                    onChangeInputValue(inputValue);
                  }}
                />
              </InputBoxWithLabel>
            </div>
          )}
        </div>

        {instanceType === 'GPU' && (
          <div className={cx('gpu-notice')}>
            <div className={cx('warning')}>
              <span>{t('gpuAllocate.warning.desc').split('\n')[0]}</span>
              <span>{t('gpuAllocate.warning.desc').split('\n')[1]}</span>
            </div>
          </div>
        )}

        <div className={cx(`${inputValue > 1 ? 'gpu-rows' : 'no-content'}`)}>
          {inputValue > 1 && (
            <div className={cx('row', 'option')}>
              <InputBoxWithLabel
                labelText={t('gpuClusterOption')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  options={gpuClusterOption}
                  customStyle={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                  }}
                  onChange={(e) =>
                    handleGpuClusterOption(e.currentTarget.value)
                  }
                  value={gpuClusterSelectedOption}
                  isShowAllDesc={false}
                  isLabelColor={true}
                />
              </InputBoxWithLabel>
            </div>
          )}

          {/* * GPU 클러스터 선택 리스트 GPU 할당 2개 이상일때 보여줘야한다. */}
          {inputValue > 1 && gpuClusterSelectedOption === 0 && (
            <div className={cx('row')}>
              <GpuNodeSelectBox
                gpuClusterList={gpuClusterList}
                handleSelectedGpuCluster={handleSelectedGpuCluster}
                podGpuGcd={podGpuGcd}
                isShowPodGpuGcd={true}
                gpuUsingError={gpuUsingError}
              />
            </div>
          )}

          {inputValue > 1 && gpuClusterType.length ? (
            <div className={cx('row')}>
              <InputBoxWithLabel
                labelText={t('gpuClusterCategory.label')}
                labelSize='large'
                disableErrorMsg
              >
                <Radio
                  options={gpuClusterType}
                  customStyle={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                  }}
                  onChange={(e) => handleGpuClusterType(e.currentTarget.value)}
                  value={selectedGpuClusterType}
                  isLabelColor={true}
                />
              </InputBoxWithLabel>
            </div>
          ) : (
            <div></div>
          )}
        </div>
      </div>
    </NewStyleModalFrame>
  );
};

export default ToolGpuAllocateModalContent;
