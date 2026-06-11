import { Badge, Switch } from '@tango/ui-react';

import { loadModalComponent } from '@src/modal';
import { useCallback, useEffect, useState } from 'react';
// i18n
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';

import SortColumn from '@src/components/molecules/Table/TableHead/SortColumn';
import useSortColumn from '@src/components/molecules/Table/TableHead/useSortColumn';
// Components
import AdminBuiltInModelContent from '@src/components/pageContents/admin/AdminBuiltInModelContent';

import { openConfirm } from '@src/store/modules/confirm';
// Actions
import { openModal } from '@src/store/modules/modal';

// Network
import { callApi, STATUS_SUCCESS } from '@src/network';
// Utils
import { defaultSuccessToastMessage, errorToastMessage } from '@src/utils';

function AdminBuilitInModelPage() {
  const { t } = useTranslation();
  // Redux Hooks
  const dispatch = useDispatch();

  // State
  const [originData, setOriginData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedRows, setSelectedRows] = useState([]);
  const [toggledClearRows, setToggledClearRows] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [modelType, setModelType] = useState({
    label: t('allModelType.label'),
    value: 'all',
  });
  const [searchKey, setSearchKey] = useState({
    label: t('modelName.label'),
    value: 'name',
  });
  const [modelTypeOptions, setModelTypeOptions] = useState([
    { label: t('allModelType.label'), value: 'all' },
  ]);
  const { sortClickFlag, onClickHandler, clickedIdx, clickedIdxHandler } =
    useSortColumn(6);

  const columns = [
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('modelType.label')}
          idx={0}
        />
      ),
      selector: 'kind',
      sortable: true,
      minWidth: '100px',
      maxWidth: '180px',
      cell: ({ kind }) => <div title={kind}>{kind}</div>,
    },
    {
      name: t('modelName.label'),
      selector: 'name',
      minWidth: '230px',
      cell: ({ name, description }) => (
        <div title={`${name}\n${description}`}>{name}</div>
      ),
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('training.label')}
          idx={1}
        />
      ),
      selector: 'training_status',
      sortable: true,
      minWidth: '180px',
      maxWidth: '200px',
      cell: ({
        id,
        training_status: status,
        enable_to_train_with_cpu: isCpuTraining,
        enable_to_train_with_gpu: isGpuTraining,
        horovod_training_multi_gpu_mode: isHorovodTrainingMultiGpu,
        nonhorovod_training_multi_gpu_mode: isNonhorovodTrainingMultiGpu,
      }) => (
        <>
          <Switch
            onChange={() => {
              onActivate(id, 'training', status);
            }}
            checked={status === 1}
            disabled={status === -1}
            customStyle={{ overflow: 'visible', marginRight: '12px' }}
          />
          <Badge
            type={isCpuTraining ? 'yellow' : 'disabled'}
            title={isCpuTraining ? 'CPU' : ''}
            label='CPU'
            customStyle={{
              marginRight: '4px',
              opacity: status === 1 && isCpuTraining ? '1' : '0.2',
            }}
          />
          <Badge
            type={isGpuTraining ? 'green' : 'disabled'}
            title={isGpuTraining ? 'GPU' : ''}
            label='GPU'
            customStyle={{
              marginRight: '4px',
              opacity: status === 1 && isGpuTraining ? '1' : '0.2',
            }}
          />
          <Badge
            type={
              isHorovodTrainingMultiGpu || isNonhorovodTrainingMultiGpu
                ? 'blue'
                : 'disabled'
            }
            title={`${
              isHorovodTrainingMultiGpu ? 'Multi GPU with horovod' : ''
            }\n${
              isNonhorovodTrainingMultiGpu ? 'Multi GPU with nonhorovod' : ''
            }`}
            label='Multi'
            customStyle={{
              opacity:
                status === 1 &&
                (isHorovodTrainingMultiGpu || isNonhorovodTrainingMultiGpu)
                  ? '1'
                  : '0.2',
            }}
          />
        </>
      ),
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('deployment.label')}
          idx={2}
        />
      ),
      selector: 'deployment_status',
      sortable: true,
      minWidth: '180px',
      maxWidth: '200px',
      cell: ({
        id,
        deployment_status: status,
        enable_to_deploy_with_cpu: isCpuDeployment,
        enable_to_deploy_with_gpu: isGpuDeployment,
        deployment_multi_gpu_mode: isDeploymentMultiGpu,
      }) => (
        <>
          <Switch
            onChange={() => {
              onActivate(id, 'deployment', status);
            }}
            checked={status === 1}
            disabled={status === -1}
            customStyle={{ overflow: 'visible', marginRight: '12px' }}
          />
          <Badge
            type={isCpuDeployment ? 'yellow' : 'disabled'}
            title={isCpuDeployment ? 'CPU' : ''}
            label='CPU'
            customStyle={{
              marginRight: '4px',
              opacity: status === 1 && isCpuDeployment ? '1' : '0.2',
            }}
          />
          <Badge
            type={isGpuDeployment ? 'green' : 'disabled'}
            title={isGpuDeployment ? 'GPU' : ''}
            label='GPU'
            customStyle={{
              marginRight: '4px',
              opacity: status === 1 && isGpuDeployment ? '1' : '0.2',
            }}
          />
          <Badge
            type={isDeploymentMultiGpu ? 'blue' : 'disabled'}
            title={isDeploymentMultiGpu ? 'Multi GPU' : ''}
            label='Multi'
            customStyle={{
              marginRight: '4px',
              opacity: status === 1 && isDeploymentMultiGpu ? '1' : '0.2',
            }}
          />
        </>
      ),
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('modelDirectory.label')}
          idx={3}
        />
      ),
      selector: 'path',
      sortable: true,
      minWidth: '180px',
      maxWidth: '300px',
      cell: ({ path }) => <div title={path}>{path}</div>,
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('dockerImage.label')}
          idx={4}
        />
      ),
      selector: 'run_docker_name',
      sortable: true,
      maxWidth: '180px',
    },
    {
      name: (
        <SortColumn
          onClickHandler={clickedIdxHandler}
          sortClickFlag={sortClickFlag}
          title={t('creator.label')}
          idx={5}
        />
      ),
      selector: 'created_by',
      sortable: true,
      maxWidth: '80px',
    },
    {
      name: t('export.label'),
      minWidth: '64px',
      maxWidth: '64px',
      cell: ({ id }) => (
        <img
          src='/images/icon/00-ic-basic-external-link-grey.svg'
          alt='Export'
          className='table-icon'
          onClick={() => {
            onExportJson(id);
          }}
        />
      ),
      button: true,
    },
    {
      name: t('edit.label'),
      minWidth: '64px',
      maxWidth: '64px',
      cell: ({ id }) => (
        <img
          src='/images/icon/00-ic-basic-pen.svg'
          alt='edit'
          className='table-icon'
          onClick={() => {
            onUpdate(id);
          }}
        />
      ),
      button: true,
    },
  ];

  const onSortHandler = (selectedColumn, sortDirection, sortedRows) => {
    onClickHandler(clickedIdx, sortDirection);
  };

  /**
   * API 호출 GET
   * 어드민 Built-in 모델 목록 가져오기
   */
  const getBuiltInModelList = useCallback(async () => {
    const response = await callApi({
      url: 'built_in_models/list',
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS && result.list) {
      setTableData(result.list);
      setOriginData(result.list);
      setTotalRows(result.list.length);
    } else {
      errorToastMessage(error, message);
    }
    return response;
  }, []);

  /**
   * API 호출 GET
   * 어드민 Built-in 모델 유형 목록 가져오기
   */
  const getBuiltInModelTypes = useCallback(async () => {
    const response = await callApi({
      url: 'options/built_in_models_kind',
      method: 'GET',
    });

    const { status, result, message, error } = response;
    if (status === STATUS_SUCCESS && result.built_in_model_kind_list) {
      const list = result.built_in_model_kind_list;
      const options = list.map((kind) => {
        return { label: kind, value: kind };
      });
      options.unshift({ label: t('allModelType.label'), value: 'all' });
      setModelTypeOptions(options);
    } else {
      errorToastMessage(error, message);
    }
    return response;
  }, [t]);

  /**
   * 빌트일 모델 상세정보 조회 (수정/내보내기에 사용)
   *
   * @param {number} id Built-in 모델 아이디
   * @returns
   */
  const getBuiltInModelData = async (id) => {
    const response = await callApi({
      url: `built_in_models/${id}`,
      method: 'get',
    });
    const { result, status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      return result;
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * Built-in 모델 생성
   */
  const onCreate = () => {
    dispatch(
      openModal({
        modalType: 'CREATE_BUILTIN_MODEL',
        modalData: {
          submit: {
            text: 'add.label',
            func: () => {
              getBuiltInModelList();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          prev: {
            text: 'prev.label',
          },
          next: {
            text: 'next.label',
          },
        },
      }),
    );
  };

  /**
   * Built-in 모델 삭제 확인 모달
   */
  const openDeleteConfirmPopup = () => {
    dispatch(
      openConfirm({
        title: 'deleteBuiltInModelPopup.title.label',
        content: 'deleteBuiltInModelPopup.message',
        submit: {
          text: 'delete.label',
          func: () => {
            onDelete();
          },
        },
        cancel: {
          text: 'cancel.label',
        },
      }),
    );
  };

  /**
   * API 호출 Delete
   * Built-in 모델 삭제
   * 체크박스 선택된 데이터 삭제
   */
  const onDelete = async () => {
    const ids = selectedRows.map(({ id }) => id);
    const response = await callApi({
      url: `built_in_models/${ids.join(',')}`,
      method: 'delete',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      setToggledClearRows(!toggledClearRows);
      getBuiltInModelList();
      defaultSuccessToastMessage('delete');
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * Built-in 모델 수정
   *
   * @param {object} id Built-in 모델 아이디
   */
  const onUpdate = async (id) => {
    const data = await getBuiltInModelData(id);
    dispatch(
      openModal({
        modalType: 'EDIT_BUILTIN_MODEL',
        modalData: {
          submit: {
            text: 'edit.label',
            func: () => {
              getBuiltInModelList();
            },
          },
          cancel: {
            text: 'cancel.label',
          },
          data,
        },
      }),
    );
  };

  /**
   * 학습/배포 활성화
   * @param {number} id
   * @param {string} type
   * @param {number} prevStatus 0(deactivate) or 1(activate)
   */
  const onActivate = async (id, type, prevStatus) => {
    let newStatus = 1;
    if (Number(prevStatus) === 0) {
      newStatus = 1;
    } else {
      newStatus = 0;
    }

    let query = '';
    if (type === 'training') {
      query = `training_status=${newStatus}`;
    } else if (type === 'deployment') {
      query = `deployment_status=${newStatus}`;
    }

    const response = await callApi({
      url: `built_in_models/activate?built_in_model_id=${id}&${query}`,
      method: 'get',
    });
    const { status, message, error } = response;
    if (status === STATUS_SUCCESS) {
      defaultSuccessToastMessage('change');
      getBuiltInModelList();
    } else {
      errorToastMessage(error, message);
    }
  };

  /**
   * JSON Export
   *
   * @param {number} id Built-in 모델 아이디
   */
  const onExportJson = async (id) => {
    const data = await getBuiltInModelData(id);
    const json = JSON.stringify(data);
    const url = window.URL.createObjectURL(new Blob([json]));
    const link = document.createElement('a');
    link.href = url;
    const fileName = `${data.name}_${data.created_by}.json`;
    link.download = fileName;
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  /**
   * 검색/필터 셀렉트 박스 이벤트 핸들러
   *
   * @param {string} name 검색/필터할 항목
   * @param {string} value 검색/필터할 내용
   */
  const selectInputHandler = (name, value) => {
    if (name === 'modelType') {
      setModelType(value);
    } else if (name === 'searchKey') {
      setSearchKey(value);
    }
  };

  /**
   * 검색
   *
   * @param {string} value 검색할 내용
   */
  const onSearch = useCallback(
    (value) => {
      let tableData = [...originData];

      if (modelType.value !== 'all') {
        tableData = tableData.filter((item) => item.kind === modelType.value);
      }

      if (searchKey.label === t('modelName.label')) {
        tableData = tableData.filter((item) =>
          item?.name.toLowerCase().includes(value.toLowerCase()),
        );
      } else if (value !== '') {
        tableData = tableData.filter((item) =>
          item[searchKey.value].includes(value),
        );
      }

      setKeyword(value);
      setTableData(tableData);
      setTotalRows(tableData.length);
    },
    [modelType.value, originData, searchKey.label, searchKey.value, t],
  );

  /**
   * 체크박스 선택
   *
   * @param {object} param0 선택된 행
   */
  const onSelect = ({ selectedRows }) => {
    setSelectedRows(selectedRows);
  };

  /**
   * 검색 내용 제거
   */
  const onClear = () => {
    onSearch('');
  };

  useEffect(() => {
    loadModalComponent('CREATE_BUILTIN_MODEL');
  }, []);

  useEffect(() => {
    if (originData.length !== 0) onSearch(keyword);
  }, [modelType, searchKey, originData, keyword, onSearch]);

  useEffect(() => {
    getBuiltInModelTypes();
  }, [originData, getBuiltInModelTypes]);

  useEffect(() => {
    getBuiltInModelList();
  }, [getBuiltInModelList]);

  return (
    <AdminBuiltInModelContent
      onCreate={onCreate}
      onSelect={onSelect}
      columns={columns}
      tableData={tableData}
      keyword={keyword}
      searchKey={searchKey}
      onSearch={onSearch}
      onSearchKeyChange={(value) => {
        selectInputHandler('searchKey', value);
      }}
      modelType={modelType}
      onModelTypeChange={(value) => {
        selectInputHandler('modelType', value);
      }}
      totalRows={totalRows}
      toggledClearRows={toggledClearRows}
      openDeleteConfirmPopup={openDeleteConfirmPopup}
      deleteBtnDisabled={selectedRows.length === 0}
      onClear={onClear}
      modelTypeOptions={modelTypeOptions}
      onSortHandler={onSortHandler}
    />
  );
}

export default AdminBuilitInModelPage;
