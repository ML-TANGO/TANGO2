// Components
import { useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { connect } from 'react-redux';

import { Badge, StatusCard } from '@jonathan/ui-react';

import Spinner from '@src/components/atoms/Spinner';
import DarkTooltip from '@src/components/molecules/DarkTooltip/DarkTooltip';
import ListStack from '@src/components/molecules/ListStack';
import History from '@src/components/organisms/Dashboard/History';
import TotalCount from '@src/components/organisms/Dashboard/TotalCount';

import { callApi } from '@src/network';

import WorkSpaceResourceChart from '../../user/UserHomeContent/WorkSpaceResourceChart';
import { calAllocateInstanceValue } from '../AdminNodeContent/InstanceDetail/InstanceDetail';
import AdminDashboardAllocated from './AdminDashboardAllocated';
import CustomTable from './CustomTable/CustomTable';

// Utils
import { convertBinaryByte, convertByte, executeWithLogging } from '@src/utils';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminDashboardContent.module.scss';

const cx = classNames.bind(style);

function AdminDashboardContent({
  totalCount,
  directLink,
  history,
  onRefresh,
  nav: { isExpand },
  serverError,
  gpuUsageByType,
  gpuUsageByGuarantee,
  storageTotalData,
  storageTableData,
  loading,
  totalUsage,
}) {
  const { t } = useTranslation();

  const [nodeInfo, setNodeInfo] = useState(null);
  const [allocatedData, setAllocatedData] = useState(null);
  const [cpuDetailData, setCpuDetailData] = useState(null);
  const [gpuDetailData, setGpuDetailData] = useState(null);
  const [ramDetailData, setRamDetailData] = useState(null);
  const [instanceData, setInstanceData] = useState(null);
  const [workspaceAllocData, setWorkspaceAllocData] = useState(null);
  const isFetching = useRef(false);

  // cpu gpu ram storage, 그 안에 workspace 값들
  const transformDetailData = (detailData) =>
    detailData
      ? Object.entries(detailData).map(([key, value]) => {
          // workspace가 존재하고, 그 안에 값이 있을 경우 배열로 변환
          const transformedWorkspace =
            value.workspace && Object.keys(value.workspace).length > 0
              ? Object.entries(value.workspace).map(([wkKey, wkValue]) => ({
                  name: wkKey,
                  ...wkValue,
                }))
              : [];

          return {
            name: key,
            ...value,
            workspace: transformedWorkspace,
          };
        })
      : [];

  useEffect(() => {
    const getNodeInfo = async () => {
      if (isFetching.current) return;
      isFetching.current = true;

      executeWithLogging(async () => {
        const { result } = await callApi({
          url: 'nodes/node-info',
          method: 'get',
        });
        setNodeInfo(result);
        const {
          usage: {
            cpu,
            gpu,
            mem,
            instance,
            workspace_instance_usage: wksUsage,
          },
        } = result;

        setCpuDetailData(transformDetailData(cpu.detail ?? []));
        setGpuDetailData(transformDetailData(gpu.detail ?? []));
        setRamDetailData(transformDetailData(mem.detail ?? []));
        setInstanceData(transformDetailData(instance ?? []));
        setWorkspaceAllocData(transformDetailData(wksUsage ?? []));
        isFetching.current = false;
      });
    };

    getNodeInfo();

    const intervalId = setInterval(() => {
      getNodeInfo();
    }, 5000);

    // Cleanup interval on component unmount
    return () => {
      isFetching.current = false;
      clearInterval(intervalId);
    };
  }, []);

  // const mergeStorageWorkspaces = (workspaces) => {
  //   const merged = [];

  //   // Map을 이용해 workspace_name을 기준으로 합치기
  //   const map = new Map();

  //   // data 배열 순회
  //   workspaces.data.forEach(({ workspace_name, alloc_size, used_size }) => {
  //     if (!map.has(workspace_name)) {
  //       map.set(workspace_name, {
  //         workspace_name,
  //         alloc_size: 0,
  //         used_size: 0,
  //       });
  //     }
  //     const current = map.get(workspace_name);
  //     current.alloc_size += alloc_size;
  //     current.used_size += used_size;
  //   });

  //   // main 배열 순회
  //   workspaces.main.forEach(({ workspace_name, alloc_size, used_size }) => {
  //     if (!map.has(workspace_name)) {
  //       map.set(workspace_name, {
  //         workspace_name,
  //         alloc_size: 0,
  //         used_size: 0,
  //       });
  //     }
  //     const current = map.get(workspace_name);
  //     current.alloc_size += alloc_size;
  //     current.used_size += used_size;
  //   });

  //   // Map의 값을 배열로 변환
  //   map.forEach((value) => merged.push(value));

  //   return merged;
  // };

  const totalCountList = totalCount.map((count) => (
    <TotalCount
      key={count.name}
      name={count.name}
      label={count.name}
      total={count.total}
      variation={count.variation}
      directLink={directLink}
    />
  ));

  const historyList = history.map((list, index) => (
    <History key={index} data={list} type='admin' />
  ));

  useEffect(() => {
    if (nodeInfo && nodeInfo.usage && storageTotalData) {
      const newAllocData = {
        cpu: nodeInfo.usage.cpu,
        gpu: nodeInfo.usage.gpu,
        ram: nodeInfo.usage.mem,
        storage: storageTotalData,
      };

      setAllocatedData(newAllocData);
    }
  }, [nodeInfo, storageTotalData]);

  return (
    <div id='AdminDashboardContent' className={cx('dashboard-contain')}>
      <div className={cx('header', isExpand && 'expand')}>
        <div className={cx('welcome')}>
          {t('welcomeBack.message')} Admin{t('sir.label')}!
        </div>
      </div>
      <div className={cx('content')}>
        <div className={cx('first-row')}>
          <div className={cx('status')}>
            <div className={cx('total-count')}>{totalCountList}</div>
          </div>
          <div className={cx('first-wrapper')}>
            <div className={cx('history')}>
              <label className={cx('title')}>
                {t('recentTasksHistory.label')}
              </label>
              {serverError ? (
                <div className={cx('no-response')}>
                  {t('noResponse.message')}
                </div>
              ) : history.length > 0 ? (
                <div className={cx('history-list')}>{historyList}</div>
              ) : (
                <div className={cx('no-history')}>
                  {t('noRecentTasks.message')}
                </div>
              )}
            </div>
            <div className={cx('allocated')}>
              <AdminDashboardAllocated
                data={allocatedData}
                nodeInfo={nodeInfo?.usage}
                storageData={storageTotalData}
                t={t}
              />
            </div>
          </div>
        </div>
        <div className={cx('dashboard-row')}>
          <div className={cx('dashboard')}>
            {!cpuDetailData && (
              <div className={cx('spinner')}>
                <Spinner color='primary' size='lg' />
              </div>
            )}
            {cpuDetailData && (
              <CustomTable
                title={t('dashboard.cpuUsage.label')}
                columns={[
                  {
                    label: t('cpuModel.label'),
                    selector: 'name',
                    headStyle: { textAlign: 'left' },
                    bodyStyle: { textAlign: 'left' },
                    maxWidth: '210px',
                    cell: ({ name }) => {
                      const [model, frequency] = name?.split('@');
                      const modelName = model?.trim();
                      return (
                        <div
                          style={{
                            overflow: 'hidden',
                            whiteSpace: 'nowrap',
                            textOverflow: 'ellipsis',
                          }}
                          title={modelName}
                        >
                          {modelName}
                        </div>
                      );
                    },
                  },
                  {
                    label: t('node.clockFrequency.label'),
                    selector: 'version',
                    headStyle: { textAlign: 'center' },
                    bodyStyle: { textAlign: 'center' },
                    width: '140px',
                    cell: ({ name }) => {
                      const [model, frequency] = name?.split('@');
                      const modelFrequency = frequency?.trim();
                      return modelFrequency;
                    },
                  },
                  {
                    label: '사용량',
                    selector: 'alloc_usage',
                    headStyle: { textAlign: 'center' },
                    bodyStyle: { textAlign: 'center' },
                    cell: (cpu) => {
                      // CPU
                      // TODO : 컴포넌트화
                      const {
                        workspace,
                        cpu_core: cpuCore,
                        alloc_usage: usage,
                        cpu_alloc: cpuAlloc,
                        used_usage: usedUsage,
                        cpu_used: cpuUsed,
                      } = cpu;

                      const allocRemaining = cpuCore - cpuAlloc;

                      const usedRemaining = cpuCore - cpuUsed;

                      const allocTransformData = (data = []) => {
                        return data.map((item) => ({
                          used: item.cpu_alloc,
                          usedPcent: item.alloc_usage,
                          name: item.name,
                          manager: item.manager,
                        }));
                      };

                      const usedTransformData = (data = []) => {
                        return data.map((item) => ({
                          used: item.cpu_used,
                          usedPcent: item.used_usage,
                          name: item.name,
                          manager: item.manager,
                        }));
                      };
                      const allocWksData = allocTransformData(workspace);
                      const usedWksData = usedTransformData(workspace);

                      return (
                        <div>
                          <div className={cx('usage-box')}>
                            <div className={cx('stack')}>
                              <div className={cx('core')}>
                                <div className={cx('label')}>
                                  {t('storageAllocationSize.label')}
                                </div>
                                <div className={cx('value')}>{`${
                                  cpuAlloc ?? 0
                                } Cores / ${cpuCore ?? 0} Cores`}</div>
                              </div>
                              <div>
                                <ListStack
                                  isTooltip={false}
                                  tooltipDirection='bottom'
                                  stackList={[{ value: usage }]}
                                  totalValue={100}
                                />
                              </div>
                            </div>
                            <div className={cx('usage')}>
                              {Math.floor(usage ?? 0)} %
                            </div>
                          </div>
                          <div className={cx('usage-box')}>
                            <div className={cx('stack')}>
                              <div className={cx('core')}>
                                <div className={cx('label')}>
                                  {t('enable.label')}
                                </div>
                                <div className={cx('value')}>{`${
                                  cpuUsed ?? 0
                                } Cores / ${cpuCore ?? 0} Cores`}</div>
                              </div>
                              <div>
                                <ListStack
                                  isTooltip={false}
                                  tooltipDirection='bottom'
                                  stackList={[{ value: usedUsage }]}
                                  totalValue={100}
                                />
                              </div>
                            </div>
                            <div className={cx('usage')}>
                              {Math.floor(usedUsage ?? 0)} %
                            </div>
                          </div>
                        </div>
                      );
                    },
                  },
                ]}
                data={cpuDetailData ?? []}
              />
            )}
          </div>
          <div className={cx('dashboard')}>
            {!gpuDetailData && (
              <div className={cx('spinner')}>
                <Spinner color='primary' size='lg' />
              </div>
            )}
            {gpuDetailData && (
              <CustomTable
                title={t('dashboard.gpuUsage.label')}
                columns={[
                  {
                    label: 'GPU 모델',
                    selector: 'name',
                    headStyle: { textAlign: 'left' },
                    bodyStyle: { textAlign: 'left' },
                    // minWidth: '100px',
                    maxWidth: '210px',
                    cell: ({ name }) => {
                      return (
                        <div
                          style={{
                            overflow: 'hidden',
                            whiteSpace: 'nowrap',
                            textOverflow: 'ellipsis',
                          }}
                          title={name}
                        >
                          {name}
                        </div>
                      );
                    },
                  },
                  {
                    label: 'CUDA Cores',
                    selector: 'cuda_core',
                    headStyle: { textAlign: 'center' },
                    bodyStyle: { textAlign: 'center' },
                    width: '130px',
                    cell: ({ cuda_core: cuda }) => {
                      return `${cuda ? cuda : '-'} Cores`;
                    },
                  },
                  {
                    label: 'VRAM',
                    selector: 'total',
                    width: '130px',
                    bodyStyle: { textAlign: 'center' },
                    headStyle: { textAlign: 'center' },
                    // minWidth: '120px', // minWidth 설정
                    cell: ({ gpu_mem: mem }) => {
                      return `${mem ?? 0} MB`;
                    },
                  },
                  {
                    label: '사용량',
                    selector: 'alloc_usage',
                    minWidth: '200px', // 사용량 열의 minWidth 증가
                    headStyle: { textAlign: 'center' },
                    bodyStyle: { textAlign: 'center' },
                    cell: (gpu) => {
                      // GPU
                      const { total, alloc: gpuAlloc, used: gpuUsed } = gpu;
                      const allocPcent =
                        gpuAlloc && total ? (gpuAlloc / total) * 100 : 0;
                      const usedPcent =
                        gpuUsed && total ? (gpuUsed / total) * 100 : 0;

                      return (
                        <div>
                          <div className={cx('usage-box')}>
                            <div className={cx('stack')}>
                              <div className={cx('core')}>
                                <div className={cx('label')}>
                                  {t('storageAllocationSize.label')}
                                </div>
                                <div className={cx('value')}>{`${
                                  gpuAlloc ?? 0
                                } EA / ${total ?? 0} EA`}</div>
                              </div>
                              <div>
                                <ListStack
                                  isTooltip={false}
                                  tooltipDirection='bottom'
                                  stackList={[{ value: allocPcent }]}
                                  totalValue={100}
                                />
                              </div>
                            </div>
                            <div className={cx('usage')}>
                              {Math.floor(allocPcent ?? 0)} %
                            </div>
                          </div>
                          <div className={cx('usage-box')}>
                            <div className={cx('stack')}>
                              <div className={cx('core')}>
                                <div className={cx('label')}>
                                  {t('enable.label')}
                                </div>
                                <div className={cx('value')}>{`${
                                  gpuUsed ?? 0
                                } EA / ${total ?? 0} EA`}</div>
                              </div>
                              <div>
                                <ListStack
                                  isTooltip={false}
                                  tooltipDirection='bottom'
                                  stackList={[{ value: usedPcent }]}
                                  totalValue={100}
                                />
                              </div>
                            </div>
                            <div className={cx('usage')}>
                              {Math.floor(usedPcent ?? 0)} %
                            </div>
                          </div>
                        </div>
                      );
                    },
                  },
                ]}
                data={gpuDetailData ?? []}
              />
            )}
          </div>
        </div>

        <div className={cx('dashboard-row')}>
          <div className={cx('dashboard')}>
            {!ramDetailData && (
              <div className={cx('spinner')}>
                <Spinner color='primary' size='lg' />
              </div>
            )}
            {ramDetailData && (
              <CustomTable
                title={t('dashboard.ramUsage.label')}
                columns={[
                  {
                    label: t('node.label'),
                    selector: 'name',
                    headStyle: { textAlign: 'left' },
                    bodyStyle: { textAlign: 'left' },
                    // minWidth: '100px',
                    maxWidth: '210px',
                    cell: ({ name }) => (
                      <div
                        style={{
                          overflow: 'hidden',
                          whiteSpace: 'nowrap',
                          textOverflow: 'ellipsis',
                        }}
                        title={name}
                      >
                        {name}
                      </div>
                    ),
                  },
                  {
                    label: t('version.label'),
                    selector: 'version',
                    headStyle: { textAlign: 'center' },
                    bodyStyle: { textAlign: 'center' },
                    // minWidth: '80px',
                    cell: ({ type }) => {
                      return type ? type : '-';
                    },
                  },
                  {
                    label: t('allocate.usage.label'),
                    selector: 'total',
                    bodyStyle: { textAlign: 'center' },
                    headStyle: { textAlign: 'center' },
                    // minWidth: '120px', // minWidth 설정
                    cell: (ram) => {
                      // TODO : 컴포넌트화
                      const {
                        workspace,
                        mem_total: ramtotal,
                        alloc_usage: ramAllocPcent,
                        mem_alloc: ramAlloc,
                        mem_used: ramUsed,
                        used_usage: usedPcent,
                      } = ram;

                      const allocRemaining =
                        ramtotal && ramAlloc ? ramtotal - ramAlloc : 0;

                      const usedRemaining =
                        ramtotal && ramUsed ? ramtotal - ramUsed : 0;

                      const allocTransformData = (data = []) => {
                        return data.map((item) => ({
                          used: item.mem_alloc ?? 0,
                          usedPcent: item.alloc_usage ?? 0,
                          name: item.name,
                          manager: item.manager,
                        }));
                      };

                      const usedTransformData = (data = []) => {
                        return data.map((item) => ({
                          used: item.mem_used ?? 0,
                          usedPcent: item.used_usage ?? 0,
                          name: item.name,
                          manager: item.manager,
                        }));
                      };
                      const allocWksData = allocTransformData(workspace);
                      const usedWksData = usedTransformData(workspace);

                      return (
                        <div>
                          <div className={cx('usage-box')}>
                            <div className={cx('stack')}>
                              <div className={cx('core')}>
                                <div className={cx('label')}>
                                  {t('storageAllocationSize.label')}
                                </div>
                                <div
                                  className={cx('value')}
                                >{`${convertBinaryByte(
                                  ramAlloc ?? 0,
                                )} / ${convertBinaryByte(ramtotal ?? 0)}`}</div>
                              </div>
                              <div>
                                <ListStack
                                  isTooltip={false}
                                  tooltipDirection='bottom'
                                  stackList={[{ value: ramAllocPcent }]}
                                  totalValue={100}
                                />
                              </div>
                            </div>
                            <div className={cx('usage')}>
                              {Math.floor(ramAllocPcent ?? 0)} %
                            </div>
                          </div>
                          <div className={cx('usage-box')}>
                            <div className={cx('stack')}>
                              <div className={cx('core')}>
                                <div className={cx('label')}>
                                  {t('enable.label')}
                                </div>
                                <div
                                  className={cx('value')}
                                >{`${convertBinaryByte(
                                  ramUsed ?? 0,
                                )}  / ${convertBinaryByte(
                                  ramtotal ?? 0,
                                )}`}</div>
                              </div>
                              <div>
                                <ListStack
                                  isTooltip={false}
                                  tooltipDirection='bottom'
                                  stackList={[{ value: usedPcent }]}
                                  totalValue={100}
                                />
                              </div>
                            </div>
                            <div className={cx('usage')}>
                              {Math.floor(usedPcent ?? 0)} %
                            </div>
                          </div>
                        </div>
                      );
                    },
                  },
                ]}
                data={ramDetailData ?? []}
              />
            )}
          </div>
          <div className={cx('dashboard')}>
            {!storageTableData && (
              <div className={cx('spinner')}>
                <Spinner color='primary' size='lg' />
              </div>
            )}
            {storageTableData && (
              <CustomTable
                title={t('dashboard.storageUsage.label')}
                columns={[
                  {
                    label: t('storageServer.label'),
                    selector: 'name',
                    headStyle: { textAlign: 'left' },
                    bodyStyle: { textAlign: 'left' },
                    // minWidth: '100px',
                    maxWidth: '210px',
                    cell: ({ name }) => (
                      <div
                        style={{
                          overflow: 'hidden',
                          whiteSpace: 'nowrap',
                          textOverflow: 'ellipsis',
                        }}
                        title={name}
                      >
                        {name}
                      </div>
                    ),
                  },
                  {
                    label: t('connectionType.label'),
                    selector: 'fstype',
                    headStyle: { textAlign: 'center' },
                    bodyStyle: { textAlign: 'center' },
                    // minWidth: '80px',
                    width: '150px',
                    cell: ({ fstype }) => {
                      if (fstype === 'nfs') {
                      }

                      return (
                        <Badge
                          type={fstype === 'nfs' ? 'primary-2' : 'red'}
                          label={fstype === 'nfs' ? t('network') : t('local')}
                          size='xl'
                          // customStyle={{}}
                        />
                      );
                    },
                  },
                  {
                    label: t('allocate.usage.label'),
                    selector: 'total',
                    bodyStyle: { textAlign: 'center' },
                    headStyle: { textAlign: 'center' },
                    // minWidth: '120px', // minWidth 설정
                    cell: (storage) => {
                      // TODO : 컴포넌트화
                      // 백엔드에서 넘어오는 pcent 가 할당쪽.사용쪽 역시 안주고있음
                      const {
                        workspace,
                        workspaces,
                        usage: storageData,
                      } = storage;

                      const {
                        size,
                        pcent: storageAllocPcent,
                        alloc_usage: ramAllocPcent,
                        mem_alloc: ramAlloc,
                        alloc: storageAlloc,
                        mem_used: ramUsed,
                        used: storageUsed,

                        usage,
                      } = storageData;

                      const { detail } = workspaces;

                      const allocRemaining =
                        size && storageAlloc ? size - storageAlloc : 0;

                      const usedRemaining =
                        storageAlloc && storageUsed
                          ? storageAlloc - storageUsed
                          : 0;

                      // const newWorkspace = mergeStorageWorkspaces(workspaces);

                      const allocPcent =
                        size && storageAlloc ? (storageAlloc / size) * 100 : 0;

                      const usedPcent =
                        size && storageUsed ? (storageUsed / size) * 100 : 0;

                      const allocTransformData = (data = []) => {
                        return detail.map((item) => ({
                          used: item.alloc_size ?? 0,
                          usedPcent: parseFloat(item.alloc_usage) ?? 0,
                          name: item.workspace_name,
                          manager: item.manager,
                        }));
                      };

                      const usedTransformData = (data = []) => {
                        return detail.map((item) => ({
                          used: item.used_size ?? 0,
                          usedPcent: parseFloat(item.used_usage) ?? 0,
                          name: item.workspace_name,
                          manager: item.manager,
                        }));
                      };
                      const allocWksData = allocTransformData(workspace);
                      const usedWksData = usedTransformData(workspace);

                      return (
                        <div>
                          <div className={cx('usage-box')}>
                            <div className={cx('stack')}>
                              <div className={cx('core')}>
                                <div className={cx('label')}>
                                  {t('storageAllocationSize.label')}
                                </div>
                                <div
                                  className={cx('value')}
                                >{`${convertBinaryByte(
                                  storageAlloc ?? 0,
                                )} / ${convertBinaryByte(size ?? 0)}`}</div>
                              </div>
                              <div>
                                <ListStack
                                  isTooltip={false}
                                  tooltipDirection='bottom'
                                  stackList={[{ value: allocPcent }]}
                                  totalValue={100}
                                />
                              </div>
                            </div>
                            <div className={cx('usage')}>
                              {Math.round(parseFloat(storageAllocPcent ?? 0))} %
                            </div>
                          </div>
                          <div className={cx('usage-box')}>
                            <div className={cx('stack')}>
                              <div className={cx('core')}>
                                <div className={cx('label')}>
                                  {t('enable.label')}
                                </div>
                                <div
                                  className={cx('value')}
                                >{`${convertBinaryByte(
                                  storageUsed ?? 0,
                                )}  / ${convertBinaryByte(size ?? 0)}`}</div>
                              </div>
                              <div>
                                <ListStack
                                  isTooltip={false}
                                  tooltipDirection='bottom'
                                  stackList={[{ value: usedPcent }]}
                                  totalValue={100}
                                />
                              </div>
                            </div>
                            <div className={cx('usage')}>
                              {Math.floor(usedPcent ?? 0)} %
                            </div>
                          </div>
                        </div>
                      );
                    },
                  },
                ]}
                data={storageTableData ?? []}
              />
            )}
          </div>
        </div>

        <div className={cx('instance-box')}>
          <div className={cx('content')}>
            <div className={cx('left')}>
              <CustomTable
                title={t('dashboard.instanceUsage.label')}
                columns={[
                  {
                    label: t('instanceName.label'),
                    selector: 'name',
                    headStyle: { textAlign: 'left' },
                    bodyStyle: { textAlign: 'left' },
                    minWidth: '270px',
                    // maxWidth: '20px',
                    cell: ({ name }) => (
                      <div
                        style={{
                          overflow: 'hidden',
                          whiteSpace: 'nowrap',
                          textOverflow: 'ellipsis',
                        }}
                        title={name}
                      >
                        {name}
                      </div>
                    ),
                  },
                  {
                    label: t('all.count.label'),
                    selector: 'fstype',

                    headStyle: { textAlign: 'center' },
                    bodyStyle: { textAlign: 'center' },
                    minWidth: '100px',
                    cell: ({
                      gpu_count: gpuCount,
                      cpu_count: cpuCount,
                      gpu,
                      instance_total_count: totalCount,
                    }) => {
                      return `${totalCount ?? 0} EA`;
                    },
                  },
                  {
                    label: t('instanceConfiguration.label'),
                    selector: 'total',
                    minWidth: '400px',
                    bodyStyle: { textAlign: 'center' },
                    headStyle: { textAlign: 'center' },
                    // minWidth: '120px', // minWidth 설정
                    cell: ({
                      cpu_count: cpu,
                      gpu_count: gpu,
                      ram_count: ram,
                      gpu_name: gpuName,
                    }) => {
                      const gpuTitle = `${
                        gpuName ?? '-'`${gpu ? `x ${gpu} EA` : ''}`
                      }`;
                      return (
                        <div className={cx('instance-conf')}>
                          <div className={cx('conf-item')}>
                            <div className={cx('label')}>vGPU</div>
                            <div
                              className={cx('value')}
                              style={{
                                overflow: 'hidden',
                                whiteSpace: 'nowrap',
                                textOverflow: 'ellipsis',
                              }}
                              title={gpuTitle}
                            >
                              {gpuName ?? '-'} {gpu ? `x ${gpu} EA` : ''}
                            </div>
                          </div>
                          <div className={cx('conf-item')}>
                            <div className={cx('label')}>vCPU</div>
                            <div className={cx('value')}>
                              {cpu ? `${cpu} Cores` : '-'}
                            </div>
                          </div>
                          <div className={cx('conf-item')}>
                            <div className={cx('label')}>RAM</div>
                            <div className={cx('value')}>
                              {ram ? `${ram} GB` : '-'}
                            </div>
                          </div>
                        </div>
                      );
                    },
                  },
                  {
                    label: t('workspace.alloc.label'),
                    selector: 'alloc_usage',
                    headStyle: { textAlign: 'center' },
                    bodyStyle: { textAlign: 'center' },
                    cell: ({
                      alloc_usage: usage,
                      workspaces,
                      allocate_workspace_list: allocList,
                      instance_total_count: totalCount,
                    }) => {
                      const transAllocListData = (allocateWorkspaceList) => {
                        return Object.entries(allocateWorkspaceList).map(
                          ([workspace_name, { instance_count }]) => ({
                            workspace_name,
                            instance_count,
                          }),
                        );
                      };

                      const newAllocList = transAllocListData(allocList ?? {});

                      const allocatetotalValue =
                        calAllocateInstanceValue(newAllocList);
                      const transfromAllocateValue = newAllocList.map((el) => {
                        return {
                          ...el,
                          value: el.instance_count,
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
                                  <span>{el.workspace_name}</span>
                                  <span>{el.instance_count}EA</span>
                                </div>
                              }
                            />
                          ),
                        };
                      });

                      return (
                        <div className={cx('flex-column')}>
                          <div
                            className={cx('flex-row')}
                            style={{
                              justifyContent: 'space-between',
                              marginBottom: '8px',
                            }}
                          >
                            <div className={cx('left-cont')}>
                              <span className={cx('label')}>
                                {t('allocateGpu.label')}
                              </span>
                              <span className={cx('value')}>
                                {totalCount} EA
                              </span>
                            </div>
                            <div className={cx('right-cont')}>
                              {(
                                (allocatetotalValue / totalCount) *
                                100
                              ).toFixed(0)}{' '}
                              %
                            </div>
                          </div>
                          <div
                            className={cx('flex-cont')}
                            style={{ marginBottom: '8px' }}
                          >
                            <ListStack
                              isTooltip={true}
                              tooltipDirection='bottom'
                              stackList={transfromAllocateValue}
                              totalValue={totalCount}
                            />
                          </div>
                          <div className={cx('flex-cont')}>
                            <div className={cx('unit-cont')}>
                              <span>(</span>
                              <span style={{ width: '34px' }}>
                                {allocatetotalValue}
                              </span>
                              <span>EA</span>
                              <span>/</span>
                              <span style={{ width: '34px' }}>
                                {totalCount}
                              </span>
                              <span>EA</span>
                              <span>)</span>
                            </div>
                          </div>
                        </div>
                      );
                    },
                  },
                ]}
                data={instanceData ?? []}
              />
            </div>
            <div className={cx('right')}>
              <div className={cx('right-title')}>
                {t('workspace.usage.detail.label')}
              </div>
              <div className={cx('right-content')}>
                {workspaceAllocData?.length > 0 ? (
                  workspaceAllocData.map(({ name, cpu, gpu, mem, usage }) => {
                    const newData = [
                      {
                        value: usage,
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
                                className={cx('wks-bar')}
                              >
                                <div className={cx('wks-bar-box')}>
                                  <div className={cx('bar-label')}>vGPU</div>
                                  <div>{gpu} EA</div>
                                </div>
                                <div className={cx('wks-bar-box')}>
                                  <div className={cx('bar-label')}>vCPU</div>
                                  <div>{cpu} Cores</div>
                                </div>

                                <div className={cx('wks-bar-box')}>
                                  <div className={cx('bar-label')}>RAM</div>
                                  <div>{convertByte(mem ?? 0)}</div>
                                </div>
                              </div>
                            }
                          />
                        ),
                      },
                    ];

                    return (
                      <div className={cx('wks-box')}>
                        <div className={cx('wks')}>
                          <div className={cx('name')}>{name}</div>
                          {/* <div className={cx('manager')}>{manager}</div> */}
                        </div>
                        <div className={cx('wks-progress')}>
                          <div className={cx('wks-pcent')}>{usage} %</div>
                          <ListStack
                            isTooltip={true}
                            tooltipDirection='bottom'
                            stackList={newData}
                            totalValue={100}
                          />
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div>{t('noData.message')}</div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className={cx('second-row')}>
          <label className={cx('title')}>
            {t('systemResourceHistory.label')}
          </label>
          {serverError ? (
            <div className={cx('no-response')}>{t('noResponse.message')}</div>
          ) : totalUsage.gpu ? (
            <div>
              <WorkSpaceResourceChart
                tagId={'WorkSpaceResourceChart'}
                totalUsage={totalUsage}
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

export default connect(({ nav }) => ({ nav }))(AdminDashboardContent);
