import { Badge, ButtonV2 } from '@tango/ui-react';

import warningIcon from '@src/static/images/icon/ic-warning-yellow-white.svg';
import { Fragment, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';

// Components

import Tooltip from '@src/components/atoms/Tooltip';
import Table from '@src/components/molecules/BorderTable/Table';

import 'react-sweet-progress/lib/style.css';

// Type
import { TRAINING_TOOL_TYPE } from '@src/types';

import Status from '@src/components/atoms/Status';
import { toast } from '@src/components/Toast';

// Network
import { callApi, STATUS_FAIL, STATUS_SUCCESS } from '@src/network';
// Utils
import { copyToClipboard, errorToastMessage } from '@src/utils';

import classNames from 'classnames/bind';
// CSS module
import style from './AdminTrainingDetail.module.scss';

const cx = classNames.bind(style);

const TOOL_STATUS = {
  running: 'working',
  installing: 'installing',
  scheduling: 'scheduling',
  pending: 'pending',
  error: 'error',
};
const TABLE_TYPE = {
  running: 'primary-2',
  // 다른 곳에서 running이 새로추가된 primary-2와 색이 다른경우 존재
  error: 'error',
  stop: 'gray',
  scheduling: 'yellow',
  installing: 'installing',
  pending: 'yellow',
};

const AdminTrainingDetail = ({ data, tableData, getTrainingsData }) => {
  const { t } = useTranslation();

  // State
  const [queueData, setQueueData] = useState([]);
  const [integratedData, setIntegratedData] = useState([]);
  const [sshIds, setSshIds] = useState([]);
  const [toolIds, setToolIds] = useState([]);
  const [stoppedIds, setStoppedIds] = useState([]);
  const [queueIds, setQueueIds] = useState([]);
  const [progress, setProgress] = useState([]);
  const [toolLoading, setToolLoading] = useState(false);
  const [inteStopLoading, setInteStopLoading] = useState(false);
  const [queueStopLoading, setQueueStopLoading] = useState(false);

  const {
    type,
    name: trainingName,
    description,
    access,
    users,
    built_in_model_name: builtInModelName,
    create_datetime: dateTime,
  } = data;

  const userList = users.map(({ user_name: user }) => {
    return user;
  });

  const integratedColumns = [
    {
      name: t('status.label'),
      selector: 'status',
      sortable: false,
      // minWidth: '128px',
      maxWidth: '128px',
      cell: ({ status }) => {
        return (
          <>
            <div className={cx('badge')}>
              <Badge
                type={TABLE_TYPE[status?.status]}
                label={t(TOOL_STATUS[status?.status])}
                size='xl'
              />
            </div>
            {status?.status === 'error' && (
              <Tooltip
                contents={
                  <div className={cx('tooltip-wrapper')}>
                    <div className={cx('tooltip')}>{status?.reason}</div>
                  </div>
                }
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
      name: t('toolName.label'),
      selector: 'toolName',
      sotrable: false,
      minWidth: '220px',
      maxWidth: '270px',
      cell: ({ toolName, toolType, replicaNum }) => {
        const toolTypeText = TRAINING_TOOL_TYPE[toolType]?.type ?? 'default';
        let toolNameData = toolName;
        if (!toolNameData) {
          toolNameData = TRAINING_TOOL_TYPE[toolType]?.label;
        }
        return (
          <>
            {toolTypeText === 'default' ? (
              toolNameData && (
                <div className={cx('initial')}>
                  {toolNameData.slice(0, 1).toUpperCase()}
                </div>
              )
            ) : (
              <img
                className={cx('table-icon')}
                src={`/images/icon/ic-${toolTypeText}.svg`}
                alt={`${toolTypeText} icon`}
                style={{
                  width: '24px',
                  height: '24px',
                }}
              />
            )}
            {/* <div className={cx('tool-replica-number')}>
              {replicaNum < 10 ? `0${replicaNum}` : replicaNum}
              // 툴 여러개 생성가능
            </div> */}
            <span className={cx('tool-name')}>{toolNameData}</span>
          </>
        );
      },
    },

    {
      name: t('configuration.label'),
      selector: 'configuration',
      sortable: false,
      minWidth: '200px',
      maxWidth: '350px',
    },
    {
      name: t('gpuAllocations.label'),
      selector: 'gpu_allocate',
      sortable: false,
      minWidth: '90px',
      cell: ({ gpu_allocate }) => {
        return gpu_allocate ? gpu_allocate : '-';
      },
    },
    {
      name: t('dockerImage.label'),
      selector: 'dockerImage',
      sortable: false,
      minWidth: '120px',
      cell: ({ dockerImage }) => {
        return dockerImage ? dockerImage : '-';
      },
    },
    {
      name: t('access.label'),
      sortable: false,
      minWidth: '224px',
      cell: ({ access, toolId, toolType, status }) => {
        const toolLink = access.map(({ type }, key) => {
          if (type === 'link') {
            return (
              <div
                key={key}
                className={cx(
                  `${status === 'running' ? 'access-content' : 'not-access'}`,
                )}
                onClick={() => {
                  if (status !== 'running') return;
                  accessClickHandler(type, toolId);
                }}
              >
                <div className={cx('access-title')}>
                  {/* {TRAINING_TOOL_TYPE[toolType]?.label} */}
                  {t('run.label')}
                </div>
                <img
                  className={cx('access-icon')}
                  src={
                    toolLoading && toolIds.includes(toolId)
                      ? '/images/icon/spinner-1s-58.svg'
                      : '/images/icon/00-ic-basic-link-external.svg'
                  }
                  alt='link'
                />
              </div>
            );
          } else {
            return <Fragment key={key}></Fragment>;
          }
        });
        return <div className={cx('access-box')}>{toolLink}</div>;
      },
    },
    {
      name: '',
      minWidth: '80px',
      maxWidth: '80px',
      cell: ({ toolId, toolName, toolType }) => {
        let toolNameData = toolName;
        if (!toolNameData) {
          toolNameData = TRAINING_TOOL_TYPE[toolType]?.label;
        }
        return (
          <ButtonV2
            size='l'
            label={t('stop.label')}
            colorType='lightRed'
            onClick={() => {
              toolHandler(toolId, toolNameData);
            }}
            disabled={inteStopLoading && stoppedIds.includes(toolId)}
            isLoading={inteStopLoading && stoppedIds.includes(toolId)}
          />
        );
      },
      button: true,
    },
  ];

  /**
   * 대기열 도구 중지 핸들러
   * @param {*} type 도구 타입
   * @param {*} groupId 그룹 id
   * @param {*} itemId 해당 id
   * @param {*} id tool id
   */
  const queueStopHandler = async (toolId) => {
    let queueIdsBucket = [...queueIds];
    queueIdsBucket.push(toolId);
    setQueueIds([...queueIdsBucket]);
    setQueueStopLoading(true);
    // here

    const response = await callApi({
      url: 'projects/stop-training',
      method: 'get',
      params: {
        training_id: toolId,
      },
    });

    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      getTrainingsData();
      toast.success(t('stopTool.message'));
    } else {
      errorToastMessage(error, message);
    }
    const newQueueIds = queueIdsBucket.filter((item) => item !== toolId);
    setQueueStopLoading(newQueueIds.length > 0);
    setQueueIds([...newQueueIds]);
  };

  /**
   * 통합 도구 접근 클릭 핸들러
   * @param {*} name ssh or link
   * @param {*} id 해당 tool id
   */
  const accessClickHandler = (name, id) => {
    if (name === 'ssh') {
      copySSHAddress(id);
    } else if (name === 'link') {
      moveToolLink(id);
    }
  };

  /**
   * SSH 주소 복사
   */
  const copySSHAddress = async (id) => {
    let sshIdsBucket = [...sshIds];
    sshIdsBucket.push(id);
    setSshIds([...sshIdsBucket]);
    const response = await callApi({
      url: `trainings/ssh_login_cmd?training_tool_id=${id}`,
      method: 'get',
    });

    const { result, status, message, error } = response;

    if (status === STATUS_SUCCESS) {
      copyToClipboard(result);
      toast.success(result);
    } else {
      errorToastMessage(error, message);
    }
    const newAccessIds = sshIdsBucket.filter((item) => item !== id);
    setSshIds([...newAccessIds]);
  };

  /**
   * 통합 도구 중지 핸들러
   * @param {number} toolId
   * @param {string} toolName
   */
  const toolHandler = async (toolId, toolName) => {
    const stoppedIdsBucket = [...stoppedIds];
    stoppedIdsBucket.push(toolId);
    setStoppedIds([...stoppedIdsBucket]);
    setInteStopLoading(true);

    const response = await callApi({
      url: 'projects/control_training_tool',
      method: 'put',
      body: {
        project_tool_id: toolId,
        action: 'off',
      },
    });
    const { status: apiStatus, message, error } = response;
    if (apiStatus === STATUS_SUCCESS) {
      getTrainingsData();
      toast.success(t('stopTool.message', { tool: toolName }));
    } else if (apiStatus === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error(message);
    }
    const newStoppedIds = stoppedIdsBucket.filter((item) => item !== toolId);
    setInteStopLoading(newStoppedIds.length > 0);
    setStoppedIds([...newStoppedIds]);
  };

  /**
   * Tool 새창에서 열기
   * @param {string} id 학습 툴 id
   */
  const moveToolLink = async (id) => {
    let toolIdsBucket = [...toolIds];
    toolIdsBucket.push(id);
    setToolIds([...toolIdsBucket]);
    setToolLoading(true);
    const response = await callApi({
      url: `projects/tool-url?project_tool_id=${id}`,
      method: 'get',
    });

    const { result, status: apiStatus, message, error } = response;
    if (apiStatus === STATUS_SUCCESS) {
      window.open(result.url, '_blank');
    } else if (apiStatus === STATUS_FAIL) {
      errorToastMessage(error, message);
    } else {
      toast.error(message);
    }
    const newDownIds = toolIdsBucket.filter((item) => item !== id);
    setToolLoading(newDownIds.length > 0);
    setToolIds([...newDownIds]);
  };

  useEffect(() => {
    const [detailData] = tableData?.filter((item) => item.id === data?.id);

    setProgress(detailData?.item_progress?.status);
    //! const integratedList = detailData?.training_tool_list;
    const integratedList = detailData?.tools;
    const trainingsList = detailData?.trainings;
    // let queueToolData = [
    //   {
    //     type: detailData?.item_progress?.type ?? '-',
    //     status: detailData.item_progress?.status.status ?? '-',
    //     configuration: detailData?.item_progress?.configurations ?? '-',
    //     dockerImage: detailData?.item_progress?.docker_image_name ?? '-',
    //     progress: detailData?.item_progress?.progress ?? '-',
    //     groupId: detailData?.item_progress?.item_group_id ?? '-',
    //     itemId: detailData?.item_progress?.item_id ?? '-',
    //     id: detailData?.id,
    //   },
    // ];
    let queueToolData = trainingsList?.map((item, i) => {
      return {
        // training_name
        toolName: item?.training_name,
        status: item?.status,
        gpu_allocate: item?.gpu_count,
        // configuration: item?.tool_configuration, // name
        configuration: detailData?.instance_name, // name
        dockerImage: item?.image_name,
        access: item?.function_info, //배열
        toolType: item?.training_type,
        // replicaNum: item?.tool_replica_number,
        toolId: item?.training_id,
      };
    });

    const integratedToolData = [];

    integratedList?.forEach((item) => {
      integratedToolData.push({
        toolName: item?.tool_name,
        status: item?.status,
        configuration: detailData?.instance_name, // name
        gpu_allocate: item?.gpu_count,
        dockerImage: item?.image_name,
        access: item?.function_info, //배열
        toolType: item?.tool_type,
        toolId: item?.tool_id,
      });
    });
    if (queueToolData[0]?.status === 'stop') {
      queueToolData = [];
    }

    setQueueData(queueToolData);
    setIntegratedData(integratedToolData);
  }, [data, tableData]);

  const columns = [
    {
      name: t('status.label'),
      selector: 'status',
      sortable: false,
      // minWidth: '1px',
      cell: ({ status }) => {
        return (
          <>
            <div className={cx('badge')}>
              <Badge
                type={TABLE_TYPE[status?.status]}
                label={t(TOOL_STATUS[status?.status])}
                size='xl'
                // customStyle={{}}
              />
            </div>
            {status?.status === 'error' && (
              <Tooltip
                contents={
                  <div className={cx('tooltip-wrapper')}>
                    <div className={cx('tooltip')}>{status?.reason}</div>
                  </div>
                }
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
      name: t('toolName.label'),
      selector: 'toolName',
      sortable: false,
      maxWidth: '120px',
    },
    // {
    //   name: t('status.label'),
    //   selector: 'status',
    //   sortable: false,
    //   minWidth: '60px',
    //   maxWidth: '90px',
    //   cell: ({ status }) => {
    //     return t(status);
    //   },
    // },
    {
      name: t('configurations.label'),
      selector: 'configuration',
      sortable: false,
      minWidth: '90px',
    },
    {
      name: t('gpuAllocations.label'),
      selector: 'gpu',
      sortable: false,
      minWidth: '90px',
      cell: ({ gpu_allocate }) => {
        return gpu_allocate ? gpu_allocate : '-';
      },
    },
    {
      name: t('dockerImage.label'),
      selector: 'dockerImage',
      sotrable: false,
      minWidth: '90px',
      cell: ({ dockerImage }) => {
        return dockerImage ? dockerImage : '-';
      },
    },
    {
      name: '',
      minWidth: '80px',
      maxWidth: '80px',
      cell: ({ toolId }) => {
        return (
          <ButtonV2
            size='l'
            label={t('stop.label')}
            colorType='lightRed'
            onClick={() => {
              queueStopHandler(toolId);
            }}
            disabled={queueStopLoading && queueIds.includes(toolId)}
            isLoading={queueStopLoading && queueIds.includes(toolId)}
          />
        );
      },
      button: true,
    },
  ];

  return (
    <div className={cx('detail')}>
      <div className={cx('header')}>
        <div className={cx('title')}>
          <span>{trainingName}</span>
          <span>{t('detailsOf')}</span>
        </div>
        <p className={cx('desc')}>{description}</p>
      </div>
      <div className={cx('info-list')}>
        <div className={cx('list-item')}>
          <label className={cx('label')}>{t('createdAt.label')}</label>
          <div className={cx('value')} title={dateTime}>
            {dateTime ?? '-'}
          </div>
        </div>
        <div className={cx('list-item')}>
          <label className={cx('label')}>{t('accessType.label')}</label>
          <div className={cx('value')}>
            {access === 1 ? 'Public' : 'Private'}
          </div>
        </div>
        <div className={cx('list-item', type)}>
          <label className={cx('label')}>
            {t('users.label')} ({users.length})
          </label>
          <div className={cx('value', 'user')} title={userList.join(', ')}>
            {userList.join(', ')}
          </div>
        </div>
        {type === 'built-in' && (
          <div className={cx('list-item')}>
            <label className={cx('label')}>{t('model.label')}</label>
            <div className={cx('value')} title={builtInModelName}>
              {builtInModelName ?? '-'}
            </div>
          </div>
        )}
      </div>
      <div className={cx('table-box')} style={{ marginBottom: '32px' }}>
        <div className={cx('table-title')}>{t('trainingTool.label')}</div>
        <Table
          data={queueData}
          columns={columns}
          selectableRows={false}
          totalRows={queueData.length}
          hideSearchBox={true}
          loading={false}
          fixedHeader={true}
          fixedHeaderScrollHeight='200px'
          noDataMessage={'noActiveTool.message'}
        />
      </div>
      <div className={cx('table-box')}>
        <div className={cx('table-title')}>{t('developTool.label')}</div>
        <Table
          data={integratedData}
          columns={integratedColumns}
          selectableRows={false}
          totalRows={integratedData.length}
          hideSearchBox={true}
          loading={false}
          fixedHeader={true}
          fixedHeaderScrollHeight='200px'
          noDataMessage={'noActiveTool.message'}
        />
      </div>
    </div>
  );
};

export default AdminTrainingDetail;
