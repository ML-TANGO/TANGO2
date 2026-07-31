// Utils
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import { convertLocalTime } from '@src/datetimeUtils';

import Status from '@src/components/atoms/Status';
import History from '@src/components/organisms/Dashboard/History';
import DashboardStorage from '@src/components/pageContents/llm/DashboardContent/DashboardStorage';

// Components

import { closeModal, openModal } from '@src/store/modules/modal';

import FlightbaseDashboardWorkspaceResource, {
  FbLLmplatformList,
} from './FlightbaseDashboardWorkspaceResource';
import InstanceList from './InstanceList';
import JobList from './JobList';
import ProjectStack from './ProjectStack';
import TotalInstance from './TotalInstance';
import useDashboardSse from './useDashboardSse';
import WorkSpaceResourceChart from './WorkSpaceResourceChart';

import classNames from 'classnames/bind';
// CSS module
import style from './UserHomeContent.module.scss';

const cx = classNames.bind(style);

// 최근 학습 현황 표시 여부
const IS_HIDE_JOB = import.meta.env.VITE_REACT_APP_IS_HIDE_JOB === 'true';
const IS_HIDE_HPS = import.meta.env.VITE_REACT_APP_IS_HIDE_HPS === 'true';
// 드론 챌린지 모드 여부
const IS_DNADRONECHALLENGE =
  import.meta.env.VITE_REACT_APP_SERVICE_LOGO === 'DNA+DRONE' &&
  import.meta.env.VITE_REACT_APP_IS_CHALLENGE === 'true';

const DEFAULT_MAIN_STORAGE = {
  total: '-',
  avail: '-',
  usage: '-',
  used: '-',
  allm_list: [],
  allm_usage: 0,
  fb_usage: 0,
};

const DEFAULT_DATA_STORAGE = {
  total: '-',
  avail: '-',
  usage: '-',
  used: '-',
  dataset_list: [],
};

