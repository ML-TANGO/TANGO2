// Utils
import { Badge, ButtonV2 } from '@jonathan/ui-react';

import { convertLocalTime } from '@src/datetimeUtils';
import { loadModalComponent } from '@src/modal';
import warningIcon from '@src/static/images/icon/ic-warning-yellow-white.svg';
//Type
import { TRAINING_TOOL_TYPE } from '@src/types';
import { useEffect, useRef, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useHistory } from 'react-router-dom';

import TableBarTooltip from '@src/components/atoms/TableBarTooltip';
import Tooltip from '@src/components/atoms/Tooltip';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
import InstanceTooltip from '@src/components/organisms/InstanceTooltip';
// Components
import AdminTrainingContent from '@src/components/pageContents/admin/AdminTrainingContent';
// CSS module
import style from '@src/components/pageContents/admin/AdminTrainingContent/AdminTrainingContent.module.scss';
import ProjectStack from '@src/components/pageContents/user/UserHomeContent/ProjectStack';
import { toast } from '@src/components/Toast';

import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';

const cx = classNames.bind(style);

const TABLE_TYPE = {
  running: 'primary-2',
  // 다른 곳에서 running이 새로추가된 primary-2와 색이 다른경우 존재해서 primary-2로 변경함
  error: 'error',
  stop: 'gray',
  pending: 'yellow',
};

