import { Badge, ButtonV2 } from '@jonathan/ui-react';

import { convertDuration, convertLocalTime } from '@src/datetimeUtils';
import { loadModalComponent } from '@src/modal';
// Utils
import warningIcon from '@src/static/images/icon/ic-warning-yellow-white.svg';
import { useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory } from 'react-router-dom';

import Status from '@src/components/atoms/Status';
import TableBarTooltip from '@src/components/atoms/TableBarTooltip';
import Tooltip from '@src/components/atoms/Tooltip';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
import InstanceTooltip from '@src/components/organisms/InstanceTooltip';
// Components
import AdminDeploymentContent from '@src/components/pageContents/admin/AdminDeploymentContent';
// CSS module
import style from '@src/components/pageContents/admin/AdminDeploymentContent/AdminDeploymentContent.module.scss';
import { toast } from '@src/components/Toast';

// Actions
import { openConfirm } from '@src/store/modules/confirm';
import { openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import {
  convertBinaryByte,
  defaultSuccessToastMessage,
  errorToastMessage,
} from '@src/utils';

import classNames from 'classnames/bind';

const cx = classNames.bind(style);

const TABLE_TYPE = {
  running: 'primary-2',
  // 다른 곳에서 running이 새로추가된 primary-2와 색이 다른경우 존재해서 primary-2로 변경함
  error: 'error',
  stop: 'gray',
  pending: 'yellow',
};

function AdminDeploymentPage() {
  // Router Hooks
  const history = useHistory();

  // Redux Hooks
  const dispatch = useDispatch();

  const { t } = useTranslation();
  // State
  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
  const [deploymentStatus, setDeploymentStatus] = useState({
    label: t('allStatus.label'),
    value: 'all',
  });
  const [deploymentType, setDeploymentType] = useState({
    label: t('allModelType.label'),
    value: 'all',
  });
  const [searchKey, setSearchKey] = useState({
    label: t('deploymentName.label'),
    value: 'deployment_name',
  });
  const [keyword, setKeyword] = useState('');
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(3);

  const testItem = [
    {
      id: 913,
      status: 'error',
    },
    {
      id: 916,
      status: 'error',
    },
  ];
  const columns = [
    {
      name: t('status.label'),
      selector: 'deployment_status',
      sortable: false,
      maxWidth: '128px',
      cell: ({
        deployment_status: { status },
        deployment_worker_list: workerList,
      }) => {
        // <Status status={status === 'running' ? 'deploymentRunning' : status} />
        let tableStatus = status;
        if (status === 'running') {
          tableStatus = 'training.running.label';
        }

        return (
          // <Status
          //   status={STATUS[status]}
          //   // title={reason}
          //   type='dark'
          // />
          <>
            <div className={cx('badge')}>
              <Badge
                type={TABLE_TYPE[status]}
                label={t(tableStatus)}
                size='xl'
                // customStyle={{}}
              />
            </div>
            {status === 'error' && workerList > 0 && (
              <Tooltip
                contents={workerList.map(
                  ({ tool_type: toolType, name: toolName, id, status }) => {
                    let tableStatus = status;
                    if (status === 'running') {
                      tableStatus = 'training.running.label';
                    }
                    // {id, status, status_reason}

                    return (
                      <div className={cx('tooltip-wrapper')}>
                        <div className={cx('tooltip')}>
                          <Badge
                            type={TABLE_TYPE[status]}
                            label={t(tableStatus)}
                            size='xl'
                            // customStyle={{}}
                          />
                          <img
                            className={cx('tool-icon')}
                            src={`/images/icon/icon-deployments-blue.svg`}
                            alt={`icon-deployments-blue-icon`}
                          />
                          <span className={cx('tool-label')}>
                            {t('worker')} {id}
                          </span>
                        </div>
                      </div>
                    );
                  },
                )}
                icon={warningIcon}
                contentsCustomStyle={{
                  border: '0.5px solid #DEE9FF',
                  borderRadius: '10px',
                  boxShadow: '0px 3px 12px 0px rgba(45, 118, 248, 0.06)',
                  padding: '16px',
                }}
              />
            )}
          </>
        );
      },
    },

    {
      name: t('deploymentName.label'),
      selector: 'deployment_name',
      minWidth: '150px',
      cell: ({ deployment_name, workspace_name }) => {
        return (
          <div className={cx('name-box')}>
            <span className={cx('name')}>{workspace_name}</span>
            <div className={cx('workspace')}>{deployment_name}</div>
          </div>
        );
      },
    },
    {
      name: t('owner.label'),
      selector: 'user_name',
      maxWidth: '170px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('runningTime.label')}
          idx={1}
        />
      ),
      selector: 'operation_time',
      sortable: true,
      minWidth: '120px',
      maxWidth: '200px',
      cell: ({ operation_time: time }) => convertDuration(time),
    },

    {
      name: t('instanceCount.label'),
      selector: 'deployment_status',
      sortable: true,
      minWidth: '150px',
      cell: ({
        deployment_status: {
          worker: { resource_usage: resource },
        },
        instance: { instance_info: instanceInfo },
      }) => {
        const {
          cpu_allocate: cpu,
          gpu_allocate: gpu,
          ram_allocate: ram,
          type,
          name,
          instance_allocate: instanceAllocate,
          gpu_name: gpuName,
          allocated,
        } = instanceInfo;
        return (
          <div>
            {allocated ? (
              <>
                {name && (
                  <>
                    <span style={{ marginRight: '3px' }}>{name}</span>
                    {instanceAllocate &&
                      `x ${instanceInfo?.instance_allocate} EA`}
                  </>
                )}
                <InstanceTooltip
                  instanceType={type}
                  gpuName={gpuName}
                  gpuAllocateNum={gpu}
                  cpuAllocateNum={cpu}
                  ramAllocateNum={ram}
                  contentsCustomStyle={{
                    minWidth: '120px',
                  }}
                  iconCustomStyle={{ marginLeft: '4px' }}
                />
              </>
            ) : (
              '-'
            )}
          </div>
        );
      },
    },

    {
      name: t('allocatedInstanceUsage.label'),
      selector: '',
      sortable: false,
      minWidth: '280px',
      cell: ({
        name,
        workspace_name,

        instance: { unused_info: unusedInstance, used_info: usedInstance },
      }) => {
        const usedData = {
          cpu: usedInstance?.cpu,
          gpu: usedInstance?.gpu,
          ram: usedInstance?.ram,
        };

        const unusedData = {
          pcent: parseInt(unusedInstance?.rate || 0),
          cpu: unusedInstance?.cpu,
          gpu: unusedInstance?.gpu,
          ram: unusedInstance?.ram,
        };

        return (
          <div style={{ width: '100%' }}>
            <TableBarTooltip
              usedData={usedData}
              remainingData={unusedData}
              t={t}
            />
          </div>
        );
      },
      isUsedBar: true,
    },

    {
      name: t('logSize.label'),
      selector: 'log_size',
      minWidth: '60px',
      maxWidth: '160px',
      cell: ({ log_size: size }) => {
        return convertBinaryByte(size);
      },
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('createdAt.label')}
          idx={0}
        />
      ),
      selector: 'create_datetime',
      sortable: true,
      // minWidth: '102px',
      cell: ({ create_datetime }) => convertLocalTime(create_datetime),
    },
    {
      name: '',
      minWidth: '120px',
      cell: ({ deployment_status: { status }, id, deployment_name: name }) => {
        const activeStatus = ['running', 'pending', 'error', 'installing'];
        // return activeStatus.includes(status) ? (
        //   <img
        //     className='table-icon'
        //     src='/images/icon/ic-stop.svg'
        //     alt='stop'
        //     onClick={() => {
        //       onStopDeployment(id, name);
        //     }}
        //   />
        // ) : (
        //   <img
        //     className='table-icon disabled'
        //     src='/images/icon/ic-stop.svg'
        //     alt='stop'
        //   />
        // );

        return (
          <ButtonV2
            label={t('stopAll.label')}
            type='clear'
            onClick={() => {
              onStopDeployment(id, name);
            }}
            colorType='red'
            boxShadow={true}
            disabled={!activeStatus.includes(status)}
            size='l'
          />
        );
      },
      button: true,
    },
    // {
    //   name: t('edit.label'),
    //   minWidth: '70px',
    //   maxWidth: '70px',
    //   cell: (row) => (
    //     <img
    //       style={{
    //         opacity: row.deployment_type !== 'example' ? 1 : 0.2,
    //       }}
    //       src='/images/icon/00-ic-basic-pen.svg'
    //       alt='edit'
    //       className='table-icon'
    //       onClick={() => {
    //         if (row.deployment_type !== 'example') onUpdate(row);
    //       }}
    //     />
    //   ),
    //   button: true,
    // },
  ];

  /**
   * API 호출 GET
   * 어드민 배포 데이터 가져오기
   */
  const getDeploymentsData = async () => {
    setLoading(true);

    const response = await callApi({
      url: 'deployments/admin',
      method: 'GET',
    });

    const { status, result, message, error } = response;

    if (status === STATUS_SUCCESS) {
      setOriginData(result);
      setTableData(result);
      setTotalRows(result.length);
      setSelectedRows([]);

      // 상세정보에서 넘어 올 경우
      if (history.location.state) {
        const { workspace, user } = history.location.state;
        if (workspace) {
          setKeyword(workspace);
          selectInputHandler('searchKey', {
            label: t('workspace.label'),
            value: 'workspace_name',
          });
        } else if (user) {
          setKeyword(user);
          selectInputHandler('searchKey', {
            label: t('user.label'),
            value: 'users',
          });
        }
      }
      if (keyword !== '') onSearch(keyword);
    } else {
      errorToastMessage(error, message);
    }
    setLoading(false);
  };

  /**
   * 배포 생성
   */
  const onCreate = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_DEPLOYMENT',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {
              getDeploymentsData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
        },
      }),
    );
  };

  /**
   * 배포 중지
   *
   * @param {number} deploymentId  배포 ID
   */
  const onStopDeployment = async (deploymentId, deploymentName) => {
    const response = await callApi({
      url: `deployments/stop?deployment_id=${deploymentId}`,
      method: 'GET',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      toast.success(
        t('allWorkerStop.toast.message', { deployment: deploymentName }),
      );
    } else {
      errorToastMessage(error, message);
    }
    setTimeout(() => {
      getDeploymentsData();
    }, 1000);
  };

  /**
   * 배포 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteDeploymentPopup.title.label',
        content: 'deleteDeploymentPopup.message',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: t('deleteDeploymentPopup.title.label'),
      }),
    );
  };

  /**
   * API 호출 Delete
   * 배포 삭제
   * 체크박스 선택된 데이터 삭제
   */
  const onDelete = async () => {
    const ids = selectedRows.map(({ id }) => id);
    const response = await callApi({
      url: `deployments/${ids.join(',')}`,
      method: 'delete',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setToggledClearRows(!toggledClearRows);
      getDeploymentsData();
      defaultSuccessToastMessage('delete');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 배포 수정
   *
   * @param {object} row 배포 데이터
   */
  const onUpdate = (row) => {
    dispatch(
      openModal({
        modalType: 'EDIT_DEPLOYMENT',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              getDeploymentsData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: row,
          deploymentId: row.id,
          workspaceName: row.workspace_name,
        },
      }),
    );
  };

  /**
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */
  const selectInputHandler = (name, value) => {
    if (name === 'deploymentStatus') {
      setDeploymentStatus(value);
    } else if (name === 'searchKey') {
      setSearchKey(value);
    } else if (name === 'deploymentType') {
      setDeploymentType(value);
    }
  };

  /**
   * 검색
   *
   * @param {string} value 검색할 내용
   */
  const onSearch = (value) => {
    let tableData = originData;

    if (deploymentStatus.value !== 'all') {
      tableData = tableData.filter(
        (item) => item.deployment_status.status === deploymentStatus.value,
      );
    }

    if (deploymentType.value !== 'all') {
      tableData = tableData.filter(
        (item) => item.deployment_type === deploymentType.value,
      );
    }

    if (value !== '') {
      if (
        searchKey.value === 'training_name' ||
        searchKey.value === 'loaded_model'
      ) {
        tableData = tableData.filter((item) =>
          item[searchKey.value].name.includes(value),
        );
      } else if (searchKey.value === 'users') {
        tableData = tableData.filter((item) => {
          let found = false;
          for (let i = 0; i < item.users?.length; i += 1) {
            if (item.users[i].user_name.includes(value)) {
              found = true;
              break;
            }
          }
          return found;
        });
      } else {
        tableData = tableData.filter((item) =>
          item[searchKey.value].includes(value),
        );
      }
    }

    setKeyword(value);
    setTableData(tableData);
    setTotalRows(tableData.length);
  };

  /**
   * 검색 내용 제거
   */
  const onClear = () => {
    setKeyword('');
    history.push({ state: undefined });
  };

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  /**
   * 체크박스 선택
   *
   * @param {object} param0 선택된 행
   */
  const onSelect = ({ selectedRows }) => {
    setSelectedRows(selectedRows);
  };

  useEffect(() => {
    onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchKey, deploymentStatus, deploymentType]);

  useEffect(() => {
    if (originData.length !== 0) onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deploymentType, searchKey, originData, keyword]);

  useEffect(() => {
    loadModalComponent('CREATE_DEPLOYMENT');
    getDeploymentsData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AdminDeploymentContent
      columns={columns}
      tableData={tableData}
      totalRows={totalRows}
      toggledClearRows={toggledClearRows}
      keyword={keyword}
      searchKey={searchKey}
      loading={loading}
      deleteBtnDisabled={selectedRows.length === 0}
      deploymentType={deploymentType}
      deploymentStatus={deploymentStatus}
      onStatusChange={(value) => {
        selectInputHandler('deploymentStatus', value);
      }}
      onDeploymentTypeChange={(value) => {
        selectInputHandler('deploymentType', value);
      }}
      onSearch={onSearch}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      onCreate={onCreate}
      onSelect={onSelect}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      onClear={onClear}
      handleRefresh={getDeploymentsData}
      onSortHandler={onSortHandler}
    />
  );
}
export default AdminDeploymentPage;
