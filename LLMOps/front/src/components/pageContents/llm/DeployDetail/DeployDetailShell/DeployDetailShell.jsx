import { useEffect, useState } from 'react';

import { Loading } from '@jonathan/ui-react';

import EmptyBox from '@src/components/molecules/EmptyBox';
import Tab from '@src/components/molecules/Tab';
import PlaygroundFrame from '@src/components/pageContents/llm/PlaygroundContent/PlaygroundFrame';

import DeployDetailHeader from '../DeployDetailHeader';

import classNames from 'classnames/bind';
import style from './DeployDetailShell.module.scss';

const cx = classNames.bind(style);

// 단일 배포 헤더(PlaygroundHeader > Message)와 같은 규약의 상태 연동 메시지.
//   주황=진행 중, 파랑=정상 실행, 빨강=사용자 조치 필요. 색 값도 단일과 동일하게 맞춘다.
//   단일은 RAG/프롬프트 조건까지 보지만 이중엔 그 개념이 없어 모델 구성 여부만 본다.
const calStatusMessage = (deployment) => {
  if (!deployment) return null;
  const { overallStatus, components } = deployment;

  if (['installing', 'pending'].includes(overallStatus))
    return { message: '배포를 설정하고 있습니다.', color: '#FF7A00' };
  if (overallStatus === 'running')
    return { message: '실행 중입니다.', color: '#2D76F8' };
  if ((components || []).some((component) => !component.modelId))
    return { message: '모델을 선택해 주세요.', color: '#FA4E57' };
  return { message: '배포를 시작해 주세요.', color: '#FA4E57' };
};

export const DeployDetailSection = ({ title, badge, children }) => (
  <PlaygroundFrame>
    {(title || badge) && (
      <div className={cx('section-head')}>
        {title && <h3 className={cx('section-title')}>{title}</h3>}
        {badge}
      </div>
    )}
    {children}
  </PlaygroundFrame>
);

const DeployDetailShell = ({
  deployment,
  loading = false,
  error = '',
  title,
  header = null,
  onBack,
  actions = null,
  sections,
  monitorDisabled = false,
}) => {
  const [tab, setTab] = useState('INFO');
  const tabOptions = [
    { label: 'information.label', value: 'INFO' },
    { label: 'Model', value: 'MODEL' },
    { label: 'Monitoring', value: 'MONITOR', disable: monitorDisabled },
  ];

  useEffect(() => {
    if (tab === 'MONITOR' && monitorDisabled) setTab('INFO');
  }, [tab, monitorDisabled]);

  const statusMessage = calStatusMessage(deployment);

  const shellHeader =
    header ||
    (deployment || error ? (
      <DeployDetailHeader
        title={title || deployment?.info?.name || '배포 상세'}
        onBack={onBack}
        right={
          <div className={cx('header-actions')}>
            {statusMessage && (
              <span
                className={cx('status-message')}
                style={{ color: statusMessage.color }}
              >
                {statusMessage.message}
              </span>
            )}
            {actions}
          </div>
        }
      />
    ) : null);

  if (loading) {
    return (
      <div className={cx('shell')}>
        {shellHeader}
        <div className={cx('state')}>
          <Loading />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cx('shell')}>
        {shellHeader}
        <DeployDetailSection>
          <EmptyBox isBox customStyle={{ height: '180px' }} text={error} />
        </DeployDetailSection>
      </div>
    );
  }

  return (
    <div className={cx('shell')} data-deploy-mode={deployment?.mode}>
      {shellHeader}
      <div className={cx('tab-bar')}>
        <Tab
          type='c'
          sidePaddingNone
          option={tabOptions}
          select={{ value: tab }}
          tabHandler={({ value }) => setTab(value)}
        />
      </div>
      <div className={cx('section-frame')}>{sections?.[tab] || null}</div>
    </div>
  );
};

export default DeployDetailShell;