function AdminTrainingPage() {
  const { t } = useTranslation();
  const history = useHistory();
  const dispatch = useDispatch();

  const _isMounted = useRef(false);
  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
  const [trainingStatus, setTrainingStatus] = useState({
    label: t('allStatus.label'),
    value: 'all',
  });
  const [trainingType, setTrainingType] = useState({
    label: t('allType.label'),
    value: 'all',
  });
  const [searchKey, setSearchKey] = useState({
    label: t('trainingName.label'),
    value: 'name',
  });
  const [keyword, setKeyword] = useState('');
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(3);

  /**
   * 테이블 데이터 컬럼 정의
   */

  const columns = [
    {
      name: t('status.label'),
      selector: 'status',
      sortable: false,
      maxWidth: '128px',
      // cell: ({ status: { status, reason } }) => (
      cell: ({ status, errors }) => {
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
            {errors && errors.length > 0 && (
              <Tooltip
                contents={errors.map(
                  ({ tool_type: toolType, name: toolName }) => {
                    return (
                      <div className={cx('tooltip-wrapper')}>
                        <div className={cx('tooltip')}>
                          <Badge
                            type={'error'}
                            label={t('error')}
                            size='xl'
                            customStyle={{ marginRight: '2px' }}
                          />
                          <img
                            className={cx('tool-icon')}
                            src={`/images/icon/ic-${TRAINING_TOOL_TYPE[toolType]?.type}.svg`}
                            alt={`${TRAINING_TOOL_TYPE[toolType]?.type} icon`}
                          />
                          <span className={cx('tool-label')}>
                            {toolName
                              ? toolName
                              : TRAINING_TOOL_TYPE[toolType]?.label}
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
      name: t('trainingName.label'),
      selector: 'name',
      sortable: false,
      minWidth: '170px',
      cell: ({ name, workspace_name }) => {
        return (
          <div className={cx('name-box')}>
            <span className={cx('name')}>{workspace_name}</span>
            <div className={cx('workspace')}>{name}</div>
          </div>
        );
      },
    },
    {
      name: t('instanceCount.label'),
      selector: 'workspace_name',
      sortable: false,
      minWidth: '170px',
      cell: ({
        instance_name,
        instance_allocate,
        instance_type,
        gpu_allocate,
        cpu_allocate,
        ram_allocate,
        resource_name,
      }) => {
        return (
          <div>
            {instance_name} {instance_allocate && `x ${instance_allocate} EA`}
            <InstanceTooltip
              instanceType={instance_type}
              gpuName={resource_name}
              gpuAllocateNum={gpu_allocate}
              cpuAllocateNum={cpu_allocate}
              ramAllocateNum={ram_allocate}
              contentsCustomStyle={{
                minWidth: '120px',
                // transform: ' translate(30px, -60px)',
                position: 'absoulte',
              }}
              iconCustomStyle={{ marginLeft: '4px' }}
            />
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
        instance_used_info: usedInstance,
        instance_unused_info: unusedInstance,
      }) => {
        const usedData = {
          cpu: usedInstance?.used_cpu,
          gpu: usedInstance?.used_gpu,
          ram: usedInstance?.used_ram,
        };

        const unusedData = {
          pcent: parseInt(unusedInstance?.unused_rate || 0),
          cpu: unusedInstance?.cpu,
          gpu: unusedInstance?.gpu,
          ram: unusedInstance?.ram,
        };

        return (
          <div className={cx('stack')}>
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
      name: t('owner.label'),
      selector: 'create_user_name',
      sortable: false,
      maxWidth: '170px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('lastRunDateTime.label')}
          idx={1}
        />
      ),
      selector: 'last_start_datetime',
      sortable: true,
      maxWidth: '192px',
      cell: ({ last_start_datetime: date }) => {
        if (date === null || date === '') {
          return <div>-</div>;
        }
        return convertLocalTime(date);
      },
    },
    // {
    //   name: (
    //     <SortColumn
    //       onClickHandler={clickedIdxHandler}
    //       sortClickFlag={sortClickFlag}
    //       title={t('resource.label')}
    //       idx={2}
    //     />
    //   ),
    //   selector: 'resource_info',
    //   sortable: true,
    //   minWidth: '120px',
    //   cell: ({ resource_info: { resource_usage: resource } }) => {
    //     return (
    //       <div>
    //         CPU*{resource.cpu}, GPU*{resource.gpu}
    //       </div>
    //     );
    //   },
    // },
    {
      name: t('stop.label'),
      minWidth: '120px',
      cell: ({ status, id }) => {
        const activeStatus = ['running', 'pending', 'error', 'installing'];

        return activeStatus.includes(status) ? (
          <ButtonV2
            label={t('stopAll.label')}
            type='clear'
            onClick={() => {
              onStop(id);
            }}
            colorType='red'
            boxShadow={true}
            size='l'
          />
        ) : (
          // <img
          //   className='table-icon disabled'
          //   src='/images/icon/ic-stop.svg'
          //   alt='stop'
          // />
          <ButtonV2
            label={t('stopAll.label')}
            type='clear'
            disabled={true}
            colorType='red'
            boxShadow={true}
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
    //       className='table-icon'
    //       src='/images/icon/00-ic-basic-pen.svg'
    //       alt='edit'
    //       onClick={() => {
    //         onUpdate(row);
    //       }}
    //     />
    //   ),
    //   button: true,
    // },
  ];

  /**
   * API 호출 GET
   * 어드민 학습 데이터 가져오기
   */
  const getTrainingsData = async () => {
    setLoading(true);
    const response = await callApi({
      url: 'projects',
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (!_isMounted.current) return;
    if (status === STATUS_SUCCESS) {
      setOriginData(result.list);
      setTableData(result.list);
      setTotalRows(result.total);
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
   * 검색 내용 제거
   */
  const onClear = () => {
    setKeyword('');
    onSearch('');
    history.push({ state: undefined });
  };

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  /**
   * 학습 생성
   */
  const onCreate = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_TRAINING',
        modalData: {
          submit: {
            text: 'create.label',
            func: () => {
              getTrainingsData();
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
   * 학습 수정
   *
   * @param {object} row 학습 데이터
   */
  const onUpdate = (row) => {
    dispatch(
      openModal({
        modalType: 'EDIT_TRAINING',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              getTrainingsData();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data: row,
          workspaceId: row.workspace_id,
        },
      }),
    );
  };

  /**
   * API 호출 Delete
   * 학습 삭제
   * 체크박스 선택된 학습 삭제
   */
  const onDelete = async () => {
    const ids = selectedRows.map(({ id }) => id);
    const response = await callApi({
      url: `projects`,
      method: 'delete',
      body: {
        id_list: ids,
      },
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setToggledClearRows(!toggledClearRows);
      await getTrainingsData();
      defaultSuccessToastMessage('delete');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 학습 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteTrainingPopup.title.label',
        content: 'deleteTrainingPopup.content.message',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
        confirmMessage: t('deleteTrainingPopup.title.label'),
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
    if (name === 'trainingStatus') {
      setTrainingStatus(value);
    } else if (name === 'searchKey') {
      setSearchKey(value);
    } else if (name === 'trainingType') {
      setTrainingType(value);
    }
  };
  /**
   * 검색
   *
   * @param {string} value 검색할 내용
   */
  const onSearch = (value) => {
    let tableData = originData;
    if (trainingStatus.value !== 'all') {
      tableData = tableData.filter(
        (item) => item.status === trainingStatus.value,
      );
    }
    if (trainingType.value !== 'all') {
      tableData = tableData.filter((item) => item.type === trainingType.value);
    }

    if (value !== '') {
      if (searchKey.value === 'users') {
        tableData = tableData.filter((item) => {
          let found = false;
          for (let i = 0; i < item.users.length; i += 1) {
            if (item.users[i].user_name.includes(value)) {
              found = true;
              break;
            }
          }
          return found;
        });
      } else if (searchKey.value === 'user_name') {
        tableData = tableData.filter((item) =>
          item['create_user_name'].includes(value),
        );
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
   * 체크박스 선택
   *
   * @param {object} param0 선택된 행
   */
  const onSelect = ({ selectedRows }) => {
    setSelectedRows(selectedRows);
  };

  /**
   * 학습 종료
   *
   * @param {number} id 학습 ID
   */
  const onStop = async (id) => {
    const response = await callApi({
      url: 'projects/stop',
      method: 'post',
      body: {
        project_id: id,
      },
    });
    const { status, message, error, result } = response;
    if (result) {
      setLoading(true);
      setTimeout(async () => {
        await getTrainingsData();
        defaultSuccessToastMessage('stop');
        setLoading(false);
      }, 2500);
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 작업/HPS 종료
   *
   * @param {string} type job or hps
   * @param {number} id 작업/HPS ID
   */
  const jobStop = async (type, id) => {
    let url = '';
    if (type === 'job') {
      url = `trainings/stop_jobs?training_id=${id}`;
    } else {
      url = `trainings/stop_hyperparam_search?hps_id=${id}`;
    }
    const response = await callApi({
      url,
      method: 'GET',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getTrainingsData();
      defaultSuccessToastMessage('stop');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * Jupyter Notebook 링크로 이동
   *
   * @param {number} trainingId 학습 ID
   * @param {boolean} editor 편집용 여부 (true or false)
   */
  const moveJupyterLink = async (trainingId, editor) => {
    let url = `trainings/jupyter_url?training_id=${trainingId}`;
    if (editor) {
      url += '&editor=true';
    }
    const response = await callApi({
      url,
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS) {
      window.open(result.url, '_blank');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * Jyputer Notebook 활성화/비활성화
   *
   * @param {*} act run or stop
   * @param {*} trainingId 학습 ID
   * @param {*} editor 편집용 여부 (true or false)
   */
  const onJupyterControl = async (act, trainingId, editor) => {
    // run or stop
    let url = `trainings/${act}_jupyter?training_id=${trainingId}`;
    if (editor) {
      url += '&editor=true';
    }
    const response = await callApi({
      url,
      method: 'GET',
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getTrainingsData();
      toast.success(act);
    } else {
      getTrainingsData();
      errorToastMessage(error, message);
    }
  };

  useEffect(() => {
    loadModalComponent('CREATE_TRAINING');
  }, []);

  useEffect(() => {
    onSearch(keyword);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchKey, trainingStatus, trainingType]);

  useEffect(() => {
    _isMounted.current = true;
    getTrainingsData();
    return () => {
      _isMounted.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AdminTrainingContent
      columns={columns}
      tableData={tableData}
      keyword={keyword}
      searchKey={searchKey}
      totalRows={totalRows}
      toggledClearRows={toggledClearRows}
      loading={loading}
      deleteBtnDisabled={selectedRows.length === 0}
      trainingType={trainingType}
      trainingStatus={trainingStatus}
      onStatusChange={(value) => {
        selectInputHandler('trainingStatus', value);
      }}
      onTypeChange={(value) => {
        selectInputHandler('trainingType', value);
      }}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      onSearch={onSearch}
      onCreate={onCreate}
      onSelect={onSelect}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      moveJupyterLink={moveJupyterLink}
      onJupyterControl={onJupyterControl}
      jobStop={jobStop}
      onClear={onClear}
      handleRefresh={getTrainingsData}
      onSortHandler={onSortHandler}
    />
  );
}

export default AdminTrainingPage;