function UserHomeContent({
  totalCount,
  directLink,
  trainingItems,
  moveJobList,
  history,
  gpuUsage,
  timeline,
  info,
  serverError,
  openWsDescEditModal,
  openGPUSettingEditModal,
  storageData,
  isManager,
  workspaceResourceUsage,
  totalInstanceCondition,
  projectInstanceInfo,
  dailyResourceUsage,
  mainStorageInfo,
  dataStorageInfo,
  workspaceId,
}) {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { dashboardData } = useDashboardSse({ workspaceId });
  const { usage, storage, total_count } = dashboardData;

  const { gpu, cpu, ram, platform_usage } = usage;
  const { 'a-llm': allm, flightbase } = platform_usage;

  const { total: gpuTotal, used: gpuUsed, usage: gpuPercent } = gpu;
  const { total: cpuTotal, used: cpuUsed, usage: cpuPercent } = cpu;
  const { total: ramTotal, used: ramUsed, usage: ramPercent } = ram;

  const { cpu: allmCpu, gpu: allmGpu, ram: allmRam } = allm;
  const { cpu: fbCpu, gpu: fbGpu, ram: fbRam } = flightbase;

  const { data_storage: dataStorage, main_storage: mainStorage } = storage;

  const isDailyResourceUsageValid =
    dailyResourceUsage.gpu &&
    dailyResourceUsage.storage_data &&
    dailyResourceUsage.storage_main;

  const title = {
    1: t('recentTasksHistory.label'),
    2: t('workspaceResourceCondition.label'),
    3: t('projectResourceManage.label'),
    4: (
      <div className={cx('title-cont')}>
        <span className={cx('title-txt')}>
          {t('dashboard.storageUsage.label')}
        </span>
        <div className={cx('platform-cont')}>
          {FbLLmplatformList.map((info) => {
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

  const historyList = history.map((list, index) => (
    <History key={index} data={list} type='user' />
  ));

  const openWorkspaceResourceModal = () => {
    dispatch(
      openModal({
        modalType: 'EDIT_WORKSPACE_RESOURCE',
        modalData: {
          submit: {
            text: 'complete',
          },
          cancel: {
            text: 'close.label',
            func: () => dispatch(closeModal('EDIT_WORKSPACE_RESOURCE')),
          },
          apply: {
            text: 'apply',
          },
          workspaceId,
        },
      }),
    );
  };

  return (
    <div className={cx('dashboard')}>
      <div className={cx('content')}>
        <div className={cx('first-row')}>
          <div className={cx('workspace-info')}>
            <div className={cx('detail')}>
              <div className={cx('info')}>
                <div className={cx('title-div')}>
                  <Status status={info?.status?.toLowerCase()} />
                  <div className={cx('workspace-name')}>
                    {t('informationOf.label', { name: info.name || '-' })}
                  </div>
                  {isManager && (
                    <button
                      className={cx('edit-btn')}
                      onClick={openWsDescEditModal}
                      title={t('edit.label')}
                    >
                      <img
                        src='/images/icon/00-ic-basic-pen.svg'
                        alt='desc edit btn'
                        width={20}
                        height={20}
                      />
                    </button>
                  )}
                </div>
                <div className={cx('workspace-description')}>
                  <div className={cx('description')}>
                    {info.description || '-'}
                  </div>
                </div>
                <div className={cx('meta')}>
                  <label className={cx('text-label')}>
                    {t('period.label')}
                  </label>
                  <span>
                    {info.start_datetime
                      ? `${convertLocalTime(
                          info.start_datetime,
                        )} ~ ${convertLocalTime(info.end_datetime)}`
                      : '-'}
                  </span>
                </div>
                <div className={cx('meta')}>
                  <div className={cx('user')}>
                    <label className={cx('text-label')}>
                      {t('users.label')}
                    </label>
                    <div className={cx('owner')}>
                      <img
                        src='/images/icon/00-ic-gray-owner.svg'
                        width={20}
                        height={20}
                        alt='owenr'
                      />
                      <span>{info.owner || '-'}</span>
                    </div>
                    <div className={cx('member')}>
                      <img
                        src='/images/icon/00-ic-gray-member.svg'
                        alt='member'
                        width={20}
                        height={20}
                      />
                      <div className={cx('member-list')}>
                        {info.users.length > 0 && `${info.users.join(', ')}`}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className={cx('price')}>
                <div className={cx('header')}>Payment</div>
                <div className={cx('content')}>{t('nopay.desc')}</div>
              </div>
            </div>
            <div className={cx('recent-record')}>
              <div className={cx('history')}>
                <span className={cx('history-title')}>
                  {t('recentTasksHistory.label')}
                </span>
                {serverError ? (
                  <div className={cx('no-response')}>
                    {t('noResponse.message')}
                  </div>
                ) : history.length > 0 ? (
                  <>
                    <div className={cx('history-list', isManager && 'manager')}>
                      {historyList}
                    </div>
                  </>
                ) : (
                  <div className={cx('no-history')}>
                    {t('noRecentTasks.message')}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/** 워크스페이스 자원 사용 현황 */}
          <div className={cx('top-right-contents')}>
            <FlightbaseDashboardWorkspaceResource
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
              isManager={isManager}
              openWorkspaceResourceModal={openWorkspaceResourceModal}
              dockerTotal={total_count.images}
              datasetTotal={total_count.datasets}
              trainingsTotal={total_count.trainings}
              deploymentsTotal={total_count.deployments}
            />
          </div>
        </div>

        <div className={cx('second-row')}>
          {/** 프로젝트 별 작업 현황 */}
          {(!IS_HIDE_JOB || !IS_HIDE_HPS) && (
            <div className={cx('latest-job')}>
              <div className={cx('job-title')}>{t('projectJob.label')}</div>
              {serverError ? (
                <div className={cx('no-response')}>
                  {t('noResponse.message')}
                </div>
              ) : trainingItems.length > 0 ? (
                <JobList trainingItems={trainingItems} />
              ) : (
                <div className={cx('no-history')}>
                  {t('noLatestJob.message')}
                </div>
              )}
            </div>
          )}

          <div className={cx('storage-row')}>
            <DashboardStorage
              title={title[4]}
              mainStorage={mainStorage ?? DEFAULT_MAIN_STORAGE}
              dataStorage={dataStorage ?? DEFAULT_DATA_STORAGE}
              customStyle={{ borderRadius: '8px' }}
              type='fb'
            />
          </div>
        </div>

        <div className={cx('instance-row')}>
          {/** 프로젝트별 인스턴스 할당 현황 테이블 */}
          <div className={cx('project-instance-row')}>
            <InstanceList
              title={t('projectInstanceAllocation.label')}
              listData={projectInstanceInfo}
              toolTipIndex={1}
              columns={[
                {
                  label: t('projectName.label'),
                  selector: 'name',
                  headStyle: {
                    flex: '4',
                    boxSizing: 'border-box',
                    // paddingLeft: '20px',
                  },
                  bodyStyle: {
                    flex: '4',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                    fontFamily: 'SpoqaM',
                  },
                },
                {
                  label: t('instanceName.label'),
                  selector: 'instance_name',
                  headStyle: { flex: '7' },
                  bodyStyle: {
                    flex: '7',
                    fontSize: '14px',
                  },
                  cell: ({ instance_name }) => {
                    return instance_name ? instance_name : '-';
                  },
                },
                {
                  label: t('count.column.label'),
                  selector: 'allocate',
                  headStyle: { flex: '2' },
                  bodyStyle: {
                    flex: '2',
                    fontSize: '16px',
                    transform: 'translateX(10px)',
                  },
                  cell: ({ allocate }) => {
                    return allocate ?? '-';
                  },
                },
              ]}
            />
          </div>
          {/** 전체 인스턴스 현황 테이블 */}
          <div className={cx('total-instance-row')}>
            <TotalInstance
              title={t('totalInstanceCondition.label')}
              listData={totalInstanceCondition}
              toolTipIndex={0}
              columns={[
                {
                  label: t('instanceName.label'),
                  selector: 'instance_name',
                  headStyle: { flex: '3' },
                  bodyStyle: {
                    flex: '3',
                    fontSize: '14px',
                    boxSizing: 'border-box',
                    fontFamily: 'SpoqaM',
                  },
                  cell: ({ instance_name }) => {
                    return instance_name ? instance_name : '-';
                  },
                },
                // {
                //   label: t('totalInstanceCount.label'),
                //   selector: 'instance_allocate',
                //   headStyle: { flex: '2' },
                //   bodyStyle: {
                //     flex: '2',
                //     fontSize: '12px',
                //   },
                //   cell: ({ instance_allocate }) => {
                //     return instance_allocate ? instance_allocate : '-';
                //   },
                // },
                {
                  label: t('instanceUsage.label'),
                  selector: 'instance_allocate',
                  headStyle: { flex: '4' },
                  bodyStyle: {
                    flex: '4',
                    fontSize: '12px',
                  },
                  cell: ({ used_rate, remaining_rate }) => {
                    const { remaining_resource } = remaining_rate;
                    // 현재 목데이터로 작업해둠, 실제 데이터 들어오면 해당 값으로
                    // 넣어서 프로퍼티값만 바꿔주면됨
                    return (
                      <ProjectStack
                        used_rate={used_rate}
                        remaining_resource={remaining_resource}
                      />
                    );
                  },
                  isUsedBar: true,
                },
              ]}
            />
          </div>
        </div>

        <div className={cx('third-row')}>
          <div className={cx('graph-title')}>
            {t('dailyWorkspaceResourceUsage.label')}
          </div>
          {isDailyResourceUsageValid ? (
            <div>
              <WorkSpaceResourceChart
                tagId={'WorkSpaceResourceChart'}
                totalUsage={dailyResourceUsage}
                maxValue={100}
                customStyle={{ width: '100%', height: '360px' }}
              />
            </div>
          ) : (
            <div className={cx('no-data')}>{t('noChartData.message')}</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default UserHomeContent;
