import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useRouteMatch } from 'react-router-dom';

import DashboardGraph from '@src/components/pageContents/llm/DashboardContent/DashboardGraph';
import DashboardInfo from '@src/components/pageContents/llm/DashboardContent/DashboardInfo';
import DashboardInstance from '@src/components/pageContents/llm/DashboardContent/DashboardInstance';
import DashboardProject from '@src/components/pageContents/llm/DashboardContent/DashboardProject';
import DashboardrecentRecord from '@src/components/pageContents/llm/DashboardContent/DashboardrecentRecord';
import DashboardStorage from '@src/components/pageContents/llm/DashboardContent/DashboardStorage';
import DashboardWorkspaceResource from '@src/components/pageContents/llm/DashboardContent/DashboardWorkspaceResource';
import { platformList } from '@src/components/pageContents/llm/DashboardContent/DashboardWorkspaceResource/DashboardWorkspaceResource';

import useDashboardSSe from './hooks/useDashboardSSe';

// CSS Module
import classNames from 'classnames/bind';
import style from './DashboardPage.module.scss';

const cx = classNames.bind(style);

const DashboardPage = () => {
  const { t } = useTranslation();
  const match = useRouteMatch();
  const { params } = match;

  const workspaceId = params.id;

  const [
    info,
    history,
    totalCount,
    usage,
    mainStorage,
    dataStorage,
    isManager,
    instanceUsed,
  ] = useDashboardSSe(workspaceId);

  const { description, name, owner, period, status, users } = info;
  const userParagraph = useMemo(() => {
    return users.join(', ');
  }, [users]);

  const { gpu, cpu, ram, platform_usage } = usage;
  const { 'a-llm': allm, flightbase } = platform_usage;

  const { total: gpuTotal, used: gpuUsed, usage: gpuPercent } = gpu;
  const { total: cpuTotal, used: cpuUsed, usage: cpuPercent } = cpu;
  const { total: ramTotal, used: ramUsed, usage: ramPercent } = ram;

  const { cpu: allmCpu, gpu: allmGpu, ram: allmRam } = allm;
  const { cpu: fbCpu, gpu: fbGpu, ram: fbRam } = flightbase;

  const {
    datasets: datasetTotal,
    models: modelTotal,
    rags: ragTotal,
    prompts: promptTotal,
    playgrounds: playgroundTotal,
  } = totalCount;

  const title = useMemo(() => {
    return {
      1: t('recentTasksHistory.label'),
      2: t('workspaceResourceCondition.label'),
      3: t('projectResourceManage.label'),
      4: (
        <div className={cx('title-cont')}>
          <span className={cx('title-txt')}>
            {t('dashboard.storageUsage.label')}
          </span>
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
        </div>
      ),
      6: t('dashboard.instanceUsage.label'),
      7: t('dailyWorkspaceResourceUsage.label'),
    };
  }, [t]);

  return (
    <div className={cx('dashboard-cont')}>
      <div className={cx('first')}>
        <DashboardInfo
          name={name}
          description={description}
          owner={owner}
          period={period}
          status={status}
          userParagraph={userParagraph}
          isManager={isManager}
        />
        <DashboardrecentRecord title={title[1]} historyList={history} />
      </div>
      <div className={cx('second')}>
        <DashboardWorkspaceResource
          title={title[2]}
          gpuTotal={gpuTotal}
          gpuUsed={gpuUsed}
          gpuPercent={gpuPercent}
          cpuTotal={cpuTotal}
          cpuUsed={cpuUsed}
          cpuPercent={cpuPercent}
          ramTotal={ramTotal}
          ramUsed={ramUsed}
          ramPercent={ramPercent}
          allmCpu={allmCpu}
          allmGpu={allmGpu}
          allmRam={allmRam}
          fbCpu={fbCpu}
          fbGpu={fbGpu}
          fbRam={fbRam}
          datasetTotal={datasetTotal}
          modelTotal={modelTotal}
          ragTotal={ragTotal}
          promptTotal={promptTotal}
          playgroundTotal={playgroundTotal}
          isManager={isManager}
        />
        <DashboardStorage
          type='allm'
          title={title[4]}
          mainStorage={mainStorage}
          dataStorage={dataStorage}
        />
      </div>
      <div className={cx('third')}>
        <DashboardProject title={title[3]} />
        <DashboardInstance title={title[6]} instances_used={instanceUsed} />
      </div>
      <div className={cx('fourth')}>
        <DashboardGraph title={title[7]} workspaceId={workspaceId} />
      </div>
    </div>
  );
};

export default DashboardPage;
