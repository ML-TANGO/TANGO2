import { useCallback, useMemo } from 'react';
import { useHistory, useRouteMatch } from 'react-router-dom';
import { useDispatch } from 'react-redux';

// i18n
import { useTranslation } from 'react-i18next';

// Actions
import { openModal } from '@src/store/modules/modal';
import { openConfirm } from '@src/store/modules/confirm';

// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

// Network
import {
  callApi,
  STATUS_SUCCESS,
  STATUS_FAIL,
  STATUS_INTERNAL_SERVER_ERROR,
} from '@src/network';

// Components
import Status from '@src/components/atoms/Status';
import Table from '@src/components/molecules/Table';
import { toast } from '@src/components/Toast';
import { Tooltip } from '@tango/ui-react';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';

// Icons
import EditIcon from '@src/static/images/icon/00-ic-basic-pen.svg';
import DeleteIcon from '@src/static/images/icon/00-ic-basic-delete.svg';
import BookmarkIcon from '@src/static/images/icon/00-ic-basic-bookmark-o.svg';
import BookmarkActiveIcon from '@src/static/images/icon/00-ic-basic-bookmark-blue.svg';
import DescriptionIcon from '@src/static/images/icon/ic-description.svg';

function TableList({ trainingList, isLoading, refreshData }) {
  const { t } = useTranslation();
  // Redux Hooks
  const dispatch = useDispatch();
  const history = useHistory();
  const match = useRouteMatch();
  const { id: workspaceId } = match.params;

  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(6);

  /**
   * 학습 상세 페이지(workbench)로 이동
   */
  const moveToTrainingDetail = (d) => {
    const { permission_level: permissionLevel, id: trainingId } = d;
    if (permissionLevel > 4) return;
    if (d.type === 'federated-learning') {
      // 연합 학습 페이지로 이동
      history.push(
        `/user/workspace/${workspaceId}/trainings/${trainingId}/federated-learning`,
      );
    } else {
      history.push(
        `/user/workspace/${workspaceId}/trainings/${trainingId}/workbench`,
      );
    }
  };

  /**
   * 학습 카드 북마크 설정
   */
  const bookmarkHandler = useCallback(
    (trainingId, bookmark) => {
      const body = { training_id: trainingId };
      const response = callApi({
        url: 'trainings/bookmark',
        method: bookmark === 0 ? 'post' : 'delete',
        body,
      });
      const { status, message, error } = response;
      if (status === STATUS_SUCCESS) {
        refreshData();
      } else if (status === STATUS_FAIL) {
        errorToastMessage(error, message);
      } else if (status === STATUS_INTERNAL_SERVER_ERROR) {
        toast.error(message);
      }
    },
    [refreshData],
  );

  /**
   * 학습 종료
   *
   * @param {number} id 학습 ID
   */
  const onStop = async (id) => {
    const response = await callApi({
      url: `trainings/stop?training_id=${id}`,
      method: 'GET',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('stop');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * 학습 수정 모달 열기
   */
  const trainingEdit = useCallback(
    (data) => {
      dispatch(
        openModal({
          modalType: 'EDIT_TRAINING',
          modalData: {
            submit: {
              text: 'edit.label',
              func: () => {
                refreshData();
              },
            },
            cancel: {
              text: 'cancel.label',
            },
            data,
            workspaceId,
          },
        }),
      );
    },
    [dispatch, refreshData, workspaceId],
  );

  /**
   * API 호출 DELETE
   * 학습 삭제
   *
   * @param {number} tId 학습 ID
   */
  const onDelete = useCallback(
    async (tId) => {
      const response = await callApi({
        url: `projects`,
        method: 'delete',
        body: {
          id_list: [tId],
        },
      });
      const { status, message, error } = response;
      if (status === STATUS_SUCCESS) {
        refreshData();
        defaultSuccessToastMessage('delete');
      } else {
        errorToastMessage(error, message);
      }
    },
    [refreshData],
  );

  /**
   * 학습 삭제
   */
  const trainingDelete = useCallback(
    (trainingId, trainingName) => {
      dispatch(
        openConfirm({
          title: 'deleteTrainingPopup.title.label',
          content: 'deleteTrainingPopup.message',
          testid: 'training-delete-modal',
          submit: {
            text: 'delete.label',
            func: () => {
              onDelete(trainingId);
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          confirmMessage: trainingName,
        }),
      );
    },
    [dispatch, onDelete],
  );

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  const columns = useMemo(
    () => [
      {
        name: (
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('bookmark.label')}
            idx={0}
          />
        ),
        selector: 'bookmark',
        minWidth: '80px',
        maxWidth: '80px',
        sortable: true,
        cell: ({ id, bookmark }) => (
          <img
            className='table-icon'
            src={bookmark ? BookmarkActiveIcon : BookmarkIcon}
            alt='bookmark'
            onClick={() => {
              bookmarkHandler(id, bookmark);
            }}
          />
        ),
        button: true,
      },
      {
        name: t('status.label'),
        selector: 'status',
        minWidth: '128px',
        maxWidth: '128px',
        cell: ({ status: { training } }) => (
          <Status
            status={training === 'running' ? 'trainingRunning' : training}
            type='dark'
          />
        ),
      },
      {
        name: t('type.label'),
        selector: 'type',
        maxWidth: '120px',
        cell: ({ type }) => (type === 'built-in' ? 'Built-in' : 'Custom'),
      },
      {
        name: (
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('trainingName.label')}
            idx={1}
          />
        ),
        selector: 'training_name',
        maxWidth: '300px',
        sortable: true,
        cell: ({ name, description }) => (
          <div title={name}>
            {name}{' '}
            {description && (
              <Tooltip
                contents={description}
                contentsAlign={{ vertical: 'top', horizontal: 'left' }}
                customStyle={{
                  position: 'relative',
                  display: 'block',
                  marginLeft: '4px',
                }}
                contentsCustomStyle={{ minWidth: '100px' }}
                globalCustomStyle={{ position: 'absolute' }}
                icon={DescriptionIcon}
                iconCustomStyle={{ width: '18px' }}
              />
            )}
          </div>
        ),
      },
      // {
      //   name: (
      //     <SortColumn
      //       onClickHandler={clickedIdxHandler}
      //       sortClickFlag={sortClickFlag}
      //       title={t('builtInModel.label')}
      //       idx={2}
      //     />
      //   ),
      //   selector: 'built_in_model_name',
      //   maxWidth: '220px',
      //   sortable: true,
      //   cell: ({ built_in_model_name: modelName }) => (
      //     <div title={modelName}>{modelName}</div>
      //   ),
      // },
      {
        name: (
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('resource.label')}
            idx={3}
          />
        ),
        selector: 'resource_info',
        sortable: true,
        minWidth: '125px',
        maxWidth: '160px',
        cell: ({
          instance_info: {
            cpu_allocate: cpu,
            resource_name: resourceName,
            ram_allocate: ram,
          },
        }) => {
          return (
            <div>
              vGPU: {resource.cpu}, vGPU: {resourceName}, RAM: {ram}
            </div>
          );
        },
      },
      // {
      //   name: t('configurations.label'),
      //   selector: 'resource_info',
      //   minWidth: '160px',
      //   sortable: false,
      //   cell: ({ resource_info: info }) => {
      //     const { configurations } = info;
      //     return (
      //       <div>
      //         {configurations.length > 0 ? configurations.join('\n') : '-'}
      //       </div>
      //     );
      //   },
      // },
      {
        name: (
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('owner.label')}
            idx={4}
          />
        ),
        selector: 'user_name',
        sortable: true,
        maxWidth: '100px',
      },
      {
        name: (
          <SortColumn
            onClickHandler={clickedIdxHandler}
            sortClickFlag={sortClickFlag}
            title={t('createdAt.label')}
            idx={5}
          />
        ),
        selector: 'create_datetime',
        sortable: true,
        minWidth: '160px',
        maxWidth: '200px',
      },
      {
        name: t('stop.label'),
        minWidth: '70px',
        maxWidth: '70px',
        cell: ({ status: { training, workbench }, id }) => {
          const activeStatus = ['running', 'pending', 'error', 'installing'];
          return training !== 'stop' && workbench !== 'stop' ? (
            <img
              className='table-icon'
              src='/images/icon/ic-stop.svg'
              alt='stop'
              onClick={() => {
                onStop(id);
              }}
            />
          ) : (
            <img
              className='table-icon disabled'
              src='/images/icon/ic-stop.svg'
              alt='stop'
            />
          );
        },
        button: true,
      },
      {
        name: t('edit.label'),
        minWidth: '64px',
        maxWidth: '64px',
        cell: (row) => (
          <img
            // className={`table-icon ${row.permission_level > 4 && 'disabled'} `}
            className={`table-icon`}
            src={EditIcon}
            alt='edit'
            onClick={() => {
              trainingEdit(row);
            }}
          />
        ),
        button: true,
      },
      {
        name: t('delete.label'),
        minWidth: '64px',
        maxWidth: '64px',
        cell: (row) => {
          const permission_level = 3;
          return (
            <img
              className={`table-icon ${
                // row.permission_level > 3 && 'disabled'
                permission_level > 3 && 'disabled'
              } `}
              src={DeleteIcon}
              alt='edit'
              onClick={() => {
                // if (row.permission_level < 4) {
                if (permission_level < 4) {
                  trainingDelete(row.id, row.training_name);
                }
              }}
            />
          );
        },
        button: true,
      },
    ],
    [
      bookmarkHandler,
      clickedIdxHandler,
      sortClickFlag,
      t,
      trainingDelete,
      trainingEdit,
    ],
  );

  return (
    <div>
      <Table
        onRowClick={moveToTrainingDetail}
        columns={columns}
        data={trainingList}
        loading={isLoading}
        selectableRows={false}
        onSortHandler={onSortHandler}
        defaultSortField='bookmark'
      />
    </div>
  );
}

export default TableList;
