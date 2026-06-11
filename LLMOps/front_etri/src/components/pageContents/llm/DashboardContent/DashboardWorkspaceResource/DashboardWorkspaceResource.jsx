import React from 'react';
import { useTranslation } from 'react-i18next';

import { ButtonV2 } from '@tango/ui-react';

import DatasetIcon from '@src/components/icon/DatasetIcon';
import ModelIcon from '@src/components/icon/ModelIcon';
import PlaygroundIcon from '@src/components/icon/PlaygroundIcon';
import PromptIcon from '@src/components/icon/PromptIcon';
import RagIcon from '@src/components/icon/RagIcon';
import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';
import ListStack from '@src/components/molecules/ListStack';

import DashboardFrame from '../DashboardFrame';

// CSS Module
import classNames from 'classnames/bind';
import style from './DashboardWorkspaceResource.module.scss';

const cx = classNames.bind(style);

export const platformList = [
  { label: 'GenAI Platform', backgroundColor: '#2D76F8' },
  // { label: 'FLIGHTBASE', backgroundColor: '#DBDBDB' },
];

const ResourceStack = React.memo(
  ({ label, stackList, totalValue, total, used, percent }) => {
    const { t } = useTranslation();
    return (
      <div className={cx('stack-wrapper')}>
        <span className={cx('label')}>{label}</span>
        <div className={cx('stack-cont')}>
          <ListStack
            isTooltip={true}
            stackList={stackList}
            totalValue={totalValue}
            tooltipDirection='bottom'
          />
          <span>{Number.isNaN(percent) ? 0 : percent} %</span>
        </div>
        <div className={cx('footer-cont')}>
          <div className={cx('used-cont')}>
            <span className={cx('label')}>{t('used.label')}</span>
            <span className={cx('value')}>{used}</span>
          </div>
          <div className={cx('used-cont')}>
            <span className={cx('label')}>{t('total.label')}</span>
            <span className={cx('value')}>{total}</span>
          </div>
        </div>
      </div>
    );
  },
);

export default function DashboardWorkspaceResource({
  title,
  gpuTotal,
  gpuUsed,
  gpuPercent,
  cpuTotal,
  cpuUsed,
  cpuPercent,
  ramTotal,
  ramUsed,
  ramPercent,
  allmCpu,
  allmGpu,
  allmRam,
  fbCpu,
  fbGpu,
  fbRam,
  datasetTotal,
  modelTotal,
  ragTotal,
  promptTotal,
  playgroundTotal,
  isManager,
}) {
  const { t } = useTranslation();
  const footerList = [
    {
      label: t('dataset'),
      value: datasetTotal,
      icon: <DatasetIcon width={16} height={16} color='#747474' />,
    },
    {
      label: t('Training'),
      value: modelTotal,
      icon: <ModelIcon width={16} height={16} color='#747474' />,
    },
    {
      label: 'RAG',
      value: ragTotal,
      icon: <RagIcon width={16} height={16} color='#747474' />,
    },
    {
      label: t('prompt.label'),
      value: promptTotal,
      icon: <PromptIcon width={16} height={16} color='#747474' />,
    },
    {
      label: t('playground.label'),
      value: playgroundTotal,
      icon: <PlaygroundIcon width={16} height={16} color='#747474' />,
    },
  ];

  return (
    <DashboardFrame title={title} style={{ height: '560px' }}>
      <div className={cx('platform-cont')}>
        {platformList.map((info) => {
          const { backgroundColor, label } = info;
          return (
            <div className={cx('item')} key={label}>
              <div className={cx('dot')} style={{ backgroundColor }}></div>
              <span className={cx('label')}>{label}</span>
            </div>
          );
        })}
      </div>
      <div className={cx('resource-stack-cont')}>
        <ResourceStack
          key={'gpu'}
          label={t('dashboard.gpuUsage.label')}
          stackList={[
            {
              color: '#DBDBDB',
              value: fbGpu,
              tooltipContent: (
                <DarkTooltip
                  direction='bottom'
                  content={
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                        fontFamily: 'SpoqaB',
                        fontSize: '10px',
                      }}
                      // className={cx('wks-bar')}
                    >
                      <span>FLIGHTBASE</span>
                      <span>{fbGpu} EA</span>
                    </div>
                  }
                />
              ),
            },
            {
              color: '#2D76F8',
              value: allmGpu,
              tooltipContent: (
                <DarkTooltip
                  direction='bottom'
                  content={
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                        fontFamily: 'SpoqaB',
                        fontSize: '10px',
                      }}
                    >
                      <span>GenAI Platform</span>
                      <span>{allmGpu} EA</span>
                    </div>
                  }
                />
              ),
            },
          ]}
          totalValue={gpuTotal}
          total={`${gpuTotal} EA`}
          used={`${gpuUsed} EA`}
          percent={Math.floor(gpuPercent)}
        />
        <ResourceStack
          key={'cpu'}
          label={t('dashboard.cpuUsage.label')}
          stackList={[
            {
              color: '#2D76F8',
              value: allmCpu,
              tooltipContent: (
                <DarkTooltip
                  direction='bottom'
                  content={
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                        fontFamily: 'SpoqaB',
                        fontSize: '10px',
                      }}
                    >
                      <span>GenAI Platform</span>
                      <span>{allmCpu} Cores</span>
                    </div>
                  }
                />
              ),
            },
            {
              color: '#DBDBDB',
              value: fbCpu,
              tooltipContent: (
                <DarkTooltip
                  direction='bottom'
                  content={
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                        fontFamily: 'SpoqaB',
                        fontSize: '10px',
                      }}
                    >
                      <span>FLIGHTBASE</span>
                      <span>{fbCpu} Cores</span>
                    </div>
                  }
                />
              ),
            },
          ]}
          totalValue={cpuTotal}
          total={`${cpuTotal} Cores`}
          used={`${cpuUsed} Cores`}
          percent={Math.floor(cpuPercent)}
        />
        <ResourceStack
          key={'ram'}
          label={t('dashboard.ramUsage.label')}
          stackList={[
            {
              color: '#2D76F8',
              value: allmRam,
              tooltipContent: (
                <DarkTooltip
                  direction='bottom'
                  content={
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                        fontFamily: 'SpoqaB',
                        fontSize: '10px',
                      }}
                    >
                      <span>GenAI Platform</span>
                      <span>{allmRam} GB</span>
                    </div>
                  }
                />
              ),
            },
            {
              color: '#DBDBDB',
              value: fbRam,
              tooltipContent: (
                <DarkTooltip
                  direction='bottom'
                  content={
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                        fontFamily: 'SpoqaB',
                        fontSize: '10px',
                      }}
                    >
                      <span>FLIGHTBASE</span>
                      <span>{fbRam} GB</span>
                    </div>
                  }
                />
              ),
            },
          ]}
          totalValue={ramTotal}
          total={`${ramTotal} GB`}
          used={`${ramUsed} GB`}
          percent={Math.floor(ramPercent)}
        />
      </div>
      <div className={cx('btn-cont')}>
        {isManager && (
          <ButtonV2
            label={t('workspaceResourceManagement.label')}
            colorType='skyblue'
            disabled
          />
        )}
      </div>
      <div className={cx('border')} />
      <div className={cx('resource-footer-cont')}>
        {footerList.map((info, idx) => {
          const { label, value, icon } = info;
          return (
            <div className={cx('content-cont')} key={idx}>
              <div className={cx('top')}>
                {icon}
                <span className={cx('label-txt')}>{label}</span>
              </div>
              <span className={cx('value-txt')}>{value}</span>
            </div>
          );
        })}
      </div>
    </DashboardFrame>
  );
}
