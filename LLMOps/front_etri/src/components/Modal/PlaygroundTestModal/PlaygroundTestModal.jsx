import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector, shallowEqual } from 'react-redux';
import { toast } from 'react-toastify';

import { ButtonV2 } from '@tango/ui-react';

import dayjs from 'dayjs';

import { getPlaygroundTestLogDownload } from '@src/apis/llm/playground';
import { closeModal } from '@src/store/modules/modal';

import NewStyleModalFrame from '../NewStyleModalFrame';
import SubTab from './SubTab';
import SystemLog from './SystemLog';
import TestComponent from './TestComponent';
import TestRecord from './TestRecord';

// CSS module
import classNames from 'classnames/bind';
import style from './PlaygroundTestModal.module.scss';

import IconSwitch from '@src/static/images/icon/switch-icon.svg';

const cx = classNames.bind(style);

const testLabelObj = {
  true: '실시간 질문 입력으로 전환',
  false: '사전 데이터셋 선택으로 전환',
};

const subTabOptions = [
  {
    label: '테스트',
    value: 0,
  },
  {
    label: '테스트 기록',
    value: 1,
  },
  {
    label: '시스템 로그',
    value: 2,
  },
];

const handleTestdownloadLog = async (playgroundId) => {
  const { data, message, status } = await getPlaygroundTestLogDownload(
    playgroundId,
  );

  if (status === 200) {
    const blob = new Blob([data], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `[${playgroundId}-LOG] ${dayjs().format(
      'YYYYMMDD hhmmss',
    )}.csv`;
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } else {
    toast.error(message);
  }
};

const calRightSubTabComponent = (
  playgroundId,
  testLabelObj,
  tab,
  integratedTestValue,
  setIntegratedTestValue,
  t,
) => {
  if (tab === 0)
    return (
      <ButtonV2
        colorType='clear'
        label={testLabelObj[integratedTestValue]}
        icon={IconSwitch}
        onClick={() => setIntegratedTestValue((prev) => !prev)}
      />
    );

  if (tab === 2) {
    return (
      <ButtonV2
        colorType='skyblue'
        label={'테스트 기록 로그 다운로드'}
        onClick={() => handleTestdownloadLog(playgroundId)}
      />
    );
  }
};

const calBodycontent = (tab, integratedTestValue, playgroundId, isExternal) => {
  if (tab === 0) {
    return (
      <TestComponent
        integratedTestValue={integratedTestValue}
        playgroundId={playgroundId}
        isExternal={isExternal}
      />
    );
  }
  if (tab === 1) return <TestRecord playgroundId={playgroundId} />;
  if (tab === 2) return <SystemLog playgroundId={playgroundId} />;
  return <></>;
};

export default function PlaygroundTestModal({ type, data }) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { playgroundId } = data;

  const trainingType = useSelector(
    (state) => state.llmPlayground?.model?.training_type,
    shallowEqual,
  );
  const isExternal = trainingType === 'external';

  const title = t('Test');
  const submit = useMemo(() => {
    return {
      text: t('close.label'),
      func: () => {
        dispatch(closeModal('PLAYGROUND_TEST_MODAL'));
      },
    };
  }, [t]);

  const [tab, setTab] = useState(0);

  const [integratedTestValue, setIntegratedTestValue] = useState(true);
  const subTabRightComponent = calRightSubTabComponent(
    playgroundId,
    testLabelObj,
    tab,
    integratedTestValue,
    setIntegratedTestValue,
    t,
  );
  const bodyComponent = calBodycontent(tab, integratedTestValue, playgroundId, isExternal);

  return (
    <NewStyleModalFrame
      submit={submit}
      type={type}
      validate={true}
      isResize={true}
      isMinimize={true}
      title={title}
      customStyle={{ width: '664px' }}
    >
      <div className={cx('subtab-cont')}>
        <SubTab
          tabOptions={subTabOptions}
          tabValue={tab}
          onClick={(value) => setTab(value)}
        />
        {subTabRightComponent}
      </div>
      <div className={cx('switch-cont')}>{bodyComponent}</div>
    </NewStyleModalFrame>
  );
}
