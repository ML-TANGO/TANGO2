import { Badge, Selectbox, Switch } from '@jonathan/ui-react';

import SettingIcon from '@src/static/images/icon/00-setting.svg';
import React, { Fragment, useCallback, useMemo, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import Table from '@src/components/molecules/Table';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';

import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { openModal } from '@src/store/modules/modal';

// 엣지 워커 행 액션(통합 노드표에 병합된 EDGE 행의 새로고침/삭제).
import { deleteEdgeWorker, refreshEdgeWorker } from '@src/apis/flightbase/edge';
import { STATUS_SUCCESS } from '@src/network';
import { toast } from '@src/components/Toast';

import { calFindNodeList, postChangeStatus } from '../util';

// Components
import AdminNodeDetail from '../AdminNodeDetail';
import EdgeWorkerDetail from '../EdgeWorkerDetail';

import classNames from 'classnames/bind';
// CSS module
import style from './NodeTable.module.scss';

const cx = classNames.bind(style);

// ** [계산] 상태 값 뱉는 **
const calStatusFlag = (toggleStatus, status) => {
  if (!toggleStatus) return status === 'Ready' ? 'attached' : 'detached';
  if (toggleStatus.status !== status) {
    if (status === 'Ready') return 'disconnecting';
    return 'attaching';
  }
  return status === 'Ready' ? 'attached' : 'detached';
};

// ** [계산] RAM 정보 계산 **
const calMergeRamInfo = (device) => {
  if (device.lenght === 0) return [];

  const copyList = device.slice();
  const mergeList = copyList.reduce((acc, cur) => {
    const findSameValue = acc.find(
      (m) => m.size === cur.size && m.speed === cur.speed,
    );
    if (findSameValue) {
      findSameValue.count += cur.count;
    } else {
      acc.push({ ...cur });
    }
    return acc;
  }, []);
  return mergeList;
};

// ** 행 스타일 **
const conditionalRowStyles = [
  {
    when: (row) => row.active_status === 0,
    style: {
      backgroundColor: '#f0f0f0',
    },
  },
];

const nodeTypeColorObj = {
  CPU: 'yellow',
  GPU: 'green',
  MANAGE: 'pink',
  DB: 'blue', // K8s node-role.kubernetes.io/db 라벨 파생
  EDGE: 'orange', // 통합표에 병합된 엣지 워커 행 표식
};

const calBadgeColor = (nodeType) => {
  return nodeTypeColorObj[nodeType];
};

// 엣지 워커 자원(heartbeat 코어 수는 정수 bytes 아님 → mem_total 만 포맷).
const formatBytes = (n) => {
  if (!n || n <= 0) return '';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), u.length - 1);
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
};

const calIsCpuGpu = (typeList) => {
  return typeList.some((type) => type === 'cpu' || type === 'gpu');
};
const calIsControlPlaneManage = (roleList) => {
  return roleList.some((role) => role === 'control-plane' || role === 'manage');
};

const calDisabledBtn = (roleList, typeList) => {
  const isCpuGpu = calIsCpuGpu(typeList);
  const isControlPlaneManage = calIsControlPlaneManage(roleList);

  if (isCpuGpu && isControlPlaneManage)
    return { isActiveBtn: false, isSettingBtn: true };

  if (!isCpuGpu) return { isActiveBtn: false, isSettingBtn: false };

  // if (
  //   typeList.length === 1 &&
  //   (typeList[0] === 'gpu') | (typeList[0] === 'cpu') &&
  //   roleList.length === 1 &&
  //   roleList[0] === 'compute'
  // ) {
  //   return { isActiveBtn: true, isSettingBtn: true };
  // }
  if (roleList.includes('compute')) {
    return { isActiveBtn: true, isSettingBtn: true };
  }

  // ** 마지막 조건 넣어야 함 **
  return { isActiveBtn: false, isSettingBtn: false };
};

