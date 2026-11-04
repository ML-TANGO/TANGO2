import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { toast } from 'react-toastify';

import { InputNumber } from '@jonathan/ui-react';

import Radio from '@src/components/atoms/input/Radio';
import InputBoxWithLabel from '@src/components/molecules/InputBoxWithLabel';

import { putPipelineRetrain } from '@src/apis/flightbase/pipeline';
import { closeModal } from '@src/store/modules/modal';
import { handleOpenPopup } from '@src/store/modules/popupState';
import { STATUS_SUCCESS } from '@src/network';

import NewStyleModalFrame from '../NewStyleModalFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './AIPipeLineDeploySettingModal.module.scss';

const cx = classNames.bind(style);

const title = '재학습 및 무중단 배포 설정';

const accessOpions = [
  { label: '데이터량', value: 'data' },
  { label: '시간', value: 'time' },
];

const reStartOptions = [
  { label: 'TB', value: 'TB', unit: 'TB' },
  { label: 'GB', value: 'GB', unit: 'GB' },
  { label: 'MB', value: 'MB', unit: 'MB' },
  { label: 'KB', value: 'KB', unit: 'KB' },
];

const timeReStartOptions = [
  { label: '시간당', value: 'hours', unit: '시간' },
  { label: '분당', value: 'minutes', unit: '분' },
];

const calReStartOptions = (defaultValue) => {
  if (defaultValue === 'data') return reStartOptions;
  return timeReStartOptions;
};

const calMessage = (reStartInputValue) => {
  if (!reStartInputValue) return '재학습 시작 조건을 입력하세요.';
  return '조건에 따라 재학습이 수행된 뒤 무중단 배포됩니다.';
};

const handleInput = (type, setDeployState, value) => {
  setDeployState((prev) => {
    const newState = { ...prev, [type]: value };

    if (type === 'defaultValue') {
      const restartOptions = calReStartOptions(value);
      newState.reStartRadioValue = restartOptions[0].value;
    }

    return newState;
  });
};

export default function AIPipeLineDeploySettingModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { pipelineId, retraining_config, handleResetData } = data;
  const {
    type: initialType,
    unit: initialUnit,
    value: initialValue,
  } = retraining_config;

  const [deployState, setDeployState] = useState({
    defaultValue: initialType ?? 'data',
    reStartRadioValue: initialUnit ?? 'TB',
    reStartInputValue: initialValue,
  });
  const { defaultValue, reStartRadioValue, reStartInputValue } = deployState;

  const restartOptions = calReStartOptions(defaultValue);
  const selectedRestartOptions = restartOptions.find(
    (el) => el.value === reStartRadioValue,
  );
  const unitLabel = selectedRestartOptions?.unit;
  const footerMessage = calMessage(reStartInputValue);

  const cancel = useMemo(() => {
    return {
      text: t('cancel.label'),
      func: () => dispatch(closeModal(type)),
    };
  }, [dispatch, t, type]);

  const submit = {
    text: t('set.label'),
    func: async () => {
      dispatch(
        handleOpenPopup({
          type: 'delete',
          popupTitle: '재학습 및 무중단 배포 설정 적용 안내',
          popupContents:
            '현재 배포가 실행 중 입니다.\n설정한 재학습 및 무중단 배포 옵션은 현재 라운드에는\n적용되지 않으며, 다음 라운드부터 반영됩니다.\n\n설정을 계속 진행하시겠습니까?',
          cancelBtnLabel: t('cancel.label'),
          submitBtnLabel: t('job.running'),
          handleSubmit: async () => {
            const { status, message } = await putPipelineRetrain({
              pipeline_id: pipelineId,
              retraining_type: defaultValue,
              retraining_unit: reStartRadioValue,
              retraining_value: reStartInputValue,
            });
            if (status !== STATUS_SUCCESS) {
              toast.error(message);
            } else {
              await handleResetData();
              dispatch(closeModal(type));
            }
          },
        }),
      );
    },
  };

  return (
    <NewStyleModalFrame
      title={title}
      type={type}
      cancel={cancel}
      submit={submit}
      validate={!!reStartInputValue}
      isResize={true}
      isMinimize={true}
      footerMessage={footerMessage}
    >
      <InputBoxWithLabel
        labelText={t('accessType.label')}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '32px' }}
      >
        <Radio
          name='default-setting-input'
          value={defaultValue}
          options={accessOpions}
          onChange={(e) =>
            handleInput('defaultValue', setDeployState, e.target.value)
          }
          isLabelColor
        />
      </InputBoxWithLabel>
      <div className={cx('border')} />
      <InputBoxWithLabel
        labelText={'재학습 시작 조건'}
        labelSize='large'
        optionalSize='medium'
        disableErrorMsg
        style={{ marginBottom: '24px' }}
      >
        <Radio
          name='reStart-input'
          value={reStartRadioValue}
          options={restartOptions}
          onChange={(e) =>
            handleInput('reStartRadioValue', setDeployState, e.target.value)
          }
          isLabelColor
        />
      </InputBoxWithLabel>
      <div className={cx('restart-input')}>
        <InputNumber
          placeholder='재학습 시작 조건으로 데이터셋의 크기를 입력하세요.'
          customSize={{ padding: '11px 42px 11px 12px' }}
          valueAlign={'left'}
          value={reStartInputValue}
          onChange={(e) =>
            handleInput('reStartInputValue', setDeployState, +e.target.value)
          }
          max={100000000}
          disableIcon
        />
        <span className={cx('unit-txt')}>{unitLabel}</span>
      </div>
    </NewStyleModalFrame>
  );
}