function NodeTable({
  nodeList: nodeTableList,
  statusList,
  setStatusList,
  handleRefresh,
  refetchEdge,
}) {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  // 통합표에 병합된 엣지 워커 행 액션(remoteManager 새로고침 / 삭제). 진행 중 busy 가드.
  const [edgeBusyId, setEdgeBusyId] = useState(null);

  const handleEdgeRefresh = useCallback(
    async (edgeId) => {
      setEdgeBusyId(edgeId);
      const res = await refreshEdgeWorker(edgeId);
      setEdgeBusyId(null);
      if (res.status === STATUS_SUCCESS) refetchEdge?.();
      else toast.error(res.message || t('edge.toast.refreshFail'));
    },
    [refetchEdge, t],
  );

  const handleEdgeDelete = useCallback(
    async (edgeId, deviceId) => {
      // eslint-disable-next-line no-alert
      if (!window.confirm(t('edge.confirm.delete', { device: deviceId }))) return;
      setEdgeBusyId(edgeId);
      const res = await deleteEdgeWorker(edgeId);
      setEdgeBusyId(null);
      if (res.status === STATUS_SUCCESS) {
        // BE 는 배포가 돌고 있으면 stop 을 best-effort 로 먼저 보내고, 결과와 무관하게
        // 삭제를 진행한다(죽은 디바이스를 영구히 못 지우는 것을 막기 위해). 실패했다면
        // 디바이스에 컨테이너가 유령으로 남으므로 조용히 넘기지 않고 알린다.
        const stop = res.result?.stop;
        if (stop?.attempted && !stop.ok) {
          toast.warning(
            t('edge.toast.deletedButStopFailed', { device: deviceId }),
          );
        }
        refetchEdge?.();
      } else toast.error(res.message || t('edge.toast.deleteFail'));
    },
    [refetchEdge, t],
  );

  const [searchKey, setSearchKey] = useState({
    label: t('nodeName.label'),
    value: 'hostname',
  });
  const [searchKeyword, setSearchKeyword] = useState('');
  const [nodeStatus, setNodeStatus] = useState({
    label: t('allStatus.label'),
    value: 'all',
  });
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(2);
  const totalRows = nodeTableList && nodeTableList.length;

  const searchOptions = useMemo(() => {
    return [
      { label: t('nodeName.label'), value: 'hostname' },
      { label: t('ipAddress.label'), value: 'ip' },
    ];
  }, [t]);

  const statusOptions = useMemo(() => {
    return [
      { label: t('allStatus.label'), value: 'all' },
      { label: t('attached'), value: 'attached' },
      { label: t('disconnecting'), value: 'disconnecting' },
      { label: t('attaching'), value: 'attaching' },
      { label: t('detached'), value: 'detached' },
    ];
  }, [t]);

  // ** 검색 **
  const onSearch = useCallback((value) => {
    setSearchKeyword(value);
  }, []);

  // ** 검색 내용 제거**
  const onClear = useCallback(() => {
    onSearch('');
  }, [onSearch]);

  // ** 설정 모달 띄우기 **
  const onUpdate = useCallback(
    (row) => {
      dispatch(
        openModal({
          modalType: 'SETTING_VIRTUAL_NODE',
          modalData: {
            data: row,
            nodeId: row.id,
          },
        }),
      );
    },
    [dispatch],
  );

  /**
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */
  const selectInputHandler = useCallback((name, value) => {
    if (name === 'searchKey') {
      setSearchKey(value);
    } else if (name === 'nodeStatus') {
      setNodeStatus(value);
    }
  }, []);

  // ** 활성화 토글 함수 **
  const doubleRef = useRef(false);
  const handleDisconnectStatus = useCallback(
    (nodeId, changeStatus, setStatusList) => {
      dispatch(
        openConfirm({
          content: 'node.status.content',
          submit: {
            text: 'yes.label',
            func: () => {
              postChangeStatus(nodeId, changeStatus, setStatusList);
            },
          },
          cancel: {
            text: 'no.label',
          },
        }),
      );
    },
    [dispatch],
  );

  const handleStatus = useCallback(
    async (nodeId, toggleStatus, setStatusList) => {
      if (doubleRef.current) return;
      doubleRef.current = true;
      const changeStatus = toggleStatus.status === 'Ready' ? false : true;

      if (toggleStatus.status === 'Ready') {
        handleDisconnectStatus(nodeId, changeStatus, setStatusList);
        doubleRef.current = false;
        return;
      }

      await postChangeStatus(nodeId, changeStatus, setStatusList);
      doubleRef.current = false;
    },
    [handleDisconnectStatus],
  );

  const commonColumns = [
    {
      name: t('status.label'),
      selector: 'condition',
      cell: (row) => {
        if (row._rowType === 'edge') {
          const on = row.conn_status === 'online';
          return (
            <Badge
              size='lg'
              label={t(on ? 'attached' : 'detached')}
              type={on ? 'primary-2' : 'gray'}
            />
          );
        }
        const { status, id } = row;
        const findList = calFindNodeList(statusList, id);
        const newStatus = calStatusFlag(findList, status);
        return (
          <Badge
            size='lg'
            label={t(newStatus)}
            type={newStatus === 'attached' ? 'primary-2' : 'gray'}
          />
        );
      },
      sortable: false,
      minWidth: '82px',
      maxWidth: '82px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('nodeName.label')}
          idx={0}
        />
      ),
      selector: 'hostname',
      minWidth: '380px',
      maxWidth: '380px',
      sortable: true,
      cell: (row) => {
        const {
          role,
          hostname: name,
          active_status: activeStatus = 1,
          type,
        } = row;
        const isEdge = row._rowType === 'edge';
        const isMaster = role.find((r) => r === 'control-plane');
        return (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              cursor: isEdge ? 'default' : 'not-allowed',
            }}
          >
            <div
              className={cx(isMaster && 'master')}
              title={name}
              style={{ textOverflow: 'hidden', textWrap: 'nowrap' }}
            >
              {name}
              {isEdge && row.deploy_model && (
                <span style={{ opacity: 0.6, marginLeft: 6 }}>
                  · {row.deploy_model}
                  {row.deploy_state ? ` (${row.deploy_state})` : ''}
                </span>
              )}
            </div>
            <div className={cx('flex-cont')}>
              {type.length !== 0 &&
                type.map((typeEl, idx) => {
                  const nodeType = typeEl.toUpperCase();
                  const nodeTypeColor = calBadgeColor(nodeType);
                  return (
                    activeStatus === 1 && (
                      <Badge
                        key={idx}
                        label={nodeType}
                        type={nodeTypeColor}
                        customStyle={{ marginLeft: '10px' }}
                      />
                    )
                  );
                })}
            </div>
          </div>
        );
      },
      style: {
        textWrap: 'nowrap',
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('ipAddress.label')}
          idx={1}
        />
      ),
      selector: 'ip',
      sortable: true,
      minWidth: '110px',
      maxWidth: '140px',
    },
  ];

  const actionColumns = [
    {
      name: t('activation.label'),
      minWidth: '100px',
      maxWidth: '120px',
      cell: (row) => {
        const { id, role, type } = row;
        const { isActiveBtn } = calDisabledBtn(role, type);

        const toggleStatus = calFindNodeList(statusList, id);
        if (!toggleStatus) return <Switch disabled />;
        return (
          <Switch
            onChange={() => handleStatus(id, toggleStatus, setStatusList)}
            checked={toggleStatus['status'] === 'Ready' ? true : false}
            disabled={!isActiveBtn}
            customStyle={{ overflow: 'visible' }}
          />
        );
      },
      button: true,
    },
    {
      name: t('setting.label'),
      selector: 'id',
      minWidth: '150px',
      maxWidth: '180px',
      cell: (row) => {
        if (row._rowType === 'edge') {
          const eid = row._edge.id;
          return (
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type='button'
                className={cx('edge-act')}
                disabled={edgeBusyId === eid}
                onClick={() => handleEdgeRefresh(eid)}
              >
                {t('edge.action.refresh')}
              </button>
              <button
                type='button'
                className={cx('edge-act', 'danger')}
                disabled={edgeBusyId === eid}
                onClick={() => handleEdgeDelete(eid, row.device_id)}
              >
                {t('delete.label')}
              </button>
            </div>
          );
        }
        const { role, type } = row;
        const { isSettingBtn } = calDisabledBtn(role, type);

        return (
          <img
            className={cx('setting-icon', !isSettingBtn && 'disabled')}
            src={SettingIcon}
            alt='setting-btn'
            onClick={() => {
              if (!isSettingBtn) return;
              onUpdate(row);
            }}
          />
        );
      },
      button: true,
      disabled: true,
    },
  ];

  const gpuColumns = [
    ...commonColumns,
    {
      name: t('cpuConfig.label'),
      minWidth: '356px',
      cell: (row) => {
        if (row._rowType === 'edge')
          return row.cpu_cores ? `${row.cpu_cores} cores` : '-';
        const { cpu_model } = row.cpu_info;
        return cpu_model;
      },
      style: {
        textWrap: 'nowrap',
      },
    },
    {
      name: t('gpuConfig.label'),
      minWidth: '280px',
      cell: (row) => {
        if (row._rowType === 'edge') return row.gpu_info || '-';
        const { gpu_info } = row;
        if (!gpu_info) return '-';

        const gpuConfigurationObj = Object.values(gpu_info).reduce(
          (acc, cur) => {
            if (acc[cur.model_name]) {
              acc[cur.model_name] += 1;
            }

            if (!acc[cur.model_name]) {
              acc[cur.model_name] = 1;
            }
            return acc;
          },
          {},
        );

        return (
          <>
            {Object.keys(gpuConfigurationObj).map((keyName, idx) => (
              <React.Fragment key={idx}>
                {keyName + ` x ${gpuConfigurationObj[keyName]}EA`}
                <br />
              </React.Fragment>
            ))}
          </>
        );
      },
      style: {
        textWrap: 'nowrap',
      },
    },
    {
      name: t('node.ramInfo.label'),
      minWidth: '210px',
      cell: (row) => {
        if (row._rowType === 'edge') return formatBytes(row.mem_total) || '-';
        const { mem_info } = row;
        if (!mem_info) return '-';

        const { device } = mem_info;
        const calFunc = calMergeRamInfo(device);
        if (calFunc.length === 0) return '-';
        return calFunc.map((info, idx) => {
          const { count, size, speed, type } = info;
          return (
            <Fragment key={idx}>
              {type}-{size}-{speed} x {count}EA
              <br />
            </Fragment>
          );
        });
      },
      style: {
        textWrap: 'nowrap',
      },
    },
    ...actionColumns,
  ];

  const filterList = useMemo(() => {
    return (
      <>
        <div style={{ width: '180px' }}>
          <Selectbox
            list={statusOptions}
            selectedItem={nodeStatus}
            onChange={(value) => selectInputHandler('nodeStatus', value)}
            customStyle={{
              fontStyle: {
                selectbox: {
                  fontSize: '14px',
                },
              },
            }}
          />
        </div>
      </>
    );
  }, [nodeStatus, statusOptions, selectInputHandler]);

  const expandedComponent = useCallback((row) => {
    // AdminNodeDetail 은 K8s 노드 shape 전용(cpu_info/sw_version/mem_info 구조분해).
    // 엣지 행은 전용 상세(EdgeWorkerDetail)로 분기 — 원본 워커 객체(_edge) 전달.
    const d = row.data;
    if (!d) return null;
    if (d._rowType === 'edge') return <EdgeWorkerDetail worker={d._edge} />;
    return <AdminNodeDetail data={d} />;
  }, []);

  const onSortHandler = useCallback(
    (sortDirection) => {
      onClickHandler(clickedIdx, sortDirection);
    },
    [clickedIdx, onClickHandler],
  );

  // ** 검색 필터 **
  const calSearchFilter = useCallback(
    (tableList, searchKey, searchKeyword, nodeStatus, statusList) => {
      if (!tableList) return [];
      if (!tableList.length) return [];
      if (searchKeyword === '' && nodeStatus.value === 'all') return tableList;

      const shallowCopyList = tableList.slice();
      const { value } = searchKey;

      const statusState =
        nodeStatus.value === 'attached' ? 'Ready' : 'Not Ready';

      const filterKeywordList = shallowCopyList.filter((el) => {
        return el[value].includes(searchKeyword);
      });

      if (nodeStatus.value === 'all') return filterKeywordList;
      if (nodeStatus.value === 'attaching') {
        const attachingList = filterKeywordList.filter((el) => {
          return statusList.some((statusInfo) => {
            return (
              statusInfo.nodeId === el.id && statusInfo.status !== el.status
            );
          });
        });
        return attachingList;
      }

      const filterStatusList = filterKeywordList.filter((el) => {
        return el['status'] === statusState;
      });

      return filterStatusList;
    },
    [],
  );

  const nodeTablefilterList = calSearchFilter(
    nodeTableList,
    searchKey,
    searchKeyword,
    nodeStatus,
    statusList,
  );

  return (
    <div className={cx('nodetable-cont')}>
      <Table
        selectableRows={false}
        loading={!nodeTableList}
        columns={gpuColumns}
        data={nodeTablefilterList}
        totalRows={totalRows}
        ExpandedComponent={expandedComponent}
        defaultSortField='hostname'
        selectableRowDisabled={({ condition }) => {
          if (condition) {
            const { role } = condition;
            if (role === 'control-plane') return true;
          }
          return false;
        }}
        filterList={filterList}
        searchOptions={searchOptions}
        searchKey={searchKey}
        keyword={searchKeyword}
        onSearchKeyChange={(value) => {
          selectInputHandler('searchKey', value);
        }}
        onSearch={(e) => {
          onSearch(e.target.value);
        }}
        conditionalRowStyles={conditionalRowStyles}
        onClear={onClear}
        onSortHandler={onSortHandler}
        handleRefresh={handleRefresh}
      />
    </div>
  );
}

export default NodeTable;
